"""Middleware transversal de la plataforma."""
from django.conf import settings
from django.db import DatabaseError, connection
from django.http import HttpResponse
from django.utils import translation
from django.utils.translation.trans_real import parse_accept_lang_header
from django.utils.cache import patch_vary_headers

HEALTH_PATH = "/healthz"


class HealthCheckMiddleware:
    """
    Responde a `GET /healthz` para los healthchecks de Docker y Nginx.

    Va el primero de `MIDDLEWARE`: contesta antes de la validación de
    `ALLOWED_HOSTS` y de la redirección a HTTPS, que harían fallar la comprobación
    interna (`http://localhost:8000`). Solo comprueba que la BD responde; no
    devuelve versiones, nombres de servicios ni ningún otro dato. Nginx no
    publica esta ruta.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path != HEALTH_PATH:
            return self.get_response(request)
        if request.method not in ("GET", "HEAD"):
            return _plain(405, "")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except DatabaseError:
            return _plain(503, "error")
        return _plain(200, "ok")


def _plain(status, body):
    response = HttpResponse(body, status=status, content_type="text/plain; charset=utf-8")
    response["Cache-Control"] = "no-store"
    return response


# --- Idioma (Fase 15) ---------------------------------------------------------------

# Panel de empleados, dashboard y admin: siempre en el idioma por defecto (gallego).
FIXED_LANGUAGE_PREFIXES = ("/dashboard/", "/panel/")
API_PREFIX = "/api/"


def fixed_language_path(path):
    """Rutas que no admiten cambio de idioma (sin banderas)."""
    return path.startswith((*FIXED_LANGUAGE_PREFIXES, "/" + settings.ADMIN_URL.lstrip("/")))


def _supported(code):
    code = (code or "").strip().lower()
    for language, _unused in settings.LANGUAGES:
        if code == language or code.startswith(language + "-"):
            return language
    return None


def _from_accept_language(header):
    for accept, _unused in parse_accept_lang_header(header or ""):
        language = _supported(accept)
        if language:
            return language
    return None


class SiteLanguageMiddleware:
    """
    Elige el idioma de cada petición (sustituye a `LocaleMiddleware`).

    - Panel, dashboard y admin: siempre `LANGUAGE_CODE` (gallego).
    - API: la cabecera `Accept-Language` si pide un idioma admitido; si no,
      `LANGUAGE_CODE`. Así la app móvil puede pedir castellano.
    - Resto de la web: la cookie que fija `django.views.i18n.set_language` al
      pulsar una bandera; sin cookie, `LANGUAGE_CODE`. El idioma del navegador
      se ignora a propósito: la web se abre siempre en gallego.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def language_for(self, request):
        if fixed_language_path(request.path):
            return settings.LANGUAGE_CODE, ()
        if request.path.startswith(API_PREFIX):
            return _from_accept_language(request.headers.get("Accept-Language")) or settings.LANGUAGE_CODE, (
                "Accept-Language",
            )
        return _supported(request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)) or settings.LANGUAGE_CODE, ("Cookie",)

    def __call__(self, request):
        language, vary = self.language_for(request)
        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()
        response = self.get_response(request)
        if vary:
            patch_vary_headers(response, vary)
        response.headers.setdefault("Content-Language", language)
        translation.deactivate()
        return response
