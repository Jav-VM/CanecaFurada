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
- `page_layout(page)` / `update_page_layout(...)` (Fase 20): orden y visibilidad
  de las secciones de Inicio y La cervecería (reglas en `layout.py`).
"""
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from apps.accounts.permissions import is_owner
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event

from . import content, layout
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
        "home_layout": layout.normalize(info.home_layout, layout.HOME_SECTIONS),
        "about_layout": layout.normalize(info.about_layout, layout.ABOUT_SECTIONS),
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
    # Fase 20: claves visibles en orden, siempre de la lista blanca.
    home = stored.get("home_layout") or layout.normalize([], layout.HOME_SECTIONS)
    about = stored.get("about_layout") or layout.normalize([], layout.ABOUT_SECTIONS)
    data["home_sections"] = layout.visible_keys(home)
    data["about_sections"] = layout.visible_keys(about)
    data.pop("home_layout", None)
    data.pop("about_layout", None)
    return data


def page_layout(page):
    """Orden guardado de `page` (`layout.HOME` o `layout.ABOUT`), ya normalizado."""
    field, sections, _label = layout.PAGES[page]
    return layout.normalize(getattr(_stored(), field), sections)


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


@transaction.atomic
def update_page_layout(*, actor, page, visible, move=None):
    """
    Guarda el orden y la visibilidad de las secciones de `page`. `visible`:
    claves que se muestran; `move`: `(clave, layout.UP | layout.DOWN)` o `None`.
    Solo se aceptan páginas y claves de la lista blanca. Devuelve si cambió algo.
    """
    if not is_owner(actor):
        raise PermissionDenied(_("Solo el propietario puede ordenar las secciones."))
    if page not in layout.PAGES:
        raise ValidationError(_("Página desconocida."), code="unknown_page")
    field, sections, _label = layout.PAGES[page]
    known = {key for key, _unused in sections}
    visible = list(visible)
    if any(key not in known for key in visible):
        raise ValidationError(_("Sección desconocida."), code="unknown_section")
    if move is not None and (move[0] not in known or move[1] not in (layout.UP, layout.DOWN)):
        raise ValidationError(_("Sección desconocida."), code="unknown_section")
    info = BusinessInfo.objects.select_for_update().filter(pk=1).first() or BusinessInfo()
    current = layout.normalize(getattr(info, field), sections)
    updated = layout.with_visibility(current, visible)
    if move is not None:
        updated = layout.move(updated, *move)
    if updated == current:
        return False
    setattr(info, field, updated)
    info.save()
    record_audit_event(action=AuditEvent.Action.SITE_CONTENT_UPDATED, actor=actor, metadata={"fields": [field]})
    transaction.on_commit(lambda: cache.delete(CACHE_KEY))
    return True
