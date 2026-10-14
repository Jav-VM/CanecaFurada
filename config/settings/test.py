"""Configuración para la ejecución de tests."""
from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "test-insecure-solo-para-tests"
ALLOWED_HOSTS = ["testserver", "localhost"]

# Hasher rápido: solo acelera los tests, nunca se usa fuera de ellos.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Los tests provocan 403/404 a propósito; no se registran para mantener la salida limpia.
LOGGING["loggers"] = {"django.request": {"level": "ERROR"}}  # noqa: F405
