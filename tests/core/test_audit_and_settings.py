import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.core.models import AuditEvent
from apps.core.services import record_audit_event
from tests.accounts.factories import make_user

BASE_DIR = Path(settings.BASE_DIR)


class AuditEventTests(TestCase):
    def test_record_event_uses_public_id(self):
        user = make_user()
        event = record_audit_event(action=AuditEvent.Action.ROLE_CHANGED, target=user)
        self.assertEqual(event.target_public_id, user.public_id)
        self.assertEqual(event.metadata, {})

    def test_audit_is_read_only_in_admin(self):
        owner = make_user(email="o@example.com", role="OWNER")
        event = record_audit_event(action=AuditEvent.Action.ROLE_CHANGED, target=owner)
        self.client.force_login(owner)
        self.assertEqual(self.client.get(reverse("admin:core_auditevent_add")).status_code, 403)
        delete_url = reverse("admin:core_auditevent_delete", args=[event.pk])
        self.assertEqual(self.client.get(delete_url).status_code, 403)


class ProductionSettingsTests(SimpleTestCase):
    """Se ejecuta en un proceso aparte para no contaminar la configuración de los tests."""

    # Configuración mínima válida (valores ficticios).
    REQUIRED = {
        "DJANGO_SECRET_KEY": "x" * 50,
        "DJANGO_ALLOWED_HOSTS": "example.com",
        "EMAIL_HOST": "smtp.example.com",
        "SITE_BASE_URL": "https://www.example.com",
    }

    def _import_prod(self, extra_env):
        prefixes = ("DJANGO_", "EMAIL_", "SITE_BASE_URL")
        env = {k: v for k, v in os.environ.items() if not k.startswith(prefixes)}
        env.update(extra_env)
        env["DJANGO_SETTINGS_MODULE"] = "config.settings.prod"
        return subprocess.run(
            [sys.executable, "-c", "import django; django.setup()"],
            cwd=BASE_DIR, env=env, capture_output=True, text=True,
        )

    def test_prod_requires_secret_key(self):
        result = self._import_prod({"DJANGO_SECRET_KEY": "", "DJANGO_ALLOWED_HOSTS": "example.com"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", result.stderr)

    def test_prod_requires_allowed_hosts(self):
        result = self._import_prod({"DJANGO_SECRET_KEY": "x" * 50, "DJANGO_ALLOWED_HOSTS": ""})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_ALLOWED_HOSTS", result.stderr)

    def test_prod_loads_with_required_variables(self):
        result = self._import_prod(self.REQUIRED)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_prod_requires_email_host(self):
        result = self._import_prod({**self.REQUIRED, "EMAIL_HOST": ""})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EMAIL_HOST", result.stderr)

    def test_prod_rejects_simulated_email_backends(self):
        for backend in ("console", "locmem", "filebased", "dummy"):
            with self.subTest(backend=backend):
                result = self._import_prod(
                    {**self.REQUIRED, "EMAIL_BACKEND": f"django.core.mail.backends.{backend}.EmailBackend"}
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("EMAIL_BACKEND", result.stderr)

    def test_prod_requires_https_site_url(self):
        result = self._import_prod({**self.REQUIRED, "SITE_BASE_URL": "http://www.example.com"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SITE_BASE_URL", result.stderr)

    def test_prod_requires_signing_key_of_32_bytes(self):
        """La clave firma también los JWT de la API (Fase 11)."""
        result = self._import_prod({**self.REQUIRED, "DJANGO_SECRET_KEY": "x" * 20})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("32 bytes", result.stderr)
        result = self._import_prod({**self.REQUIRED, "API_JWT_SIGNING_KEY": "corta"})
        self.assertNotEqual(result.returncode, 0)
        result = self._import_prod({**self.REQUIRED, "API_JWT_SIGNING_KEY": "y" * 64})
        self.assertEqual(result.returncode, 0, result.stderr)
