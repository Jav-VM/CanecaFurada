"""
Operaciones de gestión de la carta.

Solo un propietario activo puede ejecutarlas. Cada cambio se hace en una
transacción con el producto bloqueado (`select_for_update`), es idempotente
(repetir la misma operación no cambia nada ni duplica la auditoría) y deja un
`AuditEvent` con el estado anterior y el nuevo. Las usan el admin y las usará
la futura API.
"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.permissions import is_owner
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event

from .models import Product


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
