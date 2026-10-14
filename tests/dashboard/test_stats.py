"""Dashboard (Fase 9): estadísticas de negocio, geográficas y filtros por periodo."""
import datetime
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts import selectors as accounts_selectors
from apps.accounts.models import User
from apps.dashboard.forms import PeriodForm
from apps.purchases import selectors as purchase_selectors
from apps.purchases.models import Purchase
from apps.rewards import services as rewards
from tests.accounts.factories import make_user
from tests.dashboard.test_access import DashboardTestCase
from tests.loyalty.factories import buy, make_customer_with_qr, make_verified_customer
from tests.rewards.factories import give_points, make_reward, redeem


def days_ago(days):
    return timezone.now() - datetime.timedelta(days=days)


def move(model, obj, field, days):
    model.objects.filter(pk=obj.pk).update(**{field: days_ago(days)})


class BusinessStatsTests(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.other, self.other_token = make_customer_with_qr("otra@example.com", first_name="Brais")
        buy(self.employee, self.token, "12.50")
        buy(self.employee, self.other_token, "7.00")
        self.voided = buy(self.employee, self.token, "100.00")
        Purchase.objects.filter(pk=self.voided.pk).update(status=Purchase.Status.VOIDED)
        reward = make_reward(points_cost=5)
        redemption = redeem(self.customer, reward).redemption
        rewards.validate_redemption(staff=self.employee, code=redemption.code)

    def home(self, **params):
        return self.client.get(reverse("dashboard:home"), params)

    def test_summary_shows_real_figures(self):
        context = self.home().context
        self.assertEqual(context["customers"].active, 2)
        self.assertEqual(context["purchases"].purchases_count, 2)
        self.assertEqual(context["purchases"].registered_amount, Decimal("19.50"))
        # 12 + 7 puntos de las compras vigentes + 100 de la anulada (el ledger no se toca al anular).
        self.assertEqual(context["points"].issued, 119)
        self.assertEqual(context["points"].used, 5)
        self.assertEqual(context["redemptions"].used, 1)

    def test_registered_purchases_are_not_presented_as_revenue(self):
        response = self.home()
        self.assertContains(response, "Compras registradas en el programa de fidelización")
        self.assertContains(response, "No es la facturación total del local.")
        self.assertNotContains(response, "Facturación total")
        self.assertIsNone(response.context["purchases"].business_revenue)

    def test_events_and_reservations_are_not_invented(self):
        response = self.home()
        self.assertContains(response, 'data-stat="reservations">—<', html=False)
        self.assertContains(response, 'data-stat="events">—<', html=False)
        self.assertContains(response, "Disponible en la Fase 10")

    def test_period_filter_excludes_older_purchases(self):
        old = Purchase.objects.filter(status=Purchase.Status.COMPLETED).order_by("id").first()
        move(Purchase, old, "created_at", 40)
        self.assertEqual(self.home(periodo="30d").context["purchases"].purchases_count, 1)
        self.assertEqual(self.home(periodo="todo").context["purchases"].purchases_count, 2)

    def test_custom_range_and_invalid_range(self):
        old = Purchase.objects.filter(status=Purchase.Status.COMPLETED).order_by("id").first()
        move(Purchase, old, "created_at", 40)
        day = timezone.localdate(days_ago(40))
        context = self.home(periodo="rango", desde=day.isoformat(), hasta=day.isoformat()).context
        self.assertEqual(context["purchases"].purchases_count, 1)
        self.assertEqual(context["period"].key, "rango")
        response = self.home(periodo="rango", desde="2026-05-02", hasta="2026-05-01")
        self.assertContains(response, "La fecha inicial debe ser anterior")
        self.assertEqual(response.context["period"].key, "30d")

    def test_unknown_period_falls_back_to_default(self):
        response = self.home(periodo="<script>")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["period"].key, "30d")
        self.assertNotContains(response, "<script>")

    def test_purchases_section_filters_by_staff_and_status(self):
        other_staff = self.owner
        buy(other_staff, self.token, "3.00")
        url = reverse("dashboard:purchases")
        self.assertEqual(self.client.get(url, {"periodo": "todo"}).context["page"].paginator.count, 4)
        response = self.client.get(url, {"periodo": "todo", "empleado": str(self.owner.public_id)})
        self.assertEqual(response.context["page"].paginator.count, 1)
        response = self.client.get(url, {"periodo": "todo", "estado": "VOIDED"})
        self.assertEqual(response.context["page"].paginator.count, 1)
        # Un empleado inexistente se ignora (no da error ni filtra por otro).
        response = self.client.get(url, {"periodo": "todo", "empleado": "no-es-un-id"})
        self.assertEqual(response.context["page"].paginator.count, 4)

    def test_staff_stats_per_employee(self):
        stats = purchase_selectors.purchases_by_staff(actor=self.owner)
        self.assertEqual(stats[self.employee.pk], (2, Decimal("19.50")))
        response = self.client.get(reverse("dashboard:employees"))
        row = next(r for r in response.context["rows"] if r[0] == self.employee)
        self.assertEqual(row[1], (2, Decimal("19.50")))
        self.assertEqual(row[2], 1)

    def test_points_and_rewards_sections(self):
        response = self.client.get(reverse("dashboard:points"), {"periodo": "todo", "tipo": "REDEMPTION"})
        self.assertEqual(response.context["page"].paginator.count, 1)
        response = self.client.get(reverse("dashboard:rewards"), {"periodo": "todo", "estado": "USED"})
        self.assertEqual(response.context["page"].paginator.count, 1)
        self.assertEqual(response.context["stats"].used, 1)

    def test_redemption_codes_are_never_shown(self):
        give_points(self.other, 50, owner=self.owner)
        pending = redeem(self.other, make_reward(name="Otra")).redemption
        response = self.client.get(reverse("dashboard:rewards"), {"periodo": "todo"})
        self.assertNotContains(response, pending.code)
        self.assertEqual(response.context["stats"].pending_now, 1)


class PeriodFormTests(TestCase):
    def test_range_end_is_inclusive(self):
        period = PeriodForm({"periodo": "rango", "desde": "2026-01-01", "hasta": "2026-01-31"}).period()
        self.assertEqual(timezone.localtime(period.start).date(), datetime.date(2026, 1, 1))
        self.assertEqual(timezone.localtime(period.end).date(), datetime.date(2026, 2, 1))

    def test_range_requires_both_dates_and_limits_span(self):
        self.assertFalse(PeriodForm({"periodo": "rango", "desde": "2026-01-01"}).is_valid())
        self.assertFalse(PeriodForm({"periodo": "rango", "desde": "2000-01-01", "hasta": "2026-01-01"}).is_valid())

    def test_presets(self):
        self.assertIsNone(PeriodForm({"periodo": "todo"}).period().start)
        start = PeriodForm({"periodo": "hoy"}).period().start
        self.assertEqual(timezone.localtime(start).date(), timezone.localdate())


class GeographicStatsTests(DashboardTestCase):
    """Base: 1 cliente de setUp en A Coruña (15001)."""

    def setUp(self):
        super().setUp()
        make_verified_customer("c2@example.com", city="a coruña", province="a coruña", postal_code="15002")
        make_verified_customer(
            "c3@example.com", city="Santiago de Compostela", province="A Coruña", postal_code="15701"
        )
        self.porto = make_verified_customer(
            "c4@example.com", country="PT", city="Porto", province="Porto", postal_code="4000-123"
        )
        # Sin datos de dirección (cliente anterior a la Fase 2): cuenta como "sin dato".
        make_user("sindatos@example.com", role=User.Role.CUSTOMER)
        inactive = make_verified_customer("baja@example.com", city="Lugo", province="Lugo", postal_code="27001")
        User.objects.filter(pk=inactive.pk).update(is_active=False)

    def geo(self, level, **kwargs):
        return accounts_selectors.geographic_distribution(actor=self.owner, level=level, **kwargs)

    def test_groups_by_city_ignoring_case_and_excludes_inactive(self):
        result = self.geo("localidad")
        self.assertEqual(result.total, 5)
        counts = {row.label.lower(): row.count for row in result.rows}
        self.assertEqual(counts, {"a coruña": 2, "santiago de compostela": 1, "porto": 1})
        self.assertEqual(result.unknown_count, 1)
        self.assertEqual(result.rows[0].percent, Decimal("40.0"))
        self.assertNotIn("lugo", counts)

    def test_groups_by_country_province_and_postal_code(self):
        countries = {row.label: row.count for row in self.geo("pais").rows}
        self.assertEqual(countries, {"España": 3, "Portugal": 1})
        provinces = {(row.label.lower(), row.context): row.count for row in self.geo("provincia").rows}
        self.assertEqual(provinces, {("a coruña", "España"): 3, ("porto", "Portugal"): 1})
        codes = {row.label: row.count for row in self.geo("cp").rows}
        self.assertEqual(codes, {"15001": 1, "15002": 1, "15701": 1, "4000-123": 1})

    def test_country_filter_and_limit(self):
        result = self.geo("localidad", country="ES", limit=1)
        self.assertEqual(result.total, 3)
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.others_count, 1)
        self.assertEqual(result.unknown_count, 0)

    def test_period_by_registration_and_by_purchases(self):
        User.objects.filter(email="c4@example.com").update(date_joined=days_ago(100))
        self.assertEqual(self.geo("pais", start=days_ago(30)).total, 4)
        ids = purchase_selectors.customer_ids_with_purchases(actor=self.owner, start=days_ago(30))
        self.assertEqual(self.geo("pais", customer_ids=ids).total, 0)
        buy(self.employee, self.token)
        ids = purchase_selectors.customer_ids_with_purchases(actor=self.owner, start=days_ago(30))
        result = self.geo("pais", customer_ids=ids)
        self.assertEqual((result.total, result.rows[0].label), (1, "España"))

    def test_page_states_source_and_hides_full_addresses(self):
        for level in ("pais", "provincia", "localidad", "cp"):
            with self.subTest(level):
                response = self.client.get(reverse("dashboard:customer_zones"), {"nivel": level})
                self.assertContains(response, "direcciones postales declaradas por los propios clientes")
                self.assertContains(response, "No se usa geolocalización por IP")
                self.assertNotContains(response, "Rúa Ficticia")
                self.assertNotContains(response, "c2@example.com")

    def test_page_filters_and_links_to_customer_list(self):
        response = self.client.get(reverse("dashboard:customer_zones"), {"nivel": "cp", "pais": "PT"})
        self.assertContains(response, "4000-123")
        self.assertNotContains(response, "15001")
        self.assertContains(response, "?pais=PT&amp;cp=4000-123")
        response = self.client.get(reverse("dashboard:customer_zones"), {"base": "compras", "periodo": "7d"})
        self.assertEqual(response.context["distribution"].total, 0)
        self.assertEqual(self.client.get(reverse("dashboard:customer_zones"), {"nivel": "x"}).context["level"], "localidad")
