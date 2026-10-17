"""
Orden y visibilidad de las secciones de Inicio y La cervecería (Fase 20):
lista blanca, normalización, vista del dashboard, páginas públicas y accesos.
"""
import re

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.core.models import AuditEvent
from apps.web import layout
from apps.web import services as web
from tests.loyalty.factories import make_customer_with_qr, make_employee, make_owner

URL = reverse("dashboard:content_layout")
HOME_KEYS = [key for key, _label in layout.HOME_SECTIONS]


def section_order(html):
    """Ids de las secciones de la página, en orden de aparición."""
    return re.findall(r'<section aria-labelledby="([a-z]+)-titulo"', html)


class LayoutUnitTests(SimpleTestCase):
    def test_normalize_cleans_and_completes(self):
        stored = [{"key": "eventos", "visible": False}, {"key": "hackeo"}, {"key": "eventos"}, "basura"]
        result = layout.normalize(stored, layout.HOME_SECTIONS)
        self.assertEqual(result[0], {"key": "eventos", "visible": False})
        self.assertEqual([item["key"] for item in result], ["eventos"] + [k for k in HOME_KEYS if k != "eventos"])
        self.assertEqual(layout.normalize("no es una lista", layout.HOME_SECTIONS), layout.normalize([], layout.HOME_SECTIONS))

    def test_move_stays_inside_the_list(self):
        base = layout.normalize([], layout.HOME_SECTIONS)
        self.assertEqual(layout.move(base, "marca", layout.UP), base)
        self.assertEqual(layout.move(base, "local", layout.DOWN), base)
        self.assertEqual([i["key"] for i in layout.move(base, "carta", layout.UP)][:2], ["carta", "marca"])

    def test_visibility(self):
        base = layout.normalize([], layout.ABOUT_SECTIONS)
        self.assertEqual(layout.visible_keys(layout.with_visibility(base, ["como"])), ["como"])


class LayoutViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_owner()
        self.employee = make_employee()
        self.customer, _ = make_customer_with_qr()
        self.client.force_login(self.owner)

    def post(self, data):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(URL, data)

    def test_default_order_is_the_original_one(self):
        html = self.client.get(reverse("web:home")).content.decode()
        self.assertEqual(section_order(html), ["hero"] + HOME_KEYS)
        about = self.client.get(reverse("web:about")).content.decode()
        self.assertEqual(section_order(about), ["historia", "como"])

    def test_move_up_and_hide(self):
        response = self.post({"pagina": "inicio", "mostrar": [k for k in HOME_KEYS if k != "puntos"], "mover": "eventos:arriba"})
        self.assertRedirects(response, reverse("dashboard:content") + "#orden-inicio", fetch_redirect_response=False)
        html = self.client.get(reverse("web:home")).content.decode()
        self.assertEqual(section_order(html), ["hero", "marca", "carta", "cervezas", "eventos", "local"])
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.Action.SITE_CONTENT_UPDATED, metadata__fields=["home_layout"]).exists())

    def test_hero_and_announcement_stay_first(self):
        web.update_business_info(actor=self.owner, data={"announcement": "Cerrado el lunes"})
        self.post({"pagina": "inicio", "mostrar": HOME_KEYS, "mover": "local:arriba"})
        html = self.client.get(reverse("web:home")).content.decode()
        self.assertLess(html.index("data-announcement"), html.index('aria-labelledby="hero-titulo"'))
        self.assertEqual(section_order(html)[0], "hero")

    def test_about_page_order(self):
        self.post({"pagina": "cerveceria", "mostrar": ["historia", "como"], "mover": "como:arriba"})
        about = self.client.get(reverse("web:about")).content.decode()
        self.assertEqual(section_order(about), ["como", "historia"])
        self.post({"pagina": "cerveceria", "mostrar": ["historia"]})
        self.assertEqual(section_order(self.client.get(reverse("web:about")).content.decode()), ["historia"])

    def test_dashboard_lists_sections_with_arrows(self):
        response = self.client.get(reverse("dashboard:content"))
        self.assertContains(response, "data-page-layouts")
        self.assertContains(response, 'value="eventos:abajo"')
        self.assertContains(response, 'data-layout="cerveceria"')

    def test_unknown_page_or_section_is_rejected(self):
        for data in (
            {"pagina": "admin", "mostrar": ["marca"]},
            {"pagina": "inicio", "mostrar": ["../../base"]},
            {"pagina": "inicio", "mostrar": HOME_KEYS, "mover": "hackeo:arriba"},
            {"pagina": "inicio", "mostrar": HOME_KEYS, "mover": "marca:lateral"},
        ):
            with self.subTest(data=data):
                self.assertEqual(self.post(data).status_code, 400)
        self.assertEqual(web.page_layout(layout.HOME), layout.normalize([], layout.HOME_SECTIONS))

    def test_repeating_changes_nothing(self):
        self.post({"pagina": "inicio", "mostrar": HOME_KEYS})
        self.assertFalse(AuditEvent.objects.filter(metadata__fields=["home_layout"]).exists())

    def test_access(self):
        self.assertEqual(self.client.get(URL).status_code, 405)
        for user in (self.employee, self.customer):
            self.client.force_login(user)
            self.assertEqual(self.client.post(URL, {"pagina": "inicio", "mostrar": []}).status_code, 403)
        self.client.logout()
        response = self.client.post(URL, {"pagina": "inicio", "mostrar": []})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertEqual(layout.visible_keys(web.page_layout(layout.HOME)), HOME_KEYS)

    def test_content_form_does_not_touch_the_layout(self):
        self.post({"pagina": "inicio", "mostrar": ["marca"]})
        web.update_business_info(actor=self.owner, data={"address": "Rúa Ficticia 1", "home_layout": []})
        self.assertEqual(layout.visible_keys(web.page_layout(layout.HOME)), ["marca"])
