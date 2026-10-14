"""
Promociones de cumpleaños (Fase 10): detección, 29-F, email verificado,
anti-abuso, regalo único por año, preferencias, avisos y registro.
"""
import datetime
from io import StringIO
from zoneinfo import ZoneInfo

from django.core import mail
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts import services as accounts
from apps.accounts.models import CustomerProfile
from apps.core.models import AuditEvent
from apps.loyalty import birthdays, ledger
from apps.loyalty.models import PointsTransaction, Promotion
from apps.notifications import services as notifications
from apps.notifications.models import Channel, Notification
from apps.notifications.sms import LocmemSmsBackend
from tests.accounts.factories import VALID_MOBILE, registration_data

from .factories import make_customer_with_qr, make_employee, make_promotion

MADRID = ZoneInfo("Europe/Madrid")
Kind = PointsTransaction.Kind
SMS_SETTINGS = {"SMS_BACKEND": "apps.notifications.sms.LocmemSmsBackend"}


def set_birth_date(user, date_of_birth, changed_at=None):
    CustomerProfile.objects.filter(user=user).update(date_of_birth=date_of_birth, date_of_birth_changed_at=changed_at)


def gifts(customer=None):
    queryset = PointsTransaction.objects.filter(kind=Kind.BIRTHDAY_GIFT)
    if customer is not None:
        queryset = queryset.filter(customer=customer)
    return list(queryset.values_list("points", "birthday_year"))


class BirthdayTestCase(TestCase):
    # Un día fijo, no bisiesto, para que los tests no dependan de la fecha real.
    DAY = datetime.date(2027, 6, 15)
    AT = datetime.datetime(2027, 6, 15, 9, tzinfo=MADRID)

    def setUp(self):
        cache.clear()
        LocmemSmsBackend.outbox.clear()
        self.promo = make_promotion(
            name="Cumpleaños", kind=Promotion.Kind.BIRTHDAY, fixed_points=50, starts_at=datetime.datetime(2027, 1, 1, tzinfo=MADRID)
        )

    def customer(self, email="cumple@example.com", dob=datetime.date(1990, 6, 15), verified=True, **data):
        if verified:
            user, _ = make_customer_with_qr(email, **data)
        else:
            user = accounts.register_customer(**registration_data(email=email, **data))
        set_birth_date(user, dob)
        return user

    def run_day(self, day=None, at=None):
        return birthdays.run_birthday_promotions(day=day or self.DAY, at=at or self.AT)


class BirthdayGiftTests(BirthdayTestCase):
    def test_gift_is_granted_once_even_if_run_twice(self):
        user = self.customer()
        first = self.run_day()
        second = self.run_day()
        self.assertEqual(gifts(user), [(50, 2027)])
        self.assertEqual(ledger.balance(user), 50)
        self.assertEqual((first.granted, second.granted, second.not_eligible), (1, 0, 1))

    def test_only_one_gift_with_several_birthday_promotions(self):
        make_promotion(name="Otro cumpleaños", kind=Promotion.Kind.BIRTHDAY, fixed_points=80, starts_at=self.promo.starts_at)
        user = self.customer()
        self.run_day()
        self.assertEqual(gifts(user), [(50, 2027)])

    def test_other_days_and_missing_date_get_nothing(self):
        self.customer("otro@example.com", dob=datetime.date(1990, 6, 16))
        user = self.customer("sin-fecha@example.com")
        set_birth_date(user, None)
        result = self.run_day()
        self.assertEqual(gifts(), [])
        self.assertEqual(result.birthdays, 0)

    def test_unverified_inactive_and_staff_get_nothing(self):
        self.customer("sin-verificar@example.com", verified=False)
        inactive = self.customer("inactivo@example.com")
        inactive.is_active = False
        inactive.save(update_fields=["is_active"])
        employee = make_employee()
        CustomerProfile.objects.create(user=employee, date_of_birth=datetime.date(1990, 6, 15))
        self.run_day()
        self.assertEqual(gifts(), [])

    def test_no_active_promotion_means_nothing(self):
        self.customer()
        Promotion.objects.update(status=Promotion.Status.PAUSED)
        result = self.run_day()
        self.assertFalse(result.promotion)
        self.assertEqual(gifts(), [])

    def test_max_total_uses_is_respected(self):
        Promotion.objects.filter(pk=self.promo.pk).update(max_total_uses=1)
        self.customer("uno@example.com")
        self.customer("dos@example.com")
        self.run_day()
        self.assertEqual(len(gifts()), 1)

    @override_settings(LOYALTY_BIRTHDAY_DOB_STABLE_DAYS=30)
    def test_recently_changed_birth_date_is_not_eligible(self):
        user = self.customer()
        set_birth_date(user, datetime.date(1990, 6, 15), changed_at=self.AT - datetime.timedelta(days=29))
        self.run_day()
        self.assertEqual(gifts(user), [])
        set_birth_date(user, datetime.date(1990, 6, 15), changed_at=self.AT - datetime.timedelta(days=31))
        self.run_day()
        self.assertEqual(gifts(user), [(50, 2027)])

    @override_settings(LOYALTY_BIRTHDAY_MIN_DAYS_BETWEEN_BONUSES=300)
    def test_changing_birth_date_cannot_give_another_gift_soon(self):
        user = self.customer()
        self.run_day()
        # Cambia la fecha a otro día (hace tiempo suficiente para el anti-abuso de la fecha).
        set_birth_date(user, datetime.date(1990, 9, 1), changed_at=self.AT - datetime.timedelta(days=60))
        september = datetime.datetime(2027, 9, 1, 9, tzinfo=MADRID)
        # Simula que el regalo anterior fue de otro año pero reciente (78 días antes).
        PointsTransaction.objects.filter(kind=Kind.BIRTHDAY_GIFT).update(birthday_year=2026, created_at=self.AT)
        self.run_day(day=september.date(), at=september)
        self.assertEqual(len(gifts(user)), 1)

    def test_database_allows_one_birthday_per_customer_and_year(self):
        user = self.customer()
        self.run_day()
        with self.assertRaises(IntegrityError), transaction.atomic():
            PointsTransaction.objects.create(
                customer=user, kind=Kind.BIRTHDAY_GIFT, points=5, balance_after=55, promotion=self.promo, birthday_year=2027
            )

    def test_database_rejects_gift_without_promotion_or_with_purchase(self):
        user = self.customer()
        with self.assertRaises(IntegrityError), transaction.atomic():
            PointsTransaction.objects.create(customer=user, kind=Kind.BIRTHDAY_GIFT, points=5, balance_after=5, birthday_year=2027)

    def test_29_february_is_celebrated_on_28_in_common_years(self):
        user = self.customer(dob=datetime.date(1996, 2, 29))
        march = datetime.datetime(2027, 3, 1, 9, tzinfo=MADRID)
        self.run_day(day=march.date(), at=march)
        self.assertEqual(gifts(user), [])
        feb28 = datetime.datetime(2027, 2, 28, 9, tzinfo=MADRID)
        self.run_day(day=feb28.date(), at=feb28)
        self.assertEqual(gifts(user), [(50, 2027)])

    def test_29_february_in_leap_year(self):
        user = self.customer(dob=datetime.date(1996, 2, 29))
        feb28 = datetime.datetime(2028, 2, 28, 9, tzinfo=MADRID)
        self.run_day(day=feb28.date(), at=feb28)
        self.assertEqual(gifts(user), [])
        feb29 = datetime.datetime(2028, 2, 29, 9, tzinfo=MADRID)
        self.run_day(day=feb29.date(), at=feb29)
        self.assertEqual(gifts(user), [(50, 2028)])

    def test_result_is_audited_without_personal_data(self):
        self.customer()
        self.run_day()
        event = AuditEvent.objects.get(action=AuditEvent.Action.BIRTHDAY_PROMOTIONS_RUN)
        self.assertEqual(event.metadata["granted"], 1)
        self.assertNotIn("cumple@example.com", str(event.metadata))


class BirthdayNotificationTests(BirthdayTestCase):
    def notifications(self, channel=None):
        queryset = Notification.objects.filter(kind=Notification.Kind.BIRTHDAY)
        return queryset.filter(channel=channel) if channel else queryset

    def test_without_consent_gets_the_gift_but_no_message(self):
        """La verificación del email no es consentimiento publicitario."""
        user = self.customer()
        self.run_day()
        self.assertEqual(gifts(user), [(50, 2027)])
        self.assertFalse(self.notifications().exists())

    def test_with_consent_the_notice_is_queued_once_and_sent_by_the_task(self):
        self.customer(promo_email_opt_in=True)
        self.run_day()
        self.run_day()
        self.assertEqual(self.notifications().count(), 1)
        mail.outbox.clear()
        result = notifications.process_due()
        self.assertEqual(result.sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn("50 puntos", message.body)
        self.assertIn("/comunicaciones/baja/", message.body)
        self.assertIn("List-Unsubscribe", message.extra_headers)
        self.assertNotIn("Lúa", message.body)  # sin saludo personal en las promociones

    def test_consent_withdrawn_before_sending_skips_the_message(self):
        user = self.customer(promo_email_opt_in=True)
        self.run_day()
        accounts.set_communication_preferences(user=user, promo_email_opt_in=False, promo_sms_opt_in=False)
        mail.outbox.clear()
        notifications.process_due()
        self.assertEqual(mail.outbox, [])
        notification = self.notifications().get()
        self.assertEqual(notification.status, Notification.Status.SKIPPED)
        self.assertEqual(notification.last_error, notifications.SkipReason.NO_CONSENT)

    def test_sms_is_not_used_without_provider(self):
        self.customer(phone_number=VALID_MOBILE, promo_sms_opt_in=True)
        result = self.run_day()
        self.assertEqual(result.sms_queued, 0)
        self.assertFalse(self.notifications(Channel.SMS).exists())

    @override_settings(**SMS_SETTINGS)
    def test_sms_with_provider_phone_and_consent(self):
        self.customer("sms@example.com", phone_number=VALID_MOBILE, promo_sms_opt_in=True)
        self.customer("sin-sms@example.com", phone_number=VALID_MOBILE)
        result = self.run_day()
        self.assertEqual(result.sms_queued, 1)
        notifications.process_due()
        self.assertEqual(len(LocmemSmsBackend.outbox), 1)
        self.assertEqual(LocmemSmsBackend.outbox[0]["to"], "+34600000001")
        self.assertIn("Baja:", LocmemSmsBackend.outbox[0]["body"])


class BirthdayCommandTests(BirthdayTestCase):
    def test_command_processes_today(self):
        today = timezone.localdate()
        dob = datetime.date(1990, today.month, today.day) if (today.month, today.day) != (2, 29) else datetime.date(1996, 2, 29)
        Promotion.objects.update(starts_at=timezone.now() - datetime.timedelta(days=1))
        user = self.customer(dob=dob)
        out = StringIO()
        call_command("run_birthday_promotions", stdout=out)
        self.assertIn("regalos 1", out.getvalue())
        self.assertEqual(len(gifts(user)), 1)

    def test_command_rejects_future_dates_and_bad_input(self):
        tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        with self.assertRaises(CommandError):
            call_command("run_birthday_promotions", date=tomorrow.isoformat(), stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command("run_birthday_promotions", date="2027-02-30", stdout=StringIO())

    def test_days_back_is_capped(self):
        today = datetime.date(2027, 6, 15)
        days = birthdays.days_to_process(days_back=30, today=today)
        self.assertEqual(len(days), birthdays.MAX_DAYS_BACK + 1)
        self.assertEqual(days[-1], today)
