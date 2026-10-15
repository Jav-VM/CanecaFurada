"""
Concurrencia real con hilos en los canjes (ver `tests/concurrency.py`).

Se omite con la BD de test de SQLite en memoria (la de por defecto). Para
ejecutarla: con PostgreSQL (`DATABASE_URL`) o con un `TEST.NAME` de SQLite en
fichero (ver docs/fase-07-recompensas-canjes.md).
"""
import uuid

from apps.core.models import AuditEvent
from apps.loyalty import ledger
from apps.rewards import services
from apps.rewards.models import Redemption, Reward
from tests.concurrency import ConcurrencyTestCase

from .factories import give_points, make_customer_with_qr, make_employee, make_owner, make_reward, redeem


class ConcurrentRedemptionTests(ConcurrencyTestCase):
    def setUp(self):
        super().setUp()
        owner = make_owner()
        self.staff = [make_employee(f"empleado{i}@example.com") for i in range(self.threads)]
        self.customer, _ = make_customer_with_qr()
        give_points(self.customer, 100, owner=owner)
        self.redemption = redeem(self.customer, make_reward(points_cost=40)).redemption

    def test_same_code_validated_concurrently_is_used_once(self):
        code = self.redemption.code
        outcomes = self.run_in_threads(lambda i: services.validate_redemption(staff=self.staff[i], code=code))
        self.assert_only_expected(outcomes, {"code_used"})
        self.assertEqual(len(self.successes(outcomes)), 1, outcomes)
        self.redemption.refresh_from_db()
        self.assertEqual(self.redemption.status, Redemption.Status.USED)
        self.assertEqual(AuditEvent.objects.filter(action=AuditEvent.Action.REDEMPTION_VALIDATED).count(), 1)
        self.assertEqual(ledger.balance(self.customer), 60)

    def test_concurrent_requests_never_overspend(self):
        """Saldo 60 tras el canje inicial; cuatro canjes simultáneos de 40: como mucho uno."""
        rewards = [make_reward(name=f"R{i}", points_cost=40) for i in range(self.threads)]
        outcomes = self.run_in_threads(
            lambda i: services.request_redemption(customer=self.customer, reward=rewards[i], idempotency_key=uuid.uuid4())
        )
        self.assert_only_expected(outcomes, {"insufficient_points"})
        self.assertLessEqual(len(self.successes(outcomes)), 1, outcomes)
        self.assertGreaterEqual(ledger.balance(self.customer), 0)
        self.assertEqual(
            ledger.balance(self.customer), 100 - 40 * Redemption.objects.filter(customer=self.customer).count()
        )

    def test_concurrent_requests_for_same_reward_give_one_pending(self):
        reward = make_reward(name="Única", points_cost=10, stock=10)
        outcomes = self.run_in_threads(
            lambda i: services.request_redemption(customer=self.customer, reward=reward, idempotency_key=uuid.uuid4())
        )
        self.assert_only_expected(outcomes, {"duplicate_pending"})
        self.assertEqual(Redemption.objects.filter(reward=reward).count(), 1)
        self.assertEqual(Reward.objects.get(pk=reward.pk).stock, 9)
        self.assertEqual(ledger.balance(self.customer), 50)

    def test_validate_and_cancel_at_the_same_time(self):
        """
        Dos empleados validan y el cliente cancela dos veces el mismo canje a la
        vez. Sin interbloqueos (auditoría previa a la Fase 12, P2-1): el canje
        acaba usado o cancelado, nunca las dos cosas, y el saldo cuadra.
        """
        code = self.redemption.code

        def target(i):
            if i % 2 == 0:
                return services.validate_redemption(staff=self.staff[i], code=code)
            # Una instancia por hilo: el servicio la refresca y no debe compartirse.
            redemption = Redemption.objects.get(pk=self.redemption.pk)
            return services.cancel_redemption(customer=self.customer, redemption=redemption)

        outcomes = self.run_in_threads(target)
        self.assert_only_expected(outcomes, {"code_used", "code_not_pending"})
        self.redemption.refresh_from_db()
        self.assertIn(self.redemption.status, (Redemption.Status.USED, Redemption.Status.CANCELLED))
        if self.redemption.status == Redemption.Status.USED:
            self.assertIsNone(self.redemption.refund_movement_id)
            self.assertEqual(ledger.balance(self.customer), 60)
        else:
            self.assertIsNone(self.redemption.validated_by_id)
            self.assertEqual(ledger.balance(self.customer), 100)
