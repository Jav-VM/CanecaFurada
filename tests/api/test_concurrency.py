"""
Concurrencia real con hilos en la renovación de tokens de la app (ver `tests/concurrency.py`).
Se omite con la BD de test de SQLite en memoria; la verificación es en PostgreSQL.
"""
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.api import tokens
from tests.concurrency import ConcurrencyTestCase
from tests.loyalty.factories import make_verified_customer


class ConcurrentRefreshTests(ConcurrencyTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_verified_customer("cliente@example.com")
        self.pair = tokens.issue_tokens(self.customer)

    def test_same_refresh_rotated_at_the_same_time_yields_a_single_pair(self):
        """Dos dispositivos (o un reintento de red) presentan el mismo refresh a la vez."""

        def target(i):
            try:
                _, pair = tokens.rotate_refresh_token(self.pair["refresh"])
            except tokens.InvalidRefreshToken:
                return "invalid"
            return pair["refresh"]

        outcomes = self.run_in_threads(target)
        self.assert_only_expected(outcomes, set())
        issued = [result for result in self.successes(outcomes) if result != "invalid"]
        if self.row_locking():
            self.assertEqual(len(issued), 1, outcomes)
        self.assertLessEqual(len(issued), 1, outcomes)
        # El refresh usado queda revocado una sola vez y solo sigue vigente el nuevo.
        self.assertEqual(BlacklistedToken.objects.count(), 1)
        vigentes = OutstandingToken.objects.filter(user=self.customer, blacklistedtoken__isnull=True)
        self.assertEqual(vigentes.count(), len(issued))
