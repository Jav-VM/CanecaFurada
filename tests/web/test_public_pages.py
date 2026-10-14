"""Páginas públicas, plantilla base, páginas de error y recursos del sistema de diseño."""
from unittest import mock

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from apps.accounts import services
from apps.accounts.models import User
from tests.accounts.factories import PASSWORD, make_user

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
        """El JS es solo de presentación: ni validaciones ni reglas de negocio."""
        with open(finders.find("js/app.js"), encoding="utf-8") as fh:
            js = fh.read()
        for forbidden in ("setCustomValidity", "fetch(", "XMLHttpRequest", "password", "points", "puntos"):
            with self.subTest(forbidden):
                self.assertNotIn(forbidden, js)
