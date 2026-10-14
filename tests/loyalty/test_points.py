"""Ledger de puntos: conversión, redondeo, saldo, duplicados, transacciones, ajustes y permisos."""
import datetime
import uuid
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.models import AuditEvent
from apps.loyalty import conversion, ledger, selectors
from apps.loyalty.models import LoyaltyRule, PointsTransaction
from apps.purchases import services as purchases
from apps.purchases.models import Purchase

from .factories import buy, make_customer_with_qr, make_employee, make_owner

Kind = PointsTransaction.Kind


class LedgerTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.customer, self.token = make_customer_with_qr()
        self.employee = make_employee()
        self.owner = make_owner()

    def buy(self, amount="12.50", token=None):
        return buy(self.employee, token or self.token, amount)

    def make_rule(self, rate, valid_from=None):
        return conversion.create_rule(actor=self.owner, points_per_euro=rate, valid_from=valid_from)


class ConversionTests(TestCase):
    def test_rounds_down_to_whole_points(self):
        cases = [
            ("12.50", "1.00", 12),
            ("0.99", "1.00", 0),
            ("10.00", "1.50", 15),
            ("3.33", "1.50", 4),  # 4,995 -> 4
            ("999.99", "0.10", 99),  # 99,999 -> 99
            ("0.01", "100.00", 1),
        ]
        for amount, rate, expected in cases:
            with self.subTest(amount=amount, rate=rate):
                self.assertEqual(conversion.calculate_points(Decimal(amount), Decimal(rate)), expected)

    def test_rejects_floats_and_negatives(self):
        with self.assertRaises(TypeError):
            conversion.calculate_points(12.5, Decimal("1"))
        with self.assertRaises(TypeError):
            conversion.round_points(Decimal("NaN"))
        with self.assertRaises(ValueError):
            conversion.calculate_points(Decimal("-1"), Decimal("1"))

    @override_settings(LOYALTY_DEFAULT_POINTS_PER_EURO=Decimal("2.00"))
    def test_default_rate_without_rules(self):
        rate = conversion.current_rate()
        self.assertEqual(rate.points_per_euro, Decimal("2.00"))
        self.assertIsNone(rate.rule)


class RuleTests(LedgerTestCase):
    def test_owner_creates_rule_with_audit(self):
        rule = self.make_rule("1,50")
        self.assertEqual(rule.points_per_euro, Decimal("1.50"))
        self.assertEqual(rule.created_by, self.owner)
        event = AuditEvent.objects.get(action=AuditEvent.Action.LOYALTY_RULE_CREATED)
        self.assertEqual(event.metadata["points_per_euro"], "1.50")
        self.assertEqual(conversion.current_rule(), rule)

    def test_only_owner_can_change_conversion(self):
        for actor in (None, self.employee, self.customer, make_owner("inactivo@example.com", is_active=False)):
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                conversion.create_rule(actor=actor, points_per_euro="5")
        self.assertFalse(LoyaltyRule.objects.exists())

    def test_invalid_rates_are_rejected(self):
        for value in ("0", "-1", "100.01", "abc", "", None, "1.234", float("nan")):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.make_rule(value)
        self.assertFalse(LoyaltyRule.objects.exists())

    def test_rule_cannot_start_in_the_past(self):
        with self.assertRaises(ValidationError):
            self.make_rule("2", valid_from=timezone.now() - datetime.timedelta(days=1))

    def test_new_rule_applies_to_new_purchases_only(self):
        first = self.buy("10.00")
        self.make_rule("2.00")
        second = self.buy("10.00")
        movements = {m.purchase_id: m for m in PointsTransaction.objects.filter(kind=Kind.EARN_PURCHASE)}
        self.assertEqual(movements[first.pk].points, 10)
        self.assertEqual(movements[first.pk].points_per_euro, Decimal("1.00"))
        self.assertIsNone(movements[first.pk].rule)
        self.assertEqual(movements[second.pk].points, 20)
        self.assertEqual(movements[second.pk].points_per_euro, Decimal("2.00"))

    def test_future_rule_is_not_applied_yet(self):
        self.make_rule("3.00", valid_from=timezone.now() + datetime.timedelta(days=1))
        self.buy("10.00")
        self.assertEqual(ledger.balance(self.customer), 10)

    def test_rule_rate_check_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            LoyaltyRule.objects.create(points_per_euro=Decimal("0"))


class AwardTests(LedgerTestCase):
    def test_purchase_creates_earn_movement(self):
        purchase = self.buy("12.50")
        movement = PointsTransaction.objects.get()
        self.assertEqual(movement.kind, Kind.EARN_PURCHASE)
        self.assertEqual(movement.customer, self.customer)
        self.assertEqual(movement.purchase, purchase)
        self.assertEqual(movement.points, 12)
        self.assertEqual(movement.balance_after, 12)
        self.assertEqual(movement.base_amount, Decimal("12.50"))
        self.assertEqual(movement.created_by, self.employee)

    def test_small_purchase_gives_no_points(self):
        self.buy("0.50")
        self.assertEqual(Purchase.objects.count(), 1)
        self.assertFalse(PointsTransaction.objects.exists())
        self.assertEqual(ledger.balance(self.customer), 0)

    def test_balance_is_sum_and_balance_after_chain(self):
        for amount in ("10.00", "5.99", "20.01"):
            self.buy(amount)
        self.assertEqual(ledger.balance(self.customer), 10 + 5 + 20)
        chain = list(PointsTransaction.objects.order_by("id").values_list("points", "balance_after"))
        self.assertEqual(chain, [(10, 10), (5, 15), (20, 35)])

    def test_balances_are_per_customer(self):
        other, other_token = make_customer_with_qr("otra@example.com")
        self.buy("10.00")
        self.buy("7.00", token=other_token)
        self.assertEqual(ledger.balance(self.customer), 10)
        self.assertEqual(ledger.balance(other), 7)

    def test_points_cannot_be_sent_by_the_client(self):
        with self.assertRaises(TypeError):
            purchases.register_purchase(
                staff=self.employee, qr_code=self.token, amount="10", idempotency_key=uuid.uuid4(), points=999
            )
        self.assertFalse(PointsTransaction.objects.exists())

    def test_retried_purchase_does_not_duplicate_points(self):
        key = uuid.uuid4()
        for _ in range(3):
            purchases.register_purchase(staff=self.employee, qr_code=self.token, amount="10", idempotency_key=key)
        self.assertEqual(PointsTransaction.objects.count(), 1)
        self.assertEqual(ledger.balance(self.customer), 10)

    def test_award_is_idempotent(self):
        purchase = self.buy("10.00")
        again = ledger.award_points_for_purchase(purchase)
        self.assertEqual([m.pk for m in again], list(PointsTransaction.objects.values_list("pk", flat=True)))
        self.assertEqual(PointsTransaction.objects.count(), 1)

    def test_database_rejects_second_earn_for_same_purchase(self):
        purchase = self.buy("10.00")
        with self.assertRaises(IntegrityError), transaction.atomic():
            PointsTransaction.objects.create(
                customer=self.customer, kind=Kind.EARN_PURCHASE, points=10, balance_after=20, purchase=purchase
            )

    def test_database_rejects_negative_balance_and_zero_points(self):
        for points, balance_after in ((-1, -1), (0, 0)):
            with self.subTest(points=points), self.assertRaises(IntegrityError), transaction.atomic():
                PointsTransaction.objects.create(
                    customer=self.customer,
                    kind=Kind.ADJUSTMENT,
                    points=points,
                    balance_after=balance_after,
                    created_by=self.owner,
                    reason="Prueba",
                )

    def test_voided_purchase_gives_no_points(self):
        purchase = self.buy("10.00")
        PointsTransaction.objects.all().delete()  # solo en el test: simula una compra anulada sin puntos
        Purchase.objects.filter(pk=purchase.pk).update(status=Purchase.Status.VOIDED)
        purchase.refresh_from_db()
        self.assertEqual(ledger.award_points_for_purchase(purchase), [])

    def test_ledger_failure_rolls_back_the_purchase(self):
        with mock.patch.object(ledger, "_append", side_effect=RuntimeError("fallo simulado")):
            with self.assertRaises(RuntimeError):
                self.buy("10.00")
        self.assertFalse(Purchase.objects.exists())
        self.assertFalse(PointsTransaction.objects.exists())

    def test_points_failure_after_insert_leaves_nothing(self):
        real_append = ledger._append

        def append_then_fail(customer, **fields):
            real_append(customer, **fields)
            raise RuntimeError("fallo después del INSERT")

        with mock.patch.object(ledger, "_append", side_effect=append_then_fail):
            with self.assertRaises(RuntimeError):
                self.buy("10.00")
        self.assertFalse(Purchase.objects.exists())
        self.assertFalse(PointsTransaction.objects.exists())

    def test_customer_row_is_locked_while_awarding(self):
        purchase = self.buy("10.00")
        PointsTransaction.objects.all().delete()  # solo en el test
        with mock.patch.object(ledger, "_lock_customer", wraps=ledger._lock_customer) as lock:
            ledger.award_points_for_purchase(purchase)
        lock.assert_called_once()

    def test_log_has_no_personal_data(self):
        with self.assertLogs("apps.loyalty.ledger", level="INFO") as logs:
            self.buy("10.00")
        output = "\n".join(logs.output)
        self.assertNotIn("cliente@example.com", output)
        self.assertNotIn(self.token, output)


class AdjustmentTests(LedgerTestCase):
    def adjust(self, points=50, **overrides):
        data = {
            "actor": self.owner,
            "customer": self.customer,
            "points": points,
            "reason": "Corrección ficticia",
            "idempotency_key": uuid.uuid4(),
        }
        data.update(overrides)
        return ledger.adjust_points(**data)

    def test_owner_adjusts_with_audit_without_reason_text(self):
        result = self.adjust(50)
        self.assertTrue(result.created)
        self.assertEqual(result.movement.kind, Kind.ADJUSTMENT)
        self.assertEqual(ledger.balance(self.customer), 50)
        event = AuditEvent.objects.get(action=AuditEvent.Action.POINTS_ADJUSTED)
        self.assertEqual(event.actor, self.owner)
        self.assertEqual(event.target_public_id, self.customer.public_id)
        self.assertEqual(event.metadata["points"], 50)
        self.assertNotIn("Corrección", str(event.metadata))

    def test_only_owner_can_adjust(self):
        for actor in (None, self.employee, self.customer):
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                self.adjust(actor=actor)
        self.assertFalse(PointsTransaction.objects.exists())

    @override_settings(LOYALTY_MAX_ADJUSTMENT_POINTS=1000)
    def test_invalid_adjustments(self):
        for points in (0, "0", "abc", 1.5, "1.5", True, None, 1001, -1001):
            with self.subTest(points=points), self.assertRaises(ValidationError):
                self.adjust(points)
        for reason in ("", "   ", None, "x" * 201):
            with self.subTest(reason=reason), self.assertRaises(ValidationError):
                self.adjust(reason=reason)
        with self.assertRaises(ValidationError):
            self.adjust(idempotency_key="no-es-un-uuid")
        self.assertFalse(PointsTransaction.objects.exists())

    def test_accepts_signed_strings(self):
        self.adjust("+20")
        self.adjust("-5")
        self.assertEqual(ledger.balance(self.customer), 15)

    def test_cannot_leave_negative_balance(self):
        self.buy("10.00")
        with self.assertRaises(ledger.InsufficientPoints):
            self.adjust(-11)
        self.adjust(-10)
        self.assertEqual(ledger.balance(self.customer), 0)

    def test_only_customers_have_points(self):
        with self.assertRaises(ValidationError) as ctx:
            self.adjust(customer=self.employee)
        self.assertEqual(ctx.exception.code, "not_customer")

    def test_retry_with_same_key_does_not_duplicate(self):
        key = uuid.uuid4()
        first = self.adjust(30, idempotency_key=key)
        second = self.adjust(30, idempotency_key=key)
        self.assertFalse(second.created)
        self.assertEqual(first.movement, second.movement)
        self.assertEqual(ledger.balance(self.customer), 30)
        self.assertEqual(AuditEvent.objects.filter(action=AuditEvent.Action.POINTS_ADJUSTED).count(), 1)

    def test_same_key_with_other_data_is_a_conflict(self):
        key = uuid.uuid4()
        self.adjust(30, idempotency_key=key)
        other, _ = make_customer_with_qr("otra@example.com")
        for overrides in ({"points": 31}, {"customer": other}):
            with self.subTest(**{k: str(v) for k, v in overrides.items()}), self.assertRaises(ValidationError) as ctx:
                self.adjust(**{"points": 30, "idempotency_key": key, **overrides})
            self.assertEqual(ctx.exception.code, "idempotency_conflict")

    def test_concurrent_request_with_same_key_returns_existing(self):
        """
        Carrera simulada: otra petición con la misma referencia confirmó su
        movimiento después de nuestra comprobación inicial. El INSERT choca con
        la restricción única y se devuelve el movimiento existente.
        """
        key = uuid.uuid4()
        winner = self.adjust(25, idempotency_key=key).movement
        not_found = mock.MagicMock()
        not_found.filter.return_value.first.return_value = None
        with mock.patch.object(PointsTransaction.objects, "select_for_update", return_value=not_found):
            result = self.adjust(25, idempotency_key=key)
        self.assertFalse(result.created)
        self.assertEqual(result.movement, winner)
        self.assertEqual(PointsTransaction.objects.count(), 1)
        self.assertEqual(ledger.balance(self.customer), 25)


class ReversalTests(LedgerTestCase):
    def test_reversal_compensates_without_editing_history(self):
        self.buy("10.00")
        original = PointsTransaction.objects.get()
        result = ledger.reverse_movement(actor=self.owner, movement=original, reason="Compra mal registrada")
        self.assertTrue(result.created)
        self.assertEqual(result.movement.points, -10)
        self.assertEqual(result.movement.reverses, original)
        self.assertEqual(ledger.balance(self.customer), 0)
        original.refresh_from_db()
        self.assertEqual(original.points, 10)  # el original no cambia
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.Action.POINTS_REVERSED).exists())

    def test_reversal_is_idempotent(self):
        self.buy("10.00")
        original = PointsTransaction.objects.get()
        first = ledger.reverse_movement(actor=self.owner, movement=original, reason="Error")
        second = ledger.reverse_movement(actor=self.owner, movement=original, reason="Error")
        self.assertFalse(second.created)
        self.assertEqual(first.movement, second.movement)
        self.assertEqual(ledger.balance(self.customer), 0)

    def test_database_allows_one_reversal_per_movement(self):
        self.buy("10.00")
        original = PointsTransaction.objects.get()
        ledger.reverse_movement(actor=self.owner, movement=original, reason="Error")
        with self.assertRaises(IntegrityError), transaction.atomic():
            PointsTransaction.objects.create(
                customer=self.customer, kind=Kind.REVERSAL, points=-1, balance_after=0, reverses=original
            )

    def test_cannot_reverse_a_reversal_or_go_negative(self):
        self.buy("10.00")
        original = PointsTransaction.objects.get()
        reversal = ledger.reverse_movement(actor=self.owner, movement=original, reason="Error").movement
        with self.assertRaises(ValidationError):
            ledger.reverse_movement(actor=self.owner, movement=reversal, reason="Error")
        self.buy("10.00")
        second = PointsTransaction.objects.filter(kind=Kind.EARN_PURCHASE).latest("id")
        ledger.adjust_points(
            actor=self.owner, customer=self.customer, points=-10, reason="Gasto", idempotency_key=uuid.uuid4()
        )
        with self.assertRaises(ledger.InsufficientPoints):
            ledger.reverse_movement(actor=self.owner, movement=second, reason="Error")

    def test_only_owner_can_reverse(self):
        self.buy("10.00")
        original = PointsTransaction.objects.get()
        for actor in (None, self.employee, self.customer):
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                ledger.reverse_movement(actor=actor, movement=original, reason="Error")


class SummaryTests(LedgerTestCase):
    def test_summary_distinguishes_earned_used_and_corrected(self):
        self.buy("30.00")
        ledger.adjust_points(
            actor=self.owner, customer=self.customer, points=-5, reason="Corrección", idempotency_key=uuid.uuid4()
        )
        # Canje simulado (la Fase 7 tendrá su servicio).
        PointsTransaction.objects.create(
            customer=self.customer, kind=Kind.REDEMPTION, points=-8, balance_after=17
        )
        summary = selectors.points_summary(self.customer)
        self.assertEqual(summary, selectors.PointsSummary(balance=17, earned=30, used=8, corrected=5))
        self.assertEqual(summary.balance, ledger.balance(self.customer))

    def test_empty_summary(self):
        self.assertEqual(selectors.points_summary(self.customer), selectors.PointsSummary(0, 0, 0, 0))

    def test_points_for_purchase(self):
        purchase = self.buy("12.50")
        self.assertEqual(selectors.points_for_purchase(purchase), 12)
