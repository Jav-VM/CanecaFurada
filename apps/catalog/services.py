"""
Operaciones de gestión de la carta.

Solo un propietario activo puede ejecutarlas. Cada cambio se hace en una
transacción con el producto bloqueado (`select_for_update`), es idempotente
(repetir la misma operación no cambia nada ni duplica la auditoría) y deja un
`AuditEvent` con el estado anterior y el nuevo. Las usan el admin, el dashboard
y la API. Desde la Fase 24 también se crean y editan aquí las fichas del dashboard.
"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext as _

from apps.accounts.permissions import is_owner
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event

from .models import Category, Product


def ensure_can_manage_catalog(actor):
    if not is_owner(actor):
        raise PermissionDenied(_("Solo el propietario puede gestionar la carta."))


@transaction.atomic
def set_product_status(*, actor, product, status):
    """Publica, pasa a borrador o archiva un producto. Nunca lo borra."""
    ensure_can_manage_catalog(actor)
    if status not in Product.Status.values:
        raise ValidationError(_("Estado de publicación no válido."))

    locked = Product.objects.select_for_update().get(pk=product.pk)
    previous = locked.status
    if previous == status:
        return locked

    now = timezone.now()
    locked.status = status
    locked.archived_at = now if status == Product.Status.ARCHIVED else None
    if status == Product.Status.PUBLISHED:
        # Solo se publica un producto completo y coherente.
        locked.full_clean()
        locked.published_at = now
    locked.save(update_fields=["status", "published_at", "archived_at", "updated_at"])

    record_audit_event(
        action=AuditEvent.Action.PRODUCT_STATUS_CHANGED,
        actor=actor,
        target=locked,
        metadata={"from": previous, "to": status},
    )
    return locked


@transaction.atomic
def set_product_availability(*, actor, product, is_available):
    """Marca un producto como disponible o agotado (información del momento)."""
    ensure_can_manage_catalog(actor)
    is_available = bool(is_available)

    locked = Product.objects.select_for_update().get(pk=product.pk)
    if locked.is_available == is_available:
        return locked

    locked.is_available = is_available
    locked.availability_changed_at = timezone.now()
    locked.save(update_fields=["is_available", "availability_changed_at", "updated_at"])

    record_audit_event(
        action=AuditEvent.Action.PRODUCT_AVAILABILITY_CHANGED,
        actor=actor,
        target=locked,
        metadata={"is_available": is_available},
    )
    return locked


# --- Fichas desde el dashboard (Fase 24) --------------------------------------------
# Crear y editar productos, categorías, estilos y cartas de grifos sin pasar por el
# admin. `data` solo puede traer los campos de la lista blanca de cada modelo (contra
# la asignación masiva); el estado y la disponibilidad de los productos no están en
# ella: se cambian con `set_product_status` y `set_product_availability`.

PRODUCT_FIELDS = (
    "category", "kind", "name", "description", "style", "abv", "brewery",
    "price", "serving", "image", "position", "is_featured",
)
CATEGORY_FIELDS = ("name", "slug", "description", "position", "is_published")
BEER_STYLE_FIELDS = ("name",)
TAP_MENU_FIELDS = ("title", "image", "text_alternative", "is_published")


def _value(instance, name):
    """Valor comparable de un campo; en las claves ajenas, el id (sin consultar ni fallar si falta)."""
    return getattr(instance, instance._meta.get_field(name).attname)


def _save(*, actor, instance, data, fields, model_label, prepare=None):
    """Asigna los campos permitidos, valida, guarda y audita (sin textos)."""
    ensure_can_manage_catalog(actor)
    unknown = set(data) - set(fields)
    if unknown:
        raise ValidationError(_("Campos no permitidos: %(join)s.") % {"join": ", ".join(sorted(unknown))})
    created = instance.pk is None
    if not created:
        instance = type(instance).objects.select_for_update().get(pk=instance.pk)
    before = {name: _value(instance, name) for name in fields}
    for name, value in data.items():
        setattr(instance, name, value)
    if prepare:
        prepare(instance, created)
    instance.full_clean()
    changed = sorted(name for name in fields if _value(instance, name) != before[name])
    instance.save()
    record_audit_event(
        action=AuditEvent.Action.CATALOG_SAVED,
        actor=actor,
        target=instance,
        metadata={"model": model_label, "created": created, "fields": changed},
    )
    return instance


@transaction.atomic
def save_product(*, actor, product, data):
    """Crea (en borrador y disponible) o edita un producto, sin tocar su publicación ni su disponibilidad."""

    def prepare(instance, created):
        if created:
            instance.status = Product.Status.DRAFT
            instance.published_at = None
            instance.archived_at = None
            instance.is_available = True

    return _save(actor=actor, instance=product, data=data, fields=PRODUCT_FIELDS, model_label="product", prepare=prepare)


def _unique_slug(name, exclude_pk=None):
    base = slugify(name)[:70] or "categoria"
    slug, number = base, 2
    while Category.objects.filter(slug=slug).exclude(pk=exclude_pk).exists():
        slug = f"{base}-{number}"
        number += 1
    return slug


@transaction.atomic
def save_category(*, actor, category, data):
    """Crea o edita una categoría. Sin identificador en la URL, se genera a partir del nombre."""

    def prepare(instance, created):
        instance.name = (instance.name or "").strip()
        instance.slug = slugify(instance.slug or "") or _unique_slug(instance.name, exclude_pk=instance.pk)

    return _save(actor=actor, instance=category, data=data, fields=CATEGORY_FIELDS, model_label="category", prepare=prepare)


@transaction.atomic
def save_beer_style(*, actor, style, data):
    def prepare(instance, created):
        instance.name = (instance.name or "").strip()

    return _save(actor=actor, instance=style, data=data, fields=BEER_STYLE_FIELDS, model_label="beer_style", prepare=prepare)


@transaction.atomic
def save_tap_menu(*, actor, tap_menu, data):
    """Crea o edita una carta de grifos. La web muestra la publicada más reciente."""
    return _save(actor=actor, instance=tap_menu, data=data, fields=TAP_MENU_FIELDS, model_label="tap_menu")
