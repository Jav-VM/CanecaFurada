"""
Textos legales de la web (Fase 25): aviso legal, privacidad, cookies y
condiciones del programa de puntos.

El propietario los edita en Dashboard → Contenido. Mientras no guarda uno, se
muestra el borrador base de `legal_defaults.py`, marcado como pendiente de
revisión legal. Cada cambio del texto sube la versión; al registrarse, el
cliente acepta las versiones vigentes de la privacidad y de las condiciones.
"""
from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from apps.accounts.permissions import is_owner
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event

from . import legal_defaults
from .models import LegalDocument

Kind = LegalDocument.Kind
KINDS = tuple(Kind.values)
# Versión de un texto que el propietario aún no ha publicado (se muestra el borrador base).
DRAFT_VERSION = 0


@dataclass
class Document:
    kind: str
    title: str
    body: str
    version: int
    updated_at: datetime | None
    is_draft: bool


def get_document(kind, business=None):
    """El texto publicado de `kind` o, si no hay, el borrador base."""
    if kind not in KINDS:
        raise ValueError(kind)
    stored = LegalDocument.objects.filter(kind=kind).first()
    title = Kind(kind).label
    if stored is not None:
        return Document(kind, title, stored.body, stored.version, stored.updated_at, False)
    return Document(kind, title, legal_defaults.draft(kind, business), DRAFT_VERSION, None, True)


def documents(business=None):
    return [get_document(kind, business) for kind in KINDS]


def current_versions():
    """Versiones vigentes de la privacidad y de las condiciones (0 = borrador base)."""
    stored = dict(LegalDocument.objects.filter(kind__in=[Kind.PRIVACY, Kind.PROGRAM_TERMS]).values_list("kind", "version"))
    return stored.get(Kind.PRIVACY, DRAFT_VERSION), stored.get(Kind.PROGRAM_TERMS, DRAFT_VERSION)


@transaction.atomic
def save_document(*, actor, kind, body):
    """Publica o actualiza un texto legal (solo propietario). Si el texto cambia, sube la versión."""
    if not is_owner(actor):
        raise PermissionDenied(_("Solo el propietario puede editar los textos legales."))
    if kind not in KINDS:
        raise ValidationError(_("Texto legal desconocido."))
    body = "\n".join(line.rstrip() for line in str(body or "").strip().splitlines())
    if not body:
        raise ValidationError({"body": _("Escribe el texto.")})
    document = LegalDocument.objects.select_for_update().filter(kind=kind).first()
    if document is not None and document.body == body:
        return document, False
    if document is None:
        document = LegalDocument(kind=kind, body=body, version=1, updated_by=actor)
    else:
        document.body = body
        document.version += 1
        document.updated_by = actor
    document.full_clean()
    document.save()
    record_audit_event(
        action=AuditEvent.Action.SITE_CONTENT_UPDATED,
        actor=actor,
        metadata={"legal_document": kind, "version": document.version},
    )
    return document, True
