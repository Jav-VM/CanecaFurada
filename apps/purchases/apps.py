from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PurchasesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.purchases"
    label = "purchases"
    verbose_name = _("Compras")
