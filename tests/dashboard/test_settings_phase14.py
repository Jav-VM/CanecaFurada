"""
Dashboard → Configuración (Fase 14): caducidad de puntos y regalo de
cumpleaños. Acceso, escalada de privilegios, validación y campos ignorados.
"""
import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.loyalty import expiry
from apps.loyalty.models import BirthdayMessage, PointsExpiryPolicy, Promotion
from tests.rewards.factories import make_customer_with_qr, make_employee, make_owner

EXPIRY_URL = reverse("dashboard:settings_expiry")
BIRTHDAY_URL = reverse("dashboard:settings_birthday")
SETTINGS_URL = reverse("dashboard:settings")


def expiry_data(**overrides):
    data = {"caducidad-enabled": "on", "caducidad-months": "12", "caducidad-warn_days": "15", "caducidad-note": ""}
    data.update(overrides)
    return {key: value for key, value in data.items() if value is not None}


def birthday_data(**overrides):
    data = {
        "cumple-active": "on",
        "cumple-points": "40",
        "cumple-email_subject": "",
        "cumple-email_body": "",
        "cumple-sms_body": "",
    }
    data.update(overrides)
    return {key: value for key, value in data.items() if value is not None}


class SettingsPhase14TestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.customer, _ = make_customer_with_qr()
        self.employee = make_employee()
        self.owner = make_owner()
        self.client.force_login(self.owner)


class AccessTests(SettingsPhase14TestCase):
    def test_settings_page_shows_both_sections(self):
        response = self.client.get(SETTINGS_URL)
        self.assertContains(response, "data-expiry-settings")
        self.assertContains(response, "data-birthday-settings")
        self.assertContains(response, "los puntos no caducan")
        self.assertContains(response, 'name="caducidad-months"')
        self.assertContains(response, 'name="cumple-email_body"')

    def test_only_post_is_allowed(self):
        self.assertEqual(self.client.get(EXPIRY_URL).status_code, 405)
        self.assertEqual(self.client.get(BIRTHDAY_URL).status_code, 405)

    def test_employee_and_customer_are_forbidden(self):
        for user in (self.employee, self.customer):
            self.client.force_login(user)
            self.assertEqual(self.client.post(EXPIRY_URL, expiry_data()).status_code, 403)
            self.assertEqual(self.client.post(BIRTHDAY_URL, birthday_data()).status_code, 403)
        self.assertFalse(PointsExpiryPolicy.objects.exists())
        self.assertFalse(Promotion.objects.exists())

    def test_anonymous_is_sent_to_login(self):
        self.client.logout()
        for url, data in ((EXPIRY_URL, expiry_data()), (BIRTHDAY_URL, birthday_data())):
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertFalse(PointsExpiryPolicy.objects.exists())


class ExpiryViewTests(SettingsPhase14TestCase):
    def test_owner_enables_and_disables_expiry(self):
        response = self.client.post(EXPIRY_URL, expiry_data())
        self.assertRedirects(response, SETTINGS_URL)
        policy = expiry.active_policy()
        self.assertEqual((policy.months, policy.warn_days, policy.created_by), (12, 15, self.owner))
        self.assertContains(self.client.get(SETTINGS_URL), "caducan a los 12 meses")
        self.client.post(EXPIRY_URL, expiry_data(**{"caducidad-enabled": None}))
        self.assertIsNone(expiry.active_policy())

    def test_counts_from_cannot_be_sent_by_the_client(self):
        past = (timezone.now() - datetime.timedelta(days=900)).isoformat()
        self.client.post(EXPIRY_URL, expiry_data(**{"caducidad-counts_from": past, "counts_from": past}))
        policy = expiry.active_policy()
        self.assertGreater(policy.counts_from, timezone.now() - datetime.timedelta(minutes=5))

    def test_invalid_data_is_rejected(self):
        for data in (
            expiry_data(**{"caducidad-months": ""}),
            expiry_data(**{"caducidad-months": "0"}),
            expiry_data(**{"caducidad-months": "61"}),
            expiry_data(**{"caducidad-warn_days": "0"}),
            expiry_data(**{"caducidad-months": "doce"}),
        ):
            self.assertEqual(self.client.post(EXPIRY_URL, data).status_code, 400)
        self.assertFalse(PointsExpiryPolicy.objects.exists())

    def test_repeating_the_same_values_creates_no_version(self):
        self.client.post(EXPIRY_URL, expiry_data())
        response = self.client.post(EXPIRY_URL, expiry_data(), follow=True)
        self.assertContains(response, "No había cambios")
        self.assertEqual(PointsExpiryPolicy.objects.count(), 1)


class BirthdayViewTests(SettingsPhase14TestCase):
    def test_owner_saves_points_and_texts(self):
        data = birthday_data(**{"cumple-email_subject": "Felicidades", "cumple-email_body": "Tienes {puntos} puntos"})
        response = self.client.post(BIRTHDAY_URL, data)
        self.assertRedirects(response, SETTINGS_URL)
        promo = Promotion.objects.get(kind=Promotion.Kind.BIRTHDAY)
        self.assertEqual((promo.fixed_points, promo.status), (40, Promotion.Status.ACTIVE))
        message = BirthdayMessage.objects.get()
        self.assertEqual((message.email_subject, message.email_body), ("Felicidades", "Tienes {puntos} puntos"))
        page = self.client.get(SETTINGS_URL)
        self.assertContains(page, 'value="40"')
        self.assertContains(page, "Tienes {puntos} puntos")

    def test_template_syntax_is_rejected(self):
        response = self.client.post(BIRTHDAY_URL, birthday_data(**{"cumple-email_body": "Hola {{ first_name }}"}))
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "El único marcador admitido", status_code=400)
        self.assertFalse(BirthdayMessage.objects.exists())
        self.assertFalse(Promotion.objects.exists())

    def test_invalid_points_are_rejected(self):
        for points in ("0", "", "10001", "muchos"):
            self.assertEqual(self.client.post(BIRTHDAY_URL, birthday_data(**{"cumple-points": points})).status_code, 400)
        self.assertFalse(Promotion.objects.exists())

    def test_unchecking_active_pauses_the_gift(self):
        self.client.post(BIRTHDAY_URL, birthday_data())
        self.client.post(BIRTHDAY_URL, birthday_data(**{"cumple-active": None}))
        self.assertEqual(Promotion.objects.get().status, Promotion.Status.PAUSED)
