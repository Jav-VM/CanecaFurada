"""
Registro de notificaciones en el admin: solo lectura y solo propietarios.

No se muestra el contexto (aunque no lleva datos sensibles) ni se permite
reenviar, editar o borrar: los reenvíos los hace `process_notifications`.
Las campañas se gestionan en el dashboard.
"""
from django.contrib import admin

from apps.accounts.permissions import is_owner

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "channel", "status", "attempts", "last_error", "sent_at")
    list_filter = ("status", "kind", "channel", "category")
    fields = ("public_id", "kind", "category", "channel", "status", "attempts", "last_error", "created_at", "sent_at")
    readonly_fields = fields

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
