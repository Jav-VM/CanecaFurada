"""QR personal: token aleatorio y opaco, identificación, renovación y vista del cliente."""
from unittest import mock

from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts import services as accounts
from apps.loyalty import services
from apps.loyalty.models import CustomerQRCode
from apps.core.models import AuditEvent
from tests.accounts.factories import PASSWORD, VALID_MOBILE

from .factories import make_customer_with_qr, make_employee, make_verified_customer

PERSONAL_VALUES = ("Lúa", "Ficticia", "cliente@example.com", "Rúa Ficticia", "15001", "600000001", "1996")


class TokenTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_token_is_random_opaque_base32(self):
        tokens = {services.generate_token() for _ in range(200)}
        self.assertEqual(len(tokens), 200)
        for token in list(tokens)[:20]:
            self.assertRegex(token, r"^[A-Z2-7]{32}$")

    def test_qr_payload_contains_no_personal_data_or_balance(self):
        user, token = make_customer_with_qr(phone_number=VALID_MOBILE)
        payload = services.qr_payload(token)
        self.assertEqual(payload, f"CF1:{token}")
        for value in (*PERSONAL_VALUES, str(user.public_id), "saldo", "puntos"):
            with self.subTest(value=value):
                self.assertNotIn(value.upper(), payload.upper())

    def test_normalize_accepts_payload_and_typed_code(self):
        token = services.generate_token()
        for raw in (token, f"CF1:{token}", services.format_code(token), token.lower(), f" {token[:16]}-{token[16:]} "):
            with self.subTest(raw=raw):
                self.assertEqual(services.normalize_code(raw), token)

    def test_normalize_rejects_malformed_codes(self):
        for raw in (None, "", "CF1:", "A" * 31, "A" * 33, "1" * 32, "https://example.com", "X" * 200, 12345):
            with self.subTest(raw=raw):
                self.assertIsNone(services.normalize_code(raw))

    def test_mask_never_reveals_the_full_token(self):
        token = services.generate_token()
        self.assertEqual(services.mask_code(token), f"{token[:4]}…")

    def test_str_does_not_include_token(self):
        user, token = make_customer_with_qr()
        self.assertNotIn(token, str(user.qr_code))


class CustomerQRServiceTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_qr_is_created_once_and_reused(self):
        user = make_verified_customer()
        first = services.get_customer_qr(user)
        user.refresh_from_db()
        self.assertEqual(services.get_customer_qr(user).token, first.token)
        self.assertEqual(CustomerQRCode.objects.count(), 1)

    def test_only_verified_active_customers_have_qr(self):
        unverified = accounts.create_customer(email="pendiente@example.com", password=PASSWORD, first_name="A", last_name="B")
        inactive = make_verified_customer("inactiva@example.com")
        inactive.is_active = False
        for user in (unverified, inactive, make_employee()):
            with self.subTest(user=user.email), self.assertRaises(PermissionDenied):
                services.get_customer_qr(user)
        self.assertFalse(CustomerQRCode.objects.exists())

    def test_rotation_invalidates_previous_token_and_is_audited(self):
        user, old_token = make_customer_with_qr()
        new = services.rotate_customer_qr(user)
        self.assertNotEqual(new.token, old_token)
        self.assertIsNotNone(new.rotated_at)
        with self.assertRaises(services.InvalidQRCode):
            services.identify_customer(old_token)
        self.assertEqual(services.identify_customer(new.token), user)
        event = AuditEvent.objects.get(action=AuditEvent.Action.QR_ROTATED)
        self.assertNotIn(old_token, str(event.metadata))
        self.assertNotIn(new.token, str(event.metadata))

    @override_settings(LOYALTY_QR_MAX_ROTATIONS_PER_DAY=2)
    def test_rotation_is_rate_limited(self):
        user, _ = make_customer_with_qr()
        services.rotate_customer_qr(user)
        services.rotate_customer_qr(user)
        with self.assertRaises(services.RotationRateLimited):
            services.rotate_customer_qr(user)


class IdentifyCustomerTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user, self.token = make_customer_with_qr(phone_number=VALID_MOBILE)

    def test_valid_code_identifies_customer(self):
        self.assertEqual(services.identify_customer(self.token), self.user)
        self.assertEqual(services.identify_customer(f"CF1:{self.token}"), self.user)

    def test_unknown_malformed_and_inactive_get_the_same_generic_error(self):
        messages = set()
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        for raw in (services.generate_token(), "basura", self.token):
            with self.subTest(raw=raw), self.assertRaises(services.InvalidQRCode) as ctx:
                services.identify_customer(raw)
            messages.add(ctx.exception.messages[0])
        self.assertEqual(len(messages), 1)

    def test_code_of_user_who_is_no_longer_customer_is_invalid(self):
        CustomerQRCode.objects.filter(user=self.user).update(user=make_employee())
        with self.assertRaises(services.InvalidQRCode):
            services.identify_customer(self.token)

    def test_unverified_email_is_not_eligible(self):
        self.user.email_verified_at = None
        self.user.save(update_fields=["email_verified_at"])
        with self.assertRaises(services.CustomerNotEligible):
            services.identify_customer(self.token)

    def test_errors_do_not_expose_personal_data(self):
        self.user.email_verified_at = None
        self.user.save(update_fields=["email_verified_at"])
        for raw in (self.token, services.generate_token()):
            try:
                services.identify_customer(raw)
            except (services.InvalidQRCode, services.CustomerNotEligible) as exc:
                text = " ".join(exc.messages)
                for value in PERSONAL_VALUES:
                    self.assertNotIn(value, text)
                self.assertNotIn(raw, text)

    def test_display_name_is_minimal(self):
        self.assertEqual(services.customer_display_name(self.user), "Lúa F.")


class MyQRViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("loyalty:my_qr")

    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_unverified_customer_and_staff_are_denied(self):
        unverified = accounts.create_customer(email="pendiente@example.com", password=PASSWORD, first_name="A", last_name="B")
        employee = make_employee()
        employee.email_verified_at = unverified.date_joined
        employee.save(update_fields=["email_verified_at"])
        for user in (unverified, employee):
            self.client.force_login(user)
            with self.subTest(user=user.email):
                self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_customer_sees_qr_built_only_from_opaque_token(self):
        user = make_verified_customer()
        self.client.force_login(user)
        with mock.patch("apps.loyalty.views.qr_data_uri", wraps=__import__("apps.core.qr", fromlist=["qr_data_uri"]).qr_data_uri) as make:
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        token = CustomerQRCode.objects.get(user=user).token
        make.assert_called_once()
        self.assertEqual(make.call_args.args[0], f"CF1:{token}")
        self.assertContains(response, 'src="data:image/svg+xml')
        self.assertContains(response, services.format_code(token))
        self.assertIn("no-cache", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])

    def test_rotate_requires_post_and_csrf(self):
        user, token = make_customer_with_qr()
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("loyalty:rotate")).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(user)
        self.assertEqual(csrf_client.post(reverse("loyalty:rotate")).status_code, 403)
        self.assertEqual(CustomerQRCode.objects.get(user=user).token, token)

    def test_rotate_from_view(self):
        user, token = make_customer_with_qr()
        self.client.force_login(user)
        response = self.client.post(reverse("loyalty:rotate"), follow=True)
        self.assertContains(response, "El anterior ya no sirve")
        self.assertNotEqual(CustomerQRCode.objects.get(user=user).token, token)

    def test_profile_links_to_qr_only_when_verified(self):
        user = make_verified_customer()
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse("accounts:profile")), self.url)
