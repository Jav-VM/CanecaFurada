"""Correcciones de la auditoría de la Fase 11 (web y servicios)."""
import datetime
import io
import re

from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts import services
from apps.accounts.models import EmailVerificationToken, User
from apps.core.http import client_ip
from apps.core.models import AuditEvent
from tests.accounts.factories import PASSWORD, make_user, registration_data, registration_post_data

NEW_PASSWORD = "Otra-Contrasena-Ficticia-9"


class ClientIpTests(TestCase):
    def request(self, remote="203.0.113.10", forwarded=None):
        extra = {"REMOTE_ADDR": remote}
        if forwarded is not None:
            extra["HTTP_X_FORWARDED_FOR"] = forwarded
        return RequestFactory().get("/", **extra)

    @override_settings(TRUSTED_PROXY_COUNT=0)
    def test_without_proxies_forwarded_header_is_ignored(self):
        self.assertEqual(client_ip(self.request(forwarded="198.51.100.1")), "203.0.113.10")

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_with_one_proxy_uses_the_entry_added_by_it(self):
        # El cliente inventa la primera entrada; el proxy añade la IP real al final.
        self.assertEqual(client_ip(self.request(forwarded="1.2.3.4, 198.51.100.7")), "198.51.100.7")
        self.assertEqual(client_ip(self.request()), "203.0.113.10")

    @override_settings(TRUSTED_PROXY_COUNT=2)
    def test_incomplete_header_falls_back_to_remote_addr(self):
        self.assertEqual(client_ip(self.request(forwarded="198.51.100.7")), "203.0.113.10")


class RegistrationEnumerationTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_weak_password_gives_the_same_web_response_for_existing_email(self):
        make_user("nueva@example.com")
        url = reverse("accounts:register")
        weak = {"password1": "12345678", "password2": "12345678"}
        existing = self.client.post(url, registration_post_data(**weak))
        new = self.client.post(url, registration_post_data(email="otra@example.com", **weak))
        self.assertEqual(existing.status_code, new.status_code)
        self.assertEqual(existing.context["form"].errors, new.context["form"].errors)

    def test_service_validates_everything_before_checking_the_email(self):
        make_user("nueva@example.com")
        with self.assertRaises(services.ValidationError) as ctx:
            services.register_customer(**registration_data(password="123", city=""))
        self.assertNotIsInstance(ctx.exception, services.EmailAlreadyRegistered)
        self.assertTrue({"password", "city"} <= set(ctx.exception.message_dict))
        with self.assertRaises(services.EmailAlreadyRegistered):
            services.register_customer(**registration_data())


@override_settings(SITE_BASE_URL="https://www.example.com")
class PasswordAuditTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user()

    def test_web_password_change_is_audited_without_secrets(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse("accounts:password_change"),
            {"old_password": PASSWORD, "new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
        )
        event = AuditEvent.objects.get(action=AuditEvent.Action.PASSWORD_CHANGED)
        self.assertEqual(event.metadata, {"via": "change", "channel": "web"})
        self.assertEqual(event.target_public_id, self.user.public_id)

    def test_web_password_reset_is_audited(self):
        self.client.post(reverse("accounts:password_reset"), {"email": self.user.email})
        path = re.search(r"https://www\.example\.com(/cuenta/contrasena/restablecer/\S+/)", mail.outbox[0].body).group(1)
        response = self.client.get(path, follow=True)
        self.client.post(response.redirect_chain[-1][0], {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD})
        event = AuditEvent.objects.get(action=AuditEvent.Action.PASSWORD_CHANGED)
        self.assertEqual(event.metadata, {"via": "reset", "channel": "web"})

    def test_failed_change_is_not_audited(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse("accounts:password_change"),
            {"old_password": "mala", "new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
        )
        self.assertFalse(AuditEvent.objects.filter(action=AuditEvent.Action.PASSWORD_CHANGED).exists())


class PurgeEmailTokensTests(TestCase):
    def make_token(self, user, expires_at, suffix):
        return EmailVerificationToken.objects.create(
            user=user,
            purpose=EmailVerificationToken.Purpose.VERIFY,
            email=user.email,
            token_hash=EmailVerificationToken.hash_token(f"token-ficticio-{suffix}"),
            expires_at=expires_at,
        )

    def test_purges_only_tokens_expired_long_ago(self):
        user = make_user()
        now = timezone.now()
        old = self.make_token(user, now - datetime.timedelta(days=40), "viejo")
        recent = self.make_token(user, now - datetime.timedelta(days=5), "reciente")
        valid = self.make_token(user, now + datetime.timedelta(hours=10), "vigente")
        out = io.StringIO()
        call_command("purge_email_tokens", stdout=out)
        self.assertIn("1", out.getvalue())
        remaining = set(EmailVerificationToken.objects.values_list("pk", flat=True))
        self.assertEqual(remaining, {recent.pk, valid.pk})
        self.assertNotIn(old.pk, remaining)
        self.assertTrue(User.objects.filter(pk=user.pk).exists())

    def test_rejects_invalid_days(self):
        with self.assertRaises(ValueError):
            services.purge_email_tokens(older_than_days=0)
