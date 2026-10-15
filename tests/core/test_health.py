"""Endpoint de salud `/healthz` para los healthchecks del despliegue (Fase 12)."""
from unittest import mock

from django.db import DatabaseError
from django.test import TestCase, override_settings


class HealthCheckTests(TestCase):
    def test_ok_without_internal_data(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertNotIn("Set-Cookie", response)

    def test_head_is_allowed(self):
        self.assertEqual(self.client.head("/healthz").status_code, 200)

    def test_other_methods_are_rejected(self):
        for method in ("post", "put", "delete"):
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)("/healthz").status_code, 405)

    def test_answers_the_internal_check_regardless_of_host(self):
        """El healthcheck del contenedor llama a `localhost:8000`, que no está en ALLOWED_HOSTS."""
        response = self.client.get("/healthz", HTTP_HOST="web:8000")
        self.assertEqual(response.status_code, 200)

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_not_redirected_to_https_but_other_paths_are(self):
        self.assertEqual(self.client.get("/healthz").status_code, 200)
        self.assertEqual(self.client.get("/").status_code, 301)

    def test_database_failure_returns_503_without_details(self):
        with mock.patch("apps.core.middleware.connection.cursor", side_effect=DatabaseError("detalle interno")):
            response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content, b"error")

    def test_only_exact_path(self):
        self.assertEqual(self.client.get("/healthz/").status_code, 404)
        self.assertEqual(self.client.get("/healthzx").status_code, 404)

    def test_other_disallowed_hosts_still_rejected(self):
        self.assertEqual(self.client.get("/", HTTP_HOST="atacante.example.com").status_code, 400)
