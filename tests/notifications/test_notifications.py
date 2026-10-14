"""
Notificaciones (Fase 10): registro real de envíos, idempotencia, reintentos,
consentimiento, SMS opcional, campañas, baja y emails de cuentas.
"""
import datetime
from io import StringIO
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts import services as accounts
from apps.accounts.models import CommunicationPreferenceChange, CustomerProfile
from apps.core.models import AuditEvent
from apps.notifications import campaigns, services, unsubscribe
from apps.notifications.models import Campaign, Channel, Notification
from apps.notifications.sms import LocmemSmsBackend
from tests.accounts.factories import VALID_MOBILE, registration_data
from tests.loyalty.factories import make_customer_with_qr, make_employee, make_owner

Kind = Notification.Kind
Status = Notification.Status
SMS_SETTINGS = {"SMS_BACKEND": "apps.notifications.sms.LocmemSmsBackend"}


def customer(email="cliente@example.com", **data):
    return make_customer_with_qr(email, **data)[0]


class NotificationTestCase(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox.clear()
        LocmemSmsBackend.outbox.clear()


class SendImmediatelyTests(NotificationTestCase):
    def test_sent_is_recorded_without_context_or_address(self):
        user = customer()
        ok = services.send_immediately(
            kind=Kind.EXISTING_ACCOUNT,
            recipient=user,
            to=user.email,
            subject_template="emails/existing_account_subject.txt",
            body_template="emails/existing_account_body.txt",
            context={"password_reset_url": "https://example.com/x"},
        )
        self.assertTrue(ok)
        notification = Notification.objects.get(kind=Kind.EXISTING_ACCOUNT)
        self.assertEqual(notification.status, Status.SENT)
        self.assertIsNotNone(notification.sent_at)
        self.assertEqual(notification.context, {})
        self.assertEqual(len(mail.outbox), 1)

    def test_failure_is_recorded_and_logged_without_address(self):
        user = customer()
        with mock.patch("apps.notifications.services._send_email", side_effect=OSError("caído cliente@example.com")):
            with self.assertLogs("apps.notifications.services", level="ERROR") as logs:
                ok = services.send_immediately(
                    kind=Kind.EMAIL_CHANGED_NOTICE,
                    recipient=user,
                    to=user.email,
                    subject_template="emails/email_changed_notice_subject.txt",
                    body_template="emails/email_changed_notice_body.txt",
                    context={"first_name": "Ana"},
                )
        self.assertFalse(ok)
        self.assertEqual(Notification.objects.get().status, Status.FAILED)
        self.assertNotIn("cliente@example.com", " ".join(logs.output))

    def test_only_account_messages_are_sent_immediately(self):
        with self.assertRaises(ValueError):
            services.send_immediately(
                kind=Kind.CAMPAIGN, recipient=customer(), to="x@example.com", subject_template="", body_template="", context={}
            )

    def test_verification_email_is_recorded_without_token(self):
        with self.captureOnCommitCallbacks(execute=True):
            user = accounts.register_customer(**registration_data())
        notification = Notification.objects.get(recipient=user)
        self.assertEqual((notification.kind, notification.status), (Kind.EMAIL_VERIFICATION, Status.SENT))
        self.assertEqual(notification.context, {})
        self.assertIn("/cuenta/verificar-email/", mail.outbox[0].body)

    def test_password_reset_goes_through_the_registry(self):
        user = customer()
        self.client.post(reverse("accounts:password_reset"), {"email": user.email})
        notification = Notification.objects.get(kind=Kind.PASSWORD_RESET)
        self.assertEqual(notification.status, Status.SENT)
        self.assertEqual(notification.context, {})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/cuenta/contrasena/restablecer/", mail.outbox[0].body)

    def test_password_reset_for_unknown_email_sends_nothing(self):
        self.client.post(reverse("accounts:password_reset"), {"email": "nadie@example.com"})
        self.assertFalse(Notification.objects.exists())
        self.assertEqual(mail.outbox, [])


class QueueTests(NotificationTestCase):
    def enqueue(self, user, **kwargs):
        data = {
            "kind": Kind.RESERVATION_CONFIRMED,
            "recipient": user,
            "context": {"when": "01/01/2030 a las 21:00", "party_size": 2, "event_title": "", "message": ""},
        }
        data.update(kwargs)
        return services.enqueue(**data)

    def test_dedup_key_prevents_duplicates(self):
        user = customer()
        first, created1 = self.enqueue(user, dedup_key="k1")
        second, created2 = self.enqueue(user, dedup_key="k1")
        self.assertEqual((created1, created2), (True, False))
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Notification.objects.count(), 1)

    def test_context_must_be_simple_values(self):
        with self.assertRaises(ValueError):
            self.enqueue(customer(), context={"user": object()})

    def test_account_messages_cannot_be_queued(self):
        with self.assertRaises(ValueError):
            services.enqueue(kind=Kind.PASSWORD_RESET, recipient=customer())

    def test_category_follows_kind(self):
        user = customer()
        promo, _ = services.enqueue(kind=Kind.CAMPAIGN, recipient=user)
        transactional, _ = self.enqueue(user)
        self.assertEqual(promo.category, Notification.Category.PROMOTIONAL)
        self.assertEqual(transactional.category, Notification.Category.TRANSACTIONAL)

    def test_deliver_sends_once_with_first_name(self):
        user = customer()
        notification, _ = self.enqueue(user)
        self.assertEqual(services.deliver(notification.pk), Status.SENT)
        self.assertIsNone(services.deliver(notification.pk))  # ya no está pendiente
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Hola, Lúa", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, [user.email])

    @override_settings(NOTIFICATIONS_MAX_ATTEMPTS=2, NOTIFICATIONS_RETRY_BASE_MINUTES=5)
    def test_failures_are_retried_with_backoff_then_failed(self):
        notification, _ = self.enqueue(customer())
        with mock.patch("apps.notifications.services._send_email", side_effect=ConnectionError("smtp")):
            with self.assertLogs("apps.notifications.services", level="WARNING"):
                self.assertEqual(services.deliver(notification.pk), Status.PENDING)
            notification.refresh_from_db()
            self.assertEqual(notification.last_error, "ConnectionError")
            self.assertGreater(notification.next_attempt_at, timezone.now() + datetime.timedelta(minutes=4))
            # No se reintenta antes de tiempo.
            self.assertEqual(services.process_due().sent + services.process_due().failed, 0)
            later = timezone.now() + datetime.timedelta(minutes=6)
            with self.assertLogs("apps.notifications.services", level="WARNING"):
                result = services.process_due(now=later)
        self.assertEqual(result.failed, 1)
        notification.refresh_from_db()
        self.assertEqual((notification.status, notification.attempts), (Status.FAILED, 2))

    def test_inactive_recipient_is_skipped(self):
        user = customer()
        notification, _ = self.enqueue(user)
        user.is_active = False
        user.save(update_fields=["is_active"])
        self.assertEqual(services.deliver(notification.pk), Status.SKIPPED)
        self.assertEqual(mail.outbox, [])

    def test_promotional_requires_current_consent(self):
        user = customer(promo_email_opt_in=True)
        allowed, _ = services.enqueue(kind=Kind.BIRTHDAY, recipient=user, context={"points": 5, "year": 2030})
        self.assertEqual(services.deliver(allowed.pk), Status.SENT)
        other = customer("sin@example.com")
        denied, _ = services.enqueue(kind=Kind.BIRTHDAY, recipient=other, context={"points": 5, "year": 2030})
        self.assertEqual(services.deliver(denied.pk), Status.SKIPPED)
        denied.refresh_from_db()
        self.assertEqual(denied.last_error, services.SkipReason.NO_CONSENT)

    def test_sms_without_provider_is_never_sent(self):
        user = customer(phone_number=VALID_MOBILE, promo_sms_opt_in=True)
        notification, _ = services.enqueue(
            kind=Kind.BIRTHDAY, recipient=user, channel=Channel.SMS, context={"points": 5, "year": 2030}
        )
        self.assertEqual(services.deliver(notification.pk), Status.SKIPPED)
        notification.refresh_from_db()
        self.assertEqual(notification.last_error, services.SkipReason.NO_SMS_PROVIDER)
        self.assertFalse(services.sms_available())

    @override_settings(**SMS_SETTINGS)
    def test_sms_with_provider_requires_valid_phone(self):
        user = customer(phone_number=VALID_MOBILE, promo_sms_opt_in=True)
        CustomerProfile.objects.filter(user=user).update(phone_number="+340")  # dato corrupto en BD
        notification, _ = services.enqueue(
            kind=Kind.BIRTHDAY, recipient=user, channel=Channel.SMS, context={"points": 5, "year": 2030}
        )
        self.assertEqual(services.deliver(notification.pk), Status.SKIPPED)
        notification.refresh_from_db()
        self.assertEqual(notification.last_error, services.SkipReason.INVALID_PHONE)
        self.assertEqual(LocmemSmsBackend.outbox, [])

    def test_stale_sending_is_recovered(self):
        user = customer()
        queued, _ = self.enqueue(user)
        immediate = Notification.objects.create(
            recipient=user, kind=Kind.PASSWORD_RESET, category="TRANSACTIONAL", status=Status.SENDING, attempts=1
        )
        Notification.objects.filter(pk=queued.pk).update(status=Status.SENDING)
        old = timezone.now() - datetime.timedelta(hours=2)
        Notification.objects.update(updated_at=old)
        requeued, interrupted = services.recover_stale()
        self.assertEqual((requeued, interrupted), (1, 1))
        immediate.refresh_from_db()
        # Sin contexto no puede recomponerse: nunca se reenvía un enlace sin token.
        self.assertEqual(immediate.status, Status.FAILED)
        self.assertIsNone(services.deliver(immediate.pk))

    def test_process_due_respects_limit_and_command(self):
        user = customer()
        for index in range(3):
            self.enqueue(user, dedup_key=f"k{index}")
        self.assertEqual(services.process_due(limit=2).sent, 2)
        out = StringIO()
        call_command("process_notifications", stdout=out)
        self.assertIn("Enviadas: 1", out.getvalue())


class CampaignTests(NotificationTestCase):
    def setUp(self):
        super().setUp()
        self.owner = make_owner()
        self.yes = customer("si@example.com", promo_email_opt_in=True)
        self.no = customer("no@example.com")
        self.unverified = accounts.register_customer(**registration_data(email="pendiente@example.com", promo_email_opt_in=True))
        self.inactive = customer("inactivo@example.com", promo_email_opt_in=True)
        self.inactive.is_active = False
        self.inactive.save(update_fields=["is_active"])
        mail.outbox.clear()

    def draft(self, **data):
        values = {"name": "Otoño", "channel": Channel.EMAIL, "subject": "Novedades & más", "body": "Llega la cerveza de otoño."}
        values.update(data)
        return campaigns.save_campaign(actor=self.owner, campaign=Campaign(), data=values)

    def test_only_owner_manages_campaigns(self):
        for actor in (make_employee(), self.yes, None):
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                campaigns.save_campaign(actor=actor, campaign=Campaign(), data={"name": "x", "body": "y", "subject": "z"})

    def test_validation(self):
        with self.assertRaises(ValidationError):
            self.draft(subject="")
        with self.assertRaises(ValidationError):
            self.draft(channel=Channel.SMS, body="x" * 321)
        with self.assertRaises(ValidationError):
            self.draft(body="x" * 2001)

    def test_queue_does_not_send_from_the_request(self):
        campaign = self.draft()
        campaigns.queue_campaign(actor=self.owner, campaign=campaign)
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(mail.outbox, [])
        self.assertEqual(Campaign.objects.get().status, Campaign.Status.QUEUED)

    def test_dispatch_only_to_verified_active_consenting_customers(self):
        campaign = self.draft()
        campaigns.queue_campaign(actor=self.owner, campaign=campaign)
        call_command("process_notifications", stdout=StringIO())
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.DISPATCHED)
        self.assertEqual(campaign.recipients_count, 1)
        self.assertEqual([m.to for m in mail.outbox], [["si@example.com"]])
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Novedades & más")
        self.assertIn("/comunicaciones/baja/", message.body)
        # Repartir otra vez no duplica.
        self.assertEqual(campaigns.dispatch_queued(), 0)

    def test_sms_campaign_needs_provider(self):
        campaign = self.draft(channel=Channel.SMS, subject="")
        with self.assertRaises(ValidationError):
            campaigns.queue_campaign(actor=self.owner, campaign=campaign)

    def test_edit_only_in_draft_and_cancel(self):
        campaign = self.draft()
        campaigns.queue_campaign(actor=self.owner, campaign=campaign)
        with self.assertRaises(ValidationError):
            campaigns.save_campaign(actor=self.owner, campaign=campaign, data={"body": "otro"})
        campaigns.cancel_campaign(actor=self.owner, campaign=campaign)
        self.assertEqual(campaigns.dispatch_queued(), 0)
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.Action.CAMPAIGN_UPDATED).exists())

    def test_audit_does_not_store_the_text(self):
        self.draft(body="Texto secreto de la campaña")
        self.assertNotIn("secreto", str(list(AuditEvent.objects.values_list("metadata", flat=True))))


class UnsubscribeTests(NotificationTestCase):
    def test_get_asks_and_post_withdraws_with_history(self):
        user = customer(promo_email_opt_in=True)
        url = reverse("notifications:unsubscribe", args=[unsubscribe.make_token(user, Channel.EMAIL)])
        response = self.client.get(url)
        self.assertContains(response, "Darme de baja")
        user.customer_profile.refresh_from_db()
        self.assertTrue(user.customer_profile.promo_email_opt_in)
        response = self.client.post(url)
        self.assertContains(response, "Ya no recibirás")
        user.customer_profile.refresh_from_db()
        self.assertFalse(user.customer_profile.promo_email_opt_in)
        change = CommunicationPreferenceChange.objects.filter(user=user).first()
        self.assertEqual((change.channel, change.opted_in, change.source), ("EMAIL", False, "UNSUBSCRIBE"))
        # Repetir no añade historial.
        self.client.post(url)
        self.assertEqual(CommunicationPreferenceChange.objects.filter(user=user, source="UNSUBSCRIBE").count(), 1)

    def test_invalid_or_tampered_tokens(self):
        user = customer(promo_email_opt_in=True)
        token = unsubscribe.make_token(user, Channel.EMAIL)
        for bad in ("nada", token[:-2] + "xx"):
            with self.subTest(bad=bad):
                response = self.client.post(reverse("notifications:unsubscribe", args=[bad]))
                self.assertEqual(response.status_code, 400)
        user.customer_profile.refresh_from_db()
        self.assertTrue(user.customer_profile.promo_email_opt_in)

    @override_settings(NOTIFICATIONS_UNSUBSCRIBE_MAX_AGE_DAYS=1)
    def test_expired_token(self):
        user = customer(promo_email_opt_in=True)
        token = unsubscribe.make_token(user, Channel.EMAIL)
        with mock.patch("django.core.signing.time.time", return_value=timezone.now().timestamp() + 3 * 86400):
            self.assertIsNone(unsubscribe.read_token(token))

    def test_staff_tokens_are_not_valid(self):
        owner = make_owner()
        self.assertIsNone(unsubscribe.read_token(unsubscribe.make_token(owner, Channel.EMAIL)))


class ChannelStatusTests(NotificationTestCase):
    def test_dashboard_never_presents_simulated_email_as_real(self):
        owner = make_owner()
        self.client.force_login(owner)
        response = self.client.get(reverse("dashboard:communications"))
        self.assertContains(response, 'data-email-real="no"', html=False)
        self.assertContains(response, 'data-sms-configured="no"', html=False)
        self.assertContains(response, "No hay ningún proveedor de SMS integrado")
