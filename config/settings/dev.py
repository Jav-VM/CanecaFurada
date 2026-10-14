"""Configuración de desarrollo local. Nunca usar en producción."""
from .base import *  # noqa: F401,F403
from .base import env

DEBUG = env.bool("DJANGO_DEBUG", default=True)

# Clave solo para desarrollo local; producción exige DJANGO_SECRET_KEY.
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-solo-para-desarrollo-local")

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Los correos se muestran en consola: no se envía nada real en desarrollo.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
