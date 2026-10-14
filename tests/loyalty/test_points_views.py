"""Vista "Mis puntos", puntos en el panel del personal y admin de fidelización: acceso, IDOR y asignación masiva."""
import datetime
import re
import uuid
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts import services as accounts
from apps.core.models import AuditEvent
from apps.loyalty import ledger
from apps.loyalty.models import LoyaltyRule, PointsTransaction, Promotion
from apps.loyalty.views import HISTORY_PAGE_SIZE
from apps.purchases.models import Purchase
from tests.accounts.factories import registration_data

from .factories import buy, make_customer_with_qr, make_employee, make_owner, make_promotion


class MyPointsViewTests(TestCase):
    url = reverse("loyalty:my_points")

    def setUp(self):
        cache.clear()
        self.customer, self.token = make_customer_with_qr()
        self.employee = make_employee()

    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_only_verified_customers(self):
        unverified = accounts.register_customer(**registration_data(email="pendiente@example.com"))
        for user in (unverified, self.employee, make_owner()):
            with self.subTest(user=user.email):
                self.client.force_login(user)
                self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_shows_own_balance_history_and_purchases(self):
        make_promotion(name="Promo ficticia", fixed_points=5)
        buy(self.employee, self.token, "12.50")
        self.client.force_login(self.customer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-points-balance>17<')
        self.assertContains(response, 'data-points-earned>17<')
        self.assertContains(response, 'data-points-used>0<')
        self.assertContains(response, "Promo ficticia")
        self.assertContains(response, "12,50 €")
        self.assertContains(response, "17 puntos")
        self.assertIn("no-store", response["Cache-Control"])

    def test_never_shows_other_customers_data(self):
        other, other_token = make_customer_with_qr("otra@example.com")
        buy(self.employee, other_token, "99.00")
        buy(self.employee, self.token, "1.00")
        self.client.force_login(self.customer)
        # Parámetros inventados (IDOR) se ignoran: siempre es el usuario de la sesión.
        response = self.client.get(self.url, {"customer": str(other.public_id), "user": other.pk})
        self.assertContains(response, 'data-points-balance>1<')
        self.assertNotContains(response, "99,00")
        self.assertNotContains(response, "otra@example.com")

    def test_paginates_history(self):
        for _ in range(HISTORY_PAGE_SIZE + 3):
            buy(self.employee, self.token, "1.00")
        self.client.force_login(self.customer)
        first = self.client.get(self.url)
        self.assertEqual(len(first.context["movements"].object_list), HISTORY_PAGE_SIZE)
        second = self.client.get(self.url, {"page": 2, "compras": 2})
        self.assertEqual(len(second.context["movements"].object_list), 3)
        self.assertEqual(len(second.context["purchases"].object_list), 3)
        self.assertEqual(self.client.get(self.url, {"page": "x"}).status_code, 200)

    def test_post_is_not_allowed_to_change_points(self):
        self.client.force_login(self.customer)
        self.client.post(self.url, {"points": 1000, "balance": 1000})
        self.assertFalse(PointsTransaction.objects.exists())

    def test_profile_links_to_points(self):
        self.client.force_login(self.customer)
        self.assertContains(self.client.get(reverse("accounts:profile")), self.url)

    def test_qr_url_unchanged(self):
        self.assertEqual(reverse("loyalty:my_qr"), "/cuenta/mi-qr/")
        self.assertEqual(self.url, "/cuenta/puntos/")


def hidden_value(response, name):
    match = re.search(rf'name="{name}" value="([^"]+)"', response.content.decode())
    assert match, f"Falta el campo oculto {name}"
    return match.group(1)


class StaffPanelPointsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.customer, self.token = make_customer_with_qr()
        self.employee = make_employee()
        self.client.force_login(self.employee)

    def test_points_sent_by_the_browser_are_ignored(self):
        confirm = self.client.post(reverse("purchases:identify"), {"code": self.token})
        response = self.client.post(
            reverse("purchases:register"),
            {
                "code": hidden_value(confirm, "code"),
                "idempotency_key": hidden_value(confirm, "idempotency_key"),
                "amount": "10,00",
                "points": "9999",
                "balance": "9999",
                "points_per_euro": "100",
                "promotion": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ledger.balance(self.customer), 10)

    def test_result_page_shows_generated_points(self):
        purchase = buy(self.employee, self.token, "12.50")
        response = self.client.get(reverse("purchases:detail", args=[purchase.public_id]))
        self.assertContains(response, "data-purchase-points>12<")


class LoyaltyAdminTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_owner()
        self.client.force_login(self.owner)

    def test_owner_adds_rule_through_service_and_cannot_edit_it(self):
        response = self.client.post(
            reverse("admin:loyalty_loyaltyrule_add"),
            {
                "points_per_euro": "2.00",
                "valid_from_0": timezone.localtime().strftime("%d/%m/%Y"),
                "valid_from_1": timezone.localtime().strftime("%H:%M:%S"),
                "note": "Prueba",
            },
        )
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context.get("errors"))
        rule = LoyaltyRule.objects.get()
        self.assertEqual(rule.created_by, self.owner)
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.Action.LOYALTY_RULE_CREATED).exists())
        change = self.client.post(reverse("admin:loyalty_loyaltyrule_change", args=[rule.pk]), {"points_per_euro": "50"})
        self.assertEqual(change.status_code, 403)
        self.assertEqual(self.client.post(reverse("admin:loyalty_loyaltyrule_delete", args=[rule.pk]), {"post": "yes"}).status_code, 403)
        rule.refresh_from_db()
        self.assertEqual(rule.points_per_euro, Decimal("2.00"))

    def test_owner_creates_promotion_with_audit_and_cannot_delete(self):
        now = timezone.localtime()
        response = self.client.post(
            reverse("admin:loyalty_promotion_add"),
            {
                "name": "Puntos dobles",
                "description": "",
                "kind": "PURCHASE",
                "status": "ACTIVE",
                "bonus_type": "MULTIPLIER",
                "fixed_points": "",
                "multiplier": "2.00",
                "min_purchase_amount": "",
                "birthday_window_days": "7",
                "starts_at_0": now.strftime("%d/%m/%Y"),
                "starts_at_1": now.strftime("%H:%M:%S"),
                "ends_at_0": "",
                "ends_at_1": "",
                "max_uses_per_customer": "",
                "max_total_uses": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        promotion = Promotion.objects.get()
        event = AuditEvent.objects.get(action=AuditEvent.Action.PROMOTION_SAVED)
        self.assertEqual(event.target_public_id, promotion.public_id)
        self.assertEqual(
            self.client.post(reverse("admin:loyalty_promotion_delete", args=[promotion.pk]), {"post": "yes"}).status_code,
            403,
        )

    def test_invalid_promotion_shows_form_errors(self):
        now = timezone.localtime()
        response = self.client.post(
            reverse("admin:loyalty_promotion_add"),
            {
                "name": "Mal",
                "kind": "PURCHASE",
                "status": "ACTIVE",
                "bonus_type": "FIXED_POINTS",
                "multiplier": "2.00",
                "birthday_window_days": "7",
                "starts_at_0": now.strftime("%d/%m/%Y"),
                "starts_at_1": now.strftime("%H:%M:%S"),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Promotion.objects.exists())

    def test_movements_are_read_only(self):
        customer, token = make_customer_with_qr()
        buy(make_employee(), token, "10.00")
        movement = PointsTransaction.objects.get()
        self.assertEqual(self.client.get(reverse("admin:loyalty_pointstransaction_changelist")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:loyalty_pointstransaction_add")).status_code, 403)
        self.client.post(reverse("admin:loyalty_pointstransaction_change", args=[movement.pk]), {"points": 9999})
        self.assertEqual(self.client.post(reverse("admin:loyalty_pointstransaction_delete", args=[movement.pk]), {"post": "yes"}).status_code, 403)
        movement.refresh_from_db()
        self.assertEqual(movement.points, 10)

    def test_employee_has_no_access(self):
        self.client.force_login(make_employee())
        for name in ("loyaltyrule", "promotion", "pointstransaction"):
            with self.subTest(model=name):
                response = self.client.get(reverse(f"admin:loyalty_{name}_changelist"))
                self.assertNotEqual(response.status_code, 200)
