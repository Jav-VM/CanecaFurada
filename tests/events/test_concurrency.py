"""
Concurrencia real con hilos en las reservas de eventos (ver `tests/concurrency.py`).
Se omite con la BD de test de SQLite en memoria; la verificación es en PostgreSQL.
"""
from apps.events import services
from apps.events.models import Reservation
from tests.concurrency import ConcurrencyTestCase
from tests.loyalty.factories import make_owner, make_verified_customer

from .factories import make_event, reserve


class ConcurrentReservationTests(ConcurrencyTestCase):
    def setUp(self):
        super().setUp()
        self.owner = make_owner()
        self.event = make_event(capacity=10)
        # Cuatro solicitudes pendientes de 3 plazas: confirmarlas todas daría 12 > 10.
        self.reservations = [
            reserve(make_verified_customer(f"cliente{i}@example.com"), event=self.event, party_size=3).reservation
            for i in range(self.threads)
        ]

    def test_concurrent_confirmations_never_exceed_capacity(self):
        outcomes = self.run_in_threads(
            lambda i: services.confirm_reservation(actor=self.owner, reservation=self.reservations[i])
        )
        self.assert_only_expected(outcomes, {"event_full"})
        confirmed = len(self.successes(outcomes))
        if self.row_locking():
            # Caben tres de cuatro y la cuarta recibe `event_full`.
            self.assertEqual(confirmed, 3, outcomes)
        self.assertLessEqual(confirmed, 3, outcomes)
        self.assertEqual(services.confirmed_seats(self.event), 3 * confirmed)
        self.assertLessEqual(services.confirmed_seats(self.event), self.event.capacity)

    def test_same_reservation_confirmed_and_cancelled_at_the_same_time(self):
        """El propietario confirma mientras el cliente cancela: un único estado final."""
        reservation = self.reservations[0]

        def target(i):
            if i % 2 == 0:
                return services.confirm_reservation(actor=self.owner, reservation=reservation)
            return services.cancel_own_reservation(customer=reservation.customer, reservation=reservation)

        outcomes = self.run_in_threads(target)
        self.assert_only_expected(outcomes, {"invalid_transition"})
        reservation.refresh_from_db()
        self.assertIn(reservation.status, (Reservation.Status.CONFIRMED, Reservation.Status.CANCELLED))
