"""
Idioma de los textos que se guardan o se envían (Fase 15).

La interfaz sigue el idioma de cada petición, pero los textos que quedan
guardados (motivos de movimientos de puntos, nombres por defecto, contexto de
las notificaciones) y los emails y SMS van siempre en el idioma del sitio
(`LANGUAGE_CODE`, gallego). Así no dependen de la bandera que tuviera elegida
quien provocó la operación.
"""
from django.conf import settings
from django.utils import translation
from django.utils.functional import lazy


def site_language():
    """Contexto que activa el idioma del sitio: `with site_language(): texto = _("…")`."""
    return translation.override(settings.LANGUAGE_CODE)


def site_text(message, **values):
    """
    Texto en el idioma del sitio. `message` debe ser perezoso (`gettext_lazy`)
    para que se traduzca aquí y no en el idioma de la petición.
    """
    with site_language():
        text = str(message)
    return text % values if values else text


def _interpolate(message, values):
    return str(message) % values


# `_("… %(x)s …") % {...}` evalúa la traducción al momento: fuera de una función
# (atributos de formularios y modelos) quedaría fija en el idioma de arranque.
# lazy_format(_("… %(x)s …"), {"x": valor}) la evalúa al mostrarse.
lazy_format = lazy(_interpolate, str)
