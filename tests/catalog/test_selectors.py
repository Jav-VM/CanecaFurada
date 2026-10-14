"""Reglas de visibilidad pública de la carta (independientes de las plantillas)."""
from django.test import TestCase

from apps.catalog import selectors
from apps.catalog.models import Product, TapMenu

from .factories import TempMediaMixin, make_category, make_product, make_published, uploaded_image


class PublicMenuTests(TestCase):
    def setUp(self):
        self.beers = make_category("Cervezas de la casa", position=1)
        self.food = make_category("Para picar", position=2)

    def test_only_published_products_in_published_categories(self):
        visible = make_published(category=self.beers, name="Publicada")
        make_product(category=self.beers, name="Borrador")
        make_product(category=self.beers, name="Archivada", status=Product.Status.ARCHIVED, archived_at=visible.published_at)
        hidden_category = make_category("Oculta", is_published=False)
        make_published(category=hidden_category, name="En categoría oculta")

        self.assertEqual(list(selectors.public_products()), [visible])
        menu = selectors.public_menu()
        self.assertEqual(menu, [self.beers])
        self.assertEqual(menu[0].public_products, [visible])

    def test_categories_without_public_products_are_omitted_and_ordered(self):
        make_published(category=self.food, kind=Product.Kind.FIXED, name="Patatas")
        make_published(category=self.beers, name="Rubia")
        make_category("Vacía")
        self.assertEqual(selectors.public_menu(), [self.beers, self.food])

    def test_sold_out_products_are_listed_last_and_flagged(self):
        sold_out = make_published(category=self.beers, name="A agotada", is_available=False)
        available = make_published(category=self.beers, name="B disponible")
        products = selectors.public_menu()[0].public_products
        self.assertEqual(products, [available, sold_out])
        self.assertFalse(products[1].is_available)

    def test_featured_beers_are_published_available_beers_only(self):
        featured = make_published(category=self.beers, name="Destacada", is_featured=True)
        make_published(category=self.beers, name="No destacada")
        make_published(category=self.beers, name="Agotada", is_featured=True, is_available=False)
        make_product(category=self.beers, name="Borrador", is_featured=True)
        make_published(category=self.food, kind=Product.Kind.FIXED, name="Fijo", is_featured=True)
        self.assertEqual(selectors.featured_beers(), [featured])

    def test_featured_beers_limit(self):
        for i in range(selectors.FEATURED_BEERS_LIMIT + 2):
            make_published(category=self.beers, name=f"Cerveza {i}", is_featured=True)
        self.assertEqual(len(selectors.featured_beers()), selectors.FEATURED_BEERS_LIMIT)

    def test_menu_query_count_does_not_grow_with_products(self):
        for i in range(5):
            make_published(category=self.beers, name=f"Cerveza {i}")
        with self.assertNumQueries(2):
            menu = selectors.public_menu()
            for category in menu:
                for product in category.public_products:
                    str(product.style), product.category.name


class TapMenuSelectorTests(TempMediaMixin, TestCase):
    def test_none_when_nothing_published(self):
        TapMenu.objects.create(image=uploaded_image(), is_published=False)
        self.assertIsNone(selectors.current_tap_menu())

    def test_latest_published_is_returned(self):
        TapMenu.objects.create(title="Antigua", image=uploaded_image(), is_published=True)
        latest = TapMenu.objects.create(title="Actual", image=uploaded_image(), is_published=True)
        TapMenu.objects.create(title="Sin publicar", image=uploaded_image(), is_published=False)
        self.assertEqual(selectors.current_tap_menu(), latest)
