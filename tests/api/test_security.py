"""API v1: documentación, cabeceras, formato de errores, paginación y throttling."""
from django.contrib import admin
from django.test import override_settings
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from tests.loyalty.factories import make_employee, make_owner, make_verified_customer
from tests.rewards.factories import make_reward

from .base import ApiTestCase, api_url


class DocsAccessTests(ApiTestCase):
    def test_docs_restricted_outside_development(self):
        self.assertIn(self.client.get(api_url("schema")).status_code, (401, 403))
        self.authenticate(make_employee())
        self.assertEqual(self.client.get(api_url("schema")).status_code, 403)
        self.anonymous()
        self.client.force_login(make_owner())  # el propietario puede abrirla con su sesión web
        self.assertEqual(self.client.get(api_url("schema")).status_code, 200)
        self.assertEqual(self.client.get(api_url("docs")).status_code, 200)

    @override_settings(API_DOCS_PUBLIC=True)
    def test_docs_public_when_enabled(self):
        response = self.client.get(api_url("schema"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/api/v1/auth/login/", response.content)


class HeadersAndErrorsTests(ApiTestCase):
    def test_no_store_and_no_cors(self):
        self.authenticate(make_verified_customer())
        response = self.client.get(api_url("me"), HTTP_ORIGIN="https://malicioso.example.net")
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertNotIn("Access-Control-Allow-Origin", response)

    def test_error_format(self):
        response = self.client.get(api_url("me"))
        self.assertEqual(set(response.json()), {"code", "detail"})
        self.assertEqual(response.json()["code"], "not_authenticated")
        self.authenticate(make_verified_customer())
        not_found = self.client.get(api_url("redemption", "00000000-0000-0000-0000-000000000000"))
        self.assertEqual((not_found.status_code, not_found.json()["code"]), (404, "not_found"))

    def test_only_json_is_accepted(self):
        response = self.client.post(api_url("login"), "email=a@example.com&password=x", content_type="application/x-www-form-urlencoded")
        self.assertEqual(response.status_code, 415)

    def test_page_size_is_capped(self):
        for index in range(55):
            make_reward(name=f"Recompensa {index}")
        body = self.client.get(api_url("rewards"), {"page_size": 500}).json()
        self.assertEqual(len(body["results"]), 50)
        self.assertEqual(body["count"], 55)


class ThrottlingTests(ApiTestCase):
    def test_auth_endpoints_are_rate_limited_per_ip(self):
        statuses = [self.post("verify_email", {"token": f"inventado-{i}"}).status_code for i in range(11)]
        self.assertEqual(statuses[:10], [400] * 10)
        self.assertEqual(statuses[10], 429)
        self.assertEqual(self.post("verify_email", {"token": "x"}).json()["code"], "throttled")

    @override_settings(TRUSTED_PROXY_COUNT=0)
    def test_forwarded_for_is_ignored_without_trusted_proxies(self):
        for i in range(10):
            self.client.post(api_url("verify_email"), {"token": "x"}, format="json", HTTP_X_FORWARDED_FOR=f"10.0.0.{i}")
        response = self.client.post(api_url("verify_email"), {"token": "x"}, format="json", HTTP_X_FORWARDED_FOR="10.9.9.9")
        self.assertEqual(response.status_code, 429)


class TokenAdminTests(ApiTestCase):
    def test_raw_refresh_tokens_are_not_exposed_in_admin(self):
        self.assertFalse(admin.site.is_registered(OutstandingToken))
        self.assertFalse(admin.site.is_registered(BlacklistedToken))
