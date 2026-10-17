"""
Fase 25: textos legales editables (aviso legal, privacidad, cookies y condiciones
del programa), datos del titular, aceptación en el registro y sexo opcional.
"""
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts import services as accounts
from apps.accounts.models import User
from apps.core.models import AuditEvent
from apps.web import legal
from apps.web import services as web
from apps.web.models import LegalDocument
from tests.accounts.factories import registration_data, registration_post_data
from tests.loyalty.factories import make_customer_with_qr, make_employee, make_owner

KINDS = ("aviso-legal", "privacidad", "cookies", "condiciones-programa")


class LegalPagesTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_every_document_has_a_public_page_with_the_draft(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                response = self.client.get(reverse("web:legal", args=[kind]))
                self.assertContains(response, "data-legal-draft")
                self.assertContains(response, "BORRADOR PENDIENTE DE REVISIÓN LEGAL")
        self.assertEqual(self.client.get("/legal/no-existe/").status_code, 404)

    def test_missing_owner_data_is_pending_never_invented(self):
        html = self.client.get(reverse("web:legal", args=["aviso-legal"])).content.decode()
        self.assertIn("Titular: [pendiente de publicar]", html)
        self.assertIn("NIF/CIF: [pendiente de publicar]", html)

    def test_owner_data_appears_in_the_drafts(self):
        owner = make_owner()
        web.update_business_info(
            actor=owner,
            data={"legal_name": "Cervexas Ficticias SL", "tax_id": "B-1234567-8", "legal_address": "Rúa Ficticia 0", "legal_email": "LEGAL@example.com"},
        )
        cache.clear()
        html = self.client.get(reverse("web:legal", args=["privacidad"])).content.decode()
        self.assertIn("Titular: Cervexas Ficticias SL", html)
        self.assertIn("NIF/CIF: B12345678", html)  # normalizado
        self.assertIn("legal@example.com", html)

    def test_invalid_tax_id_is_rejected(self):
        owner = make_owner()
        for value in ("123", "ABCDEFGHI", "1234567Z8"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                web.update_business_info(actor=owner, data={"tax_id": value})

    def test_program_terms_use_the_real_configuration(self):
        html = self.client.get(reverse("web:legal", args=["condiciones-programa"])).content.decode()
        self.assertIn("puntos por euro", html)
        self.assertIn("30 días", html)  # REWARDS_CODE_VALIDITY_DAYS
        self.assertIn("mayores de 18 años", html)

    def test_cookies_draft_lists_only_technical_cookies(self):
        html = self.client.get(reverse("web:legal", args=["cookies"])).content.decode()
        for name in ("sessionid", "csrftoken", "django_language"):
            self.assertIn(name, html)
        self.assertIn("No usa cookies de analítica", html)

    def test_published_text_is_escaped_and_versioned(self):
        owner = make_owner()
        legal.save_document(actor=owner, kind="privacidad", body="Texto <script>x</script>\n\nSegundo")
        response = self.client.get(reverse("web:legal", args=["privacidad"]))
        self.assertContains(response, "&lt;script&gt;x&lt;/script&gt;")
        self.assertNotContains(response, "<script>x</script>")
        self.assertContains(response, "data-legal-version")
        self.assertNotContains(response, "data-legal-draft")

    def test_footer_and_rewards_link_to_the_documents(self):
        home = self.client.get(reverse("web:home")).content.decode()
        footer = home[home.index("data-footer-legal"):]
        for kind in KINDS:
            self.assertIn(reverse("web:legal", args=[kind]), footer)
        rewards = self.client.get(reverse("web:rewards")).content.decode()
        self.assertIn(reverse("web:legal", args=["condiciones-programa"]), rewards)


class LegalServiceAndDashboardTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_owner()
        self.employee = make_employee()
        self.customer, _token = make_customer_with_qr("cliente@example.com")
        self.client.force_login(self.owner)

    def test_version_goes_up_only_when_the_text_changes(self):
        document, changed = legal.save_document(actor=self.owner, kind="cookies", body="Uno")
        self.assertEqual((document.version, changed), (1, True))
        document, changed = legal.save_document(actor=self.owner, kind="cookies", body="  Uno  ")
        self.assertEqual((document.version, changed), (1, False))
        document, changed = legal.save_document(actor=self.owner, kind="cookies", body="Dos")
        self.assertEqual((document.version, changed), (2, True))
        events = AuditEvent.objects.filter(metadata__legal_document="cookies")
        self.assertEqual(events.count(), 2)
        self.assertNotIn("Dos", str(list(events.values_list("metadata", flat=True))))

    def test_only_owner_and_known_kinds(self):
        for user in (self.employee, self.customer):
            with self.assertRaises(PermissionDenied):
                legal.save_document(actor=user, kind="cookies", body="x")
        with self.assertRaises(ValidationError):
            legal.save_document(actor=self.owner, kind="otro", body="x")
        with self.assertRaises(ValidationError):
            legal.save_document(actor=self.owner, kind="cookies", body="   ")
        self.assertFalse(LegalDocument.objects.exists())

    def test_dashboard_lists_and_edits_documents(self):
        content = self.client.get(reverse("dashboard:content"))
        self.assertContains(content, "data-legal-documents")
        for kind in KINDS:
            self.assertContains(content, reverse("dashboard:legal_edit", args=[kind]))
        url = reverse("dashboard:legal_edit", args=["aviso-legal"])
        page = self.client.get(url)
        self.assertContains(page, "BORRADOR PENDIENTE DE REVISIÓN LEGAL")  # parte del borrador base
        response = self.client.post(url, {"body": "Aviso legal definitivo."})
        self.assertRedirects(response, reverse("dashboard:content") + "#textos-legales", fetch_redirect_response=False)
        self.assertEqual(LegalDocument.objects.get(kind="aviso-legal").body, "Aviso legal definitivo.")
        self.assertEqual(self.client.post(url, {"body": ""}).status_code, 400)
        self.assertEqual(self.client.get(reverse("dashboard:legal_edit", args=["otro"])).status_code, 404)

    def test_dashboard_edit_is_owner_only(self):
        url = reverse("dashboard:legal_edit", args=["privacidad"])
        for user in (self.employee, self.customer):
            self.client.force_login(user)
            self.assertEqual(self.client.post(url, {"body": "x"}).status_code, 403)
        self.client.logout()
        self.assertIn(reverse("accounts:login"), self.client.get(url)["Location"])
        self.assertFalse(LegalDocument.objects.exists())


class TermsAcceptanceTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_registration_requires_acceptance(self):
        with self.assertRaises(ValidationError) as ctx:
            accounts.register_customer(**registration_data(accept_terms=False))
        self.assertIn("accept_terms", ctx.exception.message_dict)
        response = self.client.post(reverse("accounts:register"), registration_post_data(accept_terms=None))
        self.assertTrue(response.context["form"].errors.get("accept_terms"))
        self.assertFalse(User.objects.exists())

    def test_acceptance_stores_date_and_current_versions(self):
        owner = make_owner()
        legal.save_document(actor=owner, kind="privacidad", body="Privacidad v1")
        legal.save_document(actor=owner, kind="privacidad", body="Privacidad v2")
        user = accounts.register_customer(**registration_data())
        profile = user.customer_profile
        self.assertIsNotNone(profile.terms_accepted_at)
        self.assertEqual((profile.privacy_version, profile.terms_version), (2, legal.DRAFT_VERSION))

    def test_register_page_links_the_documents(self):
        html = self.client.get(reverse("accounts:register")).content.decode()
        self.assertIn("data-accept-terms", html)
        self.assertIn(reverse("web:legal", args=["privacidad"]), html)
        self.assertIn(reverse("web:legal", args=["condiciones-programa"]), html)

    def test_api_registration_requires_acceptance(self):
        payload = registration_data(accept_terms=False)
        payload["date_of_birth"] = payload["date_of_birth"].isoformat()
        response = self.client.post(reverse("api:register"), payload, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.exists())

    def test_sex_is_optional(self):
        user = accounts.register_customer(**registration_data(email="sen-sexo@example.com", sex=""))
        self.assertEqual(user.customer_profile.sex, "")
        self.assertEqual(user.customer_profile.missing_required_fields(), [])
        self.client.post(reverse("accounts:register"), registration_post_data(email="web@example.com", sex=None))
        self.assertTrue(User.objects.filter(email="web@example.com").exists())
