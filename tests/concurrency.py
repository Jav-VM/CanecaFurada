"""
Base para las pruebas de concurrencia real con hilos.

Cada hilo abre su propia conexión, así que la BD de test tiene que poder
compartirse: PostgreSQL (`DATABASE_URL`) o SQLite en fichero. Con la BD de
SQLite en memoria (la de por defecto) se omiten.

Con SQLite en fichero las escrituras simultáneas las rechaza la propia BD
(`database is locked`): se acepta como rechazo, pero no ejercita los bloqueos
de fila. La verificación que cuenta es la de PostgreSQL, donde cualquier error
inesperado (interbloqueo incluido) hace fallar la prueba.
"""
import threading

from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase


def shared_test_db():
    # La BD de test de SQLite en memoria no se comparte entre hilos; con una BD
    # en fichero (o PostgreSQL) sí.
    return not (connection.vendor == "sqlite" and connection.is_in_memory_db())


class ConcurrencyTestCase(TransactionTestCase):
    threads = 4

    def setUp(self):
        if not shared_test_db():
            self.skipTest("La BD de test de SQLite en memoria no admite varias conexiones")
        cache.clear()

    def run_in_threads(self, target):
        """Ejecuta `target(i)` en `threads` hilos que arrancan a la vez. Devuelve los resultados."""
        barrier = threading.Barrier(self.threads)
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
            except PermissionDenied as exc:
                with lock:
                    outcomes.append(("denied", str(exc)))
            except Exception as exc:  # noqa: BLE001 - se informa en la aserción
                with lock:
                    outcomes.append(("unexpected", repr(exc)))
            finally:
                close_old_connections()
                connection.close()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(self.threads)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertEqual(len(outcomes), self.threads, "Algún hilo no terminó a tiempo")
        return outcomes

    def assert_only_expected(self, outcomes, allowed_errors):
        # SQLite rechaza una escritura simultánea con "database is locked": es
        # un rechazo, nunca un segundo consumo. En PostgreSQL no se admite.
        sqlite = connection.vendor == "sqlite"
        bad = [o for o in outcomes if o[0] in ("unexpected", "denied") and not (sqlite and "locked" in o[1])]
        bad += [o for o in outcomes if o[0] == "error" and o[1] not in allowed_errors]
        self.assertFalse(bad, outcomes)

    @staticmethod
    def successes(outcomes):
        return [o[1] for o in outcomes if o[0] == "ok"]

    @staticmethod
    def row_locking():
        """Bloqueo de filas real (PostgreSQL): las operaciones esperan en vez de fallar y los recuentos son exactos."""
        return connection.vendor == "postgresql"
