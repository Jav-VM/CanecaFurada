"""Servicio de compras: validaciones, permisos, idempotencia y transacciones."""
import uuid
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from apps.loyalty import services as loyalty
from apps.purchases import services
from apps.purchases.models import Purchase
from tests.loyalty.factories import make_customer_with_qr, make_employee, make_owner


class PurchaseTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.customer, self.token = make_customer_with_qr()
        self.employee = make_employee()

    def register(self, **overrides):
        data = {
            "staff": self.employee,
            "qr_code": self.token,
            "amount": "12,50",
            "idempotency_key": uuid.uuid4(),
        }
        data.update(overrides)
        return services.register_purchase(**data)


class RegisterPurchaseTests(PurchaseTestCase):
    def test_records_all_required_fields(self):
        key = uuid.uuid4()
        result = self.register(idempotency_key=key)
        self.assertTrue(result.created)
        purchase = Purchase.objects.get()
        self.assertEqual(purchase, result.purchase)
        self.assertEqual(purchase.customer, self.customer)
        self.assertEqual(purchase.registered_by, self.employee)
        self.assertEqual(purchase.amount, Decimal("12.50"))
        self.assertIsNotNone(purchase.created_at)
        self.assertIsInstance(purchase.public_id, uuid.UUID)
        self.assertEqual(purchase.source, Purchase.Source.MANUAL)
        self.assertEqual(purchase.status, Purchase.Status.COMPLETED)
        self.assertEqual(purchase.idempotency_key, key)
        self.assertEqual(purchase.external_reference, "")

    def test_owner_can_register(self):
        self.register(staff=make_owner())
        self.assertEqual(Purchase.objects.count(), 1)

    def test_accepts_qr_payload_and_typed_code(self):
        self.register(qr_code=f"CF1:{self.token}")
        self.register(qr_code=loyalty.format_code(self.token).lower())
        self.assertEqual(Purchase.objects.count(), 2)

    def test_identify_returns_only_display_name(self):
        identified = services.identify_for_purchase(staff=self.employee, qr_code=self.token)
        self.assertEqual(identified, services.IdentifiedCustomer(display_name="Lúa F."))


class PermissionTests(PurchaseTestCase):
    def test_non_staff_cannot_register_or_identify(self):
        inactive = make_employee("inactivo@example.com", is_active=False)
        for actor in (None, AnonymousUser(), self.customer, inactive):
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionDenied):
                    self.register(staff=actor)
                with self.assertRaises(PermissionDenied):
                    services.identify_for_purchase(staff=actor, qr_code=self.token)
        self.assertFalse(Purchase.objects.exists())

    def test_pos_source_is_not_enabled(self):
        with self.assertRaises(ValidationError) as ctx:
            self.register(source=Purchase.Source.POS)
        self.assertEqual(ctx.exception.code, "source_disabled")
        self.assertFalse(Purchase.objects.exists())


class QRValidationTests(PurchaseTestCase):
    def test_invalid_codes_are_rejected(self):
        for code in ("", "basura", loyalty.generate_token(), None):
            with self.subTest(code=code), self.assertRaises(loyalty.InvalidQRCode):
                self.register(qr_code=code)
        self.assertFalse(Purchase.objects.exists())

    def test_inactive_customer_is_rejected(self):
        self.customer.is_active = False
        self.customer.save(update_fields=["is_active"])
        with self.assertRaises(loyalty.InvalidQRCode):
            self.register()
        self.assertFalse(Purchase.objects.exists())

    def test_unverified_customer_is_rejected(self):
        self.customer.email_verified_at = None
        self.customer.save(update_fields=["email_verified_at"])
        with self.assertRaises(loyalty.CustomerNotEligible):
            self.register()

    def test_rotated_code_no_longer_works(self):
        loyalty.rotate_customer_qr(self.customer)
        with self.assertRaises(loyalty.InvalidQRCode):
            self.register()

    @override_settings(PURCHASES_MAX_QR_FAILURES=3)
    def test_repeated_invalid_codes_are_throttled_per_staff_member(self):
        for _ in range(3):
            with self.assertRaises(loyalty.InvalidQRCode):
                services.identify_for_purchase(staff=self.employee, qr_code=loyalty.generate_token())
        with self.assertRaises(services.TooManyFailedAttempts):
            self.register()
        # Otro empleado no se ve afectado.
        self.register(staff=make_employee("otro@example.com"))
        self.assertEqual(Purchase.objects.count(), 1)

    def test_logs_never_contain_the_token_or_personal_data(self):
        with self.assertLogs("apps.purchases.services", level="INFO") as logs:
            self.register()
            with self.assertRaises(loyalty.InvalidQRCode):
                self.register(qr_code=self.token[:-4] + "AAAA" if not self.token.endswith("AAAA") else self.token[:-4] + "BBBB")
        output = "\n".join(logs.output)
        self.assertNotIn(self.token, output)
        self.assertNotIn(self.token[:-4], output)
        self.assertNotIn(self.customer.email, output)
        self.assertNotIn("Lúa", output)


class AmountValidationTests(PurchaseTestCase):
    def test_invalid_amounts(self):
        cases = {
            "0": "amount_min",
            "0.00": "amount_min",
            "-5": "amount_min",
            "abc": "amount_invalid",
            "": "amount_invalid",
            None: "amount_invalid",
            "NaN": "amount_invalid",
            "Infinity": "amount_invalid",
            "1.234": "amount_decimals",
            "1000.01": "amount_max",
            "1e10": "amount_max",
        }
        for value, code in cases.items():
            with self.subTest(value=value), self.assertRaises(ValidationError) as ctx:
                self.register(amount=value)
            self.assertEqual(ctx.exception.code, code)
        self.assertFalse(Purchase.objects.exists())

    def test_valid_amounts_are_normalized_to_two_decimals(self):
        for value, expected in (("12,5", "12.50"), (" 3.40 ", "3.40"), (Decimal("1000.00"), "1000.00"), ("0.01", "0.01"), (7, "7.00")):
            with self.subTest(value=value):
                self.assertEqual(str(services.parse_amount(value)), expected)

    def test_database_rejects_non_positive_amount(self):
        purchase = self.register().purchase
        with self.assertRaises(IntegrityError), transaction.atomic():
            Purchase.objects.filter(pk=purchase.pk).update(amount=Decimal("0"))

    def test_database_rejects_self_registration(self):
        purchase = self.register().purchase
        with self.assertRaises(IntegrityError), transaction.atomic():
            Purchase.objects.filter(pk=purchase.pk).update(registered_by=self.customer)


class IdempotencyTests(PurchaseTestCase):
    def test_double_submit_returns_the_same_purchase(self):
        key = uuid.uuid4()
        first = self.register(idempotency_key=key)
        second = self.register(idempotency_key=str(key))
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.purchase.pk, second.purchase.pk)
        self.assertEqual(Purchase.objects.count(), 1)

    def test_reused_key_with_different_data_is_rejected(self):
        key = uuid.uuid4()
        self.register(idempotency_key=key)
        other_customer, other_token = make_customer_with_qr("otra@example.com")
        variants = (
            {"amount": "99.00"},
            {"staff": make_employee("otro@example.com")},
            {"qr_code": other_token},
        )
        for overrides in variants:
            with self.subTest(overrides=list(overrides)), self.assertRaises(ValidationError) as ctx:
                self.register(idempotency_key=key, **overrides)
            self.assertEqual(ctx.exception.code, "idempotency_conflict")
        self.assertEqual(Purchase.objects.count(), 1)

    def test_replay_of_voided_operation_is_rejected(self):
        key = uuid.uuid4()
        purchase = self.register(idempotency_key=key).purchase
        Purchase.objects.filter(pk=purchase.pk).update(status=Purchase.Status.VOIDED)
        with self.assertRaises(ValidationError) as ctx:
            self.register(idempotency_key=key)
        self.assertEqual(ctx.exception.code, "operation_not_completed")

    def test_invalid_idempotency_key(self):
        for key in ("", "no-es-un-uuid", None, 123):
            with self.subTest(key=key), self.assertRaises(ValidationError) as ctx:
                self.register(idempotency_key=key)
            self.assertEqual(ctx.exception.code, "idempotency_invalid")

    def test_concurrent_insert_with_same_key_returns_existing(self):
        """Simula la carrera: la primera consulta no ve la compra y el INSERT choca con la restricción única."""
        key = uuid.uuid4()
        existing = self.register(idempotency_key=key).purchase
        real_select_for_update = Purchase.objects.select_for_update
        with mock.patch.object(
            Purchase.objects, "select_for_update", side_effect=lambda *a, **k: real_select_for_update(*a, **k).none()
        ):
            result = self.register(idempotency_key=key)
        self.assertFalse(result.created)
        self.assertEqual(result.purchase.pk, existing.pk)
        self.assertEqual(Purchase.objects.count(), 1)


class TransactionTests(PurchaseTestCase):
    def test_failure_after_insert_rolls_back_the_purchase(self):
        with mock.patch("apps.purchases.services.on_purchase_registered", side_effect=RuntimeError("fallo simulado")):
            with self.assertRaises(RuntimeError):
                self.register()
        self.assertFalse(Purchase.objects.exists())

    def test_failure_during_insert_leaves_nothing(self):
        with mock.patch.object(Purchase.objects, "create", side_effect=IntegrityError("fallo simulado")):
            with self.assertRaises(IntegrityError):
                self.register()
        self.assertFalse(Purchase.objects.exists())

    def test_retry_after_failure_with_same_key_succeeds_once(self):
        key = uuid.uuid4()
        with mock.patch("apps.purchases.services.on_purchase_registered", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.register(idempotency_key=key)
        result = self.register(idempotency_key=key)
        self.assertTrue(result.created)
        self.assertEqual(Purchase.objects.count(), 1)


class VisibilityTests(PurchaseTestCase):
    def test_employee_sees_only_own_purchases_owner_sees_all(self):
        mine = self.register().purchase
        other_employee = make_employee("otro@example.com")
        theirs = self.register(staff=other_employee).purchase
        self.assertEqual(list(services.visible_purchases(self.employee)), [mine])
        self.assertEqual(set(services.visible_purchases(make_owner())), {mine, theirs})
        self.assertFalse(services.visible_purchases(self.customer).exists())
