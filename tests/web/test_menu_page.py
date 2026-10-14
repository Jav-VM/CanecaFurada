"""Visualización pública de la carta y de la selección del inicio."""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Product, TapMenu
from tests.catalog.factories import TempMediaMixin, make_category, make_product, make_published, uploaded_image


class MenuPageTests(TempMediaMixin, TestCase):
    def setUp(self):
        self.beers = make_category("Cervezas de la casa", slug="cervezas", position=1)
        self.food = make_category("Para picar", slug="para-picar", position=2)

    def get(self):
        return self.client.get(reverse("web:menu"))

    def test_shows_categories_inside_single_carta_section(self):
        make_published(category=self.beers, name="Rubia Ficticia", price=Decimal("3.50"), serving="33 cl")
        make_published(category=self.food, kind=Product.Kind.FIXED, name="Patatas Ficticias", price=Decimal("4.00"))
        response = self.get()
        self.assertContains(response, "<h1", count=1)
        self.assertContains(response, 'id="cervezas"')
        self.assertContains(response, 'href="#para-picar"')
        self.assertContains(response, "Rubia Ficticia")
        self.assertContains(response, "3,50 €")
        self.assertContains(response, "33 cl")
        self.assertContains(response, "5,5 % vol.")
        self.assertContains(response, "IPA")
        self.assertContains(response, "Patatas Ficticias")
        self.assertNotContains(response, "Estamos preparando la carta online")

    def test_drafts_archived_and_hidden_categories_are_not_shown(self):
        make_published(category=self.beers, name="Visible")
        make_product(category=self.beers, name="Borrador Secreto")
        make_product(category=self.beers, name="Archivada Antigua", status=Product.Status.ARCHIVED, archived_at="2026-01-01T00:00:00Z")
        hidden = make_category("Temporada", slug="temporada", is_published=False)
        make_published(category=hidden, name="De Temporada")
        response = self.get()
        self.assertContains(response, "Visible")
        for name in ("Borrador Secreto", "Archivada Antigua", "De Temporada", 'id="temporada"'):
            self.assertNotContains(response, name)

    def test_sold_out_beer_is_marked_and_not_presented_as_available(self):
        make_published(category=self.beers, name="Agotadísima", is_available=False)
        response = self.get()
        self.assertContains(response, "Agotadísima")
        self.assertContains(response, ">Agotada<")

    def test_sold_out_fixed_product_uses_masculine_label(self):
        make_published(category=self.food, kind=Product.Kind.FIXED, name="Nachos", is_available=False)
        self.assertContains(self.get(), ">Agotado<")

    def test_product_content_is_escaped(self):
        make_published(category=self.beers, name="<script>alert(1)</script>", description="<b>negrita</b>")
        response = self.get()
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")
        self.assertContains(response, "&lt;b&gt;negrita&lt;/b&gt;")

    def test_tap_menu_placeholder_until_owner_uploads_image(self):
        response = self.get()
        self.assertContains(response, 'id="carta-grifos"')
        self.assertContains(response, "data-tap-menu-placeholder")
        self.assertContains(response, "La carta de grifos se publicará aquí")

    def test_published_tap_menu_image_is_shown(self):
        tap_menu = TapMenu.objects.create(
            image=uploaded_image(), text_alternative="Grifo 1: Rubia Ficticia", is_published=True
        )
        response = self.get()
        self.assertNotContains(response, "data-tap-menu-placeholder")
        self.assertContains(response, tap_menu.image.url)
        self.assertContains(response, "Grifo 1: Rubia Ficticia")
        self.assertContains(response, 'width="8" height="8"')

    def test_unpublished_tap_menu_is_not_shown(self):
        tap_menu = TapMenu.objects.create(image=uploaded_image(), is_published=False)
        response = self.get()
        self.assertNotContains(response, tap_menu.image.url)
        self.assertContains(response, "data-tap-menu-placeholder")

    def test_empty_menu_keeps_empty_state(self):
        make_product(category=self.beers, name="Borrador")
        self.assertContains(self.get(), "Estamos preparando la carta online")

    def test_menu_does_not_expose_internal_ids(self):
        product = make_published(category=self.beers)
        response = self.get()
        self.assertContains(response, f"producto-{product.public_id}")
        self.assertNotContains(response, f"producto-{product.pk}\"")


class HomeFeaturedBeersTests(TestCase):
    def test_home_shows_only_featured_available_beers(self):
        category = make_category()
        make_published(category=category, name="Destacada Ficticia", is_featured=True)
        make_published(category=category, name="Agotada Ficticia", is_featured=True, is_available=False)
        make_published(category=category, name="Normal Ficticia")
        response = self.client.get(reverse("web:home"))
        self.assertContains(response, "Destacada Ficticia")
        self.assertNotContains(response, "Agotada Ficticia")
        self.assertNotContains(response, "Normal Ficticia")
        self.assertNotContains(response, "Estamos preparando la selección de cervezas")

    def test_home_empty_state_without_featured_beers(self):
        self.assertContains(self.client.get(reverse("web:home")), "Estamos preparando la selección de cervezas")
