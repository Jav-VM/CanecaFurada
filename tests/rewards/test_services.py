"""Canjes: solicitud, saldo, disponibilidad, duplicados, concurrencia, códigos, validación, caducidad y permisos."""
import datetime
import uuid
from io import StringIO
from unittest import mock

from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.models import AuditEvent
from apps.loyalty import ledger, selectors as loyalty_selectors
from apps.loyalty.models import PointsTransaction
from apps.rewards import codes, services
from apps.rewards.models import Redemption, Reward

from .factories import give_points, make_customer_with_qr, make_employee, make_owner, make_reward, redeem

Status = Redemption.Status
Kind = PointsTransaction.Kind


class RewardsTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_owner()
        self.employee = make_employee()
        self.customer, _ = make_customer_with_qr()
        give_points(self.customer, 120, owner=self.owner)
        self.reward = make_reward(points_cost=50)

    def make_due(self, *redemptions):
        """Simula que el plazo del canje ya pasó."""
        past = timezone.now() - datetime.timedelta(days=31)
        Redemption.objects.filter(pk__in=[r.pk for r in redemptions]).update(
            created_at=past, expires_at=past + datetime.timedelta(days=30)
        )

    def validate(self, redemption, staff=None):
        return services.validate_redemption(staff=staff or self.employee, code=redemption.code)

    def assert_error(self, error_code, func, *args, **kwargs):
        with self.assertRaises(ValidationError) as ctx:
            func(*args, **kwargs)
        self.assertEqual(ctx.exception.code, error_code)
        return ctx.exception


class CodeTests(TestCase):
    def test_codes_are_random_well_formed_and_unique(self):
        generated = {codes.generate_code() for _ in range(2000)}
        self.assertEqual(len(generated), 2000)
        for code in list(generated)[:200]:
            self.assertRegex(code, codes.CODE_REGEX)
            self.assertFalse(set(code) & set("01IOL"))

    def test_normalize_accepts_qr_payload_and_typed_variants(self):
        code = "ABCDEFGHJKMN"
        for raw in (code, "abcd-efgh-jkmn", " ABCD EFGH JKMN ", "CFR1:ABCDEFGHJKMN", codes.format_code(code)):
            with self.subTest(raw=raw):
                self.assertEqual(codes.normalize_code(raw), code)

    def test_normalize_rejects_other_payloads(self):
        for raw in (None, "", "ABC", "CF1:ABCDEFGHJKMN", "ABCDEFGHJKM0", "x" * 101, 123, "ABCDEFGHJKMNP"):
            with self.subTest(raw=raw):
                self.assertIsNone(codes.normalize_code(raw))


class RequestTests(RewardsTestCase):
    def test_request_deducts_points_and_issues_single_use_code(self):
        result = redeem(self.customer, self.reward)
        redemption = result.redemption
        self.assertTrue(result.created)
        self.assertEqual(redemption.status, Status.PENDING)
        self.assertEqual(redemption.points_cost, 50)
        self.assertRegex(redemption.code, codes.CODE_REGEX)
        self.assertAlmostEqual(
            redemption.expires_at - redemption.created_at, datetime.timedelta(days=30), delta=datetime.timedelta(seconds=1)
        )
        movement = redemption.spend_movement
        self.assertEqual((movement.kind, movement.points, movement.balance_after), (Kind.REDEMPTION, -50, 70))
        self.assertEqual(ledger.balance(self.customer), 70)

    @override_settings(REWARDS_CODE_VALIDITY_DAYS=2)
    def test_validity_is_configurable(self):
        redemption = redeem(self.customer, self.reward).redemption
        self.assertEqual((redemption.expires_at - redemption.created_at).days, 2)

    def test_insufficient_balance_changes_nothing(self):
        expensive = make_reward(name="Camiseta", points_cost=121, stock=3)
        self.assert_error("insufficient_points", redeem, self.customer, expensive)
        self.assertFalse(Redemption.objects.exists())
        self.assertEqual(ledger.balance(self.customer), 120)
        expensive.refresh_from_db()
        self.assertEqual(expensive.stock, 3)

    def test_exact_balance_is_enough(self):
        exact = make_reward(name="Exacta", points_cost=120)
        redeem(self.customer, exact)
        self.assertEqual(ledger.balance(self.customer), 0)

    def test_reward_must_be_active_and_in_period(self):
        now = timezone.now()
        cases = {
            "draft": make_reward(name="b", status=Reward.Status.DRAFT),
            "paused": make_reward(name="p", status=Reward.Status.PAUSED),
            "archived": make_reward(name="a", status=Reward.Status.ARCHIVED),
            "future": make_reward(name="f", valid_from=now + datetime.timedelta(hours=1)),
            "ended": make_reward(name="e", valid_from=now - datetime.timedelta(days=5), valid_until=now),
        }
        for label, reward in cases.items():
            with self.subTest(label):
                self.assert_error("reward_unavailable", redeem, self.customer, reward)
        self.assertFalse(Redemption.objects.exists())
        self.assertEqual(ledger.balance(self.customer), 120)

    def test_stock_decrements_and_runs_out(self):
        limited = make_reward(name="Limitada", points_cost=10, stock=1)
        redeem(self.customer, limited)
        limited.refresh_from_db()
        self.assertEqual(limited.stock, 0)
        other, _ = make_customer_with_qr("otra@example.com")
        give_points(other, 100, owner=self.owner)
        self.assert_error("out_of_stock", redeem, other, limited)
        self.assertEqual(ledger.balance(other), 100)

    def test_stock_cannot_go_negative_even_if_check_was_stale(self):
        """Otra petición se llevó la última unidad entre la lectura y la resta: la resta condicionada lo detecta."""
        limited = make_reward(name="Última", points_cost=10, stock=1)
        Reward.objects.filter(pk=limited.pk).update(stock=0)
        self.assert_error("out_of_stock", redeem, self.customer, limited)
        self.assertEqual(ledger.balance(self.customer), 120)

    def test_unlimited_stock_stays_null(self):
        redeem(self.customer, self.reward)
        self.reward.refresh_from_db()
        self.assertIsNone(self.reward.stock)

    def test_only_one_pending_code_per_reward(self):
        redeem(self.customer, self.reward)
        self.assert_error("duplicate_pending", redeem, self.customer, self.reward)
        self.assertEqual(Redemption.objects.count(), 1)
        self.assertEqual(ledger.balance(self.customer), 70)
        # Otra recompensa distinta sí se puede pedir.
        redeem(self.customer, make_reward(name="Otra", points_cost=10))

    def test_after_using_the_code_the_reward_can_be_requested_again(self):
        first = redeem(self.customer, self.reward).redemption
        self.validate(first)
        second = redeem(self.customer, self.reward).redemption
        self.assertNotEqual(first.code, second.code)
        self.assertEqual(ledger.balance(self.customer), 20)

    def test_retry_with_same_key_does_not_charge_twice(self):
        key = uuid.uuid4()
        first = redeem(self.customer, self.reward, key)
        second = redeem(self.customer, self.reward, key)
        self.assertFalse(second.created)
        self.assertEqual(first.redemption, second.redemption)
        self.assertEqual(PointsTransaction.objects.filter(kind=Kind.REDEMPTION).count(), 1)
        self.assertEqual(ledger.balance(self.customer), 70)

    def test_same_key_with_other_data_is_a_conflict(self):
        key = uuid.uuid4()
        redeem(self.customer, self.reward, key)
        self.assert_error("idempotency_conflict", redeem, self.customer, make_reward(name="Otra", points_cost=1), key)
        other, _ = make_customer_with_qr("otra@example.com")
        give_points(other, 100, owner=self.owner)
        self.assert_error("idempotency_conflict", redeem, other, self.reward, key)

    def test_invalid_key_is_rejected(self):
        for key in (None, "", "no-es-uuid", 123):
            with self.subTest(key=key):
                self.assert_error(
                    "idempotency_invalid",
                    services.request_redemption,
                    customer=self.customer,
                    reward=self.reward,
                    idempotency_key=key,
                )

    def test_concurrent_request_with_same_key_returns_existing(self):
        """
        Carrera simulada: otra petición con la misma referencia confirmó su
        canje después de nuestra comprobación inicial y nuestro INSERT chocó con
        la restricción única. Se devuelve el canje existente.
        """
        key = uuid.uuid4()
        winner = redeem(self.customer, self.reward, key).redemption
        with mock.patch.object(services, "_create_redemption", side_effect=IntegrityError("duplicado")):
            result = redeem(self.customer, self.reward, key)
        self.assertFalse(result.created)
        self.assertEqual(result.redemption, winner)
        self.assertEqual(ledger.balance(self.customer), 70)

    def test_concurrent_requests_with_different_keys_give_one_pending(self):
        """Dos pestañas a la vez: la segunda choca con el único pendiente por recompensa."""
        redeem(self.customer, self.reward)
        with mock.patch.object(services, "_create_redemption", side_effect=IntegrityError("duplicado")):
            self.assert_error("duplicate_pending", redeem, self.customer, self.reward)
        self.assertEqual(Redemption.objects.count(), 1)

    def test_insert_conflict_rolls_back_charge_and_stock(self):
        limited = make_reward(name="Limitada", points_cost=10, stock=5)
        with mock.patch.object(Redemption.objects, "create", side_effect=IntegrityError("simulado")):
            with self.assertRaises(IntegrityError):
                redeem(self.customer, limited)
        self.assertFalse(PointsTransaction.objects.filter(kind=Kind.REDEMPTION).exists())
        self.assertEqual(ledger.balance(self.customer), 120)
        limited.refresh_from_db()
        self.assertEqual(limited.stock, 5)

    def test_failure_after_charging_rolls_everything_back(self):
        limited = make_reward(name="Limitada", points_cost=10, stock=5)
        with mock.patch.object(Redemption.objects, "create", side_effect=RuntimeError("fallo simulado")):
            with self.assertRaises(RuntimeError):
                redeem(self.customer, limited)
        self.assertFalse(Redemption.objects.exists())
        self.assertFalse(PointsTransaction.objects.filter(kind=Kind.REDEMPTION).exists())
        self.assertEqual(ledger.balance(self.customer), 120)
        limited.refresh_from_db()
        self.assertEqual(limited.stock, 5)

    def test_customer_and_reward_rows_are_locked(self):
        with mock.patch.object(ledger, "lock_customer", wraps=ledger.lock_customer) as lock:
            redeem(self.customer, self.reward)
        lock.assert_called_once()

    def test_points_cannot_come_from_the_client(self):
        with self.assertRaises(TypeError):
            services.request_redemption(
                customer=self.customer, reward=self.reward, idempotency_key=uuid.uuid4(), points_cost=1
            )

    def test_cost_change_does_not_affect_existing_redemption(self):
        redemption = redeem(self.customer, self.reward).redemption
        Reward.objects.filter(pk=self.reward.pk).update(points_cost=5)
        redemption.refresh_from_db()
        self.assertEqual(redemption.points_cost, 50)

    def test_only_verified_active_customers_can_redeem(self):
        unverified, _ = make_customer_with_qr("sinverificar@example.com")
        unverified.email_verified_at = None
        unverified.save(update_fields=["email_verified_at"])
        inactive, _ = make_customer_with_qr("inactivo@example.com")
        inactive.is_active = False
        inactive.save(update_fields=["is_active"])
        for actor in (None, self.employee, self.owner, unverified, inactive):
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                redeem(actor, self.reward)
        self.assertFalse(Redemption.objects.exists())

    def test_logs_do_not_contain_code_or_personal_data(self):
        with self.assertLogs("apps.rewards.services", level="INFO") as logs:
            redemption = redeem(self.customer, self.reward).redemption
            self.validate(redemption)
        output = "\n".join(logs.output)
        self.assertIn(str(redemption.public_id), output)
        for secret in (redemption.code, codes.format_code(redemption.code), self.customer.email, self.customer.first_name):
            self.assertNotIn(secret, output)


class ValidationTests(RewardsTestCase):
    def test_staff_validates_and_it_is_recorded(self):
        redemption = redeem(self.customer, self.reward).redemption
        result = self.validate(redemption)
        redemption.refresh_from_db()
        self.assertTrue(result.created)
        self.assertEqual(redemption.status, Status.USED)
        self.assertEqual(redemption.validated_by, self.employee)
        self.assertIsNotNone(redemption.validated_at)
        event = AuditEvent.objects.get(action=AuditEvent.Action.REDEMPTION_VALIDATED)
        self.assertEqual(event.actor, self.employee)
        self.assertEqual(event.target_public_id, redemption.public_id)
        self.assertNotIn(redemption.code, str(event.metadata))
        # Validar no toca los puntos: ya se descontaron al solicitarlo.
        self.assertEqual(ledger.balance(self.customer), 70)

    def test_owner_can_validate(self):
        redemption = redeem(self.customer, self.reward).redemption
        self.validate(redemption, staff=self.owner)

    def test_used_code_cannot_be_used_again(self):
        redemption = redeem(self.customer, self.reward).redemption
        self.validate(redemption)
        for staff in (self.employee, self.owner):
            with self.subTest(staff=staff.email):
                self.assert_error("code_used", self.validate, redemption, staff)
        self.assertEqual(AuditEvent.objects.filter(action=AuditEvent.Action.REDEMPTION_VALIDATED).count(), 1)

    def test_concurrent_validation_only_one_wins(self):
        """
        Carrera simulada: dos empleados leen el canje pendiente a la vez y el
        otro confirma antes. El UPDATE condicionado (status = PENDING) no
        cambia ninguna fila y se rechaza como ya usado.
        """
        redemption = redeem(self.customer, self.reward).redemption
        stale = Redemption.objects.select_related("customer", "reward").get(pk=redemption.pk)
        other = make_employee("otro@example.com")
        self.validate(redemption, staff=other)
        with mock.patch.object(services, "_find", return_value=stale):
            self.assert_error("code_used", self.validate, redemption)
        redemption.refresh_from_db()
        self.assertEqual(redemption.validated_by, other)
        self.assertEqual(AuditEvent.objects.filter(action=AuditEvent.Action.REDEMPTION_VALIDATED).count(), 1)

    def test_invalid_code(self):
        for raw in ("", "ABCDEFGHJKMN", "no-es-un-codigo", "CF1:" + "A" * 32):
            with self.subTest(raw=raw):
                self.assert_error("invalid_code", services.validate_redemption, staff=self.employee, code=raw)
                self.assert_error("invalid_code", services.lookup_redemption, staff=self.employee, code=raw)

    @override_settings(REWARDS_MAX_CODE_FAILURES=3)
    def test_repeated_invalid_codes_are_rate_limited_per_staff(self):
        for _ in range(3):
            with self.assertRaises(ValidationError):
                services.lookup_redemption(staff=self.employee, code="ABCDEFGHJKMN")
        redemption = redeem(self.customer, self.reward).redemption
        with self.assertRaises(services.TooManyFailedAttempts):
            self.validate(redemption)
        # Otro miembro del personal no está bloqueado.
        self.validate(redemption, staff=self.owner)

    def test_inactive_customer_code_is_rejected_generically(self):
        redemption = redeem(self.customer, self.reward).redemption
        self.customer.is_active = False
        self.customer.save(update_fields=["is_active"])
        self.assert_error("invalid_code", self.validate, redemption)

    def test_expired_code_is_rejected_and_points_returned(self):
        redemption = redeem(self.customer, self.reward).redemption
        self.make_due(redemption)
        self.assert_error("code_expired", self.validate, redemption)
        redemption.refresh_from_db()
        self.assertEqual(redemption.status, Status.EXPIRED)
        self.assertEqual(ledger.balance(self.customer), 120)
        self.assert_error("code_expired", self.validate, redemption)
        self.assertEqual(PointsTransaction.objects.filter(kind=Kind.REVERSAL).count(), 1)

    def test_cancelled_code_is_rejected(self):
        redemption = redeem(self.customer, self.reward).redemption
        services.cancel_redemption(customer=self.customer, redemption=redemption)
        self.assert_error("code_not_pending", self.validate, redemption)

    def test_only_staff_can_validate_or_lookup(self):
        redemption = redeem(self.customer, self.reward).redemption
        inactive_employee = make_employee("baja@example.com", is_active=False)
        for actor in (None, self.customer, inactive_employee):
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionDenied):
                    services.validate_redemption(staff=actor, code=redemption.code)
                with self.assertRaises(PermissionDenied):
                    services.lookup_redemption(staff=actor, code=redemption.code)
        redemption.refresh_from_db()
        self.assertEqual(redemption.status, Status.PENDING)

    def test_lookup_shows_minimal_data_and_changes_nothing(self):
        redemption = redeem(self.customer, self.reward).redemption
        preview = services.lookup_redemption(staff=self.employee, code=codes.qr_payload(redemption.code))
        self.assertEqual(preview.reward_name, self.reward.name)
        self.assertTrue(preview.can_validate)
        self.assertEqual(preview.customer_name, "Lúa F.")
        fields = set(services.RedemptionPreview.__dataclass_fields__)
        self.assertFalse(fields & {"email", "phone", "balance", "customer", "code", "birth_date"})
        redemption.refresh_from_db()
        self.assertEqual(redemption.status, Status.PENDING)

    def test_lookup_of_used_code_cannot_be_validated(self):
        redemption = redeem(self.customer, self.reward).redemption
        self.validate(redemption)
        preview = services.lookup_redemption(staff=self.employee, code=redemption.code)
        self.assertFalse(preview.can_validate)
        self.assertEqual(preview.status, Status.USED)


class CancelAndExpireTests(RewardsTestCase):
    def test_cancel_returns_points_and_stock(self):
        limited = make_reward(name="Limitada", points_cost=30, stock=2)
        redemption = redeem(self.customer, limited).redemption
        result = services.cancel_redemption(customer=self.customer, redemption=redemption)
        self.assertTrue(result.created)
        redemption.refresh_from_db()
        self.assertEqual(redemption.status, Status.CANCELLED)
        self.assertIsNotNone(redemption.closed_at)
        refund = redemption.refund_movement
        self.assertEqual((refund.kind, refund.points, refund.reverses), (Kind.REVERSAL, 30, redemption.spend_movement))
        self.assertEqual(refund.created_by, self.customer)
        self.assertEqual(ledger.balance(self.customer), 120)
        limited.refresh_from_db()
        self.assertEqual(limited.stock, 2)
        # El movimiento del canje no se ha tocado.
        self.assertEqual(PointsTransaction.objects.get(pk=redemption.spend_movement_id).points, -30)

    def test_cancel_is_idempotent(self):
        redemption = redeem(self.customer, self.reward).redemption
        services.cancel_redemption(customer=self.customer, redemption=redemption)
        again = services.cancel_redemption(customer=self.customer, redemption=redemption)
        self.assertFalse(again.created)
        self.assertEqual(ledger.balance(self.customer), 120)
        self.assertEqual(PointsTransaction.objects.filter(kind=Kind.REVERSAL).count(), 1)

    def test_cannot_cancel_used_or_foreign_redemption(self):
        redemption = redeem(self.customer, self.reward).redemption
        other, _ = make_customer_with_qr("otra@example.com")
        with self.assertRaises(PermissionDenied):
            services.cancel_redemption(customer=other, redemption=redemption)
        with self.assertRaises(PermissionDenied):
            services.cancel_redemption(customer=self.employee, redemption=redemption)
        self.validate(redemption)
        self.assert_error("code_not_pending", services.cancel_redemption, customer=self.customer, redemption=redemption)
        self.assertEqual(ledger.balance(self.customer), 70)

    def test_cancel_racing_with_validation_does_not_refund(self):
        """Validado justo antes de que la cancelación cambie la fila: no se devuelven puntos."""
        redemption = redeem(self.customer, self.reward).redemption
        self.validate(redemption)
        stale = Redemption.objects.get(pk=redemption.pk)
        stale.status = Status.PENDING

        class StaleManager:
            def get(self, pk):
                return stale

        with mock.patch.object(Redemption.objects, "select_for_update", side_effect=lambda: StaleManager()):
            self.assert_error("code_not_pending", services.cancel_redemption, customer=self.customer, redemption=stale)
        self.assertEqual(ledger.balance(self.customer), 70)
        self.assertFalse(PointsTransaction.objects.filter(kind=Kind.REVERSAL).exists())

    def test_expire_command_returns_points_only_for_due_codes(self):
        due = redeem(self.customer, self.reward).redemption
        not_due = redeem(self.customer, make_reward(name="Otra", points_cost=20)).redemption
        used = redeem(self.customer, make_reward(name="Usada", points_cost=10)).redemption
        self.validate(used)
        self.make_due(due, used)
        out = StringIO()
        call_command("expire_redemptions", stdout=out)
        self.assertIn("Canjes caducados: 1", out.getvalue())
        due.refresh_from_db()
        not_due.refresh_from_db()
        used.refresh_from_db()
        self.assertEqual((due.status, not_due.status, used.status), (Status.EXPIRED, Status.PENDING, Status.USED))
        self.assertIsNone(due.refund_movement.created_by)
        self.assertEqual(ledger.balance(self.customer), 120 - 20 - 10)
        # Repetirlo no devuelve dos veces.
        self.assertEqual(services.expire_pending_redemptions(), 0)


class LedgerSummaryTests(RewardsTestCase):
    def test_used_points_are_net_of_refunds(self):
        kept = redeem(self.customer, self.reward).redemption
        self.validate(kept)
        cancelled = redeem(self.customer, make_reward(name="Otra", points_cost=30)).redemption
        services.cancel_redemption(customer=self.customer, redemption=cancelled)
        summary = loyalty_selectors.points_summary(self.customer)
        self.assertEqual((summary.balance, summary.earned, summary.used, summary.corrected), (70, 120, 50, 0))
        self.assertEqual(summary.balance, summary.earned - summary.used - summary.corrected)
        stats = loyalty_selectors.points_stats(actor=self.owner)
        self.assertEqual((stats.issued, stats.used, stats.outstanding), (120, 50, 70))

    def test_spend_points_requires_transaction_and_positive_points(self):
        with self.assertRaises(ValueError):
            with transaction.atomic():
                ledger.spend_points(customer=self.customer, points=0, reason="x")
        with self.assertRaises(ValueError):
            with transaction.atomic():
                ledger.spend_points(customer=self.customer, points=True, reason="x")

    def test_refund_only_for_redemption_movements(self):
        movement = PointsTransaction.objects.get(customer=self.customer)
        with self.assertRaises(ValueError):
            ledger.refund_spent_points(movement=movement, reason="x")


class DatabaseConstraintTests(RewardsTestCase):
    def test_one_pending_per_customer_and_reward_in_db(self):
        redemption = redeem(self.customer, self.reward).redemption
        with self.assertRaises(IntegrityError), transaction.atomic():
            Redemption.objects.create(
                customer=self.customer,
                reward=self.reward,
                points_cost=1,
                code="ABCDEFGHJKMN",
                expires_at=timezone.now() + datetime.timedelta(days=1),
                idempotency_key=uuid.uuid4(),
                spend_movement=PointsTransaction.objects.filter(kind=Kind.ADJUSTMENT).first(),
            )
        self.assertEqual(Redemption.objects.get().pk, redemption.pk)

    def test_used_requires_who_and_when(self):
        redemption = redeem(self.customer, self.reward).redemption
        with self.assertRaises(IntegrityError), transaction.atomic():
            Redemption.objects.filter(pk=redemption.pk).update(status=Status.USED)

    def test_closed_requires_refund(self):
        redemption = redeem(self.customer, self.reward).redemption
        with self.assertRaises(IntegrityError), transaction.atomic():
            Redemption.objects.filter(pk=redemption.pk).update(status=Status.CANCELLED, closed_at=timezone.now())

    def test_code_format_and_uniqueness_in_db(self):
        redemption = redeem(self.customer, self.reward).redemption
        with self.assertRaises(IntegrityError), transaction.atomic():
            Redemption.objects.filter(pk=redemption.pk).update(code="abc")
        other = redeem(self.customer, make_reward(name="Otra", points_cost=1)).redemption
        with self.assertRaises(IntegrityError), transaction.atomic():
            Redemption.objects.filter(pk=other.pk).update(code=redemption.code)

    def test_staff_cannot_validate_own_redemption_in_db(self):
        redemption = redeem(self.customer, self.reward).redemption
        with self.assertRaises(IntegrityError), transaction.atomic():
            Redemption.objects.filter(pk=redemption.pk).update(
                status=Status.USED, validated_by=self.customer, validated_at=timezone.now()
            )

    def test_reward_constraints(self):
        for overrides in ({"points_cost": 0}, {"points_cost": Reward.MAX_POINTS_COST + 1}, {"status": "OTRO"}):
            with self.subTest(**overrides), self.assertRaises(IntegrityError), transaction.atomic():
                make_reward(name="Mala", **overrides)
        with self.assertRaises(IntegrityError), transaction.atomic():
            now = timezone.now()
            make_reward(name="Fechas", valid_from=now, valid_until=now)


class SaveRewardTests(RewardsTestCase):
    def test_owner_saves_with_audit(self):
        reward = Reward(name="Nueva", points_cost=10)
        services.save_reward(actor=self.owner, reward=reward, changed_fields=["name", "points_cost"])
        event = AuditEvent.objects.get(action=AuditEvent.Action.REWARD_SAVED)
        self.assertEqual(event.target_public_id, reward.public_id)
        self.assertEqual(event.metadata["fields"], ["name", "points_cost"])

    def test_only_owner_manages_rewards(self):
        for actor in (None, self.employee, self.customer):
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                services.save_reward(actor=actor, reward=Reward(name="X", points_cost=1))
        self.assertFalse(Reward.objects.filter(name="X").exists())

    def test_validation_errors(self):
        now = timezone.now()
        for reward in (
            Reward(name="", points_cost=10),
            Reward(name="X", points_cost=0),
            Reward(name="X", points_cost=Reward.MAX_POINTS_COST + 1),
            Reward(name="X", points_cost=10, valid_from=now, valid_until=now - datetime.timedelta(days=1)),
        ):
            with self.subTest(reward=reward.__dict__), self.assertRaises(ValidationError):
                services.save_reward(actor=self.owner, reward=reward)
