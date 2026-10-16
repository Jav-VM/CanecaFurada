from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class LoyaltyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.loyalty"
    label = "loyalty"
    verbose_name = _("Fidelización")
