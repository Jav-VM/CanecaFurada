"""
Caducidad de los puntos (Fase 14): política versionada sin retroactividad,
cálculo FIFO, descuento idempotente, avisos previos, comando y vista del cliente.
"""
import datetime
import uuid
from io import StringIO
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from django.core import mail
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import CommandError, call_command
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditEvent
from apps.loyalty import expirations, expiry, ledger, selectors
from apps.loyalty.models import PointsExpiryPolicy, PointsTransaction
from apps.notifications import services as notifications
from apps.notifications.models import Notification
from tests.concurrency import ConcurrencyTestCase

from .factories import make_customer_with_qr, make_employee, make_owner

MADRID = ZoneInfo("Europe/Madrid")
UTC = datetime.timezone.utc
Kind = PointsTransaction.Kind


def at(year, month, day, hour=12):
    return datetime.datetime(year, month, day, hour, tzinfo=UTC)


# --- Cálculo puro --------------------------------------------------------------------


def mov(pk, points, created_at, kind=None, reverses=None, never_expires=False):
    kind = kind or (Kind.ADJUSTMENT if points > 0 else Kind.REDEMPTION)
    return SimpleNamespace(
        pk=pk, kind=kind, points=points, created_at=created_at, reverses_id=reverses, never_expires=never_expires
    )


def pol(months, counts_from=at(2020, 1, 1)):
    return SimpleNamespace(months=months, counts_from=counts_from)


class AddMonthsTests(SimpleTestCase):
    def test_clamps_to_the_end_of_the_month(self):
        self.assertEqual(expiry.add_months(at(2027, 1, 31), 1), at(2027, 2, 28))
        self.assertEqual(expiry.add_months(at(2028, 1, 31), 1), at(2028, 2, 29))
        self.assertEqual(expiry.add_months(at(2028, 2, 29), 12), at(2029, 2, 28))

    def test_crosses_years_both_ways(self):
        self.assertEqual(expiry.add_months(at(2027, 11, 15), 3), at(2028, 2, 15))
        self.assertEqual(expiry.add_months(at(2027, 2, 15), -3), at(2026, 11, 15))


class FifoTests(SimpleTestCase):
    def test_without_policy_nothing_expires(self):
        movements = [mov(1, 100, at(2020, 1, 1))]
        self.assertEqual(expiry.remaining_lots(movements, None), [])
        self.assertEqual(expiry.remaining_lots(movements, pol(None)), [])
        self.assertEqual(expiry.expirable_points(movements, None, at(2030, 1, 1)), 0)

    def test_debits_consume_the_oldest_points_first(self):
        movements = [mov(1, 100, at(2027, 1, 10)), mov(2, 50, at(2027, 3, 10)), mov(3, -120, at(2027, 4, 1))]
        lots = expiry.remaining_lots(movements, pol(12))
        self.assertEqual([(lot.expires_at, lot.points) for lot in lots], [(at(2028, 3, 10), 30)])

    def test_partial_consumption_and_expirable_amount(self):
        movements = [mov(1, 100, at(2027, 1, 10)), mov(2, -30, at(2027, 2, 1)), mov(3, 50, at(2027, 6, 1))]
        policy = pol(12)
        self.assertEqual(expiry.expirable_points(movements, policy, at(2028, 1, 9)), 0)
        self.assertEqual(expiry.expirable_points(movements, policy, at(2028, 1, 10)), 70)
        self.assertEqual(expiry.expirable_points(movements, policy, at(2028, 6, 1)), 120)

    def test_expiration_counts_as_consumed_so_it_is_idempotent(self):
        movements = [mov(1, 100, at(2027, 1, 10)), mov(2, 50, at(2027, 6, 1))]
        when = at(2028, 2, 1)
        self.assertEqual(expiry.expirable_points(movements, pol(12), when), 100)
        movements.append(mov(3, -100, when, kind=Kind.EXPIRATION))
        self.assertEqual(expiry.expirable_points(movements, pol(12), when), 0)
        self.assertEqual([lot.points for lot in expiry.remaining_lots(movements, pol(12))], [50])

    def test_a_reversed_credit_does_not_count(self):
        movements = [
            mov(1, 100, at(2027, 1, 10), kind=Kind.EARN_PURCHASE),
            mov(2, -100, at(2027, 1, 11), kind=Kind.REVERSAL, reverses=1),
            mov(3, 20, at(2027, 5, 1)),
        ]
        self.assertEqual([lot.points for lot in expiry.remaining_lots(movements, pol(12))], [20])

    def test_a_refunded_redemption_returns_points_with_their_original_date(self):
        movements = [
            mov(1, 100, at(2027, 1, 10)),
            mov(2, -80, at(2027, 2, 1), kind=Kind.REDEMPTION),
            mov(3, 80, at(2027, 2, 8), kind=Kind.REVERSAL, reverses=2),
        ]
        lots = expiry.remaining_lots(movements, pol(12))
        self.assertEqual([(lot.expires_at, lot.points) for lot in lots], [(at(2028, 1, 10), 100)])

    def test_the_term_never_starts_before_counts_from(self):
        movements = [mov(1, 100, at(2020, 5, 1)), mov(2, 40, at(2027, 9, 1))]
        lots = expiry.remaining_lots(movements, pol(6, counts_from=at(2027, 6, 1)))
        self.assertEqual([lot.expires_at for lot in lots], [at(2027, 12, 1), at(2028, 3, 1)])

    def test_next_expiry_adds_the_points_that_expire_the_same_day(self):
        movements = [mov(1, 10, at(2027, 1, 10, 9)), mov(2, 15, at(2027, 1, 10, 18)), mov(3, 40, at(2027, 2, 1))]
        upcoming = expiry.next_expiry(movements, pol(12))
        self.assertEqual((upcoming.date, upcoming.points), (datetime.date(2028, 1, 10), 25))
        self.assertIsNone(expiry.next_expiry([mov(1, 10, at(2027, 1, 1)), mov(2, -10, at(2027, 1, 2))], pol(12)))


# --- Base con BD ---------------------------------------------------------------------


class ExpiryTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_owner()
        self.customer, _ = make_customer_with_qr()

    def credit(self, points, created_at, customer=None):
        movement = ledger.adjust_points(
            actor=self.owner, customer=customer or self.customer, points=points, reason="Prueba", idempotency_key=uuid.uuid4()
        ).movement
        PointsTransaction.objects.filter(pk=movement.pk).update(created_at=created_at)
        return movement

    def spend(self, points, created_at, customer=None):
        with transaction.atomic():
            locked = ledger.lock_customer(customer or self.customer)
            movement = ledger.spend_points(customer=locked, points=points, reason="Canje de prueba")
        PointsTransaction.objects.filter(pk=movement.pk).update(created_at=created_at)
        return movement

    def policy(self, months, counts_from, warn_days=15):
        return PointsExpiryPolicy.objects.create(
            months=months, warn_days=warn_days, counts_from=counts_from, valid_from=counts_from
        )

    def expirations(self, customer=None):
        return list(
            PointsTransaction.objects.filter(customer=customer or self.customer, kind=Kind.EXPIRATION).values_list(
                "points", flat=True
            )
        )


# --- Política -------------------------------------------------------------------------


class PolicyTests(ExpiryTestCase):
    def test_only_the_owner_can_change_it(self):
        for actor in (make_employee(), self.customer):
            with self.assertRaises(PermissionDenied):
                expiry.set_policy(actor=actor, months=12)
        self.assertFalse(PointsExpiryPolicy.objects.exists())

    def test_invalid_values_are_rejected(self):
        for months in (0, 61, True, "12", 1.5):
            with self.assertRaises(ValidationError):
                expiry.set_policy(actor=self.owner, months=months)
        for warn_days in (0, 61, None):
            with self.assertRaises(ValidationError):
                expiry.set_policy(actor=self.owner, months=12, warn_days=warn_days)
        self.assertFalse(PointsExpiryPolicy.objects.exists())

    def test_counts_from_is_decided_by_the_service(self):
        activated, created = expiry.set_policy(actor=self.owner, months=12, note="Inicio")
        self.assertTrue(created)
        self.assertIsNotNone(activated.counts_from)
        # Alargar o cambiar el aviso: el plazo sigue contando desde la activación.
        longer, _ = expiry.set_policy(actor=self.owner, months=18)
        self.assertEqual(longer.counts_from, activated.counts_from)
        warn, _ = expiry.set_policy(actor=self.owner, months=18, warn_days=30)
        self.assertEqual(warn.counts_from, activated.counts_from)
        # Acortar: el nuevo plazo empieza ahora.
        shorter, _ = expiry.set_policy(actor=self.owner, months=6)
        self.assertGreater(shorter.counts_from, activated.counts_from)
        # Quitar y volver a activar.
        disabled, _ = expiry.set_policy(actor=self.owner, months=None)
        self.assertIsNone(disabled.counts_from)
        self.assertIsNone(expiry.active_policy())
        again, _ = expiry.set_policy(actor=self.owner, months=24)
        self.assertGreater(again.counts_from, shorter.counts_from)
        self.assertEqual(expiry.active_policy(), again)
        self.assertEqual(PointsExpiryPolicy.objects.count(), 6)

    def test_no_new_version_without_changes(self):
        first, _ = expiry.set_policy(actor=self.owner, months=12)
        same, created = expiry.set_policy(actor=self.owner, months=12, warn_days=first.warn_days)
        self.assertFalse(created)
        self.assertEqual(same, first)
        _, created = expiry.set_policy(actor=self.owner, months=None)
        self.assertTrue(created)
        _, created = expiry.set_policy(actor=self.owner, months=None, warn_days=40)
        self.assertFalse(created)

    def test_audit_has_no_free_text(self):
        expiry.set_policy(actor=self.owner, months=12, note="Texto libre del propietario")
        event = AuditEvent.objects.get(action=AuditEvent.Action.POINTS_EXPIRY_POLICY_CREATED)
        self.assertEqual(event.actor, self.owner)
        self.assertEqual(event.metadata["months"], 12)
        self.assertNotIn("Texto libre", str(event.metadata))

    def test_database_rejects_inconsistent_policies(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PointsExpiryPolicy.objects.create(months=12, counts_from=None)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PointsExpiryPolicy.objects.create(months=0, counts_from=timezone.now())


# --- Caducidad en el ledger ----------------------------------------------------------


class ExpirePointsTests(ExpiryTestCase):
    def test_activating_does_not_expire_old_points_at_once(self):
        self.credit(100, timezone.now() - datetime.timedelta(days=800))
        expiry.set_policy(actor=self.owner, months=12)
        result = expirations.run()
        self.assertEqual((result.policy, result.expired_points), (True, 0))
        self.assertEqual(ledger.balance(self.customer), 100)
        # Doce meses después de la activación, sí.
        later = timezone.now() + datetime.timedelta(days=370)
        self.assertEqual(expirations.run(at=later).expired_points, 100)
        self.assertEqual(ledger.balance(self.customer), 0)

    def test_expires_fifo_and_is_idempotent(self):
        self.policy(12, at(2026, 1, 1))
        self.credit(100, at(2026, 1, 10))
        self.spend(30, at(2026, 2, 1))
        self.credit(50, at(2026, 6, 1))
        result = expirations.run(at=at(2027, 1, 15))
        self.assertEqual((result.expired_customers, result.expired_points), (1, 70))
        again = expirations.run(at=at(2027, 1, 16))
        self.assertEqual(again.expired_points, 0)
        self.assertEqual(self.expirations(), [-70])
        movement = PointsTransaction.objects.get(kind=Kind.EXPIRATION)
        self.assertEqual((movement.balance_after, movement.reason, movement.created_by), (50, "Puntos caducados", None))
        self.assertEqual(ledger.balance(self.customer), 50)

    def test_without_policy_or_disabled_nothing_happens(self):
        self.credit(100, at(2020, 1, 1))
        self.assertFalse(expirations.run().policy)
        expiry.set_policy(actor=self.owner, months=1)
        expiry.set_policy(actor=self.owner, months=None)
        self.assertFalse(expirations.run(at=timezone.now() + datetime.timedelta(days=400)).policy)
        self.assertEqual(ledger.balance(self.customer), 100)
        self.assertFalse(AuditEvent.objects.filter(action=AuditEvent.Action.POINTS_EXPIRY_RUN).exists())

    def test_run_is_audited_with_counts_only(self):
        self.policy(1, at(2026, 1, 1))
        self.credit(10, at(2026, 1, 2))
        expirations.run(at=at(2026, 3, 1))
        event = AuditEvent.objects.get(action=AuditEvent.Action.POINTS_EXPIRY_RUN)
        self.assertEqual(event.metadata, {"policy": True, "warned": 0, "expired_customers": 1, "expired_points": 10})

    def test_points_of_a_refunded_redemption_keep_their_date(self):
        self.policy(12, at(2026, 1, 1))
        self.credit(100, at(2026, 1, 10))
        redemption = self.spend(100, at(2026, 3, 1))
        ledger.refund_spent_points(movement=redemption, reason="Canje cancelado")
        self.assertEqual(expirations.run(at=at(2027, 1, 11)).expired_points, 100)

    def test_an_expiration_cannot_be_reversed(self):
        self.policy(1, at(2026, 1, 1))
        self.credit(10, at(2026, 1, 2))
        expirations.run(at=at(2026, 3, 1))
        movement = PointsTransaction.objects.get(kind=Kind.EXPIRATION)
        with self.assertRaises(ValidationError) as ctx:
            ledger.reverse_movement(actor=self.owner, movement=movement, reason="Error")
        self.assertEqual(ctx.exception.code, "expiration_reversal")
        self.assertNotIn(movement.pk, selectors.reversible_ids([movement]))
        # Se devuelven con un ajuste: puntos nuevos, con fecha nueva.
        self.credit(10, at(2026, 3, 2))
        self.assertEqual(ledger.balance(self.customer), 10)

    def test_database_rejects_a_positive_expiration(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PointsTransaction.objects.create(customer=self.customer, kind=Kind.EXPIRATION, points=5, balance_after=5)

    def test_summary_separates_expired_points(self):
        self.policy(1, at(2026, 1, 1))
        self.credit(40, at(2026, 1, 2))
        self.credit(-5, at(2026, 1, 3))
        expirations.run(at=at(2026, 3, 1))
        summary = selectors.points_summary(self.customer)
        self.assertEqual((summary.balance, summary.earned, summary.corrected, summary.expired), (0, 40, 5, 35))
        stats = selectors.points_stats(actor=self.owner)
        self.assertEqual((stats.expired, stats.corrected), (35, 5))


# --- Avisos -----------------------------------------------------------------------------


class WarningTests(ExpiryTestCase):
    def setUp(self):
        super().setUp()
        self.policy(12, at(2026, 1, 1), warn_days=15)
        self.credit(80, at(2026, 1, 20))

    def warnings(self):
        return Notification.objects.filter(kind=Notification.Kind.POINTS_EXPIRING)

    def test_warns_once_inside_the_window(self):
        self.assertEqual(expirations.run(at=at(2027, 1, 4)).warned, 0)  # faltan 16 días
        self.assertEqual(expirations.run(at=at(2027, 1, 10)).warned, 1)
        self.assertEqual(expirations.run(at=at(2027, 1, 11)).warned, 0)
        notification = self.warnings().get()
        self.assertEqual(notification.category, Notification.Category.TRANSACTIONAL)
        self.assertEqual(notification.context, {"points": 80, "expires_on": "20/01/2027"})
        self.assertEqual(notification.recipient, self.customer)

    def test_email_content(self):
        expirations.run(at=at(2027, 1, 10))
        notifications.process_due()
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn("80 puntos", message.subject)
        self.assertIn("20/01/2027", message.body)
        self.assertIn(reverse("loyalty:my_points"), message.body)

    def test_no_warning_for_inactive_or_unverified_customers(self):
        self.customer.is_active = False
        self.customer.save(update_fields=["is_active"])
        expirations.run(at=at(2027, 1, 10))
        self.customer.is_active = True
        self.customer.email_verified_at = None
        self.customer.save(update_fields=["is_active", "email_verified_at"])
        expirations.run(at=at(2027, 1, 11))
        self.assertFalse(self.warnings().exists())

    def test_the_window_counts_whole_days(self):
        # Vence el 20/01 a las 13:00 (Madrid); el día 05/01 de madrugada ya entra en los 15 días.
        self.assertEqual(expirations.run(at=datetime.datetime(2027, 1, 5, 4, 40, tzinfo=MADRID)).warned, 1)

    def test_no_warning_for_points_already_due(self):
        result = expirations.run(at=at(2027, 2, 1))
        self.assertEqual((result.warned, result.expired_points), (0, 80))


# --- Comando y vista del cliente -------------------------------------------------------


class CommandAndViewTests(ExpiryTestCase):
    def test_command_without_policy(self):
        out = StringIO()
        call_command("expire_points", stdout=out)
        self.assertIn("no caducan", out.getvalue())

    def test_command_reports_counts(self):
        self.policy(1, timezone.now() - datetime.timedelta(days=90))
        self.credit(25, timezone.now() - datetime.timedelta(days=80))
        out = StringIO()
        call_command("expire_points", stdout=out)
        self.assertIn("puntos caducados 25", out.getvalue())

    def test_simulated_date_only_in_development(self):
        with self.assertRaises(CommandError):
            call_command("expire_points", at="2030-01-01", stdout=StringIO())
        with override_settings(DEBUG=True), self.assertRaises(CommandError):
            call_command("expire_points", at="01/01/2030", stdout=StringIO())

    def test_my_points_shows_the_next_expiry_and_expired_points(self):
        self.policy(1, at(2026, 1, 1))
        self.credit(10, at(2026, 1, 2))
        expirations.run(at=at(2026, 3, 1))
        self.credit(30, timezone.now())
        self.client.force_login(self.customer)
        response = self.client.get(reverse("loyalty:my_points"))
        self.assertContains(response, "data-points-expiry")
        self.assertContains(response, "<strong>30 puntos</strong>", html=False)
        self.assertContains(response, "Puntos caducados")
        self.assertContains(response, 'data-points-expired>10<', html=False)

    def test_my_points_without_policy_shows_no_expiry(self):
        self.credit(10, timezone.now())
        self.client.force_login(self.customer)
        response = self.client.get(reverse("loyalty:my_points"))
        self.assertNotContains(response, "data-points-expiry")
        self.assertNotContains(response, "data-points-expired")


# --- Concurrencia -------------------------------------------------------------------------


class ExpiryConcurrencyTests(ConcurrencyTestCase):
    def test_expiration_and_redemptions_at_the_same_time(self):
        owner = make_owner()
        customer, _ = make_customer_with_qr()
        old = ledger.adjust_points(actor=owner, customer=customer, points=100, reason="Antiguos", idempotency_key=uuid.uuid4())
        PointsTransaction.objects.filter(pk=old.movement.pk).update(created_at=at(2026, 1, 2))
        ledger.adjust_points(actor=owner, customer=customer, points=50, reason="Nuevos", idempotency_key=uuid.uuid4())
        policy = PointsExpiryPolicy.objects.create(months=1, counts_from=at(2026, 1, 1), valid_from=at(2026, 1, 1))

        def target(i):
            if i % 2 == 0:
                return ledger.expire_points(customer=customer, policy=policy)
            with transaction.atomic():
                locked = ledger.lock_customer(customer)
                return ledger.spend_points(customer=locked, points=40, reason="Canje")

        outcomes = self.run_in_threads(target)
        self.assertFalse([o for o in outcomes if o[0] == "unexpected"], outcomes)
        self.assertEqual(PointsTransaction.objects.filter(kind=Kind.EXPIRATION).count(), 1)
        balance = ledger.balance(customer)
        self.assertGreaterEqual(balance, 0)
        last = PointsTransaction.objects.filter(customer=customer).order_by("-id").first()
        self.assertEqual(last.balance_after, balance)
        # Lo antiguo que no se gastó ha caducado; lo nuevo, no.
        self.assertEqual(expiry.expirable_points(expiry.customer_movements(customer), policy, timezone.now()), 0)
