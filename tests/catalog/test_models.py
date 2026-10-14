"""Reglas del modelo y restricciones de base de datos de la carta."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from apps.catalog.models import BeerStyle, Category, Product

from .factories import make_category, make_product, make_style


class ProductValidationTests(TestCase):
    def setUp(self):
        self.category = make_category()
        self.style = make_style()

    def build(self, **overrides):
        data = {
            "category": self.category,
            "kind": Product.Kind.HOUSE_BEER,
            "name": "Cerveza Ficticia",
            "style": self.style,
            "abv": Decimal("6.0"),
            "price": Decimal("3.50"),
        }
        data.update(overrides)
        return Product(**data)

    def test_valid_beer_and_fixed_product(self):
        self.build().full_clean()
        self.build(kind=Product.Kind.FIXED, style=None, abv=None, name="Patatas").full_clean()

    def test_price_validation(self):
        for price in (Decimal("0"), Decimal("-1.00"), Decimal("3.555"), Decimal("10000.00")):
            with self.subTest(price=price), self.assertRaises(ValidationError) as ctx:
                self.build(price=price).full_clean()
            self.assertIn("price", ctx.exception.message_dict)

    def test_price_is_decimal_with_two_places(self):
        product = make_product(price=Decimal("4.5"))
        product.refresh_from_db()
        self.assertIsInstance(product.price, Decimal)
        self.assertEqual(str(product.price), "4.50")

    def test_abv_range(self):
        for abv in (Decimal("-0.1"), Decimal("100.1")):
            with self.subTest(abv=abv), self.assertRaises(ValidationError) as ctx:
                self.build(abv=abv).full_clean()
            self.assertIn("abv", ctx.exception.message_dict)

    def test_beers_require_style_and_abv(self):
        for kind in Product.BEER_KINDS:
            with self.subTest(kind=kind), self.assertRaises(ValidationError) as ctx:
                self.build(kind=kind, style=None, abv=None).full_clean()
            self.assertIn("style", ctx.exception.message_dict)
            self.assertIn("abv", ctx.exception.message_dict)

    def test_fixed_products_have_no_style_and_cannot_be_featured(self):
        with self.assertRaises(ValidationError) as ctx:
            self.build(kind=Product.Kind.FIXED, is_featured=True).full_clean()
        self.assertIn("style", ctx.exception.message_dict)
        self.assertIn("is_featured", ctx.exception.message_dict)

    def test_fixed_product_may_have_abv(self):
        self.build(kind=Product.Kind.FIXED, style=None, abv=Decimal("15.0"), name="Vermut").full_clean()

    def test_new_products_are_drafts_and_available(self):
        product = make_product()
        self.assertEqual(product.status, Product.Status.DRAFT)
        self.assertTrue(product.is_available)
        self.assertFalse(product.is_publicly_visible)
        self.assertFalse(product.is_currently_available)

    def test_current_availability_depends_on_publication_and_stock(self):
        product = make_product(status=Product.Status.PUBLISHED)
        self.assertTrue(product.is_currently_available)
        product.is_available = False
        self.assertTrue(product.is_publicly_visible)
        self.assertFalse(product.is_currently_available)
        product.is_available = True
        product.category.is_published = False
        self.assertFalse(product.is_currently_available)


class DatabaseConstraintTests(TestCase):
    """Las invariantes se protegen también en BD (p. ej. ante `update()`)."""

    def setUp(self):
        self.product = make_product()

    def assert_integrity_error(self, **values):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Product.objects.filter(pk=self.product.pk).update(**values)

    def test_price_must_be_positive(self):
        self.assert_integrity_error(price=Decimal("0"))

    def test_abv_range(self):
        self.assert_integrity_error(abv=Decimal("150.0"))

    def test_beer_needs_style_and_abv(self):
        self.assert_integrity_error(style=None)
        self.assert_integrity_error(abv=None)

    def test_fixed_product_cannot_have_style(self):
        self.assert_integrity_error(kind=Product.Kind.FIXED)

    def test_status_and_kind_must_be_valid(self):
        self.assert_integrity_error(status="DELETED")
        self.assert_integrity_error(kind="OTHER")

    def test_archived_status_requires_archived_at(self):
        self.assert_integrity_error(status=Product.Status.ARCHIVED)

    def test_category_and_style_names_are_case_insensitive_unique(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Category.objects.create(name="CERVEZAS DE LA CASA", slug="otra")
        with self.assertRaises(IntegrityError), transaction.atomic():
            BeerStyle.objects.create(name="ipa")

    def test_history_is_protected_from_deletion(self):
        """Categorías y estilos con productos (aunque estén archivados) no se pueden borrar."""
        with self.assertRaises(ProtectedError):
            self.product.category.delete()
        with self.assertRaises(ProtectedError):
            self.product.style.delete()
