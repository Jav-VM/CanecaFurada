"""
Consulta de compras para el propietario. Solo lectura: las compras se crean
con `services.register_purchase` y no se editan ni se borran (las
anulaciones llegarán como cambio de estado en una fase posterior).
"""
from django.contrib import admin

from apps.accounts.permissions import is_owner

from .models import Purchase


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("created_at", "public_id", "customer", "amount", "registered_by", "source", "status")
    list_filter = ("status", "source", "created_at")
    search_fields = ("public_id",)
    list_select_related = ("customer", "registered_by")
    date_hierarchy = "created_at"
    fields = (
        "public_id",
        "created_at",
        "customer",
        "registered_by",
        "amount",
        "source",
        "status",
        "idempotency_key",
        "external_reference",
    )
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
