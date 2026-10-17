"""
Ordenación de los listados del dashboard (Fase 18): lista blanca de columnas,
dirección, valores desconocidos, conservación de filtros y acceso.
"""
from django.http import QueryDict
from django.test import SimpleTestCase
from django.urls import reverse

from apps.dashboard.sorting import Sort
from apps.loyalty.models import PointsTransaction
from tests.dashboard.test_access import DashboardTestCase
from tests.loyalty.factories import buy, make_customer_with_qr

COLUMNS = {"nombre": ("last_name", "first_name"), "alta": ("date_joined",)}


def query(text):
    return QueryDict(text)


class SortUnitTests(SimpleTestCase):
    def test_valid_key_and_direction(self):
        sort = Sort(query("orden=alta&dir=desc"), COLUMNS)
        self.assertEqual((sort.key, sort.descending, bool(sort)), ("alta", True, True))

    def test_unknown_or_malicious_values_keep_default(self):
        for text in ("orden=password&dir=asc", "orden=-id;&dir=desc", "orden=alta&dir=sideways", "orden=alta", ""):
            with self.subTest(text=text):
                self.assertFalse(Sort(query(text), COLUMNS))

    def test_prefix_reads_its_own_parameters(self):
        sort = Sort(query("orden=alta&dir=asc&c_orden=nombre&c_dir=desc"), COLUMNS, prefix="c_")
        self.assertEqual((sort.key, sort.descending), ("nombre", True))

    def test_apply_list_puts_missing_values_last(self):
        sort = Sort(query("orden=n&dir=desc"), {"n": lambda item: item})
        self.assertEqual(sort.apply_list([2, None, 5, 1]), [5, 2, 1, None])


class CustomerSortingTests(DashboardTestCase):
    url = reverse("dashboard:customers")

    def setUp(self):
        super().setUp()
        make_customer_with_qr("abel@example.com", first_name="Abel", last_name="Abad")
        make_customer_with_qr("zoe@example.com", first_name="Zoe", last_name="Zapata")

    def names(self, response):
        return [customer.last_name for customer in response.context["page"]]

    def test_ascending_and_descending(self):
        ascending = self.names(self.client.get(self.url, {"orden": "cliente", "dir": "asc"}))
        descending = self.names(self.client.get(self.url, {"orden": "cliente", "dir": "desc"}))
        self.assertEqual(ascending[0], "Abad")
        self.assertEqual(descending[0], "Zapata")
        self.assertEqual(ascending, list(reversed(descending)))

    def test_unknown_column_falls_back_without_error(self):
        response = self.client.get(self.url, {"orden": "password", "dir": "asc"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["sort"])

    def test_headers_have_arrows_and_keep_filters(self):
        response = self.client.get(self.url, {"verificado": "si", "orden": "alta", "dir": "desc", "page": "1"})
        self.assertContains(response, "data-sort-asc")
        self.assertContains(response, 'aria-sort="descending"')
        # Conserva el filtro y vuelve a la primera página.
        self.assertContains(response, 'href="?verificado=si&amp;orden=cliente&amp;dir=asc"')

    def test_only_owner(self):
        for user in (self.employee, self.customer):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url, {"orden": "cliente", "dir": "asc"}).status_code, 403)


class OtherListsSortingTests(DashboardTestCase):
    def setUp(self):
        super().setUp()
        buy(self.employee, self.token, "5.00")
        buy(self.employee, self.token, "40.00")

    def test_purchases_by_amount(self):
        url = reverse("dashboard:purchases")
        ascending = [p.amount for p in self.client.get(url, {"orden": "importe", "dir": "asc"}).context["page"]]
        descending = [p.amount for p in self.client.get(url, {"orden": "importe", "dir": "desc"}).context["page"]]
        self.assertEqual(ascending, sorted(ascending))
        self.assertEqual(descending, sorted(descending, reverse=True))

    def test_points_by_points(self):
        url = reverse("dashboard:points")
        rows = self.client.get(url, {"orden": "puntos", "dir": "desc"}).context["page"]
        values = [m.points for m in rows]
        self.assertEqual(values, sorted(values, reverse=True))
        self.assertEqual(len(values), PointsTransaction.objects.count())

    def test_employees_in_memory(self):
        url = reverse("dashboard:employees")
        rows = self.client.get(url, {"orden": "compras", "dir": "desc"}).context["rows"]
        self.assertEqual(rows[0][0], self.employee)

    def test_two_lists_on_one_page_are_independent(self):
        url = reverse("dashboard:communications")
        response = self.client.get(url, {"c_orden": "campana", "c_dir": "asc", "orden": "fecha", "dir": "desc"})
        self.assertEqual(response.context["campaign_sort"].key, "campana")
        self.assertEqual(response.context["sort"].key, "fecha")

    def test_every_list_accepts_each_of_its_columns(self):
        from apps.dashboard import views

        pages = {
            "dashboard:customers": (views.CUSTOMER_COLUMNS, ""),
            "dashboard:employees": (views.EMPLOYEE_COLUMNS, ""),
            "dashboard:customer_zones": (views.ZONE_COLUMNS, ""),
            "dashboard:purchases": (views.PURCHASE_COLUMNS, ""),
            "dashboard:points": (views.MOVEMENT_COLUMNS, ""),
            "dashboard:rewards": (views.REDEMPTION_COLUMNS, ""),
            "dashboard:promotions": (views.PROMOTION_COLUMNS, ""),
            "dashboard:menu": (views.PRODUCT_COLUMNS, ""),
            "dashboard:beers": (views.PRODUCT_COLUMNS, ""),
            "dashboard:events": (views.EVENT_COLUMNS, ""),
            "dashboard:reservations": (views.RESERVATION_COLUMNS, ""),
            "dashboard:communications": (views.NOTIFICATION_COLUMNS, ""),
        }
        pages_prefixed = {
            "dashboard:rewards": (views.REWARD_COLUMNS, views.REWARD_SORT_PREFIX),
            "dashboard:communications": (views.CAMPAIGN_COLUMNS, views.CAMPAIGN_SORT_PREFIX),
        }
        for name, (columns, prefix) in [*pages.items(), *pages_prefixed.items()]:
            for key in columns:
                for direction in ("asc", "desc"):
                    with self.subTest(page=name, column=key, direction=direction):
                        response = self.client.get(reverse(name), {f"{prefix}orden": key, f"{prefix}dir": direction})
                        self.assertEqual(response.status_code, 200)
