"""
Concurrencia real con hilos en el registro de compras (ver `tests/concurrency.py`).
Se omite con la BD de test de SQLite en memoria; la verificación es en PostgreSQL.
"""
import uuid

from apps.loyalty import ledger
from apps.loyalty.models import PointsTransaction
from apps.purchases import services
from apps.purchases.models import Purchase
from tests.concurrency import ConcurrencyTestCase
from tests.loyalty.factories import make_customer_with_qr, make_employee


class ConcurrentPurchaseTests(ConcurrencyTestCase):
    def setUp(self):
        super().setUp()
        self.customer, self.token = make_customer_with_qr()
        self.staff = [make_employee(f"empleado{i}@example.com") for i in range(self.threads)]

    def test_double_submit_with_same_key_creates_one_purchase(self):
        """El mismo envío repetido a la vez (doble clic, reintento): una compra y unos puntos."""
        key = uuid.uuid4()
        outcomes = self.run_in_threads(
            lambda i: services.register_purchase(
                staff=self.staff[0], qr_code=self.token, amount="12.50", idempotency_key=key
            )
        )
        self.assert_only_expected(outcomes, set())
        results = self.successes(outcomes)
        self.assertEqual(sum(1 for r in results if r.created), 1, outcomes)
        self.assertEqual(Purchase.objects.count(), 1)
        self.assertEqual(PointsTransaction.objects.filter(kind=PointsTransaction.Kind.EARN_PURCHASE).count(), 1)
        self.assertEqual(ledger.balance(self.customer), 12)

    def test_concurrent_purchases_of_same_customer_keep_balance_consistent(self):
        """Cuatro empleados registran a la vez compras distintas del mismo cliente."""
        outcomes = self.run_in_threads(
            lambda i: services.register_purchase(
                staff=self.staff[i], qr_code=self.token, amount="12.50", idempotency_key=uuid.uuid4()
            )
        )
        self.assert_only_expected(outcomes, set())
        created = len(self.successes(outcomes))
        if self.row_locking():
            # En PostgreSQL esperan su turno: se registran todas.
            self.assertEqual(created, self.threads, outcomes)
        self.assertEqual(Purchase.objects.filter(customer=self.customer).count(), created)
        self.assertEqual(ledger.balance(self.customer), 12 * created)
        # Con la fila del cliente bloqueada, cada movimiento ve el saldo del anterior.
        balances = sorted(
            PointsTransaction.objects.filter(customer=self.customer).values_list("balance_after", flat=True)
        )
        self.assertEqual(balances, [12 * (n + 1) for n in range(created)])
