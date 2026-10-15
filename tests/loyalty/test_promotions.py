"""Promociones: condiciones, fechas, límites, estado, cumpleaños (29-F, duplicados, abuso) y consentimiento."""
import datetime
import uuid
from decimal import Decimal
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import CustomerProfile
from apps.core.models import AuditEvent
from apps.loyalty import ledger, promotions
from apps.loyalty.models import PointsTransaction, Promotion
from tests.accounts.factories import VALID_MOBILE

from .factories import buy, make_customer_with_qr, make_employee, make_owner, make_promotion

Kind = PointsTransaction.Kind
MADRID = ZoneInfo("Europe/Madrid")


def bonuses(customer):
    return list(
        PointsTransaction.objects.filter(customer=customer, kind=Kind.PROMOTION_BONUS).values_list(
            "promotion__name", "points", "birthday_year"
        )
    )


class PromotionTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.customer, self.token = make_customer_with_qr()
        self.employee = make_employee()
        self.owner = make_owner()

    def buy(self, amount="10.00", token=None):
        return buy(self.employee, token or self.token, amount)


class PurchasePromotionTests(PromotionTestCase):
    def test_fixed_points_bonus(self):
        make_promotion(name="Bienvenida", fixed_points=25)
        self.buy("10.00")
        self.assertEqual(bonuses(self.customer), [("Bienvenida", 25, None)])
        self.assertEqual(ledger.balance(self.customer), 35)

    def test_multiplier_bonus_rounds_down(self):
        make_promotion(name="Doble", bonus_type=Promotion.BonusType.MULTIPLIER, fixed_points=None, multiplier=Decimal("2.00"))
        make_promotion(name="Y medio", bonus_type=Promotion.BonusType.MULTIPLIER, fixed_points=None, multiplier=Decimal("1.50"))
        self.buy("5.00")  # 5 puntos base -> +5 (doble) y +2 (2,5 redondeado hacia abajo)
        self.assertEqual(sorted(bonuses(self.customer)), [("Doble", 5, None), ("Y medio", 2, None)])
        self.assertEqual(ledger.balance(self.customer), 12)

    def test_multiplier_without_base_points_gives_nothing(self):
        make_promotion(bonus_type=Promotion.BonusType.MULTIPLIER, fixed_points=None, multiplier=Decimal("3.00"))
        self.buy("0.50")
        self.assertFalse(PointsTransaction.objects.exists())

    def test_only_active_promotions_within_dates(self):
        now = timezone.now()
        make_promotion(name="Borrador", status=Promotion.Status.DRAFT)
        make_promotion(name="Pausada", status=Promotion.Status.PAUSED)
        make_promotion(name="Finalizada", status=Promotion.Status.ENDED)
        make_promotion(name="Futura", starts_at=now + datetime.timedelta(hours=1))
        make_promotion(name="Caducada", starts_at=now - datetime.timedelta(days=5), ends_at=now - datetime.timedelta(days=1))
        make_promotion(name="Vigente", ends_at=now + datetime.timedelta(days=1))
        self.buy()
        self.assertEqual(bonuses(self.customer), [("Vigente", 10, None)])

    def test_minimum_purchase_amount(self):
        make_promotion(min_purchase_amount=Decimal("20.00"))
        self.buy("19.99")
        self.assertEqual(bonuses(self.customer), [])
        self.buy("20.00")
        self.assertEqual(len(bonuses(self.customer)), 1)

    def test_limit_per_customer(self):
        make_promotion(max_uses_per_customer=2)
        for _ in range(4):
            self.buy()
        self.assertEqual(len(bonuses(self.customer)), 2)

    def test_total_limit_across_customers(self):
        make_promotion(max_total_uses=2)
        other, other_token = make_customer_with_qr("otra@example.com")
        third, third_token = make_customer_with_qr("tercera@example.com")
        self.buy()
        self.buy(token=other_token)
        self.buy(token=third_token)
        self.assertEqual(PointsTransaction.objects.filter(kind=Kind.PROMOTION_BONUS).count(), 2)
        self.assertEqual(bonuses(third), [])

    def test_retry_does_not_duplicate_bonus(self):
        make_promotion()
        from apps.purchases import services as purchases

        key = uuid.uuid4()
        for _ in range(2):
            purchases.register_purchase(staff=self.employee, qr_code=self.token, amount="10", idempotency_key=key)
        self.assertEqual(len(bonuses(self.customer)), 1)

    def test_database_rejects_duplicate_bonus_for_same_purchase(self):
        promotion = make_promotion()
        purchase = self.buy()
        with self.assertRaises(IntegrityError), transaction.atomic():
            PointsTransaction.objects.create(
                customer=self.customer,
                kind=Kind.PROMOTION_BONUS,
                points=10,
                balance_after=30,
                purchase=purchase,
                promotion=promotion,
            )


class PromotionValidationTests(PromotionTestCase):
    def build(self, **overrides):
        data = {
            "name": "Ficticia",
            "bonus_type": Promotion.BonusType.FIXED_POINTS,
            "fixed_points": 10,
            "starts_at": timezone.now(),
            "status": Promotion.Status.ACTIVE,
        }
        data.update(overrides)
        return Promotion(**data)

    def test_clean_rejects_inconsistent_promotions(self):
        now = timezone.now()
        invalid = [
            {"fixed_points": None},
            {"fixed_points": 0},
            {"fixed_points": 10001},
            {"multiplier": Decimal("2.00")},
            {"bonus_type": Promotion.BonusType.MULTIPLIER, "fixed_points": None},
            {"bonus_type": Promotion.BonusType.MULTIPLIER, "fixed_points": None, "multiplier": Decimal("1.00")},
            {"bonus_type": Promotion.BonusType.MULTIPLIER, "fixed_points": None, "multiplier": Decimal("10.01")},
            {"ends_at": now - datetime.timedelta(seconds=1)},
            {"min_purchase_amount": Decimal("0")},
            {"max_total_uses": 0},
            {"birthday_window_days": 32},
            {"status": "INVENTADO"},
        ]
        for overrides in invalid:
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                self.build(starts_at=now, **overrides).full_clean()

    def test_database_constraints(self):
        now = timezone.now()
        for overrides in (
            {"fixed_points": None},
            {"multiplier": Decimal("2.00")},
            {"ends_at": now - datetime.timedelta(days=1)},
            # Cabe en el campo (8): así falla la CHECK y no la longitud (PostgreSQL).
            {"status": "INVALIDO"},
            {"birthday_window_days": 40},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(IntegrityError), transaction.atomic():
                self.build(starts_at=now, **overrides).save()

    def test_only_owner_saves_promotions_with_audit(self):
        for actor in (None, self.employee, self.customer):
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                promotions.save_promotion(actor=actor, promotion=self.build())
        self.assertFalse(Promotion.objects.exists())
        promotion = promotions.save_promotion(actor=self.owner, promotion=self.build(), changed_fields=["name"])
        event = AuditEvent.objects.get(action=AuditEvent.Action.PROMOTION_SAVED)
        self.assertEqual(event.target_public_id, promotion.public_id)
        self.assertEqual(event.metadata, {"created": True, "status": "ACTIVE", "fields": ["name"]})

    def test_save_validates(self):
        with self.assertRaises(ValidationError):
            promotions.save_promotion(actor=self.owner, promotion=self.build(fixed_points=None))


def set_birth_date(user, date_of_birth, changed_at=None):
    CustomerProfile.objects.filter(user=user).update(date_of_birth=date_of_birth, date_of_birth_changed_at=changed_at)


def birthday_today(years=30):
    today = timezone.localdate()
    return today.replace(year=today.year - years) if not (today.month == 2 and today.day == 29) else datetime.date(today.year - 32, 2, 29)


class BirthdayOccurrenceTests(TestCase):
    def test_29_february_is_celebrated_on_28_in_common_years(self):
        dob = datetime.date(2000, 2, 29)
        self.assertEqual(promotions.birthday_occurrence(dob, datetime.date(2027, 2, 28), 0), datetime.date(2027, 2, 28))
        self.assertIsNone(promotions.birthday_occurrence(dob, datetime.date(2027, 3, 1), 0))
        self.assertEqual(promotions.birthday_occurrence(dob, datetime.date(2028, 2, 29), 0), datetime.date(2028, 2, 29))
        self.assertIsNone(promotions.birthday_occurrence(dob, datetime.date(2028, 2, 28), 0))

    def test_window_crosses_the_new_year(self):
        dob = datetime.date(1990, 1, 2)
        self.assertEqual(promotions.birthday_occurrence(dob, datetime.date(2026, 12, 28), 7), datetime.date(2027, 1, 2))
        dob = datetime.date(1990, 12, 30)
        self.assertEqual(promotions.birthday_occurrence(dob, datetime.date(2027, 1, 3), 7), datetime.date(2026, 12, 30))

    def test_window_edges(self):
        dob = datetime.date(1990, 6, 15)
        self.assertIsNotNone(promotions.birthday_occurrence(dob, datetime.date(2026, 6, 22), 7))
        self.assertIsNotNone(promotions.birthday_occurrence(dob, datetime.date(2026, 6, 8), 7))
        self.assertIsNone(promotions.birthday_occurrence(dob, datetime.date(2026, 6, 23), 7))


class BirthdayPromotionAtPurchaseTests(PromotionTestCase):
    """Desde la Fase 10 las promociones de cumpleaños no dan nada al comprar: regalan el día."""

    def test_birthday_promotion_gives_nothing_at_purchase(self):
        make_promotion(name="Cumpleaños", kind=Promotion.Kind.BIRTHDAY, fixed_points=50)
        set_birth_date(self.customer, birthday_today())
        self.buy()
        self.assertEqual(bonuses(self.customer), [])
        self.assertEqual(ledger.balance(self.customer), 10)

    def test_birthday_promotion_requires_fixed_points(self):
        promo = Promotion(
            name="Cumpleaños doble",
            kind=Promotion.Kind.BIRTHDAY,
            bonus_type=Promotion.BonusType.MULTIPLIER,
            multiplier=Decimal("2.00"),
            starts_at=timezone.now(),
        )
        with self.assertRaises(ValidationError) as ctx:
            promo.full_clean()
        self.assertIn("bonus_type", ctx.exception.message_dict)
        with self.assertRaises(IntegrityError), transaction.atomic():
            promo.save()


