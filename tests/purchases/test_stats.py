"""Estadísticas: compras registradas frente a facturación, puntos del programa y permisos."""
import datetime
import uuid
from decimal import Decimal

from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from apps.loyalty import ledger, selectors as loyalty_selectors
from apps.purchases import selectors
from apps.purchases.models import Purchase
from tests.loyalty.factories import buy, make_customer_with_qr, make_employee, make_owner


class RegisteredPurchasesStatsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_owner()
        self.employee = make_employee()
        self.customer, self.token = make_customer_with_qr()
        self.other, self.other_token = make_customer_with_qr("otra@example.com")

    def test_registered_purchases_are_not_business_revenue(self):
        buy(self.employee, self.token, "10.00")
        buy(self.employee, self.token, "5.00")
        buy(self.employee, self.other_token, "0.01")
        voided = buy(self.employee, self.other_token, "100.00")
        Purchase.objects.filter(pk=voided.pk).update(status=Purchase.Status.VOIDED)
        stats = selectors.registered_purchases_stats(actor=self.owner)
        self.assertEqual(stats.purchases_count, 3)
        self.assertEqual(stats.customers_count, 2)
        self.assertEqual(stats.registered_amount, Decimal("15.01"))
        self.assertEqual(stats.average_amount, Decimal("5.00"))  # 5,0033 -> 5,00
        self.assertIsNone(stats.business_revenue)
        self.assertIn("No es la facturación total", stats.note)
        self.assertIn("Compras registradas", stats.label)

    def test_empty_period(self):
        stats = selectors.registered_purchases_stats(actor=self.owner)
        self.assertEqual((stats.purchases_count, stats.registered_amount, stats.average_amount), (0, Decimal("0.00"), None))

    def test_period_filter(self):
        old = buy(self.employee, self.token, "10.00")
        Purchase.objects.filter(pk=old.pk).update(created_at=timezone.now() - datetime.timedelta(days=40))
        buy(self.employee, self.token, "7.00")
        start = timezone.now() - datetime.timedelta(days=30)
        stats = selectors.registered_purchases_stats(actor=self.owner, start=start)
        self.assertEqual(stats.registered_amount, Decimal("7.00"))
        stats = selectors.registered_purchases_stats(actor=self.owner, end=start)
        self.assertEqual(stats.registered_amount, Decimal("10.00"))

    def test_only_owner(self):
        for actor in (None, self.employee, self.customer):
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionDenied):
                    selectors.registered_purchases_stats(actor=actor)
                with self.assertRaises(PermissionDenied):
                    loyalty_selectors.points_stats(actor=actor)

    def test_points_stats(self):
        buy(self.employee, self.token, "30.00")
        buy(self.employee, self.other_token, "10.00")
        ledger.adjust_points(
            actor=self.owner, customer=self.customer, points=-5, reason="Corrección", idempotency_key=uuid.uuid4()
        )
        stats = loyalty_selectors.points_stats(actor=self.owner)
        self.assertEqual(stats.issued, 40)
        self.assertEqual(stats.used, 0)
        self.assertEqual(stats.corrected, 5)
        self.assertEqual(stats.outstanding, 35)
        self.assertEqual(stats.customers_with_points, 2)

    def test_customer_purchase_history_includes_points(self):
        buy(self.employee, self.token, "12.50")
        buy(self.employee, self.token, "0.50")
        history = list(selectors.customer_purchases(self.customer).values_list("amount", "points"))
        self.assertEqual(history, [(Decimal("0.50"), 0), (Decimal("12.50"), 12)])
        self.assertEqual(selectors.customer_purchases(self.other).count(), 0)
