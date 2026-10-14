import datetime
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts import services
from apps.accounts.models import EmailVerificationToken, User
from apps.accounts.permissions import verified_email_required
from apps.core.models import AuditEvent

from .factories import make_user, registration_data, token_from_email


class VerificationTestMixin:
    def register(self, **overrides):
        with self.captureOnCommitCallbacks(execute=True):
            user = services.register_customer(**registration_data(**overrides))
        return user, token_from_email(mail.outbox[-1])

    def confirm(self, token):
        with self.captureOnCommitCallbacks(execute=True):
            return services.confirm_email_token(token)


class ConfirmTokenServiceTests(VerificationTestMixin, TestCase):
    def test_valid_token_verifies_email_and_is_single_use(self):
        user, token = self.register()
        self.confirm(token)
        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.Action.EMAIL_VERIFIED).exists())
        with self.assertRaises(ValidationError) as ctx:
            self.confirm(token)
        self.assertEqual(ctx.exception.code, "used")

    def test_invalid_tokens(self):
        self.register()
        for token in ("", "x", "a" * 43, "a" * 500):
            with self.subTest(token=token[:10]):
                with self.assertRaises(ValidationError) as ctx:
                    self.confirm(token)
                self.assertEqual(ctx.exception.code, "invalid")

    def test_expired_token(self):
        user, token = self.register()
        EmailVerificationToken.objects.filter(user=user).update(
            expires_at=timezone.now() - datetime.timedelta(seconds=1)
        )
        with self.assertRaises(ValidationError) as ctx:
            self.confirm(token)
        self.assertEqual(ctx.exception.code, "expired")
        user.refresh_from_db()
        self.assertFalse(user.is_email_verified)

    def test_token_expires_after_configured_ttl(self):
        user, _ = self.register()
        token = EmailVerificationToken.objects.get(user=user)
        self.assertAlmostEqual(
            (token.expires_at - token.created_at).total_seconds(), 24 * 3600, delta=1
        )

    def test_resend_revokes_previous_token(self):
        user, old_token = self.register()
        EmailVerificationToken.objects.update(created_at=timezone.now() - datetime.timedelta(minutes=5))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertTrue(services.resend_verification_email(user))
        new_token = token_from_email(mail.outbox[-1])
        self.assertNotEqual(old_token, new_token)
        with self.assertRaises(ValidationError) as ctx:
            self.confirm(old_token)
        self.assertEqual(ctx.exception.code, "revoked")
        self.confirm(new_token)
        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)

    def test_inactive_user_cannot_verify(self):
        user, token = self.register()
        User.objects.filter(pk=user.pk).update(is_active=False)
        with self.assertRaises(ValidationError):
            self.confirm(token)

    def test_concurrent_consumption_only_one_succeeds(self):
        """Simula que otra petición consume el token entre la lectura y el UPDATE."""
        user, token = self.register()
        original_filter = EmailVerificationToken.objects.filter

        def racing_filter(*args, **kwargs):
            if "used_at__isnull" in kwargs and "pk" in kwargs:
                original_filter(pk=kwargs["pk"]).update(used_at=timezone.now())
            return original_filter(*args, **kwargs)

        with mock.patch.object(EmailVerificationToken.objects, "filter", side_effect=racing_filter):
            with self.assertRaises(ValidationError) as ctx:
                services.confirm_email_token(token)
        self.assertEqual(ctx.exception.code, "used")
        user.refresh_from_db()
        self.assertFalse(user.is_email_verified)

    def test_verify_token_is_invalid_after_email_changed(self):
        user, token = self.register()
        user.email = "otra@example.com"
        user.save()
        with self.assertRaises(ValidationError) as ctx:
            self.confirm(token)
        self.assertEqual(ctx.exception.code, "invalid")


@override_settings(EMAIL_VERIFICATION_RESEND_INTERVAL_SECONDS=60, EMAIL_VERIFICATION_MAX_PER_DAY=3)
class ResendLimitTests(VerificationTestMixin, TestCase):
    def test_minimum_interval_between_sends(self):
        user, _ = self.register()
        with self.assertRaises(services.RateLimited):
            services.resend_verification_email(user)

    def test_daily_maximum(self):
        user, _ = self.register()
        for _ in range(2):
            EmailVerificationToken.objects.update(
                created_at=timezone.now() - datetime.timedelta(minutes=10)
            )
            services.resend_verification_email(user)
        EmailVerificationToken.objects.update(created_at=timezone.now() - datetime.timedelta(minutes=10))
        with self.assertRaises(services.RateLimited):
            services.resend_verification_email(user)
        self.assertEqual(EmailVerificationToken.objects.filter(user=user).count(), 3)

    def test_old_tokens_do_not_count(self):
        user, _ = self.register()
        EmailVerificationToken.objects.update(created_at=timezone.now() - datetime.timedelta(days=2))
        self.assertTrue(services.resend_verification_email(user))

    def test_verified_user_gets_no_new_email(self):
        user, token = self.register()
        self.confirm(token)
        sent = len(mail.outbox)
        self.assertFalse(services.resend_verification_email(user))
        self.assertEqual(len(mail.outbox), sent)


class VerificationViewTests(VerificationTestMixin, TestCase):
    def setUp(self):
        cache.clear()

    def test_get_does_not_consume_token(self):
        user, token = self.register()
        url = reverse("accounts:verify_email", args=[token])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirmar email")
        user.refresh_from_db()
        self.assertFalse(user.is_email_verified)
        self.assertIn("no-cache", response["Cache-Control"])

    def test_post_verifies(self):
        user, token = self.register()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("accounts:verify_email", args=[token]))
        self.assertContains(response, "Email confirmado")
        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)

    def test_invalid_token_shows_error_without_404(self):
        response = self.client.post(reverse("accounts:verify_email", args=["token-falso"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "El enlace no es válido.")

    def test_used_token_shows_error(self):
        _, token = self.register()
        url = reverse("accounts:verify_email", args=[token])
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url)
        response = self.client.post(url)
        self.assertContains(response, "ya se ha utilizado")

    def test_public_resend_does_not_reveal_accounts(self):
        user, _ = self.register()
        EmailVerificationToken.objects.update(created_at=timezone.now() - datetime.timedelta(minutes=5))
        url = reverse("accounts:resend_verification")
        responses = []
        for email in (user.email, "noexiste@example.com"):
            with self.captureOnCommitCallbacks(execute=True):
                responses.append(self.client.post(url, {"email": email}, follow=True))
        self.assertEqual(responses[0].redirect_chain, responses[1].redirect_chain)
        self.assertEqual(
            [str(m) for m in responses[0].context["messages"]],
            [str(m) for m in responses[1].context["messages"]],
        )
        self.assertEqual(len(mail.outbox), 2)  # registro + un reenvío; nada para el inexistente

    def test_logged_in_resend(self):
        user, _ = self.register()
        EmailVerificationToken.objects.update(created_at=timezone.now() - datetime.timedelta(minutes=5))
        self.client.force_login(user)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("accounts:resend_verification_self"))
        self.assertEqual(len(mail.outbox), 2)
        response = self.client.post(reverse("accounts:resend_verification_self"), follow=True)
        self.assertContains(response, "Espera un minuto")

    def test_resend_self_requires_post_and_login(self):
        url = reverse("accounts:resend_verification_self")
        self.assertEqual(self.client.post(url).status_code, 302)
        self.client.force_login(make_user())
        self.assertEqual(self.client.get(url).status_code, 405)


class PendingAccountRestrictionsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        @verified_email_required
        def protected(request):
            return HttpResponse("ok")

        self.view = protected

    def request_as(self, user):
        request = self.factory.get("/protegido/")
        request.user = user
        return request

    def test_pending_account_is_denied(self):
        with self.assertRaises(PermissionDenied):
            self.view(self.request_as(make_user()))
        with self.assertRaises(PermissionDenied):
            services.require_verified_email(make_user(email="b@example.com"))

    def test_verified_account_is_allowed(self):
        user = make_user(email_verified_at=timezone.now())
        self.assertEqual(self.view(self.request_as(user)).status_code, 200)
        services.require_verified_email(user)

    def test_pending_account_can_log_in(self):
        user = make_user()
        self.assertTrue(self.client.login(username=user.email, password="Contrasena-Ficticia-2026"))


class EmailFailureTests(VerificationTestMixin, TestCase):
    def test_smtp_failure_does_not_break_registration_nor_log_address(self):
        with mock.patch(
            "apps.notifications.services._send_email", side_effect=OSError("smtp caído nueva@example.com")
        ):
            with self.assertLogs("apps.notifications.services", level="ERROR") as logs:
                with self.captureOnCommitCallbacks(execute=True):
                    user = services.register_customer(**registration_data())
        self.assertTrue(User.objects.filter(pk=user.pk).exists())
        joined = " ".join(logs.output)
        self.assertNotIn("nueva@example.com", joined)
        self.assertIn("OSError", joined)
        # Fase 10: el fallo queda registrado, sin contexto (el token no se guarda).
        from apps.notifications.models import Notification

        notification = Notification.objects.get(recipient=user)
        self.assertEqual(notification.kind, Notification.Kind.EMAIL_VERIFICATION)
        self.assertEqual(notification.status, Notification.Status.FAILED)
        self.assertEqual(notification.context, {})
