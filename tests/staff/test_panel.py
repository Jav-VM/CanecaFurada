"""Panel del personal (Fase 8): acceso, inicio, perfil, resultados, flujos y privacidad."""
import datetime
import uuid
from decimal import Decimal

from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.loyalty import ledger
from apps.purchases import selectors as purchase_selectors
from apps.purchases.models import Purchase
from apps.rewards import services as rewards
from apps.rewards.models import Redemption
from apps.staff import views as staff_views
from apps.staff.forms import period_start
from tests.accounts.factories import VALID_MOBILE
from tests.loyalty.factories import buy
from tests.purchases.test_views import PRIVATE_VALUES, hidden_value
from tests.rewards.factories import give_points, make_customer_with_qr, make_employee, make_owner, make_reward, redeem

PANEL_URLS = ("staff:home", "staff:profile", "staff:results")
CUSTOMER_NAME = "Lúa F."


def move_purchase(purchase, days):
    Purchase.objects.filter(pk=purchase.pk).update(created_at=timezone.now() - datetime.timedelta(days=days))


class PanelTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.customer, self.token = make_customer_with_qr(phone_number=VALID_MOBILE)
        self.employee = make_employee()
        self.other_employee = make_employee("otro@example.com", first_name="Brais")
        self.owner = make_owner()
        self.client.force_login(self.employee)

    def validated_redemption(self, staff=None):
        reward = make_reward(name=f"Recompensa {uuid.uuid4().hex[:6]}")
        give_points(self.customer, reward.points_cost, owner=self.owner)
        redemption = redeem(self.customer, reward).redemption
        rewards.validate_redemption(staff=staff or self.employee, code=redemption.code)
        return redemption


class AccessTests(PanelTestCase):
    def test_anonymous_is_sent_to_login(self):
        self.client.logout()
        for name in PANEL_URLS:
            with self.subTest(name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("accounts:login"), response["Location"])

    def test_customer_is_forbidden(self):
        self.client.force_login(self.customer)
        for name in PANEL_URLS:
            with self.subTest(name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_employee_and_owner_can_open_panel(self):
        for user in (self.employee, self.owner):
            self.client.force_login(user)
            for name in PANEL_URLS:
                with self.subTest(role=user.role, page=name):
                    self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_deactivated_employee_loses_access(self):
        User.objects.filter(pk=self.employee.pk).update(is_active=False)
        response = self.client.get(reverse("staff:home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_panel_pages_are_read_only(self):
        for name in PANEL_URLS:
            with self.subTest(name):
                self.assertEqual(self.client.post(reverse(name), {"role": "OWNER"}).status_code, 405)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role, User.Role.EMPLOYEE)

    def test_pages_are_not_cached(self):
        for name in PANEL_URLS:
            with self.subTest(name):
                self.assertIn("no-store", self.client.get(reverse(name))["Cache-Control"])

    def test_employee_login_lands_on_panel(self):
        self.assertRedirects(self.client.get(reverse("accounts:home")), reverse("staff:home"))


class EscalationTests(PanelTestCase):
    """El empleado no puede tocar roles, saldos ni configuración."""

    def test_employee_cannot_open_admin(self):
        for url in (
            reverse("admin:index"),
            reverse("admin:accounts_user_changelist"),
            reverse("admin:accounts_user_change", args=[self.employee.pk]),
        ):
            with self.subTest(url):
                self.assertNotEqual(self.client.get(url).status_code, 200)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role, User.Role.EMPLOYEE)

    def test_employee_cannot_adjust_points(self):
        with self.assertRaises(PermissionDenied):
            ledger.adjust_points(
                actor=self.employee, customer=self.customer, points=100, reason="x", idempotency_key=uuid.uuid4()
            )
        self.assertEqual(ledger.balance(self.customer), 0)

    def test_panel_offers_no_management_actions(self):
        for name in PANEL_URLS:
            with self.subTest(name):
                response = self.client.get(reverse(name))
                self.assertNotContains(response, reverse("admin:index"))
                self.assertNotContains(response, 'name="role"')
                self.assertNotContains(response, 'name="points"')


class HomeTests(PanelTestCase):
    def test_big_actions_and_navigation(self):
        response = self.client.get(reverse("staff:home"))
        for name in ("purchases:scan", "rewards_panel:scan", "staff:results", "staff:profile"):
            self.assertContains(response, reverse(name))
        self.assertContains(response, "panel-tile")
        self.assertContains(response, 'aria-label="Panel del personal"')

    def test_today_summary_counts_only_own_operations_of_today(self):
        buy(self.employee, self.token, "10.00")
        buy(self.employee, self.token, "2.50")
        move_purchase(buy(self.employee, self.token, "99.00"), days=3)
        buy(self.other_employee, self.token, "50.00")
        self.validated_redemption()
        self.validated_redemption(staff=self.other_employee)
        summary = self.client.get(reverse("staff:home")).context["today"]
        self.assertEqual(summary["purchases_count"], 2)
        self.assertEqual(summary["purchases_amount"], Decimal("12.50"))
        self.assertEqual(summary["validations_count"], 1)

    def test_header_shows_panel_link_to_staff_only(self):
        self.assertContains(self.client.get(reverse("web:home")), reverse("staff:home"))
        self.client.force_login(self.customer)
        self.assertNotContains(self.client.get(reverse("web:home")), reverse("staff:home"))


class ProfileTests(PanelTestCase):
    def test_shows_own_access_data_and_account_links(self):
        response = self.client.get(reverse("staff:profile"))
        self.assertContains(response, self.employee.email)
        self.assertContains(response, "Empleado")
        self.assertContains(response, reverse("accounts:email_change"))
        self.assertContains(response, reverse("accounts:password_change"))
        self.assertNotContains(response, self.other_employee.email)
        self.assertNotContains(response, "<form method=\"post\" novalidate")


class ResultsTests(PanelTestCase):
    def results(self, **params):
        return self.client.get(reverse("staff:results"), params)

    def test_defaults_to_todays_purchases(self):
        purchase = buy(self.employee, self.token, "12.50")
        response = self.results()
        self.assertEqual((response.context["kind"], response.context["period"]), ("compras", "hoy"))
        self.assertContains(response, reverse("purchases:detail", args=[purchase.public_id]))
        self.assertContains(response, "12,50 €")
        self.assertContains(response, "+12 pts")
        self.assertContains(response, CUSTOMER_NAME)

    def test_lists_only_own_purchases_even_for_owner(self):
        own = buy(self.employee, self.token)
        other = buy(self.other_employee, self.token)
        response = self.results()
        self.assertContains(response, str(own.public_id))
        self.assertNotContains(response, str(other.public_id))
        self.client.force_login(self.owner)
        response = self.results()
        self.assertNotContains(response, str(own.public_id))
        self.assertNotContains(response, str(other.public_id))

    def test_other_employees_purchase_detail_is_404(self):
        other = buy(self.other_employee, self.token)
        self.assertEqual(self.client.get(reverse("purchases:detail", args=[other.public_id])).status_code, 404)

    def test_period_filter(self):
        today = buy(self.employee, self.token)
        week = buy(self.employee, self.token)
        month = buy(self.employee, self.token)
        old = buy(self.employee, self.token)
        move_purchase(week, days=5)
        move_purchase(month, days=20)
        move_purchase(old, days=40)
        expected = {"hoy": {today}, "7d": {today, week}, "30d": {today, week, month}}
        for period, purchases in expected.items():
            with self.subTest(period):
                listed = {item for item, _ in self.results(periodo=period).context["rows"]}
                self.assertEqual(listed, purchases)

    def test_period_start_is_local_midnight(self):
        now = timezone.make_aware(datetime.datetime(2026, 3, 10, 0, 30))
        self.assertEqual(period_start("hoy", now), timezone.make_aware(datetime.datetime(2026, 3, 10)))
        self.assertEqual(period_start("7d", now), timezone.make_aware(datetime.datetime(2026, 3, 4)))

    def test_validated_redemptions_tab(self):
        own = self.validated_redemption()
        other = self.validated_redemption(staff=self.other_employee)
        response = self.results(tipo="canjes")
        self.assertContains(response, reverse("rewards_panel:detail", args=[own.public_id]))
        self.assertNotContains(response, str(other.public_id))
        self.assertContains(response, own.reward.name)
        self.assertNotContains(response, own.code)

    def test_pending_redemptions_are_not_listed(self):
        reward = make_reward()
        give_points(self.customer, reward.points_cost, owner=self.owner)
        pending = redeem(self.customer, reward).redemption
        self.assertNotContains(self.results(tipo="canjes"), str(pending.public_id))

    def test_unknown_filters_fall_back_to_defaults(self):
        response = self.results(tipo="<script>", periodo="365d", page="abc")
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.context["kind"], response.context["period"]), ("compras", "hoy"))
        self.assertNotContains(response, "<script>")

    def test_pagination(self):
        for _ in range(staff_views.RESULTS_PAGE_SIZE + 1):
            buy(self.employee, self.token, "1.00")
        first = self.results()
        self.assertEqual(len(first.context["rows"]), staff_views.RESULTS_PAGE_SIZE)
        self.assertContains(first, "page=2")
        self.assertEqual(len(self.results(page=2).context["rows"]), 1)
        self.assertEqual(self.results(page=999).status_code, 200)

    def test_empty_states(self):
        self.assertContains(self.results(), "No has registrado ninguna compra")
        self.assertContains(self.results(tipo="canjes"), "No has validado ningún canje")

    def test_results_query_count_does_not_grow_with_rows(self):
        for _ in range(5):
            buy(self.employee, self.token)
        self.results()  # calienta la sesión
        with self.assertNumQueries(6):
            self.results()
        for _ in range(5):
            buy(self.employee, self.token)
        with self.assertNumQueries(6):
            self.results()


class PrivacyTests(PanelTestCase):
    def test_no_personal_data_balance_or_history_in_panel(self):
        buy(self.employee, self.token)
        self.validated_redemption()
        pages = [reverse(name) for name in PANEL_URLS] + [reverse("staff:results") + "?tipo=canjes"]
        for url in pages:
            with self.subTest(url):
                response = self.client.get(url)
                for value in PRIVATE_VALUES:
                    self.assertNotContains(response, value)
                self.assertNotContains(response, self.token)
                self.assertNotContains(response, "Saldo")


class PanelFlowTests(PanelTestCase):
    """Escaneo -> confirmación -> resultado, a través de las vistas reales."""

    def test_purchase_flow_shows_visible_confirmation_and_appears_in_results(self):
        scan = self.client.get(reverse("purchases:scan"))
        self.assertContains(scan, 'aria-current="page">Compra')
        self.assertContains(scan, "data-qr-scanner")
        confirm = self.client.post(reverse("purchases:identify"), {"code": self.token})
        self.assertContains(confirm, CUSTOMER_NAME)
        self.assertContains(confirm, "text-2xl font-bold")
        response = self.client.post(
            reverse("purchases:register"),
            {
                "code": hidden_value(confirm, "code"),
                "idempotency_key": hidden_value(confirm, "idempotency_key"),
                "amount": "8,40",
            },
            follow=True,
        )
        self.assertContains(response, "data-operation-done")
        self.assertContains(response, "Compra registrada")
        purchase = Purchase.objects.get()
        self.assertContains(self.client.get(reverse("staff:results")), str(purchase.public_id))
        self.assertEqual(self.client.get(reverse("staff:home")).context["today"]["purchases_count"], 1)

    def test_invalid_qr_shows_clear_error_and_registers_nothing(self):
        response = self.client.post(reverse("purchases:identify"), {"code": "CF1:" + "A" * 32})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'role="alert"', status_code=400)
        self.assertFalse(Purchase.objects.exists())

    def test_redemption_flow_shows_visible_confirmation_and_appears_in_results(self):
        reward = make_reward()
        give_points(self.customer, reward.points_cost, owner=self.owner)
        redemption = redeem(self.customer, reward).redemption
        scan = self.client.get(reverse("rewards_panel:scan"))
        self.assertContains(scan, 'aria-current="page">Canje')
        lookup = self.client.post(reverse("rewards_panel:lookup"), {"code": redemption.code})
        self.assertContains(lookup, "Validar y entregar")
        response = self.client.post(
            reverse("rewards_panel:validate"), {"code": hidden_value(lookup, "code")}, follow=True
        )
        self.assertContains(response, "data-operation-done")
        redemption.refresh_from_db()
        self.assertEqual(redemption.status, Redemption.Status.USED)
        self.assertContains(self.client.get(reverse("staff:results"), {"tipo": "canjes"}), str(redemption.public_id))

    def test_used_code_cannot_be_validated_twice(self):
        redemption = self.validated_redemption()
        response = self.client.post(reverse("rewards_panel:validate"), {"code": redemption.code})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'role="alert"', status_code=400)
        self.assertEqual(Redemption.objects.filter(status=Redemption.Status.USED).count(), 1)


class SelectorTests(PanelTestCase):
    def test_summary_ignores_voided_purchases(self):
        buy(self.employee, self.token, "5.00")
        voided = buy(self.employee, self.token, "7.00")
        Purchase.objects.filter(pk=voided.pk).update(status=Purchase.Status.VOIDED)
        count, amount = purchase_selectors.staff_purchases_summary(self.employee, since=period_start("hoy"))
        self.assertEqual((count, amount), (1, Decimal("5.00")))
