"""
Servicio reutilizable de notificaciones (Fase 10).

Toda comunicación de la plataforma pasa por aquí y queda registrada en
`Notification` con su estado real:

- `send_immediately(...)`: mensajes de cuentas (verificación y cambio de
  email, recuperación de la cuenta, avisos de seguridad). Se envían en el
  momento porque llevan un enlace con token o van a una dirección distinta de
  la actual; **no se guarda ni el contexto ni el destinatario**, así que no se
  reintentan (el usuario pide otro enlace).
- `enqueue(...)`: el resto (reservas, campañas, cumpleaños). Se crea una
  notificación `PENDING` con un contexto sin datos sensibles y se envía con
  `deliver(...)`: al confirmar la transacción si `deliver_on_commit` (avisos
  de reservas) o desde el comando `process_notifications` (promociones; nunca
  desde una petición web). Idempotente por `dedup_key`.
- `deliver(...)`: reclama la notificación con un `UPDATE` condicionado (dos
  procesos no la envían a la vez), **vuelve a comprobar** justo antes de
  enviar que la cuenta sigue activa y, si es promocional, que el cliente
  mantiene el consentimiento del canal (la verificación del email no es
  consentimiento). Los fallos se reintentan con espera creciente hasta
  `NOTIFICATIONS_MAX_ATTEMPTS`.

Privacidad: los logs solo llevan el `public_id` de la notificación, su tipo y
el tipo de error; nunca destinatarios, tokens, enlaces ni el texto enviado.
"""
import datetime
import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.template.loader import render_to_string
from django.utils import timezone

from apps.accounts.validators import validate_e164

from . import sms, unsubscribe
from .models import Channel, Notification

logger = logging.getLogger(__name__)

Kind = Notification.Kind
Status = Notification.Status
Category = Notification.Category

# Mensajes de cuentas: se envían al momento y nunca quedan pendientes.
IMMEDIATE_KINDS = (
    Kind.EMAIL_VERIFICATION,
    Kind.EMAIL_CHANGE,
    Kind.EMAIL_CHANGED_NOTICE,
    Kind.EXISTING_ACCOUNT,
    Kind.PASSWORD_RESET,
)


class SkipReason:
    """Motivos de no envío (se guardan en `last_error`)."""

    INACTIVE = "cuenta_inactiva"
    NO_CONSENT = "sin_consentimiento"
    NO_SMS_PROVIDER = "sms_sin_proveedor"
    INVALID_PHONE = "telefono_no_valido"
    NO_EMAIL = "sin_email"
    INTERRUPTED = "envio_interrumpido"


def category_for(kind):
    return Category.PROMOTIONAL if kind in Notification.PROMOTIONAL_KINDS else Category.TRANSACTIONAL


def sms_available():
    return sms.is_configured()


# --- Composición -----------------------------------------------------------------


def _subject(template, context):
    # Una sola línea: un salto en el asunto rompería las cabeceras.
    return " ".join(render_to_string(template, context).split())


def _send_email(*, to, subject, body, headers=None):
    EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [to], headers=headers or None).send()


def _check_context(context):
    """Solo valores JSON simples: el contexto se guarda y no debe arrastrar objetos."""
    for key, value in (context or {}).items():
        if not isinstance(key, str) or not (value is None or isinstance(value, (str, int, float, bool))):
            raise ValueError(f"Valor no permitido en el contexto de la notificación: {key}")


def _context_for(notification):
    context = {"site_base_url": settings.SITE_BASE_URL, **notification.context}
    if notification.is_promotional:
        # Las promociones no saludan por el nombre: no hace falta ningún dato personal.
        context["unsubscribe_url"] = unsubscribe.unsubscribe_url(notification.recipient, notification.channel)
    else:
        context["first_name"] = notification.recipient.first_name
    if notification.campaign_id:
        context["campaign_subject"] = notification.campaign.subject
        context["campaign_body"] = notification.campaign.body
    return context


def _template(notification, suffix):
    return f"notifications/{notification.kind.lower()}_{suffix}.txt"


def _phone_for(user):
    try:
        phone = user.customer_profile.phone_number
    except Exception:  # noqa: BLE001 - sin perfil no hay teléfono
        return ""
    try:
        validate_e164(phone)
    except ValidationError:
        return ""
    return phone


# --- Envío inmediato (cuentas) -----------------------------------------------------


def send_immediately(*, kind, recipient, to, subject_template, body_template, context):
    """
    Envía ya un mensaje de cuentas y registra el resultado sin su contexto ni
    su destinatario. Devuelve `True` si el proveedor lo aceptó. Un fallo del
    proveedor no rompe el flujo que lo llama.
    """
    if kind not in IMMEDIATE_KINDS:
        raise ValueError("Solo los mensajes de cuentas se envían al momento.")
    notification = Notification.objects.create(
        recipient=recipient,
        kind=kind,
        category=Category.TRANSACTIONAL,
        channel=Channel.EMAIL,
        status=Status.SENDING,
        attempts=1,
    )
    full_context = {"site_base_url": settings.SITE_BASE_URL, **context}
    try:
        subject = _subject(subject_template, full_context)
        body = render_to_string(body_template, full_context)
        _send_email(to=to, subject=subject, body=body)
    except Exception as exc:  # noqa: BLE001 - un fallo del proveedor no debe romper el flujo
        Notification.objects.filter(pk=notification.pk).update(
            status=Status.FAILED, last_error=type(exc).__name__[:100], updated_at=timezone.now()
        )
        logger.error("No se pudo enviar la notificación %s (%s): %s.", notification.public_id, kind, type(exc).__name__)
        return False
    now = timezone.now()
    Notification.objects.filter(pk=notification.pk).update(status=Status.SENT, sent_at=now, updated_at=now)
    return True


# --- Cola ---------------------------------------------------------------------------


def enqueue(*, kind, recipient, context=None, channel=Channel.EMAIL, dedup_key=None, campaign=None, deliver_on_commit=False):
    """
    Crea una notificación pendiente. Devuelve `(notificación, creada)`: con la
    misma `dedup_key` no se crea otra (tampoco en una carrera: la restricción
    única decide). `context` no debe llevar tokens ni datos personales.
    """
    if kind in IMMEDIATE_KINDS:
        raise ValueError("Los mensajes de cuentas no se encolan: usa send_immediately.")
    _check_context(context)
    if dedup_key:
        existing = Notification.objects.filter(dedup_key=dedup_key).first()
        if existing is not None:
            return existing, False
    try:
        with transaction.atomic():
            notification = Notification.objects.create(
                recipient=recipient,
                kind=kind,
                category=category_for(kind),
                channel=channel,
                context=context or {},
                dedup_key=dedup_key,
                campaign=campaign,
                next_attempt_at=timezone.now(),
            )
    except IntegrityError:
        existing = Notification.objects.filter(dedup_key=dedup_key).first() if dedup_key else None
        if existing is None:
            raise
        return existing, False
    if deliver_on_commit:
        transaction.on_commit(lambda: deliver(notification.pk))
    return notification, True


# --- Entrega ------------------------------------------------------------------------


def _skip_reason(notification):
    user = notification.recipient
    if not user.is_active:
        return SkipReason.INACTIVE
    if notification.is_promotional:
        # Importación diferida: `accounts` envía sus emails a través de este módulo.
        from apps.accounts import services as accounts

        if notification.channel == Channel.EMAIL:
            allowed = accounts.can_receive_promotional_email(user)
        else:
            allowed = accounts.can_receive_promotional_sms(user) and user.is_email_verified
        if not allowed:
            return SkipReason.NO_CONSENT
    if notification.channel == Channel.SMS:
        if not sms.is_configured():
            return SkipReason.NO_SMS_PROVIDER
        if not _phone_for(user):
            return SkipReason.INVALID_PHONE
    elif not user.email:
        return SkipReason.NO_EMAIL
    return None


def _send(notification):
    context = _context_for(notification)
    if notification.channel == Channel.EMAIL:
        headers = None
        if notification.is_promotional:
            headers = {"List-Unsubscribe": f"<{context['unsubscribe_url']}>"}
        _send_email(
            to=notification.recipient.email,
            subject=_subject(_template(notification, "subject"), context),
            body=render_to_string(_template(notification, "body"), context),
            headers=headers,
        )
    else:
        text = " ".join(render_to_string(_template(notification, "sms"), context).split())
        sms.get_backend().send(to=_phone_for(notification.recipient), body=text)


def _register_failure(notification, exc):
    now = timezone.now()
    notification.last_error = type(exc).__name__[:100]
    if notification.attempts >= settings.NOTIFICATIONS_MAX_ATTEMPTS:
        notification.status = Status.FAILED
        notification.next_attempt_at = None
    else:
        delay = settings.NOTIFICATIONS_RETRY_BASE_MINUTES * 2 ** (notification.attempts - 1)
        notification.status = Status.PENDING
        notification.next_attempt_at = now + datetime.timedelta(minutes=delay)
    notification.save(update_fields=["status", "last_error", "next_attempt_at", "updated_at"])
    logger.warning(
        "Notificación %s (%s) no enviada en el intento %s: %s.",
        notification.public_id,
        notification.kind,
        notification.attempts,
        notification.last_error,
    )


def deliver(notification_id):
    """
    Envía una notificación pendiente. Devuelve su estado final, o `None` si
    no estaba pendiente (otro proceso la reclamó o ya se envió).
    """
    now = timezone.now()
    claimed = Notification.objects.filter(pk=notification_id, status=Status.PENDING).exclude(
        kind__in=IMMEDIATE_KINDS
    ).update(status=Status.SENDING, attempts=F("attempts") + 1, updated_at=now)
    if not claimed:
        return None
    notification = Notification.objects.select_related("recipient", "campaign").get(pk=notification_id)
    reason = _skip_reason(notification)
    if reason:
        notification.status = Status.SKIPPED
        notification.last_error = reason
        notification.next_attempt_at = None
        notification.save(update_fields=["status", "last_error", "next_attempt_at", "updated_at"])
        return notification.status
    try:
        _send(notification)
    except Exception as exc:  # noqa: BLE001 - se registra y se reintenta
        _register_failure(notification, exc)
        return notification.status
    notification.status = Status.SENT
    notification.sent_at = timezone.now()
    notification.next_attempt_at = None
    notification.last_error = ""
    notification.save(update_fields=["status", "sent_at", "next_attempt_at", "last_error", "updated_at"])
    return notification.status


@dataclass
class ProcessResult:
    requeued: int = 0
    interrupted: int = 0
    sent: int = 0
    failed: int = 0
    retrying: int = 0
    skipped: int = 0


def recover_stale(now=None):
    """
    Notificaciones que se quedaron `SENDING` (proceso interrumpido): las de la
    cola vuelven a `PENDING`; las de cuentas, sin contexto para recomponerlas,
    se dan por fallidas. Puede causar un duplicado si el proveedor llegó a
    aceptar el mensaje justo antes de la interrupción.
    """
    now = now or timezone.now()
    stale = Notification.objects.filter(
        status=Status.SENDING,
        updated_at__lt=now - datetime.timedelta(minutes=settings.NOTIFICATIONS_STALE_SENDING_MINUTES),
    )
    interrupted = stale.filter(kind__in=IMMEDIATE_KINDS).update(
        status=Status.FAILED, last_error=SkipReason.INTERRUPTED, updated_at=now
    )
    requeued = stale.exclude(kind__in=IMMEDIATE_KINDS).update(status=Status.PENDING, next_attempt_at=now, updated_at=now)
    return requeued, interrupted


def process_due(*, limit=None, now=None):
    """Envía las notificaciones pendientes cuyo turno ha llegado (comando `process_notifications`)."""
    now = now or timezone.now()
    result = ProcessResult()
    result.requeued, result.interrupted = recover_stale(now)
    limit = limit or settings.NOTIFICATIONS_BATCH_SIZE
    due = (
        Notification.objects.filter(status=Status.PENDING)
        .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
        .exclude(kind__in=IMMEDIATE_KINDS)
        .order_by("created_at", "id")
        .values_list("pk", flat=True)[:limit]
    )
    for pk in list(due):
        status = deliver(pk)
        if status == Status.SENT:
            result.sent += 1
        elif status == Status.FAILED:
            result.failed += 1
        elif status == Status.PENDING:
            result.retrying += 1
        elif status == Status.SKIPPED:
            result.skipped += 1
    return result
