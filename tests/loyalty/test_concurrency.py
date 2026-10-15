"""
Concurrencia real con hilos en los ajustes manuales de puntos (ver `tests/concurrency.py`).
Se omite con la BD de test de SQLite en memoria; la verificación es en PostgreSQL.
"""
import uuid

from apps.loyalty import ledger
from apps.loyalty.models import PointsTransaction
from tests.concurrency import ConcurrencyTestCase

from .factories import make_owner, make_verified_customer


class ConcurrentAdjustmentTests(ConcurrencyTestCase):
    def setUp(self):
        super().setUp()
        self.owner = make_owner()
        self.customer = make_verified_customer()
        ledger.adjust_points(
            actor=self.owner, customer=self.customer, points=100, reason="Saldo inicial", idempotency_key=uuid.uuid4()
        )

    def adjust(self, points, key=None):
        return ledger.adjust_points(
            actor=self.owner, customer=self.customer, points=points, reason="Corrección", idempotency_key=key or uuid.uuid4()
        )

    def test_concurrent_negative_adjustments_never_leave_negative_balance(self):
        """Saldo 100; cuatro ajustes simultáneos de -40: solo caben dos."""
        outcomes = self.run_in_threads(lambda i: self.adjust(-40))
        self.assert_only_expected(outcomes, {"insufficient_points"})
        applied = len(self.successes(outcomes))
        if self.row_locking():
            self.assertEqual(applied, 2, outcomes)
        self.assertLessEqual(applied, 2, outcomes)
        self.assertEqual(ledger.balance(self.customer), 100 - 40 * applied)

    def test_same_adjustment_sent_concurrently_is_applied_once(self):
        key = uuid.uuid4()
        outcomes = self.run_in_threads(lambda i: self.adjust(-10, key=key))
        self.assert_only_expected(outcomes, set())
        self.assertEqual(sum(1 for r in self.successes(outcomes) if r.created), 1, outcomes)
        self.assertEqual(PointsTransaction.objects.filter(idempotency_key=key).count(), 1)
        self.assertEqual(ledger.balance(self.customer), 90)
