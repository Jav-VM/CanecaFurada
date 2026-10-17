import datetime

from django.core import mail
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
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
    adult_birth_date,
    make_user,
    registration_data,
    token_from_email,
)


def register(test, **overrides):
    with test.captureOnCommitCallbacks(execute=True):
        user = services.register_customer(**registration_data(**overrides))
    return user


def profile_kwargs(**overrides):
    data = registration_data()
    kwargs = {name: data[name] for name in ("first_name", "last_name", *services.PROFILE_FIELDS)}
    kwargs.update(overrides)
    return kwargs


class UpdateProfileServiceTests(TestCase):
    def setUp(self):
        self.user = register(self)

    def test_updates_allowed_fields_and_audits_field_names_only(self):
        services.update_customer_profile(
            user=self.user, **profile_kwargs(city="Ferrol", postal_code="15401", phone_number=VALID_MOBILE)
        )
        profile = CustomerProfile.objects.get(user=self.user)
        self.assertEqual(profile.city, "Ferrol")
        self.assertEqual(profile.phone_number, VALID_MOBILE_E164)
        event = AuditEvent.objects.get(action=AuditEvent.Action.PROFILE_UPDATED)
        self.assertEqual(event.metadata, {"fields": ["city", "phone_number", "postal_code"]})
        self.assertNotIn("Ferrol", str(event.metadata))

    def test_rejects_non_whitelisted_fields(self):
        for field in ("role", "email", "is_staff", "promo_email_opt_in", "user"):
            with self.subTest(field=field):
                with self.assertRaises((ValidationError, TypeError)):
                    services.update_customer_profile(user=self.user, **profile_kwargs(**{field: "x"}))
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.CUSTOMER)

    def test_required_fields_cannot_be_emptied(self):
        with self.assertRaises(ValidationError) as ctx:
            services.update_customer_profile(user=self.user, **profile_kwargs(city="", last_name=""))
        self.assertIn("city", ctx.exception.message_dict)
        self.assertIn("last_name", ctx.exception.message_dict)

    def test_phone_can_be_changed_and_removed(self):
        services.update_customer_profile(user=self.user, **profile_kwargs(phone_number="+351912345678"))
        services.update_customer_profile(user=self.user, **profile_kwargs(phone_number=""))
        self.assertEqual(CustomerProfile.objects.get(user=self.user).phone_number, "")

    def test_removing_phone_withdraws_sms_consent(self):
        services.update_customer_profile(user=self.user, **profile_kwargs(phone_number=VALID_MOBILE))
        services.set_communication_preferences(user=self.user, promo_email_opt_in=False, promo_sms_opt_in=True)
        services.update_customer_profile(user=self.user, **profile_kwargs(phone_number=""))
        self.assertFalse(CustomerProfile.objects.get(user=self.user).promo_sms_opt_in)
        last = CommunicationPreferenceChange.objects.filter(user=self.user).first()
        self.assertEqual((last.channel, last.opted_in, last.source), ("SMS", False, "SYSTEM"))

    def test_date_of_birth_change_cooldown(self):
        services.update_customer_profile(user=self.user, **profile_kwargs(date_of_birth=adult_birth_date(31)))
        with self.assertRaises(ValidationError) as ctx:
            services.update_customer_profile(
                user=self.user, **profile_kwargs(date_of_birth=adult_birth_date(32))
            )
        self.assertIn("date_of_birth", ctx.exception.message_dict)
        CustomerProfile.objects.filter(user=self.user).update(
            date_of_birth_changed_at=timezone.now() - datetime.timedelta(days=366)
        )
        services.update_customer_profile(user=self.user, **profile_kwargs(date_of_birth=adult_birth_date(32)))
        self.assertEqual(CustomerProfile.objects.get(user=self.user).date_of_birth, adult_birth_date(32))

    def test_date_of_birth_validation_on_update(self):
        future = timezone.localdate() + datetime.timedelta(days=1)
        with self.assertRaises(ValidationError):
            services.update_customer_profile(user=self.user, **profile_kwargs(date_of_birth=future))

    def test_staff_cannot_use_customer_profile_service(self):
        employee = make_user(email="e@example.com", role=User.Role.EMPLOYEE)
        with self.assertRaises(PermissionDenied):
            services.update_customer_profile(user=employee, **profile_kwargs())

    def test_street_is_optional_and_province_follows_postal_code(self):
        services.update_customer_profile(
            user=self.user,
            **profile_kwargs(address_line_1="", postal_code="27001", city="lugo", province="A Coruña", sex="MALE"),
        )
        profile = CustomerProfile.objects.get(user=self.user)
        self.assertEqual(
            (profile.address_line_1, profile.city, profile.province, profile.sex), ("", "Lugo", "Lugo", "MALE")
        )
        self.assertEqual(profile.missing_required_fields(), [])

    def test_sex_can_be_emptied(self):
        # Fase 25: el sexo es opcional; dejarlo vacío es válido.
        services.update_customer_profile(user=self.user, **profile_kwargs(sex=""))
        self.assertEqual(CustomerProfile.objects.get(user=self.user).sex, "")

    def test_legacy_customer_without_data_can_complete_profile(self):
        legacy = make_user(email="legacy@example.com")
        services.ensure_customer_profile(legacy)
        services.update_customer_profile(user=legacy, **profile_kwargs())
        self.assertEqual(CustomerProfile.objects.get(user=legacy).missing_required_fields(), [])


class PreferencesServiceTests(TestCase):
    def setUp(self):
        self.user = register(self, phone_number=VALID_MOBILE)

    def test_changes_are_recorded(self):
        services.set_communication_preferences(user=self.user, promo_email_opt_in=True, promo_sms_opt_in=False)
        services.set_communication_preferences(user=self.user, promo_email_opt_in=True, promo_sms_opt_in=True)
        services.set_communication_preferences(user=self.user, promo_email_opt_in=False, promo_sms_opt_in=True)
        history = list(
            CommunicationPreferenceChange.objects.filter(user=self.user, source="PROFILE")
            .order_by("created_at", "id")
            .values_list("channel", "opted_in")
        )
        self.assertEqual(history, [("EMAIL", True), ("SMS", True), ("EMAIL", False)])

    def test_unchanged_values_are_not_recorded(self):
        before = CommunicationPreferenceChange.objects.count()
        services.set_communication_preferences(user=self.user, promo_email_opt_in=False, promo_sms_opt_in=False)
        self.assertEqual(CommunicationPreferenceChange.objects.count(), before)

    def test_sms_requires_phone(self):
        other = register(self, email="sinmovil@example.com")
        with self.assertRaises(ValidationError):
            services.set_communication_preferences(user=other, promo_email_opt_in=False, promo_sms_opt_in=True)

    def test_db_constraint_sms_requires_phone(self):
        other = register(self, email="sinmovil@example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            CustomerProfile.objects.filter(user=other).update(promo_sms_opt_in=True)

    def test_verification_is_not_consent(self):
        token = token_from_email(mail.outbox[-1])
        services.confirm_email_token(token)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)
        self.assertFalse(services.can_receive_promotional_email(self.user))

    def test_promotional_email_requires_verified_email_and_consent(self):
        services.set_communication_preferences(user=self.user, promo_email_opt_in=True, promo_sms_opt_in=False)
        self.user.refresh_from_db()
        self.assertFalse(services.can_receive_promotional_email(self.user))  # sin verificar
        services.confirm_email_token(token_from_email(mail.outbox[-1]))
        self.user.refresh_from_db()
        self.assertTrue(services.can_receive_promotional_email(self.user))
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.user.refresh_from_db()
        self.assertFalse(services.can_receive_promotional_email(self.user))

    def test_promotional_sms_requires_consent(self):
        self.assertFalse(services.can_receive_promotional_sms(self.user))
        services.set_communication_preferences(user=self.user, promo_email_opt_in=False, promo_sms_opt_in=True)
        self.user.refresh_from_db()
        self.assertTrue(services.can_receive_promotional_sms(self.user))

    def test_staff_never_receive_promotions(self):
        owner = make_user(email="o@example.com", role=User.Role.OWNER, email_verified_at=timezone.now())
        self.assertFalse(services.can_receive_promotional_email(owner))


class EmailChangeServiceTests(TestCase):
    def setUp(self):
        self.user = register(self)
        services.confirm_email_token(token_from_email(mail.outbox[-1]))
        self.user.refresh_from_db()
        mail.outbox.clear()

    def request_change(self, new_email="cambio@example.com", password=PASSWORD):
        with self.captureOnCommitCallbacks(execute=True):
            services.request_email_change(user=self.user, new_email=new_email, password=password)

    def test_full_change_flow(self):
        self.request_change("Cambio@Example.com")
        self.assertEqual(mail.outbox[-1].to, ["cambio@example.com"])
        self.user.refresh_from_db()
        # Hasta confirmar, el email y su verificación no cambian.
        self.assertEqual(self.user.email, "nueva@example.com")
        self.assertTrue(self.user.is_email_verified)
        token = token_from_email(mail.outbox[-1])
        with self.captureOnCommitCallbacks(execute=True):
            services.confirm_email_token(token)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "cambio@example.com")
        self.assertTrue(self.user.is_email_verified)
        self.assertEqual(mail.outbox[-1].to, ["nueva@example.com"])  # aviso a la dirección anterior
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.Action.EMAIL_CHANGED).exists())
        with self.assertRaises(ValidationError):
            services.confirm_email_token(token)

    def test_wrong_password(self):
        with self.assertRaises(ValidationError) as ctx:
            self.request_change(password="incorrecta")
        self.assertIn("password", ctx.exception.message_dict)
        self.assertEqual(mail.outbox, [])

    def test_invalid_or_same_email(self):
        for value in ("no-es-email", "NUEVA@example.com"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError) as ctx:
                    self.request_change(value)
                self.assertIn("new_email", ctx.exception.message_dict)

    def test_taken_email_sends_nothing_and_reveals_nothing(self):
        make_user(email="ocupado@example.com")
        self.request_change("ocupado@example.com")  # no lanza excepción
        self.assertEqual(mail.outbox, [])
        self.assertFalse(EmailVerificationToken.objects.filter(purpose="CHANGE").exists())

    def test_email_taken_before_confirmation(self):
        self.request_change()
        token = token_from_email(mail.outbox[-1])
        make_user(email="cambio@example.com")
        with self.assertRaises(ValidationError) as ctx:
            services.confirm_email_token(token)
        self.assertEqual(ctx.exception.code, "email_taken")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "nueva@example.com")

    def test_email_changed_without_confirmation_loses_verification(self):
        """Cualquier cambio de email fuera del flujo de confirmación (p. ej. el admin) anula la verificación."""
        self.user.email = "admin-cambio@example.com"
        self.user.save()
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_email_verified)

    def test_change_email_with_update_fields_also_resets(self):
        self.user.email = "otro@example.com"
        self.user.save(update_fields=["email"])
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_email_verified)

    def test_partial_save_without_email_keeps_verification(self):
        self.user.email = "solo-en-memoria@example.com"
        self.user.save(update_fields=["first_name"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "nueva@example.com")
        self.assertTrue(self.user.is_email_verified)

    def test_saving_other_fields_keeps_verification(self):
        self.user.first_name = "Outro"
        self.user.save()
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)


class ProfileViewTests(TestCase):
    url = reverse("accounts:profile")

    def setUp(self):
        cache.clear()
        self.user = register(self)
        self.other = register(self, email="otra@example.com", city="Lugo", postal_code="27001", province="Lugo")
        self.client.force_login(self.user)

    def post_data(self, **overrides):
        data = profile_kwargs()
        data["date_of_birth"] = data["date_of_birth"].isoformat()
        data.update(overrides)
        return data

    def test_anonymous_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_shows_only_own_data(self):
        response = self.client.get(self.url)
        self.assertContains(response, "nueva@example.com")
        self.assertNotContains(response, "otra@example.com")
        self.assertNotContains(response, "Lugo")

    def test_update_profile(self):
        response = self.client.post(self.url, self.post_data(city="Santiago de Compostela", postal_code="15701"))
        self.assertRedirects(response, self.url)
        self.assertEqual(CustomerProfile.objects.get(user=self.user).city, "Santiago de Compostela")

    def test_cannot_modify_other_profile_by_sending_identifiers(self):
        self.client.post(
            self.url,
            self.post_data(city="Vigo", postal_code="36201", user=self.other.pk,
                           public_id=str(self.other.public_id), email="otra@example.com"),
        )
        self.assertEqual(CustomerProfile.objects.get(user=self.other).city, "Lugo")
        self.assertEqual(CustomerProfile.objects.get(user=self.user).city, "Vigo")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "nueva@example.com")

    def test_cannot_escalate_role_from_profile(self):
        self.client.post(self.url, self.post_data(role="OWNER", is_staff="on", is_superuser="on"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.CUSTOMER)
        self.assertFalse(self.user.is_staff or self.user.is_superuser)

    def test_invalid_data_shows_errors(self):
        response = self.client.post(self.url, self.post_data(phone_number="123", city=""))
        self.assertEqual(response.status_code, 200)
        errors = response.context["form"].errors
        self.assertIn("phone_number", errors)
        self.assertIn("city", errors)

    def test_staff_cannot_access_customer_profile(self):
        for role in (User.Role.EMPLOYEE, User.Role.OWNER):
            with self.subTest(role=role):
                self.client.force_login(make_user(email=f"{role.lower()}@example.com", role=role))
                self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_inactive_customer_denied(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)  # la sesión deja de ser válida

    def test_full_birth_date_not_shown_outside_profile(self):
        response = self.client.get(reverse("accounts:home"), follow=True)
        self.assertEqual(response.request["PATH_INFO"], self.url)
        employee = make_user(email="e@example.com", role=User.Role.EMPLOYEE)
        self.client.force_login(employee)
        response = self.client.get(reverse("accounts:home"), follow=True)
        dob = registration_data()["date_of_birth"]
        self.assertNotContains(response, dob.isoformat())

    def test_preferences_view(self):
        response = self.client.post(reverse("accounts:preferences"), {"promo_email_opt_in": "on"})
        self.assertRedirects(response, self.url + "#preferencias")
        profile = CustomerProfile.objects.get(user=self.user)
        self.assertTrue(profile.promo_email_opt_in)
        self.assertFalse(profile.promo_sms_opt_in)
        self.assertTrue(
            CommunicationPreferenceChange.objects.filter(user=self.user, source="PROFILE", opted_in=True).exists()
        )

    def test_preferences_sms_without_phone_shows_error(self):
        response = self.client.post(reverse("accounts:preferences"), {"promo_sms_opt_in": "on"}, follow=True)
        self.assertContains(response, "indica antes un teléfono móvil")
        self.assertFalse(CustomerProfile.objects.get(user=self.user).promo_sms_opt_in)

    def test_preferences_requires_post(self):
        self.assertEqual(self.client.get(reverse("accounts:preferences")).status_code, 405)

    def test_email_change_view(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("accounts:email_change"), {"new_email": "cambio@example.com", "password": PASSWORD}
            )
        self.assertRedirects(response, reverse("accounts:home"), fetch_redirect_response=False)
        self.assertEqual(mail.outbox[-1].to, ["cambio@example.com"])

    def test_email_change_view_wrong_password(self):
        response = self.client.post(
            reverse("accounts:email_change"), {"new_email": "cambio@example.com", "password": "mala"}
        )
        self.assertIn("password", response.context["form"].errors)
