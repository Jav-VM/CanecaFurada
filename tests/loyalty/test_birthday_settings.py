"""
Regalo y aviso de cumpleaños configurables (Fase 14): puntos, activación,
textos editables con `{puntos}`, validación anti-SSTI, permisos y auditoría.
"""
import datetime

from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import override_settings
from django.utils import timezone

from apps.core.models import AuditEvent
from apps.loyalty import birthday_settings, ledger
from apps.loyalty.models import BirthdayMessage, Promotion
from apps.notifications import services as notifications
from apps.notifications.models import Channel, Notification
from apps.notifications.sms import LocmemSmsBackend
from tests.accounts.factories import VALID_MOBILE

from .factories import make_employee, make_owner, make_promotion
from .test_birthdays import SMS_SETTINGS, BirthdayTestCase


class BirthdaySettingsTestCase(BirthdayTestCase):
    def setUp(self):
        super().setUp()
        self.owner = make_owner()
        # El servicio usa la fecha real: la promoción ya ha empezado hoy (y antes de `AT`).
        Promotion.objects.filter(pk=self.promo.pk).update(starts_at=timezone.now() - datetime.timedelta(days=1))
        self.promo.refresh_from_db()

    def update(self, **overrides):
        data = {"active": True, "points": 50, "email_subject": "", "email_body": "", "sms_body": ""}
        data.update(overrides)
        return birthday_settings.update_birthday_gift(actor=self.owner, **data)


class GiftSettingsTests(BirthdaySettingsTestCase):
    def test_creates_the_promotion_when_there_is_none(self):
        Promotion.objects.all().delete()
        self.assertTrue(self.update(points=75))
        promo = Promotion.objects.get(kind=Promotion.Kind.BIRTHDAY)
        self.assertEqual((promo.fixed_points, promo.status, promo.name), (75, Promotion.Status.ACTIVE, "Regalo de cumpleaños"))
        state = birthday_settings.current_state()
        self.assertEqual((state.active, state.points), (True, 75))

    def test_new_points_apply_to_next_gifts_only(self):
        first = self.customer()
        self.run_day()
        self.update(points=120)
        second = self.customer("otro@example.com")
        self.run_day()
        self.assertEqual(ledger.balance(first), 50)
        self.assertEqual(ledger.balance(second), 120)
        self.assertEqual(Promotion.objects.filter(kind=Promotion.Kind.BIRTHDAY).count(), 1)

    def test_deactivating_pauses_every_birthday_promotion(self):
        make_promotion(name="Otra", kind=Promotion.Kind.BIRTHDAY, fixed_points=80, starts_at=self.promo.starts_at)
        # También una programada para más adelante.
        make_promotion(name="Futura", kind=Promotion.Kind.BIRTHDAY, fixed_points=90, starts_at=self.AT)
        user = self.customer()
        self.update(active=False)
        self.assertFalse(Promotion.objects.filter(kind=Promotion.Kind.BIRTHDAY, status=Promotion.Status.ACTIVE).exists())
        self.assertFalse(self.run_day().promotion)
        self.assertEqual(ledger.balance(user), 0)
        self.assertFalse(birthday_settings.current_state().active)
        # Y se puede volver a activar.
        self.update(active=True, points=60)
        self.assertTrue(birthday_settings.current_state().active)

    def test_reactivating_an_ended_promotion_removes_its_end_date(self):
        Promotion.objects.filter(pk=self.promo.pk).update(
            starts_at=timezone.now() - datetime.timedelta(days=60), ends_at=timezone.now() - datetime.timedelta(days=1)
        )
        self.assertFalse(birthday_settings.current_state().active)
        self.update(active=True)
        self.promo.refresh_from_db()
        self.assertIsNone(self.promo.ends_at)
        self.assertTrue(birthday_settings.current_state().active)

    def test_without_changes_nothing_is_saved_or_audited(self):
        self.assertFalse(self.update(active=True, points=50))
        self.assertFalse(AuditEvent.objects.filter(action=AuditEvent.Action.BIRTHDAY_SETTINGS_UPDATED).exists())
        self.assertFalse(BirthdayMessage.objects.exists())

    def test_only_the_owner_can_change_it(self):
        for actor in (make_employee(), self.customer()):
            with self.assertRaises(PermissionDenied):
                birthday_settings.update_birthday_gift(actor=actor, active=False, points=1)
        self.promo.refresh_from_db()
        self.assertEqual((self.promo.status, self.promo.fixed_points), (Promotion.Status.ACTIVE, 50))

    def test_invalid_points_are_rejected(self):
        for points in (0, -5, Promotion.MAX_FIXED_POINTS + 1, True, "50", None):
            with self.assertRaises(ValidationError):
                self.update(points=points)

    def test_audit_has_no_texts(self):
        self.update(points=70, email_subject="Asunto secreto", email_body="Cuerpo del propietario")
        event = AuditEvent.objects.get(action=AuditEvent.Action.BIRTHDAY_SETTINGS_UPDATED)
        self.assertEqual(event.actor, self.owner)
        self.assertEqual(event.metadata, {"active": True, "points": 70, "texts_changed": ["email_body", "email_subject"]})
        self.assertNotIn("secreto", str(event.metadata))


class MessageValidationTests(BirthdaySettingsTestCase):
    def test_only_the_points_placeholder_is_allowed(self):
        for text in ("Hola {{ first_name }}", "{% load static %}", "Te damos {points}", "Llave suelta }"):
            with self.assertRaises(ValidationError):
                self.update(email_body=text)
        self.assertFalse(BirthdayMessage.objects.exists())

    def test_subject_and_sms_are_single_line_and_limited(self):
        with self.assertRaises(ValidationError):
            self.update(email_subject="Línea 1\nLínea 2")
        with self.assertRaises(ValidationError):
            self.update(sms_body="Uno\nDos")
        with self.assertRaises(ValidationError):
            self.update(sms_body="x" * (BirthdayMessage.MAX_SMS_BODY + 1))
        with self.assertRaises(ValidationError):
            self.update(email_body="x" * (BirthdayMessage.MAX_EMAIL_BODY + 1))

    def test_texts_are_trimmed_and_normalized(self):
        self.update(email_subject="  Felicidades  ", email_body="Hola\r\n\r\nTienes {puntos} puntos  ")
        message = BirthdayMessage.objects.get()
        self.assertEqual((message.email_subject, message.email_body), ("Felicidades", "Hola\n\nTienes {puntos} puntos"))
        self.assertEqual(message.updated_by, self.owner)


class NotificationTextTests(BirthdaySettingsTestCase):
    def test_custom_email_replaces_the_placeholder_and_keeps_the_unsubscribe_footer(self):
        self.update(email_subject="¡{puntos} puntos para ti & los tuyos!", email_body="Feliz día. Te regalamos {puntos} puntos.")
        self.customer(promo_email_opt_in=True)
        self.run_day()
        notifications.process_due()
        message = mail.outbox[-1]
        self.assertEqual(message.subject, "¡50 puntos para ti & los tuyos!")
        self.assertIn("Te regalamos 50 puntos.", message.body)
        self.assertNotIn("¡Salud!", message.body)
        self.assertIn("darte de baja", message.body)
        self.assertIn("List-Unsubscribe", message.extra_headers)

    def test_empty_texts_use_the_default_message(self):
        self.customer(promo_email_opt_in=True)
        self.run_day()
        notifications.process_due()
        message = mail.outbox[-1]
        self.assertEqual(message.subject, "¡Feliz cumpleaños de parte de Caneca Furada!")
        self.assertIn("te hemos regalado 50 puntos", message.body)

    def test_template_syntax_stored_in_the_message_is_not_interpreted(self):
        # Aunque llegara a la BD sin pasar por el servicio, se envía tal cual.
        BirthdayMessage.objects.create(email_body="{{ site_base_url }} {% now 'Y' %} {puntos}")
        self.customer(promo_email_opt_in=True)
        self.run_day()
        notifications.process_due()
        self.assertIn("{{ site_base_url }} {% now 'Y' %} 50", mail.outbox[-1].body)

    def test_queued_notifications_keep_the_text_they_were_created_with(self):
        self.update(email_body="Primer texto {puntos}")
        self.customer(promo_email_opt_in=True)
        self.run_day()
        self.update(email_body="Segundo texto {puntos}")
        notifications.process_due()
        self.assertIn("Primer texto 50", mail.outbox[-1].body)
        notification = Notification.objects.get(kind=Notification.Kind.BIRTHDAY)
        self.assertEqual(notification.context["custom_body"], "Primer texto 50")

    @override_settings(**SMS_SETTINGS)
    def test_custom_sms_keeps_the_brand_and_the_unsubscribe_link(self):
        self.update(sms_body="¡Felicidades! Tienes {puntos} puntos de regalo.")
        self.customer(phone_number=VALID_MOBILE, promo_sms_opt_in=True)
        self.run_day()
        notifications.process_due()
        sms = [m for m in LocmemSmsBackend.outbox if "Felicidades" in m["body"]]
        self.assertEqual(len(sms), 1)
        self.assertTrue(sms[0]["body"].startswith("Caneca Furada: ¡Felicidades! Tienes 50 puntos de regalo. Baja: "))
        self.assertTrue(Notification.objects.filter(kind=Notification.Kind.BIRTHDAY, channel=Channel.SMS).exists())
