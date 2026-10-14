"""
Fidelización en el admin (solo propietarios).

- **Reglas de conversión:** solo se añaden (`conversion.create_rule`); no se
  editan ni se borran, así queda la historia de cada cambio.
- **Promociones:** se crean y modifican con `promotions.save_promotion`, que
  valida y deja auditoría. No se borran: se pausan o finalizan.
- **Movimientos de puntos:** solo lectura. Las correcciones se hacen con
  movimientos compensatorios (`ledger`), nunca editando filas.

El QR del cliente no aparece en el admin.
"""
from django.contrib import admin

from apps.accounts.permissions import is_owner

from . import conversion, promotions
from .models import LoyaltyRule, PointsTransaction, Promotion


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


@admin.register(LoyaltyRule)
class LoyaltyRuleAdmin(OwnerOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("points_per_euro", "valid_from", "note", "created_by", "created_at")
    fields = ("points_per_euro", "valid_from", "note")

    def has_change_permission(self, request, obj=None):
        # La lista es visible, pero una regla guardada no se modifica.
        return False

    def save_model(self, request, obj, form, change):
        rule = conversion.create_rule(
            actor=request.user,
            points_per_euro=obj.points_per_euro,
            valid_from=obj.valid_from,
            note=obj.note,
        )
        obj.pk, obj.public_id, obj.created_by = rule.pk, rule.public_id, rule.created_by


@admin.register(Promotion)
class PromotionAdmin(OwnerOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("name", "kind", "bonus_type", "status", "starts_at", "ends_at", "uses")
    list_filter = ("status", "kind")
    search_fields = ("name",)
    readonly_fields = ("public_id", "uses")
    fieldsets = (
        (None, {"fields": ("name", "description", "kind", "status")}),
        ("Bonificación", {"fields": ("bonus_type", "fixed_points", "multiplier")}),
        # `birthday_window_days` no se usa desde la Fase 10 (el regalo es el día del cumpleaños).
        ("Condiciones", {"fields": ("min_purchase_amount",)}),
        ("Fechas", {"fields": ("starts_at", "ends_at")}),
        ("Límites", {"fields": ("max_uses_per_customer", "max_total_uses", "uses")}),
        ("Referencia", {"fields": ("public_id",)}),
    )

    @admin.display(description="usos")
    def uses(self, obj):
        if obj.pk is None:
            return 0
        return obj.points_transactions.filter(
            kind__in=[PointsTransaction.Kind.PROMOTION_BONUS, PointsTransaction.Kind.BIRTHDAY_GIFT]
        ).count()

    def save_model(self, request, obj, form, change):
        promotions.save_promotion(actor=request.user, promotion=obj, changed_fields=form.changed_data)


@admin.register(PointsTransaction)
class PointsTransactionAdmin(OwnerOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("created_at", "public_id", "customer", "kind", "points", "balance_after", "promotion")
    list_filter = ("kind", "created_at")
    search_fields = ("public_id",)
    list_select_related = ("customer", "promotion")
    date_hierarchy = "created_at"
    fields = (
        "public_id",
        "created_at",
        "customer",
        "kind",
        "points",
        "balance_after",
        "purchase",
        "promotion",
        "birthday_year",
        "reverses",
        "rule",
        "base_amount",
        "points_per_euro",
        "created_by",
        "reason",
    )
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
