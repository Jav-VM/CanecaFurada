"""
Gestión de la carta desde el admin (solo propietarios).

- Nada se borra desde aquí: los productos se archivan, las categorías se
  despublican y las cartas de grifos antiguas quedan despublicadas.
- La publicación y la disponibilidad de los productos pasan siempre por
  `services`, que comprueban el rol, bloquean la fila y dejan auditoría, tanto
  desde las acciones de la lista como desde el formulario.
- El resto de ediciones quedan en el historial del admin (`LogEntry`).
"""
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count
from django.utils.html import format_html

from apps.accounts.permissions import is_owner

from . import services
from .models import BeerStyle, Category, Product, TapMenu


class OwnerOnlyAdminMixin:
    """Defensa adicional: aunque otro rol llegara al admin, no vería la carta."""

    def has_module_permission(self, request):
        return is_owner(request.user)

    def has_view_permission(self, request, obj=None):
        return is_owner(request.user)

    def has_add_permission(self, request):
        return is_owner(request.user)

    def has_change_permission(self, request, obj=None):
        return is_owner(request.user)

    def has_delete_permission(self, request, obj=None):
        # Se conserva el historial: nada de la carta se borra.
        return False


def _image_preview(image, height=48):
    if not image:
        return "—"
    return format_html('<img src="{}" alt="" style="height:{}px;width:auto">', image.url, height)


@admin.register(Category)
class CategoryAdmin(OwnerOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("name", "position", "is_published", "product_count")
    list_editable = ("position", "is_published")
    list_filter = ("is_published",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    fields = ("name", "slug", "description", "position", "is_published")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_product_count=Count("products"))

    @admin.display(description="productos", ordering="_product_count")
    def product_count(self, obj):
        return obj._product_count


@admin.register(BeerStyle)
class BeerStyleAdmin(OwnerOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


def _service_action(description, name, call):
    def action(modeladmin, request, queryset):
        changed = 0
        for product in queryset:
            try:
                call(actor=request.user, product=product)
                changed += 1
            except (PermissionDenied, ValidationError) as exc:
                messages.error(request, f"{product}: {'; '.join(getattr(exc, 'messages', [str(exc)]))}")
        if changed:
            messages.success(request, f"{description}: {changed} producto(s).")

    action.__name__ = name
    action.short_description = description
    return action


def _status_action(status, description, name):
    return _service_action(
        description,
        name,
        lambda *, actor, product: services.set_product_status(actor=actor, product=product, status=status),
    )


def _availability_action(is_available, description, name):
    return _service_action(
        description,
        name,
        lambda *, actor, product: services.set_product_availability(
            actor=actor, product=product, is_available=is_available
        ),
    )


@admin.register(Product)
class ProductAdmin(OwnerOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "kind",
        "price",
        "status",
        "is_available",
        "is_featured",
        "thumbnail",
        "updated_at",
    )
    list_filter = ("status", "is_available", "kind", "category", "is_featured")
    search_fields = ("name", "brewery", "style__name")
    list_select_related = ("category", "style")
    autocomplete_fields = ("style",)
    readonly_fields = ("public_id", "published_at", "archived_at", "availability_changed_at", "thumbnail")
    fieldsets = (
        (
            "Información permanente",
            {"fields": ("category", "kind", "name", "description", "style", "abv", "brewery")},
        ),
        ("Precio", {"fields": ("price", "serving")}),
        ("Imagen", {"fields": ("image", "thumbnail")}),
        ("Presentación", {"fields": ("position", "is_featured")}),
        (
            "Publicación",
            {
                "fields": ("status", "published_at", "archived_at"),
                "description": "Los productos archivados no se ven en la web y se conservan como historial.",
            },
        ),
        ("Disponibilidad actual", {"fields": ("is_available", "availability_changed_at")}),
        ("Identificador", {"fields": ("public_id",), "classes": ("collapse",)}),
    )
    actions = [
        _status_action(Product.Status.PUBLISHED, "Publicar", "publish_products"),
        _status_action(Product.Status.DRAFT, "Pasar a borrador (ocultar)", "unpublish_products"),
        _status_action(Product.Status.ARCHIVED, "Archivar", "archive_products"),
        _availability_action(False, "Marcar como agotado", "mark_sold_out"),
        _availability_action(True, "Marcar como disponible", "mark_available"),
    ]

    @admin.display(description="vista previa")
    def thumbnail(self, obj):
        return _image_preview(obj.image)

    def save_model(self, request, obj, form, change):
        # El estado y la disponibilidad pedidos en el formulario se aplican con
        # los servicios después de guardar el resto de los datos.
        requested_status = obj.status
        requested_available = obj.is_available
        if change:
            current = Product.objects.only(
                "status", "published_at", "archived_at", "is_available", "availability_changed_at"
            ).get(pk=obj.pk)
            obj.status = current.status
            obj.published_at = current.published_at
            obj.archived_at = current.archived_at
            obj.is_available = current.is_available
            obj.availability_changed_at = current.availability_changed_at
        else:
            obj.status = Product.Status.DRAFT
            obj.archived_at = None
        super().save_model(request, obj, form, change)

        if change:
            services.set_product_availability(actor=request.user, product=obj, is_available=requested_available)
        updated = services.set_product_status(actor=request.user, product=obj, status=requested_status)
        obj.refresh_from_db()
        return updated


@admin.register(TapMenu)
class TapMenuAdmin(OwnerOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("title", "is_published", "thumbnail", "created_at", "updated_at")
    list_filter = ("is_published",)
    fields = ("title", "image", "thumbnail", "text_alternative", "is_published")
    readonly_fields = ("thumbnail",)

    @admin.display(description="vista previa")
    def thumbnail(self, obj):
        return _image_preview(obj.image, height=96)
