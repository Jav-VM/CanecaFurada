"""
Concurrencia real con hilos en la regla del último propietario (ver
`tests/concurrency.py`). Se omite con la BD de test de SQLite en memoria; la
verificación es en PostgreSQL.

R-1 (docs/refactorizacion-final.md): `change_role` y `set_user_active`
bloquean primero a los propietarios activos (en orden de pk) y después al
usuario afectado. Con ese orden único, dos propietarios que se retiran
mutuamente a la vez esperan su turno: no hay interbloqueo y queda uno activo.
"""
import threading
import time

from django.db import close_old_connections, connection, transaction

from apps.accounts import services
from apps.accounts.models import User
from tests.accounts.factories import make_user
from tests.concurrency import ConcurrencyTestCase

ROUNDS = 5


class LastOwnerConcurrencyTests(ConcurrencyTestCase):
    threads = 2

    def setUp(self):
        super().setUp()
        self.owners = [make_user(email=f"dueno{i}@example.com", role=User.Role.OWNER) for i in range(3)]

    def reset(self):
        User.objects.filter(pk__in=[o.pk for o in self.owners]).update(role=User.Role.OWNER, is_active=True)

    def assert_one_owner_left(self, outcomes):
        # Una operación gana. La otra se rechaza porque su actor ya fue retirado
        # (PermissionDenied) o por la regla del último propietario; nunca por
        # interbloqueo. Con SQLite en fichero se admite además la BD bloqueada.
        sqlite = connection.vendor == "sqlite"
        for kind, detail in outcomes:
            if kind == "unexpected":
                self.assertTrue(sqlite and "locked" in detail, outcomes)
            elif kind == "error":
                self.assertIsNone(detail, outcomes)
        self.assertEqual(len(self.successes(outcomes)), 1, outcomes)
        self.assertEqual(User.objects.filter(role=User.Role.OWNER, is_active=True).count(), 1, outcomes)

    def test_two_owners_deactivating_each_other_leave_one_active(self):
        User.objects.filter(pk=self.owners[2].pk).update(is_active=False)
        a, b = self.owners[:2]
        for _ in range(ROUNDS):
            outcomes = self.run_in_threads(
                lambda i: services.set_user_active(actor=(a, b)[i], user=(b, a)[i], is_active=False)
            )
            self.assert_one_owner_left(outcomes)
            self.reset()
            User.objects.filter(pk=self.owners[2].pk).update(is_active=False)

    def test_two_owners_demoting_each_other_leave_one_active(self):
        User.objects.filter(pk=self.owners[2].pk).update(is_active=False)
        a, b = self.owners[:2]
        for _ in range(ROUNDS):
            outcomes = self.run_in_threads(
                lambda i: services.change_role(actor=(a, b)[i], user=(b, a)[i], new_role=User.Role.EMPLOYEE)
            )
            self.assert_one_owner_left(outcomes)
            self.reset()
            User.objects.filter(pk=self.owners[2].pk).update(is_active=False)

    def test_owner_deactivated_while_waiting_cannot_act(self):
        """
        A desactiva a B y mantiene la transacción abierta; mientras tanto B
        (todavía activo para quien lee sin bloquear) intenta desactivar a C.
        Cuando A confirma, la operación de B ya no está autorizada.
        """
        if not self.row_locking():
            self.skipTest("Necesita bloqueo de filas real (PostgreSQL)")
        a, b, c = self.owners
        locked, result = threading.Event(), {}

        def owner_a():
            try:
                with transaction.atomic():
                    services.set_user_active(actor=a, user=b, is_active=False)
                    locked.set()
                    time.sleep(0.5)  # B llega a la espera del bloqueo
            finally:
                close_old_connections()
                connection.close()

        def owner_b():
            try:
                services.set_user_active(actor=b, user=c, is_active=False)
                result["outcome"] = "ok"
            except Exception as exc:  # noqa: BLE001 - se comprueba abajo
                result["outcome"] = type(exc).__name__
            finally:
                close_old_connections()
                connection.close()

        first = threading.Thread(target=owner_a)
        first.start()
        self.assertTrue(locked.wait(timeout=10))
        second = threading.Thread(target=owner_b)
        second.start()
        first.join(timeout=30)
        second.join(timeout=30)

        self.assertEqual(result.get("outcome"), "PermissionDenied")
        self.assertEqual(
            set(User.objects.filter(role=User.Role.OWNER, is_active=True).values_list("pk", flat=True)), {a.pk, c.pk}
        )
