"""Configuración de desarrollo local. Nunca usar en producción."""
from .base import *  # noqa: F401,F403
from .base import env

DEBUG = env.bool("DJANGO_DEBUG", default=True)

# Clave solo para desarrollo local; producción exige DJANGO_SECRET_KEY.
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-solo-para-desarrollo-local")

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Por defecto los correos se muestran en consola (no se envía nada real). Para
# probar un SMTP de desarrollo (p. ej. Mailpit) define EMAIL_BACKEND en .env.
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")

# La documentación de la API se puede consultar sin sesión en desarrollo.
API_DOCS_PUBLIC = env.bool("API_DOCS_PUBLIC", default=True)
