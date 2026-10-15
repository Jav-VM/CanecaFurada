"""Configuración de producción. Todos los valores sensibles vienen del entorno."""
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import SECRET_KEY, env

DEBUG = False

if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY es obligatoria en producción.")
# La clave firma también los JWT de la app (HS256): mínimo 32 bytes (RFC 7518).
if len(SIMPLE_JWT.get("SIGNING_KEY", SECRET_KEY).encode("utf-8")) < 32:  # noqa: F405
    raise ImproperlyConfigured("La clave de firma (DJANGO_SECRET_KEY o API_JWT_SIGNING_KEY) debe tener al menos 32 bytes.")

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS es obligatoria en producción.")

CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# --- Base de datos ---------------------------------------------------------------
# SQLite es solo la alternativa de desarrollo: no bloquea filas (`select_for_update`)
# ni aplica longitudes, y las protecciones de concurrencia dependen de ello.

if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":  # noqa: F405
    raise ImproperlyConfigured("DATABASE_URL es obligatoria en producción y debe apuntar a PostgreSQL.")

# --- Caché compartida --------------------------------------------------------------
# Los límites de intentos (login, QR, códigos de canje, reenvíos), el throttling
# de la API y la invalidación del contenido del local viven en la caché. Con una
# caché por proceso (memoria) o por máquina (fichero), cada worker de Gunicorn
# llevaría su propia cuenta y los límites reales se multiplicarían.

_LOCAL_CACHE_BACKENDS = {
    "django.core.cache.backends.locmem.LocMemCache",
    "django.core.cache.backends.dummy.DummyCache",
    "django.core.cache.backends.filebased.FileBasedCache",
}
if CACHES["default"]["BACKEND"] in _LOCAL_CACHE_BACKENDS:  # noqa: F405
    raise ImproperlyConfigured(
        "CACHE_URL es obligatoria en producción y debe apuntar a una caché compartida (p. ej. redis://redis:6379/1)."
    )

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
