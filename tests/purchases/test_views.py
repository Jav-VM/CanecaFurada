"""Panel del personal: escaneo, confirmación, registro, resultado y admin de compras."""
import hashlib
import re
import uuid

from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from apps.purchases.models import Purchase
from tests.accounts.factories import VALID_MOBILE

from .test_services import make_customer_with_qr, make_employee, make_owner

PRIVATE_VALUES = ("cliente@example.com", "Ficticia Exemplo", "Rúa Ficticia", "15001", "600 000 001", "+34600000001", "1996")
JSQR_SHA256 = "bc40c8a15196236b2314db0856f72ca0b49980cd5413b8c852a7349f5fee0859"


def hidden_value(response, name):
    match = re.search(rf'name="{name}" value="([^"]+)"', response.content.decode())
    assert match, f"Falta el campo oculto {name}"
    return match.group(1)


class PanelTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.customer, self.token = make_customer_with_qr(phone_number=VALID_MOBILE)
        self.employee = make_employee()
        self.client.force_login(self.employee)

    def identify(self, code=None):
        return self.client.post(reverse("purchases:identify"), {"code": code if code is not None else self.token})

    def register(self, amount="12,50", **overrides):
        confirm = self.identify()
        data = {
            "code": hidden_value(confirm, "code"),
            "idempotency_key": hidden_value(confirm, "idempotency_key"),
            "amount": amount,
        }
        data.update(overrides)
        return self.client.post(reverse("purchases:register"), data), data


class AccessTests(PanelTestCase):
    def test_anonymous_is_sent_to_login(self):
        self.client.logout()
        for name in ("purchases:scan", "purchases:identify", "purchases:register"):
            with self.subTest(name):
                response = self.client.get(reverse(name)) if name == "purchases:scan" else self.client.post(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("accounts:login"), response["Location"])

    def test_customer_cannot_use_panel(self):
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse("purchases:scan")).status_code, 403)
        self.assertEqual(self.identify().status_code, 403)
        response = self.client.post(
            reverse("purchases:register"), {"code": self.token, "amount": "5", "idempotency_key": str(uuid.uuid4())}
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Purchase.objects.exists())

    def test_employee_and_owner_can_open_scanner(self):
        for user in (self.employee, make_owner()):
            self.client.force_login(user)
            with self.subTest(role=user.role):
                response = self.client.get(reverse("purchases:scan"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "js/qr-scanner.js")
                self.assertContains(response, "vendor/jsqr/jsQR.js")
                self.assertContains(response, "data-qr-scanner")

    def test_staff_home_links_to_panel(self):
        self.assertContains(self.client.get(reverse("accounts:home")), reverse("purchases:scan"))

    def test_identify_and_register_require_post_and_csrf(self):
        self.assertEqual(self.client.get(reverse("purchases:identify")).status_code, 405)
        self.assertEqual(self.client.get(reverse("purchases:register")).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.employee)
        self.assertEqual(csrf_client.post(reverse("purchases:identify"), {"code": self.token}).status_code, 403)


class IdentifyViewTests(PanelTestCase):
    def test_valid_qr_shows_only_minimal_customer_data(self):
        response = self.identify(f"CF1:{self.token}")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "purchases/confirm.html")
        self.assertContains(response, "Lúa F.")
        for value in PRIVATE_VALUES:
            with self.subTest(value=value):
                self.assertNotContains(response, value)
        uuid.UUID(hidden_value(response, "idempotency_key"))
        self.assertIn("no-store", response["Cache-Control"])

    def test_each_confirmation_gets_a_new_idempotency_key(self):
        self.assertNotEqual(hidden_value(self.identify(), "idempotency_key"), hidden_value(self.identify(), "idempotency_key"))

    def test_invalid_qr_shows_generic_error(self):
        response = self.identify("CF1:" + "A" * 32)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "El código no es válido o la cuenta no está activa.", status_code=400)

    def test_inactive_customer_gets_same_error_without_personal_data(self):
        self.customer.is_active = False
        self.customer.save(update_fields=["is_active"])
        response = self.identify()
        self.assertContains(response, "El código no es válido o la cuenta no está activa.", status_code=400)
        self.assertNotContains(response, "Lúa", status_code=400)
        for value in PRIVATE_VALUES:
            self.assertNotContains(response, value, status_code=400)


class RegisterViewTests(PanelTestCase):
    def test_full_flow_registers_and_redirects_to_result(self):
        response, _ = self.register("12,50")
        purchase = Purchase.objects.get()
        self.assertRedirects(response, reverse("purchases:detail", args=[purchase.public_id]))
        self.assertNotIn(self.token, response["Location"])
        detail = self.client.get(response["Location"])
        self.assertContains(detail, "12,50 €")
        self.assertContains(detail, "Lúa F.")
        self.assertContains(detail, "Compra registrada")
        self.assertContains(detail, str(purchase.public_id))
        for value in PRIVATE_VALUES:
            self.assertNotContains(detail, value)

    def test_double_submit_does_not_duplicate(self):
        response, data = self.register()
        again = self.client.post(reverse("purchases:register"), data, follow=True)
        self.assertEqual(Purchase.objects.count(), 1)
        self.assertContains(again, "ya estaba registrada")

    def test_invalid_amount_returns_to_confirmation(self):
        response, _ = self.register("0")
        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "purchases/confirm.html")
        self.assertContains(response, "mayor que cero", status_code=400)
        self.assertContains(response, "Lúa F.", status_code=400)
        self.assertFalse(Purchase.objects.exists())

    def test_tampered_idempotency_key_goes_back_to_scan(self):
        response, _ = self.register(idempotency_key="manipulada")
        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "purchases/scan.html")
        self.assertFalse(Purchase.objects.exists())

    def test_client_cannot_choose_customer_staff_or_status(self):
        """Campos extra (asignación masiva) se ignoran: el servidor fija cliente, personal, origen y estado."""
        other_employee = make_employee("otro@example.com")
        response, _ = self.register(
            registered_by=str(other_employee.pk), status="VOIDED", source="POS", customer="1"
        )
        purchase = Purchase.objects.get()
        self.assertEqual(purchase.registered_by, self.employee)
        self.assertEqual(purchase.customer, self.customer)
        self.assertEqual(purchase.status, Purchase.Status.COMPLETED)
        self.assertEqual(purchase.source, Purchase.Source.MANUAL)

    def test_customer_deactivated_between_steps_is_rejected(self):
        confirm = self.identify()
        self.customer.is_active = False
        self.customer.save(update_fields=["is_active"])
        response = self.client.post(
            reverse("purchases:register"),
            {"code": hidden_value(confirm, "code"), "idempotency_key": hidden_value(confirm, "idempotency_key"), "amount": "5"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "purchases/scan.html")
        self.assertFalse(Purchase.objects.exists())

    def test_recent_purchases_list_shows_only_own(self):
        self.register("7,00")
        self.client.force_login(make_employee("otro@example.com"))
        self.assertContains(self.client.get(reverse("purchases:scan")), "Todavía no has registrado")


class DetailViewTests(PanelTestCase):
    def setUp(self):
        super().setUp()
        self.register()
        self.purchase = Purchase.objects.get()
        self.url = reverse("purchases:detail", args=[self.purchase.public_id])

    def test_other_employee_gets_404(self):
        self.client.force_login(make_employee("otro@example.com"))
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_owner_can_see_any_purchase(self):
        self.client.force_login(make_owner())
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_customer_cannot_see_panel_detail(self):
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_unknown_id_is_404(self):
        self.assertEqual(self.client.get(reverse("purchases:detail", args=[uuid.uuid4()])).status_code, 404)


class PurchaseAdminTests(PanelTestCase):
    def test_owner_can_view_but_not_modify(self):
        self.register()
        purchase = Purchase.objects.get()
        self.client.force_login(make_owner())
        self.assertEqual(self.client.get(reverse("admin:purchases_purchase_changelist")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:purchases_purchase_change", args=[purchase.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:purchases_purchase_add")).status_code, 403)
        self.assertEqual(self.client.post(reverse("admin:purchases_purchase_delete", args=[purchase.pk]), {"post": "yes"}).status_code, 403)
        self.assertTrue(Purchase.objects.filter(pk=purchase.pk).exists())

    def test_qr_tokens_are_not_in_admin(self):
        self.client.force_login(make_owner())
        response = self.client.get(reverse("admin:index"))
        # Desde la Fase 6 la app de fidelización está en el admin (puntos y
        # promociones), pero el modelo del QR y su token siguen fuera.
        self.assertNotContains(response, "customerqrcode")
        self.assertNotContains(response, self.token)
        self.register()
        for url in (reverse("admin:loyalty_pointstransaction_changelist"), reverse("admin:purchases_purchase_changelist")):
            self.assertNotContains(self.client.get(url), self.token)

    def test_employee_has_no_admin_access(self):
        response = self.client.get(reverse("admin:purchases_purchase_changelist"))
        self.assertEqual(response.status_code, 302)


class ScannerAssetsTests(TestCase):
    def test_vendored_jsqr_matches_pinned_checksum(self):
        with open(finders.find("vendor/jsqr/jsQR.js"), "rb") as fh:
            self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), JSQR_SHA256)
        self.assertIsNotNone(finders.find("vendor/jsqr/LICENSE"))

    def test_scanner_script_has_no_network_calls_or_rules(self):
        with open(finders.find("js/qr-scanner.js"), encoding="utf-8") as fh:
            js = fh.read()
        for forbidden in ("fetch(", "XMLHttpRequest", "localStorage", "sessionStorage", "console.log", "amount"):
            with self.subTest(forbidden):
                self.assertNotIn(forbidden, js)
