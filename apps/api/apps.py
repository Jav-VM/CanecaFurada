from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.api"
    label = "api"
    verbose_name = _("API REST v1")

    def ready(self):
        # Registra la descripción OpenAPI de la autenticación propia.
        from . import schema  # noqa: F401
