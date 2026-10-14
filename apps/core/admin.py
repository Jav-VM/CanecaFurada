from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    """Auditoría de solo lectura: no se crea, edita ni borra desde el admin."""

    list_display = ("created_at", "action", "actor", "target_public_id")
    list_filter = ("action",)
    readonly_fields = ("created_at", "action", "actor", "target_public_id", "metadata")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
