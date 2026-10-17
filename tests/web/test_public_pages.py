"""Páginas públicas, plantilla base, páginas de error y recursos del sistema de diseño."""
import re
from unittest import mock

from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts import services
from apps.accounts.models import User
from apps.web import services as web
from apps.web.models import BusinessInfo, is_google_maps_url
from tests.accounts.factories import PASSWORD, make_user
from tests.loyalty.factories import make_owner

PUBLIC_PAGES = (
    ("web:home", "web/home.html"),
    ("web:about", "web/about.html"),
    ("web:menu", "web/menu.html"),
    ("web:rewards", "web/rewards.html"),
    ("web:events", "web/events.html"),
    ("web:contact", "web/contact.html"),
)


def make_customer(email="cliente@example.com"):
    return services.create_customer(email=email, password=PASSWORD, first_name="Lúa", last_name="Ficticia")


class PublicPagesTests(TestCase):
    def test_pages_are_public_and_render(self):
        for url_name, template in PUBLIC_PAGES:
            with self.subTest(url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template)
                self.assertTemplateUsed(response, "base.html")
                self.assertContains(response, "<h1", count=1)

    def test_current_page_is_marked_in_navigation(self):
        response = self.client.get(reverse("web:menu"))
        self.assertContains(
            response, f'<a href="{reverse("web:menu")}" class="nav-link" aria-current="page">', html=False
        )
        self.assertContains(response, 'aria-current="page"', count=1)

    def test_layout_includes_brand_assets_and_skip_link(self):
        response = self.client.get(reverse("web:home"))
        self.assertContains(response, "css/app.css")
        self.assertContains(response, "js/app.js")
        self.assertContains(response, "img/brand/bannerknk.jpeg")
        self.assertContains(response, 'href="#contenido"')
        self.assertContains(response, 'aria-controls="menu-principal"')
        # El logo de la cabecera y el del pie enlazan al inicio.
        self.assertContains(response, 'aria-label="Caneca Furada, ir al inicio"', count=2)
        self.assertContains(
            response, f'<a href="{reverse("web:home")}" class="rounded-2xl" aria-label="Caneca Furada, ir al inicio">', html=False
        )

    def test_home_has_all_sections(self):
        response = self.client.get(reverse("web:home"))
        for section_id in (
            "hero-titulo",
            "marca-titulo",
            "carta-titulo",
            "cervezas-titulo",
            "puntos-titulo",
            "eventos-titulo",
            "local-titulo",
        ):
            self.assertContains(response, f'id="{section_id}"')
        self.assertContains(response, "<footer", count=1)

    def test_no_invented_business_data(self):
        """Sin datos aportados se muestran estados vacíos y pendientes, nunca precios o eventos."""
        for url_name, _ in PUBLIC_PAGES:
            with self.subTest(url_name):
                response = self.client.get(reverse(url_name))
                self.assertNotContains(response, "€")
        home = self.client.get(reverse("web:home"))
        # El programa de puntos funciona desde las Fases 5–7: ya no se anuncia como «Próximamente».
        self.assertNotContains(home, "Programa de puntos <span")
        self.assertContains(home, "Pendiente de publicar")
        self.assertContains(self.client.get(reverse("web:menu")), "Estamos preparando la carta online")
        self.assertContains(self.client.get(reverse("web:events")), "No hay eventos publicados")

    def test_footer_shows_opening_hours_in_its_own_column(self):
        business = {"opening_hours": (("Martes a domingo", "18:00–00:00"),)}
        with mock.patch.dict("apps.web.content.BUSINESS", business):
            html = self.client.get(reverse("web:home")).content.decode()
            contact = self.client.get(reverse("web:contact"))
        visit = html[html.index("data-footer-visit"):html.index("data-footer-hours")]
        hours = html[html.index("data-footer-hours"):]
        self.assertNotIn("Martes a domingo", visit)
        self.assertIn("Martes a domingo", hours)
        self.assertIn("18:00–00:00", hours)
        # Una línea por franja: la hora a la derecha del día, sin salto de línea.
        self.assertRegex(hours, r"<li[^>]*><span[^>]*>Martes a domingo</span><span[^>]*>18:00–00:00</span></li>")
        # En Contacto el horario sigue dentro de los datos del local.
        self.assertContains(contact, "Martes a domingo", count=2)

    def test_contact_sections_are_side_by_side(self):
        html = self.client.get(reverse("web:contact")).content.decode()
        self.assertRegex(html, r'<div class="grid items-start gap-6 md:grid-cols-2" data-contact-sections>')
        grid = html[html.index("data-contact-sections"):]
        self.assertLess(grid.index('aria-labelledby="datos-local"'), grid.index('aria-labelledby="contacto-cuenta"'))

    def test_contact_local_has_a_line_between_title_and_content(self):
        business = {"social_links": (("Instagram", "https://example.com/ig"),)}
        with mock.patch.dict("apps.web.content.BUSINESS", business):
            contact = self.client.get(reverse("web:contact")).content.decode()
            home = self.client.get(reverse("web:home")).content.decode()
        section = contact[contact.index('aria-labelledby="datos-local"'):contact.index('aria-labelledby="contacto-cuenta"')]
        # Dirección, Horario, Contacto y Redes: todos con el espacio.
        self.assertEqual(section.count("<dd"), 4)
        self.assertEqual(len(re.findall(r'<dd class="[^"]*mt-5"', section)), 4)
        # Inicio y el pie no cambian.
        self.assertNotIn('<dd class="text-mist mt-5"', home)

    def test_contact_local_highlighted_days_and_larger_titles(self):
        business = {"opening_hours": (("Lunes", "18:00-00:00"), ("Martes", "18:00-00:00"))}
        with mock.patch.dict("apps.web.content.BUSINESS", business):
            contact = self.client.get(reverse("web:contact")).content.decode()
            home = self.client.get(reverse("web:home")).content.decode()
        section = contact[contact.index('aria-labelledby="datos-local"'):contact.index('aria-labelledby="contacto-cuenta"')]
        self.assertIn('<li><span class="text-paper">Lunes</span>: 18:00-00:00</li>', section)
        self.assertIn('<li><span class="text-paper">Martes</span>: 18:00-00:00</li>', section)
        self.assertEqual(section.count('<dt class="font-semibold text-paper text-base">'), 3)  # sin redes
        # Inicio no cambia.
        self.assertIn("<li>Lunes: 18:00-00:00</li>", home)
        self.assertNotIn("text-paper text-base", home)

    def test_contact_local_address_links_to_google_maps(self):
        with mock.patch.dict("apps.web.content.BUSINESS", {"address": "Rúa Ficticia 0"}):
            contact = self.client.get(reverse("web:contact")).content.decode()
            home = self.client.get(reverse("web:home")).content.decode()
        self.assertIn(
            '<a class="link" href="https://maps.app.goo.gl/1azgzDRChyNmEtHy8" rel="noopener noreferrer" data-contact-map>Rúa Ficticia 0</a>',
            contact,
        )
        # En el pie («Visítanos») también enlaza; en «El local» de Inicio, no.
        footer = home[home.index("data-footer-visit"):home.index("data-footer-hours")]
        self.assertIn('href="https://maps.app.goo.gl/1azgzDRChyNmEtHy8" rel="noopener noreferrer" data-contact-map>Rúa Ficticia 0</a>', footer)
        local = home[home.index('aria-labelledby="local-titulo"'):]
        local = local[:local.index("</section>")]
        self.assertIn("Rúa Ficticia 0", local)
        self.assertNotIn("data-contact-map", local)

    def test_owner_can_change_the_maps_url(self):
        owner = make_owner()
        url = "https://www.google.com/maps/place/Rua+Ficticia"
        web.update_business_info(actor=owner, data={"address": "Rúa Ficticia 0", "maps_url": url})
        cache.clear()
        for name in ("web:contact", "web:home"):
            html = self.client.get(reverse(name)).content.decode()
            self.assertIn(f'href="{url}" rel="noopener noreferrer" data-contact-map>', html)
        # Vacío: vuelve el enlace de siempre.
        web.update_business_info(actor=owner, data={"maps_url": ""})
        cache.clear()
        self.assertIn('href="https://maps.app.goo.gl/1azgzDRChyNmEtHy8"', self.client.get(reverse("web:contact")).content.decode())
        self.assertEqual(BusinessInfo.objects.get().maps_url, "")

    def test_maps_url_only_accepts_google_maps(self):
        good = (
            "https://maps.app.goo.gl/1azgzDRChyNmEtHy8",
            "https://goo.gl/maps/abc",
            "https://www.google.com/maps/place/X",
            "https://google.com/maps?q=X",
            "https://maps.google.com/?q=X",
        )
        bad = (
            "http://maps.app.goo.gl/x",
            "https://example.com/maps",
            "https://maps.app.goo.gl.example.com/x",
            "https://www.google.com/search?q=x",
            "https://goo.gl/abc",
            "https://user:pass@maps.app.goo.gl/x",
            "https://maps.app.goo.gl:8443/x",
            "javascript:alert(1)",
            "https://maps.app.goo.gl/a b",
        )
        for url in good:
            self.assertTrue(is_google_maps_url(url), url)
        owner = make_owner()
        for url in bad:
            with self.subTest(url=url):
                self.assertFalse(is_google_maps_url(url))
                with self.assertRaises(ValidationError):
                    web.update_business_info(actor=owner, data={"maps_url": url})

    def test_contact_local_without_address_has_no_map_link(self):
        contact = self.client.get(reverse("web:contact")).content.decode()
        self.assertNotIn("data-contact-map", contact)
        self.assertIn("dirección pendiente de publicar", contact)

    def test_contact_local_labels_phone_and_email(self):
        business = {"phone": "600 000 000", "email": "info@example.com"}
        with mock.patch.dict("apps.web.content.BUSINESS", business):
            contact = self.client.get(reverse("web:contact")).content.decode()
            home = self.client.get(reverse("web:home")).content.decode()
        section = contact[contact.index('aria-labelledby="datos-local"'):contact.index('aria-labelledby="contacto-cuenta"')]
        # Teléfono arriba y email justo debajo, sin espacio.
        self.assertIn('<p data-contact-phone><span class="text-paper">Teléfono:</span> <a class="link" href="tel:600 000 000">', section)
        self.assertIn('<p data-contact-email><span class="text-paper">E-mail:</span> <a class="link" href="mailto:info@example.com">', section)
        self.assertLess(section.index("data-contact-phone"), section.index("data-contact-email"))
        # Inicio y el pie siguen sin etiquetas.
        self.assertNotIn("Teléfono:", home)
        self.assertNotIn("E-mail:", home)

    def test_contact_local_email_only_has_no_phone_line(self):
        with mock.patch.dict("apps.web.content.BUSINESS", {"email": "info@example.com"}):
            contact = self.client.get(reverse("web:contact")).content.decode()
        self.assertIn('<p data-contact-email><span class="text-paper">E-mail:</span>', contact)
        self.assertNotIn("data-contact-phone", contact)

    def test_business_info_is_rendered_when_provided(self):
        business = {
            "name": "Caneca Furada",
            "city": "A Coruña",
            "address": "Rúa Ficticia 0, A Coruña",
            "opening_hours": (("Lunes a domingo", "00:00–00:00"),),
            "email": "info@example.com",
            "phone": None,
            "social_links": (("Red ficticia", "https://example.com/caneca"),),
            "about_text": "Texto de prueba.",
        }
        with mock.patch.dict("apps.web.content.BUSINESS", business):
            response = self.client.get(reverse("web:contact"))
        self.assertContains(response, "Rúa Ficticia 0, A Coruña")
        self.assertContains(response, 'href="mailto:info@example.com"')
        self.assertContains(response, 'rel="noopener noreferrer"')
        self.assertNotContains(response, "dirección pendiente de publicar")

    def test_anonymous_header_offers_login_and_register(self):
        response = self.client.get(reverse("web:home"))
        self.assertContains(response, reverse("accounts:login"))
        self.assertContains(response, reverse("accounts:register"))
        self.assertNotContains(response, reverse("accounts:logout"))

    def test_authenticated_header_offers_account_and_post_logout(self):
        self.client.force_login(make_customer())
        response = self.client.get(reverse("web:home"))
        self.assertContains(response, "Mi cuenta")
        self.assertContains(response, f'<form method="post" action="{reverse("accounts:logout")}">', html=False)
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_public_pages_do_not_expose_personal_data(self):
        user = make_customer("privada@example.com")
        self.client.force_login(user)
        for url_name, _ in PUBLIC_PAGES:
            with self.subTest(url_name):
                self.assertNotContains(self.client.get(reverse(url_name)), "privada@example.com")

    def test_only_get_and_head_allowed(self):
        response = self.client.post(reverse("web:home"))
        self.assertEqual(response.status_code, 405)


class ErrorPagesTests(TestCase):
    def test_404_uses_branded_template(self):
        response = self.client.get("/esta-pagina-no-existe/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Volver al inicio", status_code=404)

    def test_403_uses_branded_template(self):
        employee = make_user("empleado@example.com", role=User.Role.EMPLOYEE)
        self.client.force_login(employee)
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "403.html")

    def test_500_template_renders_without_request_context(self):
        from django.template import loader

        html = loader.get_template("500.html").render()
        self.assertIn("Algo ha fallado", html)
        self.assertIn("css/app.css", html)


class DesignSystemAssetsTests(TestCase):
    def test_compiled_css_and_js_are_served_by_staticfiles(self):
        for path in ("css/app.css", "js/app.js", "img/brand/logoknk.jpeg", "img/brand/bannerknk.jpeg"):
            with self.subTest(path):
                self.assertIsNotNone(finders.find(path))

    def test_compiled_css_contains_brand_palette(self):
        with open(finders.find("css/app.css"), encoding="utf-8") as fh:
            css = fh.read().lower()
        for color in ("#080808", "#171717", "#ffb800", "#a5a5a5"):
            with self.subTest(color):
                self.assertIn(color, css)

    def test_reference_image_of_other_brand_is_not_used(self):
        response = self.client.get(reverse("web:home"))
        self.assertNotContains(response, "appejemplo")


class NoJavaScriptBusinessRulesTests(TestCase):
    def test_app_js_contains_no_validation_rules(self):
        """
        El JS es solo de presentación: ni validaciones ni reglas de negocio.

        Desde la Fase 16 hay dos ayudas que no deciden nada: el aviso de edad
        (no bloquea el envío; decide el servidor) y una única consulta de
        lectura a la lista pública de localidades por CP.
        """
        with open(finders.find("js/app.js"), encoding="utf-8") as fh:
            js = fh.read()
        for forbidden in ("setCustomValidity", "XMLHttpRequest", "password", "points", "puntos"):
            with self.subTest(forbidden):
                self.assertNotIn(forbidden, js)
        self.assertEqual(js.count("fetch("), 1)
        self.assertIn("fetch(initial.dataset.localitiesUrl", js)
        self.assertNotIn("method:", js)
