"""Dashboard del propietario (Fase 9): acceso y escalada de privilegios."""
import uuid

from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from apps.accounts import selectors as accounts_selectors
from apps.accounts.models import User
from apps.catalog import selectors as catalog_selectors
from apps.core.models import AuditEvent
from apps.loyalty import promotions
from apps.loyalty import selectors as loyalty_selectors
from apps.loyalty.models import PointsTransaction, Promotion
from apps.purchases import selectors as purchase_selectors
from apps.rewards import selectors as reward_selectors
from apps.rewards import services as rewards
from apps.rewards.models import Reward
from apps.web import services as web
from apps.web.models import BusinessInfo
from tests.loyalty.factories import make_promotion
from tests.rewards.factories import make_customer_with_qr, make_employee, make_owner, make_reward

GET_URLS = (
    "dashboard:home",
    "dashboard:customers",
    "dashboard:customer_zones",
    "dashboard:employees",
    "dashboard:purchases",
    "dashboard:points",
    "dashboard:rewards",
    "dashboard:menu",
    "dashboard:beers",
    "dashboard:events",
    "dashboard:reservations",
    "dashboard:promotions",
    "dashboard:content",
    "dashboard:settings",
)


class DashboardTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.customer, self.token = make_customer_with_qr()
        self.employee = make_employee()
        self.owner = make_owner()
        self.client.force_login(self.owner)


class AccessTests(DashboardTestCase):
    def all_get_urls(self):
        return [reverse(name) for name in GET_URLS] + [
            reverse("dashboard:customer_detail", args=[self.customer.public_id])
        ]

    def test_anonymous_is_sent_to_login(self):
        self.client.logout()
        for url in self.all_get_urls():
            with self.subTest(url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("accounts:login"), response["Location"])

    def test_employee_and_customer_are_forbidden(self):
        for user in (self.employee, self.customer):
            self.client.force_login(user)
            for url in self.all_get_urls():
                with self.subTest(role=user.role, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)

    def test_owner_can_open_every_section(self):
        for url in self.all_get_urls():
            with self.subTest(url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn("no-store", response["Cache-Control"])

    def test_deactivated_owner_loses_access(self):
        make_owner("otro-owner@example.com")
        User.objects.filter(pk=self.owner.pk).update(is_active=False)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 302)

    def test_owner_lands_on_dashboard_and_sees_link(self):
        self.assertRedirects(self.client.get(reverse("accounts:home")), reverse("dashboard:home"))
        self.assertContains(self.client.get(reverse("web:home")), reverse("dashboard:home"))

    def test_employee_header_has_no_dashboard_link(self):
        self.client.force_login(self.employee)
        self.assertNotContains(self.client.get(reverse("web:home")), reverse("dashboard:home"))

    def test_action_urls_reject_get(self):
        urls = [
            reverse("dashboard:customer_adjust_points", args=[self.customer.public_id]),
            reverse("dashboard:customer_reverse_movement", args=[self.customer.public_id]),
            reverse("dashboard:employee_create"),
            reverse("dashboard:employee_status", args=[self.employee.public_id]),
            reverse("dashboard:employee_role", args=[self.employee.public_id]),
        ]
        for url in urls:
            with self.subTest(url):
                self.assertEqual(self.client.get(url).status_code, 405)


class EscalationTests(DashboardTestCase):
    """Un empleado no puede ejecutar ninguna acción del dashboard aunque conozca las URLs."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.employee)

    def assertForbidden(self, url, data):
        self.assertEqual(self.client.post(url, data).status_code, 403)

    def test_cannot_adjust_points(self):
        self.assertForbidden(
            reverse("dashboard:customer_adjust_points", args=[self.customer.public_id]),
            {"points": "500", "reason": "Intento", "idempotency_key": str(uuid.uuid4())},
        )
        self.assertFalse(PointsTransaction.objects.exists())

    def test_cannot_create_employees_or_change_roles(self):
        self.assertForbidden(
            reverse("dashboard:employee_create"),
            {"first_name": "X", "last_name": "Y", "email": "nuevo@example.com", "password1": "Contrasena-Ficticia-2026", "password2": "Contrasena-Ficticia-2026"},
        )
        self.assertFalse(User.objects.filter(email="nuevo@example.com").exists())
        self.assertForbidden(
            reverse("dashboard:employee_role", args=[self.employee.public_id]), {"role": "OWNER", "confirm": "on"}
        )
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role, User.Role.EMPLOYEE)
        self.assertForbidden(reverse("dashboard:employee_status", args=[self.owner.public_id]), {"accion": "desactivar"})
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)

    def test_cannot_change_catalog_rewards_promotions_content_or_settings(self):
        reward = make_reward()
        promo = make_promotion()
        self.assertForbidden(reverse("dashboard:reward_status", args=[reward.public_id]), {"estado": "ARCHIVED"})
        self.assertForbidden(reverse("dashboard:promotion_status", args=[promo.public_id]), {"estado": "ENDED"})
        self.assertForbidden(reverse("dashboard:content"), {"address": "Rúa Falsa 0"})
        self.assertForbidden(reverse("dashboard:settings"), {"points_per_euro": "50"})
        reward.refresh_from_db()
        promo.refresh_from_db()
        self.assertEqual(reward.status, Reward.Status.ACTIVE)
        self.assertEqual(promo.status, Promotion.Status.ACTIVE)
        self.assertFalse(BusinessInfo.objects.exists())

    def test_customer_detail_is_not_audited_when_forbidden(self):
        self.client.get(reverse("dashboard:customer_detail", args=[self.customer.public_id]))
        self.assertFalse(AuditEvent.objects.filter(action=AuditEvent.Action.CUSTOMER_DATA_VIEWED).exists())


class SelectorPermissionTests(DashboardTestCase):
    """La lógica de dominio protege también los datos sin pasar por las vistas (futura API)."""

    def test_owner_only_selectors_reject_employee(self):
        calls = [
            lambda a: accounts_selectors.search_customers(actor=a),
            lambda a: accounts_selectors.customer_for_owner(actor=a, public_id=self.customer.public_id),
            lambda a: accounts_selectors.customer_counts(actor=a),
            lambda a: accounts_selectors.geographic_distribution(actor=a, level="pais"),
            lambda a: accounts_selectors.staff_members(actor=a),
            lambda a: purchase_selectors.all_purchases(actor=a),
            lambda a: purchase_selectors.purchases_by_staff(actor=a),
            lambda a: loyalty_selectors.all_movements(actor=a),
            lambda a: loyalty_selectors.promotions_overview(actor=a),
            lambda a: reward_selectors.redemption_stats(actor=a),
            lambda a: reward_selectors.all_redemptions(actor=a),
            lambda a: reward_selectors.rewards_overview(actor=a),
            lambda a: reward_selectors.validations_by_staff(actor=a),
            lambda a: catalog_selectors.products_for_management(actor=a),
        ]
        for actor in (self.employee, self.customer):
            for call in calls:
                with self.subTest(role=actor.role, call=call):
                    with self.assertRaises(PermissionDenied):
                        call(actor)

    def test_owner_only_services_reject_employee(self):
        with self.assertRaises(PermissionDenied):
            web.update_business_info(actor=self.employee, data={"address": "X"})
        with self.assertRaises(PermissionDenied):
            rewards.set_reward_status(actor=self.employee, reward=make_reward(), status="PAUSED")
        with self.assertRaises(PermissionDenied):
            promotions.set_promotion_status(actor=self.employee, promotion=make_promotion(), status="PAUSED")
