from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.api"
    label = "api"
    verbose_name = "API REST v1"

    def ready(self):
        # Registra la descripción OpenAPI de la autenticación propia.
        from . import schema  # noqa: F401
