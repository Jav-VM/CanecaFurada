"""
Configuración común a todos los entornos.

Los valores sensibles o dependientes del entorno se leen de variables de entorno
(o de un fichero `.env` local no versionado). Ver `.env.example`.
"""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# El fichero .env es opcional: en producción las variables llegan del entorno.
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

# --- Aplicaciones -----------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.web",
]

INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.web.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Base de datos ----------------------------------------------------------
# PostgreSQL es la base de datos objetivo. Si DATABASE_URL no está definida se
# usa SQLite local solo para facilitar el desarrollo (ver docs/fase-00-fundacion.md).

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = False
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DATABASE_CONN_MAX_AGE", default=0)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Autenticación ----------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:home"
LOGOUT_REDIRECT_URL = "accounts:login"

# Enlaces de recuperación de contraseña (tokens nativos de Django).
PASSWORD_RESET_TIMEOUT = 60 * 60 * 2  # 2 horas

# --- Cuentas de cliente -------------------------------------------------------

# URL pública del sitio para construir los enlaces de los emails. No se deduce
# de la cabecera Host de la petición para evitar enlaces manipulados.
SITE_BASE_URL = env("SITE_BASE_URL", default="http://localhost:8000").rstrip("/")

# Verificación de email: caducidad del enlace y límites de reenvío por cuenta.
EMAIL_VERIFICATION_TOKEN_TTL_HOURS = env.int("EMAIL_VERIFICATION_TOKEN_TTL_HOURS", default=24)
EMAIL_VERIFICATION_RESEND_INTERVAL_SECONDS = 60
EMAIL_VERIFICATION_MAX_PER_DAY = 5

# Edad mínima para registrarse y días entre cambios de la fecha de nacimiento.
ACCOUNTS_MIN_CUSTOMER_AGE = env.int("ACCOUNTS_MIN_CUSTOMER_AGE", default=18)
ACCOUNTS_DATE_OF_BIRTH_CHANGE_COOLDOWN_DAYS = 365

# Región por defecto para interpretar teléfonos escritos sin prefijo internacional.
PHONE_DEFAULT_REGION = "ES"

# Límite de intentos fallidos de inicio de sesión por email y por IP (el de IP
# es más alto porque muchos clientes comparten la wifi del local).
LOGIN_MAX_FAILURES_PER_EMAIL = 5
LOGIN_MAX_FAILURES_PER_IP = 30
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60

# Límite de registros y reenvíos públicos por IP y hora.
PUBLIC_FORM_MAX_PER_IP_PER_HOUR = 20

# --- Sesiones y cookies -----------------------------------------------------

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # 2 semanas
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# --- Internacionalización ---------------------------------------------------

LANGUAGE_CODE = "es-es"
TIME_ZONE = "Europe/Madrid"
USE_I18N = True
USE_TZ = True

# --- Ficheros estáticos y subidos -------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- Email ------------------------------------------------------------------
# Proveedor SMTP configurable por variables de entorno. Desarrollo usa la
# consola y los tests la memoria; producción rechaza los backends simulados.

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@example.com")

# --- Caché ------------------------------------------------------------------
# Se usa para limitar intentos de inicio de sesión. La caché en memoria es por
# proceso: con varios procesos en producción conviene una caché compartida.

CACHES = {"default": env.cache("CACHE_URL", default="locmemcache://")}

# --- Admin ------------------------------------------------------------------
# Ruta del admin configurable para no exponerla en la ruta por defecto.

ADMIN_URL = env("DJANGO_ADMIN_URL", default="admin/")

# --- Logging ----------------------------------------------------------------
# Solo consola. No registrar datos personales, contraseñas ni tokens.

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", default="INFO")},
}
