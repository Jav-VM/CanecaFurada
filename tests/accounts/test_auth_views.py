import re

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User

from .factories import PASSWORD, make_user


class LoginLogoutTests(TestCase):
    url = reverse("accounts:login")

    def setUp(self):
        cache.clear()
        self.user = make_user()

    def test_login_is_case_insensitive_and_redirects_by_role(self):
        response = self.client.post(self.url, {"username": "CLIENTE@example.com", "password": PASSWORD})
        self.assertRedirects(response, reverse("accounts:home"), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse("accounts:home")), reverse("accounts:profile"))

    def test_owner_and_employee_home(self):
        owner = make_user(email="o@example.com", role=User.Role.OWNER)
        self.client.force_login(owner)
        # Desde la Fase 9 el propietario va a su dashboard.
        self.assertRedirects(self.client.get(reverse("accounts:home")), reverse("dashboard:home"))
        employee = make_user(email="e@example.com", role=User.Role.EMPLOYEE)
        self.client.force_login(employee)
        self.assertRedirects(self.client.get(reverse("accounts:home")), reverse("staff:home"))

    def test_generic_error_message(self):
        unknown = self.client.post(self.url, {"username": "nadie@example.com", "password": "x"})
        wrong = self.client.post(self.url, {"username": self.user.email, "password": "x"})
        self.assertEqual(unknown.context["form"].non_field_errors(), wrong.context["form"].non_field_errors())

    def test_inactive_user_cannot_login(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        response = self.client.post(self.url, {"username": self.user.email, "password": PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(LOGIN_MAX_FAILURES_PER_EMAIL=3)
    def test_login_throttled_after_failures(self):
        for _ in range(3):
            self.client.post(self.url, {"username": self.user.email, "password": "mala"})
        # Ni siquiera la contraseña correcta funciona mientras dura el bloqueo.
        response = self.client.post(self.url, {"username": self.user.email, "password": PASSWORD})
        self.assertContains(response, "Demasiados intentos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_open_redirect_is_blocked(self):
        response = self.client.post(
            self.url, {"username": self.user.email, "password": PASSWORD, "next": "https://malicioso.example.net/"}
        )
        self.assertRedirects(response, reverse("accounts:home"), fetch_redirect_response=False)

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.client.post(reverse("accounts:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)


class AdminLoginThrottleTests(TestCase):
    """El login del admin técnico tiene el mismo límite que el web (auditoría previa a la Fase 12)."""

    url = reverse("admin:login")

    def setUp(self):
        cache.clear()
        self.owner = make_user(email="propietario@example.com", role=User.Role.OWNER)

    def test_owner_can_log_in(self):
        response = self.client.post(self.url, {"username": self.owner.email, "password": PASSWORD})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session["_auth_user_id"], str(self.owner.pk))

    @override_settings(LOGIN_MAX_FAILURES_PER_EMAIL=3)
    def test_admin_login_throttled_after_failures(self):
        for _ in range(3):
            self.client.post(self.url, {"username": self.owner.email, "password": "mala"})
        # Ni siquiera la contraseña correcta funciona mientras dura el bloqueo.
        response = self.client.post(self.url, {"username": self.owner.email, "password": PASSWORD})
        self.assertContains(response, "Demasiados intentos")
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(LOGIN_MAX_FAILURES_PER_IP=3, LOGIN_MAX_FAILURES_PER_EMAIL=100)
    def test_admin_login_throttled_by_ip_with_different_emails(self):
        for i in range(3):
            self.client.post(self.url, {"username": f"nadie{i}@example.com", "password": "mala"})
        response = self.client.post(self.url, {"username": self.owner.email, "password": PASSWORD})
        self.assertContains(response, "Demasiados intentos")
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(LOGIN_MAX_FAILURES_PER_EMAIL=3)
    def test_admin_and_web_share_the_counter(self):
        web = reverse("accounts:login")
        for _ in range(2):
            self.client.post(web, {"username": self.owner.email, "password": "mala"})
        self.client.post(self.url, {"username": self.owner.email, "password": "mala"})
        self.assertContains(
            self.client.post(self.url, {"username": self.owner.email, "password": PASSWORD}), "Demasiados intentos"
        )
        self.assertContains(
            self.client.post(web, {"username": self.owner.email, "password": PASSWORD}), "Demasiados intentos"
        )

    @override_settings(LOGIN_MAX_FAILURES_PER_EMAIL=3)
    def test_non_staff_with_valid_password_counts_as_failure(self):
        """Un cliente con su contraseña correcta no entra al admin y el intento cuenta."""
        customer = make_user(email="cliente2@example.com")
        for _ in range(3):
            response = self.client.post(self.url, {"username": customer.email, "password": PASSWORD})
            self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "Demasiados intentos", count=0)
        response = self.client.post(self.url, {"username": customer.email, "password": PASSWORD})
        self.assertContains(response, "Demasiados intentos")


@override_settings(SITE_BASE_URL="https://www.example.com")
class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user()

    def test_same_response_for_unknown_email(self):
        url = reverse("accounts:password_reset")
        known = self.client.post(url, {"email": self.user.email})
        unknown = self.client.post(url, {"email": "nadie@example.com"})
        self.assertEqual(known["Location"], unknown["Location"])
        self.assertEqual(len(mail.outbox), 1)

    def test_reset_link_uses_site_base_url_and_works_once(self):
        self.client.post(
            reverse("accounts:password_reset"), {"email": self.user.email}, HTTP_HOST="localhost"
        )
        body = mail.outbox[0].body
        match = re.search(r"https://www\.example\.com(/cuenta/contrasena/restablecer/\S+/)", body)
        self.assertIsNotNone(match, body)
        response = self.client.get(match.group(1), follow=True)
        self.assertTrue(response.context["validlink"])
        new_password = "Nueva-Contrasena-Ficticia-1"
        self.client.post(response.redirect_chain[-1][0], {"new_password1": new_password, "new_password2": new_password})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        response = self.client.get(match.group(1), follow=True)
        self.assertFalse(response.context["validlink"])


class PasswordChangeTests(TestCase):
    def test_requires_current_password(self):
        user = make_user()
        self.client.force_login(user)
        url = reverse("accounts:password_change")
        new = "Otra-Contrasena-Ficticia-9"
        self.client.post(url, {"old_password": "mala", "new_password1": new, "new_password2": new})
        user.refresh_from_db()
        self.assertTrue(user.check_password(PASSWORD))
        self.client.post(url, {"old_password": PASSWORD, "new_password1": new, "new_password2": new})
        user.refresh_from_db()
        self.assertTrue(user.check_password(new))

    def test_anonymous_redirected(self):
        response = self.client.get(reverse("accounts:password_change"))
        self.assertIn(reverse("accounts:login"), response["Location"])
