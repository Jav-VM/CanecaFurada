"""
Orden, visibilidad y textos de las secciones de Carta, Recompensas, Eventos y
Contacto (Fase 22), con las mismas reglas que Inicio (Fases 20–21).
"""
import re

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.web import blocks, layout
from apps.web import services as web
from tests.catalog.factories import uploaded_image
from tests.loyalty.factories import make_customer_with_qr, make_owner

PAGE_URLS = {
    layout.MENU: "web:menu",
    layout.REWARDS: "web:rewards",
    layout.EVENTS: "web:events",
    layout.CONTACT: "web:contact",
}
DEFAULT_ORDER = {
    layout.MENU: ["carta-grifos", "carta-listado"],
    layout.REWARDS: ["como-funciona", "catalogo", "unete"],
    layout.EVENTS: ["eventos-listado", "eventos-reservar"],
    layout.CONTACT: ["datos-local", "contacto-cuenta"],
}


def order(html):
    """Ids de las secciones en orden (las categorías de la carta no cuentan: no hay ninguna)."""
    return re.findall(r'<section aria-labelledby="([a-z-]+)"', html)


class MorePagesTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_owner()
        self.client.force_login(self.owner)

    def post(self, url, data):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(url, data)

    def page(self, page):
        return self.client.get(reverse(PAGE_URLS[page])).content.decode()

    def keys(self, page):
        return [key for key, _label in web.sections_for(page)]


class OrderTests(MorePagesTestCase):
    def test_default_order_is_the_original_one(self):
        for page, expected in DEFAULT_ORDER.items():
            with self.subTest(page=page):
                self.assertEqual(order(self.page(page)), expected)

    def test_move_and_hide_on_every_page(self):
        for page in PAGE_URLS:
            keys = self.keys(page)
            with self.subTest(page=page):
                self.post(reverse("dashboard:content_layout"), {"pagina": page, "mostrar": keys, "mover": f"{keys[-1]}:arriba"})
                moved = order(self.page(page))
                self.assertEqual(moved[-2], DEFAULT_ORDER[page][-1])
                self.post(reverse("dashboard:content_layout"), {"pagina": page, "mostrar": keys[1:]})
                self.assertNotIn(DEFAULT_ORDER[page][0], order(self.page(page)))

    def test_menu_index_links_to_taps_only_when_visible(self):
        from tests.catalog.factories import make_published

        make_published()
        self.assertIn('href="#carta-grifos"', self.page(layout.MENU))
        self.post(reverse("dashboard:content_layout"), {"pagina": "carta", "mostrar": ["listado"]})
        self.assertNotIn('href="#carta-grifos"', self.page(layout.MENU))

    def test_phone_reservations_notice_stays_first(self):
        web.set_online_reservations(actor=self.owner, enabled=False)
        self.post(reverse("dashboard:content_layout"), {"pagina": "contacto", "mostrar": ["local", "cuenta"], "mover": "cuenta:arriba"})
        html = self.page(layout.CONTACT)
        self.assertLess(html.index("data-phone-reservations"), html.index('aria-labelledby="contacto-cuenta"'))
        self.assertLess(html.index("contacto-cuenta"), html.index('aria-labelledby="datos-local"'))


class TextTests(MorePagesTestCase):
    def test_edit_and_restore_texts(self):
        url = reverse("dashboard:section_edit", args=["agasallos", "catalogo"])
        self.post(url, {"eyebrow": "Premios", "title": "O que podes levar", "body": "Cambia os teus puntos."})
        html = self.page(layout.REWARDS)
        self.assertIn("O que podes levar", html)
        self.assertIn("Cambia os teus puntos.", html)
        self.post(url, {"eyebrow": "", "title": "", "body": ""})
        self.assertIn("Recompensas disponibles", self.page(layout.REWARDS))

    def test_state_dependent_texts_keep_working(self):
        html = self.page(layout.REWARDS)
        self.assertIn("Ya formas parte", html)  # propietario con sesión
        self.client.logout()
        self.assertIn("Únete al club", self.page(layout.REWARDS))
        self.client.force_login(self.owner)
        self.assertIn("Envía una solicitud desde tu cuenta", self.page(layout.EVENTS))
        web.set_online_reservations(actor=self.owner, enabled=False)
        cache.clear()
        self.assertIn("Las reservas se hacen por teléfono", self.page(layout.EVENTS))

    def test_owner_text_replaces_the_state_dependent_one(self):
        self.post(reverse("dashboard:section_edit", args=["eventos", "reservar"]), {"body": "Chama ao local."})
        html = self.page(layout.EVENTS)
        self.assertIn("Chama ao local.", html)
        self.assertNotIn("Envía una solicitud desde tu cuenta", html)

    def test_listing_heading_only_when_written(self):
        self.assertNotIn('id="carta-categorias"', self.page(layout.MENU))
        self.post(reverse("dashboard:section_edit", args=["carta", "listado"]), {"title": "Toda a carta"})
        self.assertIn("Toda a carta", self.page(layout.MENU))

    def test_tap_menu_heading_uses_owner_text(self):
        self.post(reverse("dashboard:section_edit", args=["carta", "grifos"]), {"title": "Na billa hoxe"})
        self.assertIn("Na billa hoxe", self.page(layout.MENU))

    def test_texts_are_escaped(self):
        self.post(reverse("dashboard:section_edit", args=["contacto", "cuenta"]), {"title": "<script>x</script>"})
        html = self.page(layout.CONTACT)
        self.assertNotIn("<script>x</script>", html)
        self.assertIn("&lt;script&gt;", html)


class RulesTests(MorePagesTestCase):
    def test_no_images_or_articles_on_new_pages(self):
        for page in PAGE_URLS:
            self.assertFalse(blocks.allows_images(page))
            key = self.keys(page)[0]
            self.assertNotContains(self.client.get(reverse("dashboard:section_edit", args=[page, key])), 'name="images"')
        with self.assertRaises(ValidationError):
            blocks.save_block(actor=self.owner, page="carta", key="grifos", data={}, new_images=[uploaded_image()])

    def test_unknown_sections_are_rejected(self):
        self.assertEqual(self.client.get(reverse("dashboard:section_edit", args=["carta", "historia"])).status_code, 404)
        response = self.post(reverse("dashboard:content_layout"), {"pagina": "eventos", "mostrar": ["../base"]})
        self.assertEqual(response.status_code, 400)

    def test_only_owner(self):
        customer, _ = make_customer_with_qr()
        self.client.force_login(customer)
        url = reverse("dashboard:section_edit", args=["contacto", "local"])
        self.assertEqual(self.client.post(url, {"title": "x"}).status_code, 403)

    def test_dashboard_lists_the_new_pages(self):
        response = self.client.get(reverse("dashboard:content"))
        for page in PAGE_URLS:
            self.assertContains(response, f'data-layout="{page}"')
        self.assertContains(response, reverse("dashboard:section_edit", args=["agasallos", "unete"]))
