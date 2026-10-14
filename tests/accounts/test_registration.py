import datetime

from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts import services
from apps.accounts.models import CommunicationPreferenceChange, CustomerProfile, EmailVerificationToken, User
from apps.core.models import AuditEvent

from .factories import (
    PASSWORD,
    VALID_MOBILE,
    VALID_MOBILE_E164,
    make_user,
    registration_data,
    registration_post_data,
)

REQUIRED_SERVICE_FIELDS = (
    "first_name",
    "last_name",
    "address_line_1",
    "postal_code",
    "city",
    "province",
    "country",
    "date_of_birth",
)


class RegisterCustomerServiceTests(TestCase):
    def register(self, **overrides):
        with self.captureOnCommitCallbacks(execute=True):
            return services.register_customer(**registration_data(**overrides))

    def test_valid_registration_creates_pending_customer_with_profile(self):
        user = self.register(email="  Nueva@Example.COM ")
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertEqual(user.email, "nueva@example.com")
        self.assertFalse(user.is_email_verified)
        self.assertFalse(user.is_staff or user.is_superuser)
        profile = user.customer_profile
        self.assertEqual(profile.postal_code, "15001")
        self.assertEqual(profile.city, "A Coruña")
        self.assertEqual(profile.country, "ES")
        self.assertEqual(profile.phone_number, "")
        self.assertEqual(profile.missing_required_fields(), [])
        self.assertEqual(CustomerProfile.objects.count(), 1)
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.Action.CUSTOMER_CREATED).exists())

    def test_sends_verification_email_and_stores_only_token_hash(self):
        user = self.register()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["nueva@example.com"])
        token = EmailVerificationToken.objects.get(user=user)
        self.assertEqual(token.purpose, EmailVerificationToken.Purpose.VERIFY)
        self.assertNotIn(token.token_hash, mail.outbox[0].body)
        self.assertEqual(len(token.token_hash), 64)

    def test_public_registration_cannot_choose_role(self):
        with self.assertRaises(TypeError):
            services.register_customer(**registration_data(), role=User.Role.OWNER)
        with self.assertRaises(TypeError):
            services.register_customer(**registration_data(), is_staff=True)
        self.assertFalse(User.objects.exists())

    def test_cannot_self_verify_on_registration(self):
        with self.assertRaises(TypeError):
            services.register_customer(**registration_data(), email_verified_at=timezone.now())

    def test_required_fields(self):
        for field in REQUIRED_SERVICE_FIELDS:
            with self.subTest(field=field):
                value = None if field == "date_of_birth" else ""
                with self.assertRaises(ValidationError) as ctx:
                    services.register_customer(**registration_data(**{field: value}))
                self.assertIn(field, ctx.exception.message_dict)
        self.assertFalse(User.objects.exists())

    def test_incomplete_address(self):
        with self.assertRaises(ValidationError) as ctx:
            services.register_customer(
                **registration_data(address_line_1="  ", city="", postal_code="")
            )
        for field in ("address_line_1", "city", "postal_code"):
            self.assertIn(field, ctx.exception.message_dict)
        self.assertFalse(User.objects.exists())

    def test_whitespace_is_normalized(self):
        user = self.register(city="  A   Coruña ", postal_code=" 15001 ")
        self.assertEqual(user.customer_profile.city, "A Coruña")
        self.assertEqual(user.customer_profile.postal_code, "15001")

    def test_invalid_spanish_postal_code(self):
        for code in ("1500", "99001", "ABCDE"):
            with self.subTest(code=code):
                with self.assertRaises(ValidationError) as ctx:
                    services.register_customer(**registration_data(postal_code=code))
                self.assertIn("postal_code", ctx.exception.message_dict)

    def test_international_address(self):
        user = self.register(country="PT", postal_code="4000-123", city="Porto", province="Porto")
        self.assertEqual(user.customer_profile.country, "PT")
        user2 = self.register(
            email="uk@example.com", country="GB", postal_code="sw1a 1aa", province="London"
        )
        self.assertEqual(user2.customer_profile.postal_code, "SW1A 1AA")

    def test_invalid_country(self):
        with self.assertRaises(ValidationError) as ctx:
            services.register_customer(**registration_data(country="XX"))
        self.assertIn("country", ctx.exception.message_dict)

    def test_invalid_email(self):
        with self.assertRaises(ValidationError) as ctx:
            services.register_customer(**registration_data(email="no-es-un-email"))
        self.assertIn("email", ctx.exception.message_dict)

    def test_duplicate_email_case_insensitive(self):
        make_user(email="nueva@example.com")
        with self.assertRaises(services.EmailAlreadyRegistered):
            services.register_customer(**registration_data(email="NUEVA@example.com"))
        self.assertEqual(User.objects.count(), 1)

    def test_weak_password(self):
        with self.assertRaises(ValidationError):
            services.register_customer(**registration_data(password="12345678"))
        self.assertFalse(User.objects.exists())

    def test_future_birth_date(self):
        tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        with self.assertRaises(ValidationError) as ctx:
            services.register_customer(**registration_data(date_of_birth=tomorrow))
        self.assertIn("date_of_birth", ctx.exception.message_dict)

    def test_impossible_birth_date(self):
        for value in ("1990-02-30", "1990-13-01", "no-es-fecha"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError) as ctx:
                    services.register_customer(**registration_data(date_of_birth=value))
                self.assertIn("date_of_birth", ctx.exception.message_dict)

    def test_implausible_or_underage_birth_date(self):
        today = timezone.localdate()
        for value in (datetime.date(1850, 1, 1), datetime.date(today.year - 10, 1, 1)):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    services.register_customer(**registration_data(date_of_birth=value))

    def test_iso_birth_date_string_accepted(self):
        user = self.register(date_of_birth="1990-02-28")
        self.assertEqual(user.customer_profile.date_of_birth, datetime.date(1990, 2, 28))

    def test_leap_day_birth_date(self):
        user = self.register(date_of_birth=datetime.date(1996, 2, 29))
        self.assertEqual(user.customer_profile.date_of_birth, datetime.date(1996, 2, 29))

    def test_phone_is_optional_and_normalized(self):
        user = self.register(phone_number=VALID_MOBILE)
        self.assertEqual(user.customer_profile.phone_number, VALID_MOBILE_E164)

    def test_international_phone(self):
        user = self.register(phone_number="+351 912 345 678")
        self.assertEqual(user.customer_profile.phone_number, "+351912345678")

    def test_invalid_phone(self):
        for value in ("123", "abc", "+34 900 000 000", "981 000 000"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError) as ctx:
                    services.register_customer(**registration_data(phone_number=value))
                self.assertIn("phone_number", ctx.exception.message_dict)
        self.assertFalse(User.objects.exists())

    def test_promotions_disabled_by_default_and_recorded(self):
        user = self.register()
        profile = user.customer_profile
        self.assertFalse(profile.promo_email_opt_in)
        self.assertFalse(profile.promo_sms_opt_in)
        changes = CommunicationPreferenceChange.objects.filter(user=user)
        self.assertEqual(changes.count(), 2)
        self.assertFalse(changes.filter(opted_in=True).exists())
        self.assertTrue(all(c.source == "REGISTRATION" for c in changes))

    def test_opt_in_at_registration(self):
        user = self.register(phone_number=VALID_MOBILE, promo_email_opt_in=True, promo_sms_opt_in=True)
        self.assertTrue(user.customer_profile.promo_email_opt_in)
        self.assertTrue(user.customer_profile.promo_sms_opt_in)

    def test_sms_opt_in_requires_phone(self):
        with self.assertRaises(ValidationError) as ctx:
            services.register_customer(**registration_data(promo_sms_opt_in=True))
        self.assertIn("promo_sms_opt_in", ctx.exception.message_dict)

    def test_providing_email_or_phone_does_not_enable_promotions(self):
        user = self.register(phone_number=VALID_MOBILE)
        self.assertFalse(services.can_receive_promotional_email(user))
        self.assertFalse(services.can_receive_promotional_sms(user))


class RegisterViewTests(TestCase):
    url = reverse("accounts:register")

    def setUp(self):
        cache.clear()

    def post(self, **overrides):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url, registration_post_data(**overrides))

    def test_form_shows_sections_and_marks(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        for title in (
            "A. Datos personales",
            "B. Dirección postal",
            "C. Acceso a la cuenta",
            "D. Preferencias de comunicación",
        ):
            self.assertContains(response, title)
        self.assertContains(response, "(opcional)")
        self.assertContains(response, "(obligatorio)")
        self.assertNotContains(response, 'name="role"')

    def test_valid_registration(self):
        response = self.post()
        self.assertRedirects(response, reverse("accounts:register_done"))
        user = User.objects.get(email="nueva@example.com")
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertEqual(len(mail.outbox), 1)

    def test_role_and_flags_in_post_are_ignored(self):
        self.post(role="OWNER", is_staff="on", is_superuser="on", email_verified_at="2026-01-01")
        user = User.objects.get(email="nueva@example.com")
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertFalse(user.is_email_verified)

    def test_missing_required_fields(self):
        for field in ("first_name", "last_name", "address_line_1", "postal_code", "city",
                      "province", "country", "email", "password1", "password2", "date_of_birth"):
            with self.subTest(field=field):
                response = self.post(**{field: ""})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors.get(field))
        self.assertFalse(User.objects.exists())

    def test_password_mismatch(self):
        response = self.post(password2="Otra-Contrasena-2026")
        self.assertIn("password2", response.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_weak_password_shown_on_password_field(self):
        response = self.post(password1="12345678", password2="12345678")
        self.assertIn("password1", response.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_invalid_email(self):
        response = self.post(email="no-es-email")
        self.assertIn("email", response.context["form"].errors)

    def test_impossible_and_future_dates(self):
        future = (timezone.localdate() + datetime.timedelta(days=3)).isoformat()
        for value in ("1990-02-30", future):
            with self.subTest(value=value):
                response = self.post(date_of_birth=value)
                self.assertIn("date_of_birth", response.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_invalid_phone(self):
        response = self.post(phone_number="12345")
        self.assertIn("phone_number", response.context["form"].errors)

    def test_duplicate_email_does_not_reveal_existence(self):
        make_user(email="nueva@example.com")
        response = self.post(email="Nueva@example.com")
        self.assertRedirects(response, reverse("accounts:register_done"))
        self.assertEqual(User.objects.count(), 1)
        # El titular recibe un aviso, no un enlace de verificación.
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("ya tienes una", mail.outbox[0].body)
        self.assertNotIn("verificar-email", mail.outbox[0].body)

    def test_authenticated_user_is_redirected(self):
        self.client.force_login(make_user())
        self.assertRedirects(
            self.client.get(self.url), reverse("accounts:home"), fetch_redirect_response=False
        )

    def test_csrf_required(self):
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        response = client.post(self.url, registration_post_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.exists())

    def test_password_not_echoed_back(self):
        response = self.post(password2="Otra-Contrasena-2026")
        self.assertNotContains(response, PASSWORD)
