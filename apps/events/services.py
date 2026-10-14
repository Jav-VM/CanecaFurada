"""
Reglas de eventos y reservas (Fase 10). Son la única vía de escritura: las
vistas web, el dashboard y la futura API solo traducen la entrada y llaman
aquí.

Eventos (solo propietario, auditado):
- `save_event(...)`: crea o modifica (lista blanca de campos).
- `set_event_status(...)`: publicar, volver a borrador o archivar. Solo se
  publica un evento que todavía no ha empezado. Nada se borra.

Reservas:
- `request_reservation(...)`: el cliente autenticado con email verificado
  (nunca un ID enviado por él) pide mesa o plaza en un evento publicado que
  admite reservas. Valida en servidor fecha (antelación mínima y máxima),
  personas, aforo del evento, una reserva activa por evento y un máximo de
  reservas activas por cliente. Idempotente con `idempotency_key` y limitada
  por hora.
- Transiciones (`confirm_`, `reject_`, `cancel_`, `complete_reservation` por
  el propietario; `cancel_own_reservation` por el cliente): se comprueban con
  la fila bloqueada según `Reservation.TRANSITIONS`. Confirmar vuelve a
  comprobar el aforo con el evento bloqueado, de modo que dos confirmaciones
  simultáneas no lo superan. Repetir la misma transición no hace nada.
- Cada cambio queda auditado (estados, sin notas ni mensajes) y genera su
  notificación transaccional (`apps.notifications`), que se envía al
  confirmar la transacción y se reintenta si el proveedor falla. Los emails
  no llevan notas, teléfonos ni direcciones.
"""
import datetime
import logging
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.permissions import is_owner
from apps.core import throttling
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event
from apps.notifications import services as notifications
from apps.notifications.models import Notification

from .models import Event, Reservation

logger = logging.getLogger(__name__)

Status = Reservation.Status
EventStatus = Event.Status
NKind = Notification.Kind

EVENT_FIELDS = (
    "title",
    "summary",
    "description",
    "starts_at",
    "ends_at",
    "image",
    "is_featured",
    "accepts_reservations",
    "capacity",
)
EVENT_TRANSITIONS = {
    EventStatus.DRAFT: {EventStatus.PUBLISHED, EventStatus.ARCHIVED},
    EventStatus.PUBLISHED: {EventStatus.DRAFT, EventStatus.ARCHIVED},
    EventStatus.ARCHIVED: {EventStatus.DRAFT},
}
MAX_TEXT = 300
_HOUR = 60 * 60


def _require_owner(actor):
    if not is_owner(actor):
        raise PermissionDenied("Solo el propietario gestiona los eventos y las reservas.")


def _error(message, code):
    return ValidationError(message, code=code)


# --- Eventos -------------------------------------------------------------------------


def confirmed_seats(event):
    return (
        Reservation.objects.filter(event=event, status=Status.CONFIRMED).aggregate(total=Sum("party_size"))["total"]
        or 0
    )


@transaction.atomic
def save_event(*, actor, event, data):
    """Crea o modifica un evento. `data` solo puede traer campos de `EVENT_FIELDS`."""
    _require_owner(actor)
    unknown = set(data) - set(EVENT_FIELDS)
    if unknown:
        raise ValidationError(f"Campos no permitidos: {', '.join(sorted(unknown))}.")
    created = event.pk is None
    if not created:
        event = Event.objects.select_for_update().get(pk=event.pk)
    before = {name: getattr(event, name) for name in EVENT_FIELDS}
    for name, value in data.items():
        setattr(event, name, value)
    event.full_clean()
    if not created and event.capacity is not None:
        seats = confirmed_seats(event)
        if event.capacity < seats:
            raise ValidationError({"capacity": f"Ya hay {seats} plazas confirmadas: el aforo no puede ser menor."})
    changed = sorted(name for name in EVENT_FIELDS if getattr(event, name) != before[name])
    event.save()
    if not created and "starts_at" in changed:
        # Las reservas activas del evento siguen su nueva hora. No se avisa
        # automáticamente: el propietario decide cómo comunicar el cambio.
        Reservation.objects.filter(event=event, status__in=Reservation.ACTIVE_STATUSES).update(
            requested_for=event.starts_at, updated_at=timezone.now()
        )
    record_audit_event(
        action=AuditEvent.Action.EVENT_SAVED,
        actor=actor,
        target=event,
        metadata={"created": created, "status": event.status, "fields": changed},
    )
    return event


@transaction.atomic
def set_event_status(*, actor, event, status):
    _require_owner(actor)
    if status not in EventStatus.values:
        raise _error("Estado de evento no válido.", "invalid_status")
    locked = Event.objects.select_for_update().get(pk=event.pk)
    if locked.status == status:
        return locked
    if status not in EVENT_TRANSITIONS[locked.status]:
        raise _error("Ese cambio de estado no está permitido.", "invalid_transition")
    if status == EventStatus.PUBLISHED:
        if locked.has_started():
            raise _error("No se puede publicar un evento que ya ha empezado.", "event_started")
        locked.published_at = timezone.now()
    old = locked.status
    locked.status = status
    locked.save(update_fields=["status", "published_at", "updated_at"])
    record_audit_event(
        action=AuditEvent.Action.EVENT_SAVED,
        actor=actor,
        target=locked,
        metadata={"created": False, "status": status, "from": old, "fields": ["status"]},
    )
    return locked


# --- Reservas: utilidades ------------------------------------------------------------


@dataclass(frozen=True)
class ReservationResult:
    reservation: Reservation
    created: bool


def new_idempotency_key():
    return uuid.uuid4()


def parse_idempotency_key(value):
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise _error("La operación no es válida. Vuelve a intentarlo.", "idempotency_invalid") from None


def _parse_party_size(value):
    if isinstance(value, bool):
        value = None
    elif isinstance(value, str):
        value = int(value) if value.strip().isdigit() else None
    elif not isinstance(value, int):
        value = None
    maximum = settings.EVENTS_RESERVATION_MAX_PARTY_SIZE
    if value is None or not 1 <= value <= maximum:
        raise ValidationError({"party_size": f"Indica entre 1 y {maximum} personas."})
    return value


def _parse_text(value, field):
    value = value.strip() if isinstance(value, str) else ""
    # Sin caracteres de control (salvo saltos de línea) en textos que se muestran.
    value = "".join(ch for ch in value if ch in "\n" or ch.isprintable())
    if len(value) > MAX_TEXT:
        raise ValidationError({field: f"Admite como máximo {MAX_TEXT} caracteres."})
    return value


def _validate_table_datetime(requested_for, now):
    if not isinstance(requested_for, datetime.datetime) or timezone.is_naive(requested_for):
        raise ValidationError({"requested_for": "Indica la fecha y la hora de la reserva."})
    earliest = now + datetime.timedelta(hours=settings.EVENTS_RESERVATION_MIN_NOTICE_HOURS)
    latest = now + datetime.timedelta(days=settings.EVENTS_RESERVATION_MAX_DAYS_AHEAD)
    if requested_for < earliest:
        raise ValidationError(
            {"requested_for": f"Reserva con al menos {settings.EVENTS_RESERVATION_MIN_NOTICE_HOURS} horas de antelación."}
        )
    if requested_for > latest:
        raise ValidationError(
            {"requested_for": f"Solo se puede reservar hasta {settings.EVENTS_RESERVATION_MAX_DAYS_AHEAD} días vista."}
        )
    return requested_for


def ensure_can_reserve(customer):
    """Cliente activo con email verificado (comprobado en BD por quien bloquea la fila)."""
    if not (
        getattr(customer, "is_authenticated", False)
        and customer.is_active
        and customer.role == User.Role.CUSTOMER
        and customer.is_email_verified
    ):
        raise PermissionDenied("Para reservar necesitas una cuenta de cliente con el email verificado.")


def format_when(value):
    return timezone.localtime(value).strftime("%d/%m/%Y a las %H:%M")


def _context(reservation, **extra):
    return {
        "when": format_when(reservation.requested_for),
        "party_size": reservation.party_size,
        "event_title": reservation.event.title if reservation.event_id else "",
        **extra,
    }


def _notify_customer(reservation, kind, **extra):
    notifications.enqueue(
        kind=kind,
        recipient=reservation.customer,
        context=_context(reservation, **extra),
        dedup_key=f"reservation:{reservation.public_id}:{kind}",
        deliver_on_commit=True,
    )


def _notify_owners(reservation, alert):
    for owner in User.objects.filter(role=User.Role.OWNER, is_active=True).order_by("pk"):
        notifications.enqueue(
            kind=NKind.RESERVATION_OWNER_ALERT,
            recipient=owner,
            context=_context(reservation, alert=alert),
            dedup_key=f"reservation:{reservation.public_id}:owner:{owner.public_id}:{reservation.status}",
            deliver_on_commit=True,
        )


def _replay(existing, customer):
    if existing.customer_id != customer.pk:
        raise _error("Esta operación ya se registró con otros datos.", "idempotency_conflict")
    return ReservationResult(reservation=existing, created=False)


# --- Reservas: solicitud del cliente ---------------------------------------------------


def _create(customer, *, event, requested_for, party_size, notes, key, now):
    with transaction.atomic():
        existing = Reservation.objects.select_for_update().filter(idempotency_key=key).first()
        if existing is not None:
            return _replay(existing, customer)
        # Bloquea al cliente: serializa sus solicitudes para el límite de activas.
        customer = User.objects.select_for_update().get(pk=customer.pk)
        ensure_can_reserve(customer)
        if event is not None:
            event = Event.objects.select_for_update().get(pk=event.pk)
            if not (event.status == EventStatus.PUBLISHED and event.accepts_reservations and not event.has_started(now)):
                raise _error("Este evento ya no admite reservas.", "event_not_bookable")
            requested_for = event.starts_at
            if Reservation.objects.filter(customer=customer, event=event, status__in=Reservation.ACTIVE_STATUSES).exists():
                raise _error("Ya tienes una reserva activa para este evento.", "already_reserved")
            if event.capacity is not None and confirmed_seats(event) + party_size > event.capacity:
                raise _error("No quedan plazas suficientes para este evento.", "event_full")
        else:
            requested_for = _validate_table_datetime(requested_for, now)
        active = Reservation.objects.filter(
            customer=customer, status__in=Reservation.ACTIVE_STATUSES, requested_for__gte=now
        ).count()
        if active >= settings.EVENTS_MAX_ACTIVE_RESERVATIONS_PER_CUSTOMER:
            raise _error(
                f"Ya tienes {active} reservas activas. Cancela alguna antes de pedir otra.", "too_many_active"
            )
        reservation = Reservation.objects.create(
            customer=customer,
            event=event,
            requested_for=requested_for,
            party_size=party_size,
            notes=notes,
            idempotency_key=key,
            created_at=now,
        )
        _notify_customer(reservation, NKind.RESERVATION_RECEIVED)
        _notify_owners(reservation, "Nueva solicitud de reserva")
    return ReservationResult(reservation=reservation, created=True)


def request_reservation(*, customer, party_size, idempotency_key, requested_for=None, event=None, notes=""):
    ensure_can_reserve(customer)
    key = parse_idempotency_key(idempotency_key)
    party_size = _parse_party_size(party_size)
    notes = _parse_text(notes, "notes")
    existing = Reservation.objects.filter(idempotency_key=key).first()
    if existing is not None:
        return _replay(existing, customer)
    scope, limit = "reservation-request", settings.EVENTS_RESERVATION_MAX_REQUESTS_PER_HOUR
    if throttling.is_limited(scope, customer.pk, limit):
        raise _error("Has hecho demasiadas solicitudes de reserva. Inténtalo más tarde.", "rate_limited")
    now = timezone.now()
    try:
        result = _create(
            customer, event=event, requested_for=requested_for, party_size=party_size, notes=notes, key=key, now=now
        )
    except IntegrityError:
        existing = Reservation.objects.filter(idempotency_key=key).first()
        if existing is not None:
            return _replay(existing, customer)
        if event is not None and Reservation.objects.filter(
            customer=customer, event=event, status__in=Reservation.ACTIVE_STATUSES
        ).exists():
            raise _error("Ya tienes una reserva activa para este evento.", "already_reserved") from None
        raise
    throttling.register_attempt(scope, customer.pk, _HOUR)
    logger.info("Reserva solicitada %s", result.reservation.public_id)
    return result


# --- Reservas: cambios de estado --------------------------------------------------------


def _transition(*, reservation, to_status, actor, message="", by_customer=False):
    message = _parse_text(message, "message")
    now = timezone.now()
    with transaction.atomic():
        locked = Reservation.objects.select_for_update().select_related("event", "customer").get(pk=reservation.pk)
        if by_customer and locked.customer_id != actor.pk:
            raise PermissionDenied
        if locked.status == to_status:
            return ReservationResult(reservation=locked, created=False)
        if not locked.can_transition_to(to_status):
            raise _error(
                f"Una reserva {locked.get_status_display().lower()} no puede pasar a "
                f"{Status(to_status).label.lower()}.",
                "invalid_transition",
            )
        if to_status == Status.CONFIRMED:
            if locked.requested_for <= now:
                raise _error("La fecha de la reserva ya ha pasado.", "in_the_past")
            if locked.event_id:
                event = Event.objects.select_for_update().get(pk=locked.event_id)
                if event.capacity is not None and confirmed_seats(event) + locked.party_size > event.capacity:
                    raise _error("Confirmarla superaría el aforo del evento.", "event_full")
        if to_status == Status.COMPLETED and timezone.localdate(locked.requested_for) > timezone.localdate(now):
            raise _error("Una reserva solo se completa a partir de su día.", "too_early")
        if by_customer and locked.requested_for <= now:
            raise _error("La hora de la reserva ya ha pasado: ya no se puede cancelar.", "in_the_past")

        old_status = locked.status
        locked.status = to_status
        locked.status_changed_at = now
        locked.status_changed_by = actor
        fields = ["status", "status_changed_at", "status_changed_by", "updated_at"]
        if message:
            locked.owner_message = message
            fields.append("owner_message")
        locked.save(update_fields=fields)
        record_audit_event(
            action=AuditEvent.Action.RESERVATION_STATUS_CHANGED,
            actor=actor,
            target=locked,
            metadata={"from": old_status, "to": to_status, "by": "customer" if by_customer else "owner"},
        )
        if to_status == Status.CONFIRMED:
            _notify_customer(locked, NKind.RESERVATION_CONFIRMED, message=message)
        elif to_status == Status.REJECTED:
            _notify_customer(locked, NKind.RESERVATION_REJECTED, message=message)
        elif to_status == Status.CANCELLED:
            _notify_customer(locked, NKind.RESERVATION_CANCELLED, message=message, by_customer=by_customer)
            if by_customer:
                _notify_owners(locked, "Reserva cancelada por el cliente")
    return ReservationResult(reservation=locked, created=True)


def confirm_reservation(*, actor, reservation, message=""):
    _require_owner(actor)
    return _transition(reservation=reservation, to_status=Status.CONFIRMED, actor=actor, message=message)


def reject_reservation(*, actor, reservation, message=""):
    _require_owner(actor)
    return _transition(reservation=reservation, to_status=Status.REJECTED, actor=actor, message=message)


def cancel_reservation(*, actor, reservation, message=""):
    _require_owner(actor)
    return _transition(reservation=reservation, to_status=Status.CANCELLED, actor=actor, message=message)


def complete_reservation(*, actor, reservation):
    _require_owner(actor)
    return _transition(reservation=reservation, to_status=Status.COMPLETED, actor=actor)


def cancel_own_reservation(*, customer, reservation):
    """El cliente cancela su propia reserva (pendiente o confirmada) antes de la hora."""
    ensure_can_reserve(customer)
    return _transition(reservation=reservation, to_status=Status.CANCELLED, actor=customer, by_customer=True)


def record_reservation_data_access(*, actor, reservation):
    """El propietario abrió el detalle con el contacto del cliente: queda auditado sin los datos."""
    _require_owner(actor)
    record_audit_event(action=AuditEvent.Action.RESERVATION_DATA_VIEWED, actor=actor, target=reservation)
