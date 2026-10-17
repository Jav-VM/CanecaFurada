"""
Contenido del local (Fase 9): lectura para la web y edición por el propietario.

- `business_info()`: datos que usan las plantillas públicas. Parte de
  `content.BUSINESS` (nombre y ciudad de la marca, el resto `None`) y solo
  sustituye lo que el propietario haya rellenado. Se guarda en la caché para
  no consultar la BD en cada página; la edición la invalida.
- `update_business_info(...)`: solo propietario, validado y auditado (solo los
  nombres de los campos cambiados, no sus valores).
- `online_reservations_enabled()` / `set_online_reservations(...)` (Fase 17):
  interruptor de las reservas online. No forma parte de `EDITABLE_FIELDS`: solo
  se cambia desde Configuración.
"""
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils.translation import gettext as _

from apps.accounts.permissions import is_owner
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event

from . import content
from .models import BusinessInfo, parse_pairs

CACHE_KEY = "web:business_info"
CACHE_TIMEOUT = 300
EDITABLE_FIELDS = (
    "address",
    "opening_hours",
    "email",
    "phone",
    "social_links",
    "about_text",
    "hero_text",
    "announcement",
)


def _stored():
    """Fila guardada o una instancia vacía sin guardar."""
    return BusinessInfo.objects.filter(pk=1).first() or BusinessInfo()


def _stored_values():
    info = _stored()
    return {
        "address": info.address or None,
        "opening_hours": tuple(parse_pairs(info.opening_hours)) or None,
        "email": info.email or None,
        "phone": info.phone or None,
        "social_links": tuple(parse_pairs(info.social_links)),
        "about_text": info.about_text or None,
        "hero_text": info.hero_text or None,
        "announcement": info.announcement or None,
        "online_reservations_enabled": info.online_reservations_enabled,
    }


def business_info():
    stored = cache.get(CACHE_KEY)
    if stored is None:
        stored = _stored_values()
        cache.set(CACHE_KEY, stored, CACHE_TIMEOUT)
    data = dict(content.BUSINESS)
    # Lo que el propietario no ha rellenado sigue como en `content.BUSINESS`.
    data.update({key: value for key, value in stored.items() if value})
    # Booleano: `False` también cuenta (el filtro anterior lo descartaría).
    data["online_reservations_enabled"] = stored.get("online_reservations_enabled", True)
    return data


def online_reservations_enabled():
    return business_info()["online_reservations_enabled"]


def editable_business_info():
    return _stored()


@transaction.atomic
def update_business_info(*, actor, data):
    """Guarda los campos editables (lista blanca contra asignación masiva)."""
    if not is_owner(actor):
        raise PermissionDenied(_("Solo el propietario puede editar el contenido del local."))
    info = BusinessInfo.objects.select_for_update().filter(pk=1).first() or BusinessInfo()
    before = {name: getattr(info, name) for name in EDITABLE_FIELDS}
    for name in EDITABLE_FIELDS:
        if name in data:
            setattr(info, name, data[name] or "")
    info.full_clean()
    changed = sorted(name for name in EDITABLE_FIELDS if getattr(info, name) != before[name])
    if not changed and info.pk is not None:
        return info, []
    info.save()
    record_audit_event(action=AuditEvent.Action.SITE_CONTENT_UPDATED, actor=actor, metadata={"fields": changed})
    transaction.on_commit(lambda: cache.delete(CACHE_KEY))
    return info, changed


@transaction.atomic
def set_online_reservations(*, actor, enabled):
    """Activa o desactiva las reservas online. Devuelve si ha cambiado algo."""
    if not is_owner(actor):
        raise PermissionDenied(_("Solo el propietario puede cambiar las reservas online."))
    enabled = bool(enabled)
    info = BusinessInfo.objects.select_for_update().filter(pk=1).first() or BusinessInfo()
    if info.online_reservations_enabled == enabled:
        return False
    info.online_reservations_enabled = enabled
    info.save()
    record_audit_event(
        action=AuditEvent.Action.SITE_CONTENT_UPDATED,
        actor=actor,
        metadata={"fields": ["online_reservations_enabled"], "enabled": enabled},
    )
    transaction.on_commit(lambda: cache.delete(CACHE_KEY))
    return True
