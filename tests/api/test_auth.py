"""API v1: registro, verificación, login, tokens, cierre de sesión y contraseña."""
import datetime
import re

from django.core import mail
from django.test import override_settings
from django.urls import reverse

from apps.accounts.models import EmailVerificationToken, User
from apps.core.models import AuditEvent
from tests.accounts.factories import PASSWORD, adult_birth_date, make_user, registration_data, token_from_email

from .base import ApiTestCase, api_url, jwt_payload

NEW_PASSWORD = "Otra-Contrasena-Ficticia-9"


def register_payload(**overrides):
    data = registration_data(**overrides)
    if isinstance(data["date_of_birth"], datetime.date):
        data["date_of_birth"] = data["date_of_birth"].isoformat()
    return data


class RegisterTests(ApiTestCase):
    def test_register_creates_unverified_customer_and_sends_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.post("register", register_payload())
        self.assertEqual(response.status_code, 202)
        self.assertNotIn("access", response.json())
        user = User.objects.get(email="nueva@example.com")
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertFalse(user.is_email_verified)
        self.assertEqual(user.customer_profile.city, "A Coruña")
        self.assertEqual(len(mail.outbox), 1)

    def test_privileged_fields_in_payload_are_ignored(self):
        payload = register_payload(
            role="OWNER", is_staff=True, is_superuser=True, email_verified_at="2026-01-01T00:00:00Z", balance=999
        )
        self.assertEqual(self.post("register", payload).status_code, 202)
        user = User.objects.get(email="nueva@example.com")
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertFalse(user.is_staff or user.is_superuser or user.is_email_verified)

    def test_missing_required_fields(self):
        response = self.post("register", {"email": "nueva@example.com", "password": PASSWORD})
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["code"], "invalid")
        for field in ("first_name", "last_name", "date_of_birth", "sex", "postal_code"):
            self.assertIn(field, body["fields"])
        # Fase 16: calle, localidad y provincia no son obligatorias en la entrada.
        for field in ("address_line_1", "city", "province"):
            self.assertNotIn(field, body["fields"])
        self.assertFalse(User.objects.exists())

    def test_register_with_postal_code_only(self):
        payload = register_payload(postal_code="15142", city="Arteixo")
        for name in ("address_line_1", "address_line_2", "province"):
            payload.pop(name)
        self.assertEqual(self.post("register", payload).status_code, 202)
        profile = User.objects.get(email="nueva@example.com").customer_profile
        self.assertEqual((profile.city, profile.province, profile.sex), ("Arteixo", "A Coruña", "UNDISCLOSED"))

    def test_localities_endpoint(self):
        response = self.client.get(api_url("localities", "15179"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"localities": ["Oleiros"]})
        self.assertEqual(self.client.get(api_url("localities", "04070")).json(), {"localities": []})
        invalid = self.client.get(api_url("localities", "99999"))
        self.assertEqual(invalid.status_code, 400)
        self.assertNotIn("99999", invalid.content.decode())

    def test_invalid_data_is_rejected_by_the_services(self):
        future = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        response = self.post("register", register_payload(date_of_birth=future, postal_code="ABC"))
        self.assertEqual(response.status_code, 400)
        self.assertTrue({"date_of_birth", "postal_code"} <= set(response.json()["fields"]))
        phone = self.post("register", register_payload(phone_number="123"))
        self.assertIn("phone_number", phone.json()["fields"])
        self.assertFalse(User.objects.exists())

    def test_minor_cannot_register(self):
        payload = register_payload(date_of_birth=adult_birth_date(years=15).isoformat())
        response = self.post("register", payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("date_of_birth", response.json()["fields"])

    def test_existing_email_gets_the_same_response(self):
        make_user("nueva@example.com")
        with self.captureOnCommitCallbacks(execute=True):
            response = self.post("register", register_payload(email="NUEVA@example.com"))
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), self.post("register", register_payload(email="otra@example.com")).json())
        self.assertEqual(User.objects.filter(email="nueva@example.com").count(), 1)
        # El titular recibe un aviso con el enlace de recuperación.
        self.assertIn("contrasena/recuperar", mail.outbox[0].body)

    def test_weak_password_error_does_not_reveal_existing_email(self):
        make_user("nueva@example.com")
        existing = self.post("register", register_payload(password="12345678"))
        new = self.post("register", register_payload(email="otra@example.com", password="12345678"))
        self.assertEqual(existing.status_code, 400)
        self.assertEqual(existing.json(), new.json())


class LoginTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()

    def login(self, email=None, password=PASSWORD):
        return self.post("login", {"email": email or self.user.email, "password": password})

    def test_login_returns_tokens_and_minimal_user(self):
        response = self.login(email="CLIENTE@example.com")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["token_type"], "Bearer")
        self.assertEqual(body["access_expires_in"], 15 * 60)
        self.assertEqual(
            set(body["user"]),
            {"public_id", "email", "first_name", "last_name", "role", "email_verified", "profile_complete"},
        )

    def test_token_identifies_user_by_public_id_without_personal_data(self):
        payload = jwt_payload(self.login().json()["access"])
        self.assertEqual(payload["sub"], str(self.user.public_id))
        self.assertNotIn("user_id", payload)
        for value in map(str, payload.values()):
            self.assertNotIn("example.com", value)
        self.assertNotIn(str(self.user.pk), {str(v) for v in payload.values()})

    def test_same_error_for_wrong_password_and_unknown_email(self):
        wrong = self.login(password="mala")
        unknown = self.login(email="nadie@example.com", password="mala")
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(wrong.json(), unknown.json())
        self.assertEqual(wrong.json()["code"], "invalid_credentials")

    @override_settings(LOGIN_MAX_FAILURES_PER_EMAIL=3)
    def test_login_throttled_and_shared_with_web(self):
        self.client.post(reverse("accounts:login"), {"username": self.user.email, "password": "mala"})
        self.login(password="mala")
        self.login(password="mala")
        response = self.login()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["code"], "login_throttled")

    def test_inactive_user_cannot_login(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.login().status_code, 401)

    def test_access_token_authenticates_and_session_does_not(self):
        self.assertEqual(self.client.get(api_url("me")).status_code, 401)
        self.client.force_login(self.user)  # cookie de sesión de la web
        self.assertEqual(self.client.get(api_url("me")).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer no-es-un-token")
        self.assertEqual(self.client.get(api_url("me")).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.login().json()['access']}")
        self.assertEqual(self.client.get(api_url("me")).status_code, 200)

    def test_refresh_token_is_not_an_access_token(self):
        refresh = self.login().json()["refresh"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh}")
        self.assertEqual(self.client.get(api_url("me")).status_code, 401)


class TokenLifecycleTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.pair = self.authenticate(self.user)

    def refresh(self, token):
        return self.post("token_refresh", {"refresh": token})

    def test_refresh_rotates_and_old_refresh_is_revoked(self):
        response = self.refresh(self.pair["refresh"])
        self.assertEqual(response.status_code, 200)
        new_pair = response.json()
        self.assertNotEqual(new_pair["refresh"], self.pair["refresh"])
        reused = self.refresh(self.pair["refresh"])
        self.assertEqual(reused.status_code, 401)
        self.assertEqual(reused.json()["code"], "token_not_valid")
        self.assertEqual(self.refresh(new_pair["refresh"]).status_code, 200)

    def test_invalid_refresh(self):
        self.assertEqual(self.refresh("basura").status_code, 401)
        self.assertEqual(self.refresh(self.pair["access"]).status_code, 401)

    def test_logout_revokes_this_refresh_only(self):
        other_device = self.authenticate(self.user, client=self.client_class())
        self.authenticate(self.user)
        response = self.post("logout", {"refresh": self.pair["refresh"]})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.refresh(self.pair["refresh"]).status_code, 401)
        self.assertEqual(self.refresh(other_device["refresh"]).status_code, 200)

    def test_logout_cannot_revoke_another_users_token(self):
        victim = make_user("otra@example.com")
        victim_pair = self.authenticate(victim, client=self.client_class())
        self.assertEqual(self.post("logout", {"refresh": victim_pair["refresh"]}).status_code, 204)
        self.assertEqual(self.refresh(victim_pair["refresh"]).status_code, 200)

    def test_logout_all_revokes_every_refresh_and_is_audited(self):
        other = self.authenticate(self.user, client=self.client_class())
        self.assertEqual(self.post("logout_all").status_code, 204)
        self.assertEqual(self.refresh(other["refresh"]).status_code, 401)
        self.assertEqual(self.refresh(self.pair["refresh"]).status_code, 401)
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.Action.API_SESSIONS_REVOKED).exists())

    def test_password_change_via_api_revokes_old_tokens(self):
        wrong = self.post("password_change", {"current_password": "mala", "new_password": NEW_PASSWORD})
        self.assertEqual(wrong.status_code, 400)
        self.assertIn("current_password", wrong.json()["fields"])
        weak = self.post("password_change", {"current_password": PASSWORD, "new_password": "123"})
        self.assertIn("new_password", weak.json()["fields"])

        response = self.post("password_change", {"current_password": PASSWORD, "new_password": NEW_PASSWORD})
        self.assertEqual(response.status_code, 200)
        new_pair = response.json()
        self.assertEqual(self.client.get(api_url("me")).status_code, 401)  # access anterior
        self.assertEqual(self.refresh(self.pair["refresh"]).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_pair['access']}")
        self.assertEqual(self.client.get(api_url("me")).status_code, 200)
        event = AuditEvent.objects.get(action=AuditEvent.Action.PASSWORD_CHANGED)
        self.assertEqual(event.metadata, {"via": "change", "channel": "api"})

    def test_password_change_outside_the_api_revokes_tokens_at_once(self):
        self.user.set_password(NEW_PASSWORD)
        self.user.save()
        response = self.client.get(api_url("me"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "token_revoked")
        self.assertEqual(self.refresh(self.pair["refresh"]).status_code, 401)

    def test_deactivated_account_is_rejected(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.client.get(api_url("me")).status_code, 401)
        self.assertEqual(self.refresh(self.pair["refresh"]).status_code, 401)


@override_settings(SITE_BASE_URL="https://www.example.com")
class PasswordResetTests(ApiTestCase):
    def test_same_response_and_reset_with_link(self):
        user = make_user()
        known = self.post("password_reset", {"email": user.email})
        unknown = self.post("password_reset", {"email": "nadie@example.com"})
        self.assertEqual(known.status_code, 202)
        self.assertEqual(known.json(), unknown.json())
        self.assertEqual(len(mail.outbox), 1)
        match = re.search(r"https://www\.example\.com/cuenta/contrasena/restablecer/([^/]+)/([^/]+)/", mail.outbox[0].body)
        self.assertIsNotNone(match)
        uid, token = match.groups()
        old_pair = self.authenticate(user)

        data = {"uid": uid, "token": token, "new_password": NEW_PASSWORD}
        self.anonymous()
        self.assertEqual(self.post("password_reset_confirm", data).status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password(NEW_PASSWORD))
        reused = self.post("password_reset_confirm", {**data, "new_password": "Tercera-Contrasena-Ficticia-3"})
        self.assertEqual(reused.status_code, 400)
        self.assertEqual(reused.json()["code"], "invalid_token")
        self.assertEqual(self.post("token_refresh", {"refresh": old_pair["refresh"]}).status_code, 401)
        self.assertEqual(
            AuditEvent.objects.get(action=AuditEvent.Action.PASSWORD_CHANGED).metadata, {"via": "reset", "channel": "api"}
        )

    def test_invalid_uid_or_token(self):
        response = self.post("password_reset_confirm", {"uid": "xx", "token": "yy", "new_password": NEW_PASSWORD})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_token")


class EmailVerificationTests(ApiTestCase):
    def register(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.post("register", register_payload())
        return token_from_email(mail.outbox[-1])

    def test_verify_email_with_token_once(self):
        token = self.register()
        response = self.post("verify_email", {"token": token})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.get(email="nueva@example.com").is_email_verified)
        reused = self.post("verify_email", {"token": token})
        self.assertEqual(reused.status_code, 400)
        self.assertEqual(reused.json()["code"], "used")
        self.assertEqual(self.post("verify_email", {"token": "inventado"}).json()["code"], "invalid")

    def test_public_resend_gives_the_same_answer(self):
        self.register()
        EmailVerificationToken.objects.update(created_at=datetime.datetime(2000, 1, 1, tzinfo=datetime.UTC))
        known = self.post("resend_verification", {"email": "nueva@example.com"})
        unknown = self.post("resend_verification", {"email": "nadie@example.com"})
        self.assertEqual(known.status_code, 202)
        self.assertEqual(known.json(), unknown.json())

    def test_email_change_requires_password_and_new_verification(self):
        user = make_user()
        self.authenticate(user)
        self.assertEqual(
            self.post("email_change", {"new_email": "nuevo@example.com", "password": "mala"}).status_code, 400
        )
        with self.captureOnCommitCallbacks(execute=True):
            response = self.post("email_change", {"new_email": "nuevo@example.com", "password": PASSWORD})
        self.assertEqual(response.status_code, 202)
        user.refresh_from_db()
        self.assertEqual(user.email, "cliente@example.com")  # no cambia hasta confirmar
        token = token_from_email(mail.outbox[-1])
        self.assertEqual(self.post("verify_email", {"token": token}).status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.email, "nuevo@example.com")
        self.assertTrue(user.is_email_verified)

    def test_email_change_to_taken_address_does_not_reveal_it(self):
        make_user("ocupado@example.com")
        self.authenticate(make_user())
        taken = self.post("email_change", {"new_email": "ocupado@example.com", "password": PASSWORD})
        self.assertEqual(taken.status_code, 202)
        self.assertEqual(len(mail.outbox), 0)
