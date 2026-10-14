"""
Concurrencia real con hilos: varias validaciones del mismo código a la vez.

Se omite con la BD de test de SQLite en memoria (la de por defecto). Para
ejecutarla: con PostgreSQL (`DATABASE_URL`) o con un `TEST.NAME` de SQLite en
fichero (ver docs/fase-07-recompensas-canjes.md).

Con SQLite en fichero las escrituras simultáneas las rechaza la propia BD
(`database is locked`): la prueba demuestra que no hay doble consumo ni saldo
negativo, pero no ejercita los bloqueos de fila. Esa es la verificación que
falta en PostgreSQL (Fase 12), donde no se admite ningún error de bloqueo.
"""
import threading
import uuid

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from apps.core.models import AuditEvent
from apps.loyalty import ledger
from apps.rewards import services
from apps.rewards.models import Redemption, Reward

from .factories import give_points, make_customer_with_qr, make_employee, make_owner, make_reward, redeem

THREADS = 4


def _shared_test_db():
    # La BD de test de SQLite en memoria no se comparte entre hilos; con una BD
    # en fichero (o PostgreSQL) sí.
    return not (connection.vendor == "sqlite" and connection.is_in_memory_db())


class ConcurrentRedemptionTests(TransactionTestCase):
    def setUp(self):
        if not _shared_test_db():
            self.skipTest("La BD de test de SQLite en memoria no admite varias conexiones")
        cache.clear()
        owner = make_owner()
        self.staff = [make_employee(f"empleado{i}@example.com") for i in range(THREADS)]
        self.customer, _ = make_customer_with_qr()
        give_points(self.customer, 100, owner=owner)
        self.redemption = redeem(self.customer, make_reward(points_cost=40)).redemption

    def run_in_threads(self, target):
        barrier = threading.Barrier(THREADS)
        outcomes = []
        lock = threading.Lock()

        def worker(i):
            try:
                barrier.wait()
                result = target(i)
                with lock:
                    outcomes.append(("ok", result))
            except ValidationError as exc:
                with lock:
                    outcomes.append(("error", exc.code))
            except Exception as exc:  # noqa: BLE001 - se informa en la aserción
                with lock:
                    outcomes.append(("unexpected", repr(exc)))
            finally:
                close_old_connections()
                connection.close()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(THREADS)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        return outcomes

    def test_same_code_validated_concurrently_is_used_once(self):
        code = self.redemption.code
        outcomes = self.run_in_threads(lambda i: services.validate_redemption(staff=self.staff[i], code=code))
        self.assert_only_expected(outcomes, {"code_used"})
        self.assertEqual(sum(1 for o in outcomes if o[0] == "ok"), 1, outcomes)
        self.redemption.refresh_from_db()
        self.assertEqual(self.redemption.status, Redemption.Status.USED)
        self.assertEqual(AuditEvent.objects.filter(action=AuditEvent.Action.REDEMPTION_VALIDATED).count(), 1)
        self.assertEqual(ledger.balance(self.customer), 60)

    def assert_only_expected(self, outcomes, allowed_errors):
        # SQLite rechaza una escritura simultánea con "database is locked": es
        # un rechazo, nunca un segundo consumo. En PostgreSQL no se admite.
        sqlite = connection.vendor == "sqlite"
        bad = [o for o in outcomes if o[0] == "unexpected" and not (sqlite and "locked" in o[1])]
        bad += [o for o in outcomes if o[0] == "error" and o[1] not in allowed_errors]
        self.assertFalse(bad, outcomes)

    def test_concurrent_requests_never_overspend(self):
        """Saldo 60 tras el canje inicial; cuatro canjes simultáneos de 40: como mucho uno."""
        rewards = [make_reward(name=f"R{i}", points_cost=40) for i in range(THREADS)]
        outcomes = self.run_in_threads(
            lambda i: services.request_redemption(customer=self.customer, reward=rewards[i], idempotency_key=uuid.uuid4())
        )
        self.assert_only_expected(outcomes, {"insufficient_points"})
        self.assertLessEqual(sum(1 for o in outcomes if o[0] == "ok"), 1, outcomes)
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
