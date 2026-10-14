"""Configuración de producción. Todos los valores sensibles vienen del entorno."""
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import SECRET_KEY, env

DEBUG = False

if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY es obligatoria en producción.")

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS es obligatoria en producción.")

CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# --- Email real obligatorio ----------------------------------------------------
# En producción no se simulan envíos: se rechazan los backends de consola,
# memoria, fichero o nulo y se exige un servidor SMTP y una URL pública HTTPS.

_SIMULATED_EMAIL_BACKENDS = {
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.filebased.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
}
if EMAIL_BACKEND in _SIMULATED_EMAIL_BACKENDS:  # noqa: F405
    raise ImproperlyConfigured("EMAIL_BACKEND no puede ser un backend simulado en producción.")
if EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend" and not EMAIL_HOST:  # noqa: F405
    raise ImproperlyConfigured("EMAIL_HOST es obligatoria en producción.")
if SMS_BACKEND in {"apps.notifications.sms.LocmemSmsBackend"}:  # noqa: F405
    raise ImproperlyConfigured("SMS_BACKEND no puede ser un backend simulado en producción.")
if not SITE_BASE_URL.startswith("https://"):  # noqa: F405
    raise ImproperlyConfigured("SITE_BASE_URL es obligatoria en producción y debe usar https://.")

# --- HTTPS y cookies seguras -------------------------------------------------

SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
SECURE_HSTS_PRELOAD = env.bool("DJANGO_SECURE_HSTS_PRELOAD", default=False)

# Solo si hay un proxy inverso de confianza que termina TLS y fija la cabecera.
if env.bool("DJANGO_BEHIND_TLS_PROXY", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
