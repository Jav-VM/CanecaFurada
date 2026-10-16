"""
Recompensas en el admin (solo propietarios).

- **Recompensas:** se crean y modifican con `services.save_reward`, que valida
  y deja auditoría. No se borran: se pausan o se archivan.
- **Canjes:** solo lectura. El código no se muestra (es lo que el cliente
  enseña en barra); los canjes se validan en el panel del personal.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.accounts.permissions import is_owner

from . import services
from .models import Redemption, Reward


class OwnerOnlyAdminMixin:
    def has_module_permission(self, request):
        return is_owner(request.user)

    def has_view_permission(self, request, obj=None):
        return is_owner(request.user)

    def has_add_permission(self, request):
        return is_owner(request.user)

    def has_change_permission(self, request, obj=None):
        return is_owner(request.user)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Reward)
class RewardAdmin(OwnerOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("name", "points_cost", "status", "stock_display", "valid_from", "valid_until", "position")
    list_filter = ("status",)
    search_fields = ("name",)
    readonly_fields = ("public_id", "image_preview", "redemptions_count")
    fieldsets = (
        (None, {"fields": ("name", "description", "image", "image_preview", "status", "position")}),
        (_("Canje"), {"fields": ("points_cost", "stock", "valid_from", "valid_until")}),
        (_("Referencia"), {"fields": ("public_id", "redemptions_count")}),
    )

    @admin.display(description=_("unidades"))
    def stock_display(self, obj):
        return _("Sin límite") if obj.stock is None else obj.stock

    @admin.display(description=_("vista previa"))
    def image_preview(self, obj):
        if not obj.image:
            return "—"
        return format_html('<img src="{}" alt="" style="height:96px;width:auto">', obj.image.url)

    @admin.display(description=_("canjes"))
    def redemptions_count(self, obj):
        return obj.redemptions.count() if obj.pk else 0

    def save_model(self, request, obj, form, change):
        services.save_reward(actor=request.user, reward=obj, changed_fields=form.changed_data)


@admin.register(Redemption)
class RedemptionAdmin(OwnerOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("created_at", "public_id", "customer", "reward", "points_cost", "status", "validated_by", "validated_at")
    list_filter = ("status", "reward")
    search_fields = ("public_id",)
    list_select_related = ("customer", "reward", "validated_by")
    date_hierarchy = "created_at"
    fields = (
        "public_id",
        "customer",
        "reward",
        "points_cost",
        "status",
        "created_at",
        "expires_at",
        "validated_by",
        "validated_at",
        "closed_at",
        "spend_movement",
        "refund_movement",
    )
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
