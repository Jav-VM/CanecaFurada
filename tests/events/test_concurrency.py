"""
Concurrencia real con hilos en las reservas de eventos (ver `tests/concurrency.py`).
Se omite con la BD de test de SQLite en memoria; la verificación es en PostgreSQL.
"""
import uuid

from django.test import override_settings

from apps.events import services
from apps.events.models import Reservation
from tests.concurrency import ConcurrencyTestCase
from tests.loyalty.factories import make_owner, make_verified_customer

from .factories import make_event, reserve, table_time


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


class ConcurrentReservationRequestTests(ConcurrencyTestCase):
    """Solicitudes simultáneas del mismo cliente (doble envío o varias pestañas)."""

    def setUp(self):
        super().setUp()
        self.customer = make_verified_customer("cliente@example.com")

    def test_same_idempotency_key_creates_a_single_reservation(self):
        key = uuid.uuid4()
        outcomes = self.run_in_threads(lambda i: reserve(self.customer, key=key))
        self.assert_only_expected(outcomes, set())
        results = self.successes(outcomes)
        if self.row_locking():
            self.assertEqual(len(results), self.threads, outcomes)
            self.assertEqual(len({result.reservation.pk for result in results}), 1)
        self.assertLessEqual(sum(result.created for result in results), 1)
        self.assertEqual(Reservation.objects.filter(idempotency_key=key).count(), 1)

    @override_settings(EVENTS_MAX_ACTIVE_RESERVATIONS_PER_CUSTOMER=3)
    def test_concurrent_requests_never_exceed_active_limit(self):
        outcomes = self.run_in_threads(lambda i: reserve(self.customer, requested_for=table_time(days=3 + i)))
        self.assert_only_expected(outcomes, {"too_many_active"})
        created = len(self.successes(outcomes))
        if self.row_locking():
            # Caben tres de cuatro y la cuarta recibe `too_many_active`.
            self.assertEqual(created, 3, outcomes)
        self.assertLessEqual(created, 3, outcomes)
        self.assertEqual(Reservation.objects.filter(customer=self.customer).count(), created)

    def test_same_event_requested_twice_at_the_same_time(self):
        event = make_event(capacity=10)
        outcomes = self.run_in_threads(lambda i: reserve(self.customer, event=event))
        self.assert_only_expected(outcomes, {"already_reserved"})
        if self.row_locking():
            self.assertEqual(len(self.successes(outcomes)), 1, outcomes)
        self.assertEqual(Reservation.objects.filter(customer=self.customer, event=event).count(), 1)
