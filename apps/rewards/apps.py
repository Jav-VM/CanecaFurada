from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class RewardsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.rewards"
    label = "rewards"
    verbose_name = _("Recompensas")
