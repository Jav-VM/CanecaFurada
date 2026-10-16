"""
Idioma (Fase 15): gallego por defecto, castellano con la bandera de España en
la web pública y el área de cliente, panel/dashboard/admin siempre en gallego,
API según Accept-Language, emails y textos guardados en gallego, catálogo
completo.

La suite general se ejecuta en castellano (`config.settings.test`); aquí se
activa el gallego como idioma del sitio con `override_settings`.
"""
import re
from pathlib import Path

from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone, translation

from apps.events import services as events
from apps.notifications import services as notifications
from apps.notifications.models import Notification
from tests.accounts.factories import PASSWORD
from tests.loyalty.factories import make_customer_with_qr, make_employee, make_owner

PO_FILE = Path(settings.BASE_DIR) / "locale" / "gl" / "LC_MESSAGES" / "django.po"
PO_FILE_ES = Path(settings.BASE_DIR) / "locale" / "es" / "LC_MESSAGES" / "django.po"
# Cambiar también LANGUAGES (con el mismo valor) vacía la caché de catálogos de
# Django: si no, el catálogo castellano cargado por otros tests (con el
# castellano como idioma del sitio) ocultaría el respaldo al gallego.
SITE = override_settings(LANGUAGE_CODE="gl", LANGUAGES=list(settings.LANGUAGES))


def choose(client, language, **headers):
    return client.post(reverse("set_language"), {"language": language}, **headers)


@SITE
class DefaultLanguageTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_public_site_opens_in_galician_even_if_the_browser_asks_for_spanish(self):
        response = self.client.get(reverse("web:home"), HTTP_ACCEPT_LANGUAGE="es-ES,es;q=0.9")
        self.assertContains(response, '<html lang="gl"')
        self.assertContains(response, "A cervexaría")
        self.assertNotContains(response, "La cervecería")
        self.assertEqual(response["Content-Language"], "gl")
        self.assertIn("Cookie", response["Vary"])

    def test_galician_flag_is_marked_and_both_flags_are_shown(self):
        response = self.client.get(reverse("web:home"))
        html = response.content.decode()
        self.assertIn("data-language-switch", html)
        self.assertRegex(html, r'value="gl"[^>]*aria-pressed="true"')
        self.assertRegex(html, r'value="es"[^>]*aria-pressed="false"')
        self.assertIn("flag-btn-active", html)

    def test_spanish_flag_switches_public_site_and_client_area(self):
        response = choose(self.client, "es", HTTP_REFERER="http://testserver" + reverse("web:menu"))
        self.assertRedirects(response, "http://testserver" + reverse("web:menu"), fetch_redirect_response=False)
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "es")
        home = self.client.get(reverse("web:home"))
        self.assertContains(home, '<html lang="es"')
        self.assertContains(home, "La cervecería")
        self.assertNotContains(home, "A cervexaría")
        self.assertContains(home, "Recompensas")
        self.assertRegex(home.content.decode(), r'value="es"[^>]*aria-pressed="true"')
        login = self.client.get(reverse("accounts:login"))
        self.assertContains(login, "¿Has olvidado tu contraseña?")
        # Y de vuelta al gallego.
        choose(self.client, "gl")
        self.assertContains(self.client.get(reverse("accounts:login")), "Esqueciches o contrasinal?")

    def test_rewards_are_called_agasallos_in_galician(self):
        response = self.client.get(reverse("web:home"))
        self.assertContains(response, "Agasallos")
        self.assertNotContains(response, "Recompensas")

    def test_language_cookie_is_restricted_and_ignores_unknown_values(self):
        response = choose(self.client, "es")
        cookie = response.cookies[settings.LANGUAGE_COOKIE_NAME]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fr"
        self.assertContains(self.client.get(reverse("web:home")), '<html lang="gl"')

    def test_switch_requires_post_and_csrf_and_never_redirects_outside(self):
        csrf_client = Client(enforce_csrf_checks=True)
        self.assertEqual(choose(csrf_client, "es").status_code, 403)
        self.assertNotIn(settings.LANGUAGE_COOKIE_NAME, csrf_client.cookies)
        self.client.get(reverse("set_language"), {"language": "es"})
        self.assertNotIn(settings.LANGUAGE_COOKIE_NAME, self.client.cookies)
        response = choose(self.client, "es", HTTP_REFERER="https://malicioso.example/robo")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(response["Location"].startswith("https://malicioso.example"))
        response = self.client.post(reverse("set_language"), {"language": "es", "next": "https://malicioso.example/"})
        self.assertFalse(response["Location"].startswith("https://malicioso.example"))

    def test_switch_form_does_not_write_the_current_url_into_the_page(self):
        # La URL de algunas páginas lleva tokens (verificación de email, contraseña).
        response = self.client.get(reverse("accounts:verify_email", args=["token-ficticio-de-prueba"]))
        self.assertContains(response, "data-language-switch")
        self.assertNotContains(response, "token-ficticio-de-prueba")


@SITE
class FixedGalicianAreasTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "es"

    def test_dashboard_is_always_galician_and_has_no_flags(self):
        self.client.force_login(make_owner())
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, '<html lang="gl"')
        self.assertContains(response, "Resumo")
        self.assertNotContains(response, "data-language-switch")

    def test_staff_panel_is_always_galician_and_has_no_flags(self):
        self.client.force_login(make_employee())
        response = self.client.get(reverse("staff:home"))
        self.assertContains(response, "Que queres facer?")
        self.assertNotContains(response, "data-language-switch")

    def test_admin_is_always_galician(self):
        response = self.client.get(reverse("admin:login"))
        self.assertContains(response, '<html lang="gl"')
        self.assertContains(response, "Contrasinal")

    def test_dashboard_rewards_section_is_agasallos(self):
        self.client.force_login(make_owner())
        response = self.client.get(reverse("dashboard:rewards"))
        self.assertContains(response, "Agasallos")
        self.assertContains(response, "Novo agasallo")
        self.assertNotContains(response, "Recompensas")

    def test_client_area_follows_the_flag(self):
        customer, _token = make_customer_with_qr()
        self.client.force_login(customer)
        self.assertContains(self.client.get(reverse("loyalty:my_points")), "Saldo disponible")
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "gl"
        self.assertContains(self.client.get(reverse("loyalty:my_points")), "Saldo dispoñible")


@SITE
class ApiLanguageTests(TestCase):
    def setUp(self):
        cache.clear()

    def login_error(self, **headers):
        response = self.client.post(
            reverse("api:login"), {"email": "nadie@example.com", "password": "x"}, content_type="application/json", **headers
        )
        self.assertEqual(response.status_code, 401)
        return response

    def test_galician_by_default_and_spanish_on_request(self):
        response = self.login_error()
        self.assertEqual(response.json()["detail"], "Email ou contrasinal incorrectos.")
        self.assertEqual(response.json()["code"], "invalid_credentials")
        self.assertIn("Accept-Language", response["Vary"])
        spanish = self.login_error(HTTP_ACCEPT_LANGUAGE="es-ES")
        self.assertEqual(spanish.json()["detail"], "Email o contraseña incorrectos.")
        self.assertEqual(spanish.json()["code"], "invalid_credentials")

    def test_api_ignores_the_web_cookie(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "es"
        self.assertEqual(self.login_error().json()["detail"], "Email ou contrasinal incorrectos.")


@SITE
class SiteLanguageMessagesTests(TestCase):
    """Emails, SMS y textos guardados: siempre en gallego, sea cual sea la bandera."""

    def setUp(self):
        cache.clear()

    def test_emails_are_galician_even_from_a_spanish_request(self):
        customer, _token = make_customer_with_qr("aviso@example.com")
        with translation.override("es"):
            notifications.send_immediately(
                kind=Notification.Kind.EMAIL_VERIFICATION,
                recipient=customer,
                to=customer.email,
                subject_template="emails/verify_email_subject.txt",
                body_template="emails/verify_email_body.txt",
                context={"first_name": "Lúa", "verification_url": "https://example.com/v/", "ttl_hours": 24},
            )
        message = mail.outbox[-1]
        self.assertEqual(message.subject, "Confirma o teu email en Caneca Furada")
        self.assertIn("Grazas por rexistrarte", message.body)

    def test_queued_notifications_are_galician(self):
        customer, _token = make_customer_with_qr("cola@example.com")
        with translation.override("es"):
            notifications.enqueue(
                kind=Notification.Kind.POINTS_EXPIRING,
                recipient=customer,
                context={"points": 10, "expires_on": "01/01/2030"},
            )
            notifications.process_due()
        self.assertIn("caducan o 01/01/2030", mail.outbox[-1].body)

    def test_reservation_dates_for_notifications_are_galician(self):
        when = timezone.make_aware(timezone.datetime(2030, 5, 4, 20, 30))
        with translation.override("es"):
            self.assertEqual(events.format_when(when), "04/05/2030 ás 20:30")


@SITE
class GalicianFormsAndMessagesTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_form_errors_are_galician(self):
        response = self.client.post(reverse("accounts:login"), {"username": "nadie@example.com", "password": "x"})
        self.assertContains(response, "Email ou contrasinal incorrectos.", status_code=200)

    def test_flash_messages_are_galician(self):
        customer, _token = make_customer_with_qr("flash@example.com")
        self.client.login(username=customer.email, password=PASSWORD)
        response = self.client.post(reverse("loyalty:rotate"), follow=True)
        self.assertContains(response, "Renovouse o teu código QR.")


@SITE
class SpanishCatalogTests(TestCase):
    """Con el gallego como idioma del sitio, el castellano no puede caer al gallego."""

    def test_every_source_text_is_returned_unchanged_in_spanish(self):
        text = PO_FILE.read_text(encoding="utf-8")
        msgids = [m for m in re.findall(r'^msgid "(.+)"$', text, re.M) if "\\" not in m]
        self.assertGreater(len(msgids), 1000)
        with translation.override("es"):
            changed = [m for m in msgids if translation.gettext(m) != m]
        self.assertEqual(changed, [])
        with translation.override("gl"):
            self.assertEqual(translation.gettext("Recompensas"), "Agasallos")

    def test_contextual_and_plural_texts_stay_in_spanish(self):
        with translation.override("es"):
            self.assertEqual(translation.pgettext("recompensa", "Activa"), "Activa")
            self.assertEqual(translation.ngettext("%(points)s punto", "%(points)s puntos", 3), "%(points)s puntos")
        with translation.override("gl"):
            self.assertEqual(translation.pgettext("recompensa", "Activa"), "Activo")

    def test_spanish_catalog_is_generated_from_the_galician_one(self):
        es = PO_FILE_ES.read_text(encoding="utf-8")
        gl = PO_FILE.read_text(encoding="utf-8")
        self.assertEqual(es.count("\nmsgid "), gl.count("\nmsgid "))
        self.assertIn('"Language: es\\n"', es)


class CatalogTests(TestCase):
    """El catálogo gallego está completo: ninguna entrada vacía ni dudosa (fuzzy)."""

    def test_po_file_is_complete(self):
        text = PO_FILE.read_text(encoding="utf-8")
        entries = [e for e in re.split(r"\n\s*\n", text) if "msgid" in e][1:]  # sin la cabecera
        self.assertGreater(len(entries), 1000)
        self.assertNotIn("#, fuzzy", text)
        # Vacía = `msgstr ""` sin líneas de continuación detrás.
        empty = [e for e in entries if re.search(r'^msgstr(\[\d\])? ""\n(?!")', e + "\n", re.M)]
        self.assertEqual(empty, [], "Entradas sin traducir en locale/gl")
