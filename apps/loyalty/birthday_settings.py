"""
Regalo de cumpleaños configurable desde el dashboard (Fase 14).

- **Puntos y activación:** se guardan en la promoción de cumpleaños
  (`Promotion` de tipo `BIRTHDAY`) que usa `birthdays.run_birthday_promotions`.
  Si no hay ninguna se crea; desactivar el regalo pausa todas las de
  cumpleaños activas. Los regalos ya concedidos no cambian (el ledger guarda
  sus puntos).
- **Textos del aviso:** `BirthdayMessage` (fila única). Vacío = texto por
  defecto. El único marcador es `{puntos}` y se sustituye con `str.replace`,
  nunca con el motor de plantillas: lo que escriba el propietario no se
  interpreta (ni `{{ }}` ni `{% %}`). El enlace de baja lo añade siempre la
  plantilla.
"""
import re
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.permissions import is_owner
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event

from . import promotions
from .models import BirthdayMessage, Promotion

PLACEHOLDER = "{puntos}"
TEXT_FIELDS = ("email_subject", "email_body", "sms_body")
DEFAULT_NAME = "Regalo de cumpleaños"
_BRACES = re.compile(r"[{}]")


def render_text(text, points):
    """Sustituye `{puntos}`. Sin motor de plantillas: el resto del texto se deja tal cual."""
    return text.replace(PLACEHOLDER, str(points))


def get_message():
    """Los textos guardados, o una fila sin guardar (todo por defecto)."""
    return BirthdayMessage.objects.filter(pk=BirthdayMessage.SINGLETON_ID).first() or BirthdayMessage(
        pk=BirthdayMessage.SINGLETON_ID
    )


def notification_texts(points):
    """Textos personalizados ya resueltos para el contexto de la notificación (solo los no vacíos)."""
    message = get_message()
    texts = {
        "custom_subject": message.email_subject,
        "custom_body": message.email_body,
        "custom_sms": message.sms_body,
    }
    return {key: render_text(value, points) for key, value in texts.items() if value}


def _managed_promotion(lock=False):
    """
    La promoción de cumpleaños que se edita: la vigente; si no hay, la activa
    más antigua (aunque esté programada o vencida); si tampoco, la última
    modificada sin finalizar.
    """
    queryset = Promotion.objects.select_for_update() if lock else Promotion.objects.all()
    birthday = queryset.filter(kind=Promotion.Kind.BIRTHDAY)
    active = promotions.active_birthday_promotion()
    if active is not None:
        return birthday.get(pk=active.pk)
    return (
        birthday.filter(status=Promotion.Status.ACTIVE).order_by("starts_at", "id").first()
        or birthday.exclude(status=Promotion.Status.ENDED).order_by("-updated_at", "-id").first()
    )


@dataclass(frozen=True)
class BirthdayGiftState:
    active: bool
    points: int | None
    message: BirthdayMessage


def current_state():
    promotion = _managed_promotion()
    return BirthdayGiftState(
        active=promotions.active_birthday_promotion() is not None,
        points=promotion.fixed_points if promotion else None,
        message=get_message(),
    )


def _clean_text(value, field, max_length, *, single_line=False):
    value = (value or "").replace("\r\n", "\n").replace("\r", "\n").strip() if isinstance(value, str) else ""
    if len(value) > max_length:
        raise ValidationError({field: f"Admite como máximo {max_length} caracteres."})
    if single_line and "\n" in value:
        raise ValidationError({field: "Escríbelo en una sola línea."})
    if _BRACES.search(value.replace(PLACEHOLDER, "")):
        raise ValidationError({field: f"El único marcador admitido es {PLACEHOLDER}; no uses otras llaves."})
    return value


def _clean_points(points):
    if isinstance(points, bool) or not isinstance(points, int) or not 1 <= points <= Promotion.MAX_FIXED_POINTS:
        raise ValidationError({"points": f"Indica entre 1 y {Promotion.MAX_FIXED_POINTS} puntos."})
    return points


@transaction.atomic
def update_birthday_gift(*, actor, active, points, email_subject="", email_body="", sms_body=""):
    """
    Guarda el regalo de cumpleaños (solo propietario). Devuelve `True` si
    cambió algo. Validado en el servidor y auditado sin los textos.
    """
    if not is_owner(actor):
        raise PermissionDenied("Solo el propietario configura el regalo de cumpleaños.")
    active = bool(active)
    points = _clean_points(points)
    texts = {
        "email_subject": _clean_text(email_subject, "email_subject", BirthdayMessage.MAX_SUBJECT, single_line=True),
        "email_body": _clean_text(email_body, "email_body", BirthdayMessage.MAX_EMAIL_BODY),
        "sms_body": _clean_text(sms_body, "sms_body", BirthdayMessage.MAX_SMS_BODY, single_line=True),
    }
    now = timezone.now()
    status = Promotion.Status.ACTIVE if active else Promotion.Status.PAUSED

    promotion = _managed_promotion(lock=True)
    if promotion is None:
        promotion = Promotion(
            name=DEFAULT_NAME,
            kind=Promotion.Kind.BIRTHDAY,
            bonus_type=Promotion.BonusType.FIXED_POINTS,
            fixed_points=points,
            starts_at=now,
            status=status,
        )
        promotions.save_promotion(actor=actor, promotion=promotion, changed_fields=["fixed_points", "status"])
        promotion_changed = True
    else:
        changed = []
        if promotion.fixed_points != points:
            promotion.fixed_points = points
            changed.append("fixed_points")
        if promotion.status != status:
            promotion.status = status
            changed.append("status")
        if active and promotion.ends_at is not None and promotion.ends_at <= now:
            # Reactivar una promoción ya terminada: sin fecha de fin.
            promotion.ends_at = None
            changed.append("ends_at")
        if active and promotion.starts_at > now:
            promotion.starts_at = now
            changed.append("starts_at")
        if changed:
            promotions.save_promotion(actor=actor, promotion=promotion, changed_fields=changed)
        promotion_changed = bool(changed)
    if not active:
        # Ninguna otra promoción de cumpleaños sigue activa, tampoco las programadas.
        others = Promotion.objects.filter(kind=Promotion.Kind.BIRTHDAY, status=Promotion.Status.ACTIVE).exclude(
            pk=promotion.pk
        )
        for other in others:
            promotions.set_promotion_status(actor=actor, promotion=other, status=Promotion.Status.PAUSED)
            promotion_changed = True

    message = BirthdayMessage.objects.select_for_update().filter(pk=BirthdayMessage.SINGLETON_ID).first()
    message = message or BirthdayMessage(pk=BirthdayMessage.SINGLETON_ID)
    texts_changed = sorted(field for field in TEXT_FIELDS if getattr(message, field) != texts[field])
    if texts_changed:
        for field, value in texts.items():
            setattr(message, field, value)
        message.updated_by = actor
        message.full_clean()
        message.save()

    if not (promotion_changed or texts_changed):
        return False
    # Sin los textos: son texto libre.
    record_audit_event(
        action=AuditEvent.Action.BIRTHDAY_SETTINGS_UPDATED,
        actor=actor,
        target=promotion,
        metadata={"active": active, "points": points, "texts_changed": texts_changed},
    )
    return True
