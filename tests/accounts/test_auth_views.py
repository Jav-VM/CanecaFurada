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
        self.assertRedirects(
            self.client.get(reverse("accounts:home")), reverse("admin:index"), fetch_redirect_response=False
        )
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
