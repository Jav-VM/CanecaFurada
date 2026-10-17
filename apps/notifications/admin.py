"""
Registro de notificaciones y campañas en el admin: solo lectura y solo propietarios.

No se muestra el contexto (aunque no lleva datos sensibles) ni se permite
reenviar, editar o borrar: los reenvíos los hace `process_notifications`.
Las campañas se gestionan en el dashboard; aquí se consultan, también las
que se han quitado del dashboard con «Eliminar» (Fase 24).
"""
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.accounts.permissions import is_owner

from .models import Campaign, Notification


class ReadOnlyOwnerAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return is_owner(request.user)

    def has_view_permission(self, request, obj=None):
        return is_owner(request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class HiddenFilter(admin.SimpleListFilter):
    title = _("quitada del dashboard")
    parameter_name = "quitada"

    def lookups(self, request, model_admin):
        return (("si", _("Sí")), ("no", _("No")))

    def queryset(self, request, queryset):
        if self.value() == "si":
            return queryset.filter(hidden_at__isnull=False)
        if self.value() == "no":
            return queryset.filter(hidden_at__isnull=True)
        return queryset


@admin.register(Campaign)
class CampaignAdmin(ReadOnlyOwnerAdmin):
    list_display = (
        "name", "channel", "status", "audience", "queued_at", "dispatched_at",
        "recipients_count", "gift_points", "gifted_count", "hidden_at",
    )
    list_filter = ("status", "channel", HiddenFilter)
    search_fields = ("name",)
    fields = (
        "public_id", "name", "channel", "subject", "body", "status", "audience", "image",
        "gift_points", "gift_points_expire", "gifted_count", "recipients_count",
        "queued_at", "dispatched_at", "hidden_at", "created_at",
    )
    readonly_fields = fields


@admin.register(Notification)
class NotificationAdmin(ReadOnlyOwnerAdmin):
    list_display = ("created_at", "kind", "channel", "status", "attempts", "last_error", "sent_at")
    list_filter = ("status", "kind", "channel", "category")
    fields = ("public_id", "kind", "category", "channel", "status", "attempts", "last_error", "created_at", "sent_at")
    readonly_fields = fields
