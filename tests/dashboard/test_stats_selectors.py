"""
Selectores de estadísticas y listados del propietario: periodo `[start, end)`
y cifras de situación actual.

Tests de caracterización añadidos antes de la refactorización final (ver
docs/refactorizacion-final.md): fijan el comportamiento de cada filtro de
periodo y de cada campo de `RedemptionStats` y `ReservationStats`.
"""
import datetime

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.accounts import selectors as accounts_selectors
from apps.accounts.models import User
from apps.events import selectors as event_selectors
from apps.events.models import Event, Reservation
from apps.loyalty import selectors as loyalty_selectors
from apps.loyalty.models import PointsTransaction
from apps.purchases import selectors as purchase_selectors
from apps.purchases.models import Purchase
from apps.rewards import selectors as reward_selectors
from apps.rewards import services as rewards
from apps.rewards.models import Redemption
from tests.dashboard.test_access import DashboardTestCase
from tests.events.factories import make_event, reserve, table_time
from tests.loyalty.factories import buy, make_verified_customer
from tests.rewards.factories import give_points, make_reward, redeem

HOUR = datetime.timedelta(hours=1)


class PeriodBoundaryTests(DashboardTestCase):
    """
    Todo lo registrado exactamente en el instante `T`: un periodo que empieza
    en `T` lo incluye y uno que termina en `T` lo excluye.
    """

    def setUp(self):
        super().setUp()
        self.t = timezone.now() - datetime.timedelta(days=10)
        buy(self.employee, self.token, "10.00")
        give_points(self.customer, 100, owner=self.owner)
        used = redeem(self.customer, make_reward(name="Caña")).redemption
        rewards.validate_redemption(staff=self.employee, code=used.code)
        cancelled = redeem(self.customer, make_reward(name="Tapa")).redemption
        rewards.cancel_redemption(customer=self.customer, redemption=cancelled)
        reserve(self.customer)

        Purchase.objects.update(created_at=self.t)
        PointsTransaction.objects.update(created_at=self.t)
        Redemption.objects.update(created_at=self.t)
        Redemption.objects.filter(status=Redemption.Status.USED).update(validated_at=self.t)
        Redemption.objects.filter(status=Redemption.Status.CANCELLED).update(closed_at=self.t)
        Reservation.objects.update(created_at=self.t, requested_for=self.t)
        User.objects.filter(pk=self.customer.pk).update(date_joined=self.t)

    def measures(self):
        owner = self.owner
        return {
            "purchases.registered_purchases_stats": lambda s, e: purchase_selectors.registered_purchases_stats(
                actor=owner, start=s, end=e
            ).purchases_count,
            "purchases.all_purchases": lambda s, e: purchase_selectors.all_purchases(actor=owner, start=s, end=e).count(),
            "purchases.purchases_by_staff": lambda s, e: sum(
                count for count, _ in purchase_selectors.purchases_by_staff(actor=owner, start=s, end=e).values()
            ),
            "purchases.customer_ids_with_purchases": lambda s, e: purchase_selectors.customer_ids_with_purchases(
                actor=owner, start=s, end=e
            ).count(),
            "rewards.redemption_stats.requested": lambda s, e: reward_selectors.redemption_stats(
                actor=owner, start=s, end=e
            ).requested,
            "rewards.redemption_stats.used": lambda s, e: reward_selectors.redemption_stats(
                actor=owner, start=s, end=e
            ).used,
            "rewards.redemption_stats.closed": lambda s, e: reward_selectors.redemption_stats(
                actor=owner, start=s, end=e
            ).closed,
            "rewards.all_redemptions": lambda s, e: reward_selectors.all_redemptions(actor=owner, start=s, end=e).count(),
            "rewards.validations_by_staff": lambda s, e: sum(
                reward_selectors.validations_by_staff(actor=owner, start=s, end=e).values()
            ),
            "loyalty.points_stats.issued": lambda s, e: loyalty_selectors.points_stats(actor=owner, start=s, end=e).issued,
            "loyalty.points_stats.used": lambda s, e: loyalty_selectors.points_stats(actor=owner, start=s, end=e).used,
            "loyalty.all_movements": lambda s, e: loyalty_selectors.all_movements(actor=owner, start=s, end=e).count(),
            "accounts.search_customers": lambda s, e: accounts_selectors.search_customers(
                actor=owner, start=s, end=e
            ).count(),
            "accounts.customer_counts.new_in_period": lambda s, e: accounts_selectors.customer_counts(
                actor=owner, start=s, end=e
            ).new_in_period,
            "accounts.geographic_distribution": lambda s, e: accounts_selectors.geographic_distribution(
                actor=owner, level="pais", start=s, end=e
            ).total,
            "events.reservation_stats.requested": lambda s, e: event_selectors.reservation_stats(
                actor=owner, start=s, end=e
            ).requested,
            "events.reservations_for_management": lambda s, e: event_selectors.reservations_for_management(
                actor=owner, start=s, end=e
            ).count(),
        }

    def test_start_is_inclusive_and_end_is_exclusive(self):
        t = self.t
        expected = {
            "purchases.registered_purchases_stats": 1,
            "purchases.all_purchases": 1,
            "purchases.purchases_by_staff": 1,
            "purchases.customer_ids_with_purchases": 1,
            "rewards.redemption_stats.requested": 2,
            "rewards.redemption_stats.used": 1,
            "rewards.redemption_stats.closed": 1,
            "rewards.all_redemptions": 2,
            "rewards.validations_by_staff": 1,
            # 10 de la compra + 100 del ajuste; la devolución del canje cancelado cuenta en "utilizados".
            "loyalty.points_stats.issued": 110,
            "loyalty.points_stats.used": 50,
            # Compra, ajuste, dos canjes y la devolución del cancelado.
            "loyalty.all_movements": 5,
            "accounts.search_customers": 1,
            "accounts.customer_counts.new_in_period": 1,
            "accounts.geographic_distribution": 1,
            "events.reservation_stats.requested": 1,
            "events.reservations_for_management": 1,
        }
        for name, measure in self.measures().items():
            with self.subTest(name):
                self.assertEqual(measure(None, None), expected[name])
                self.assertEqual(measure(t, t + HOUR), expected[name])
                self.assertEqual(measure(t, None), expected[name])
                self.assertEqual(measure(t - HOUR, t), 0)
                self.assertEqual(measure(None, t), 0)
                self.assertEqual(measure(t + HOUR, None), 0)


class RedemptionStatsTests(DashboardTestCase):
    """Cada campo usa su propia fecha: solicitud, validación o cierre."""

    def setUp(self):
        super().setUp()
        self.now = timezone.now()
        give_points(self.customer, 500, owner=self.owner)

    def make(self, name, *, created_days, status, closed_days=None):
        redemption = redeem(self.customer, make_reward(name=name, points_cost=10)).redemption
        if status == Redemption.Status.USED:
            rewards.validate_redemption(staff=self.employee, code=redemption.code)
            Redemption.objects.filter(pk=redemption.pk).update(validated_at=self.now - datetime.timedelta(days=closed_days))
        elif status == Redemption.Status.CANCELLED:
            rewards.cancel_redemption(customer=self.customer, redemption=redemption)
            Redemption.objects.filter(pk=redemption.pk).update(closed_at=self.now - datetime.timedelta(days=closed_days))
        Redemption.objects.filter(pk=redemption.pk).update(created_at=self.now - datetime.timedelta(days=created_days))

    def test_each_field_counts_by_its_own_date(self):
        Status = Redemption.Status
        self.make("Pedido antiguo, usado antiguo", created_days=40, status=Status.USED, closed_days=40)
        self.make("Pedido antiguo, usado reciente", created_days=40, status=Status.USED, closed_days=2)
        self.make("Pedido y cancelado reciente", created_days=1, status=Status.CANCELLED, closed_days=1)
        self.make("Pedido y cancelado antiguo", created_days=40, status=Status.CANCELLED, closed_days=40)
        self.make("Pendiente antiguo", created_days=40, status=Status.PENDING)
        self.make("Pendiente reciente", created_days=1, status=Status.PENDING)
        last_30 = self.now - datetime.timedelta(days=30)
        ten_days_ago = self.now - datetime.timedelta(days=10)
        cases = [
            ((None, None), reward_selectors.RedemptionStats(requested=6, used=2, closed=2, pending_now=2)),
            ((last_30, None), reward_selectors.RedemptionStats(requested=2, used=1, closed=1, pending_now=2)),
            ((None, ten_days_ago), reward_selectors.RedemptionStats(requested=4, used=1, closed=1, pending_now=2)),
            ((last_30, ten_days_ago), reward_selectors.RedemptionStats(requested=0, used=0, closed=0, pending_now=2)),
        ]
        for (start, end), expected in cases:
            with self.subTest(start=start, end=end):
                self.assertEqual(reward_selectors.redemption_stats(actor=self.owner, start=start, end=end), expected)

    def test_single_query(self):
        with self.assertNumQueries(1):
            reward_selectors.redemption_stats(actor=self.owner, start=self.now - HOUR, end=self.now)

    def test_expired_redemptions_count_as_closed(self):
        redemption = redeem(self.customer, make_reward(points_cost=10)).redemption
        Redemption.objects.filter(pk=redemption.pk).update(created_at=self.now - 2 * HOUR, expires_at=self.now - HOUR)
        rewards.expire_pending_redemptions()
        stats = reward_selectors.redemption_stats(actor=self.owner)
        self.assertEqual((stats.requested, stats.closed, stats.pending_now), (1, 1, 0))


class ReservationStatsTests(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.now = timezone.now()

    def reservation(self, email, *, status, requested_days, created_days=0):
        customer = make_verified_customer(email)
        reservation = reserve(customer, requested_for=table_time(days=2)).reservation
        Reservation.objects.filter(pk=reservation.pk).update(
            status=status,
            requested_for=self.now + datetime.timedelta(days=requested_days),
            created_at=self.now - datetime.timedelta(days=created_days),
            status_changed_at=None if status == Reservation.Status.PENDING else self.now,
        )

    def test_period_and_current_figures(self):
        Status = Reservation.Status
        self.reservation("a@example.com", status=Status.PENDING, requested_days=3)
        self.reservation("b@example.com", status=Status.PENDING, requested_days=-3)  # pasada: no cuenta como pendiente
        self.reservation("c@example.com", status=Status.CONFIRMED, requested_days=5, created_days=40)
        self.reservation("d@example.com", status=Status.CONFIRMED, requested_days=-1)
        self.reservation("e@example.com", status=Status.COMPLETED, requested_days=-2)
        self.reservation("f@example.com", status=Status.REJECTED, requested_days=4)
        make_event(title="Publicado próximo")
        make_event(title="Borrador", status=Event.Status.DRAFT)
        make_event(title="Ya celebrado", starts_at=self.now - datetime.timedelta(days=2))
        make_event(title="En curso", starts_at=self.now - HOUR)  # no ha terminado, pero ya empezó

        last_30 = self.now - datetime.timedelta(days=30)
        cases = [
            ((None, None), event_selectors.ReservationStats(
                requested=6, confirmed=3, pending_now=1, upcoming_confirmed=1, upcoming_events=1
            )),
            ((last_30, None), event_selectors.ReservationStats(
                requested=5, confirmed=2, pending_now=1, upcoming_confirmed=1, upcoming_events=1
            )),
            ((None, last_30), event_selectors.ReservationStats(
                requested=1, confirmed=1, pending_now=1, upcoming_confirmed=1, upcoming_events=1
            )),
        ]
        for (start, end), expected in cases:
            with self.subTest(start=start, end=end):
                stats = event_selectors.reservation_stats(actor=self.owner, start=start, end=end, now=self.now)
                self.assertEqual(stats, expected)

    def test_one_query_for_reservations_and_one_for_events(self):
        with self.assertNumQueries(2):
            event_selectors.reservation_stats(actor=self.owner, start=self.now - HOUR, end=self.now)

    def test_only_owner(self):
        for actor in (self.employee, self.customer):
            with self.subTest(role=actor.role), self.assertRaises(PermissionDenied):
                event_selectors.reservation_stats(actor=actor)
