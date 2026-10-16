"""
Consultas de eventos y reservas (Fase 10).

- Públicas: solo eventos publicados que no han terminado.
- Cliente: siempre filtradas por el usuario autenticado; una reserva ajena
  devuelve `None` (la vista responde 404 y no revela si existe).
- Propietario: exigen el rol en el servidor. Los listados no cargan datos de
  contacto; el detalle sí (y la vista audita la consulta).
"""
import datetime
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.permissions import is_owner
from apps.core.querysets import period_q

from .models import Event, Reservation

Status = Reservation.Status
FEATURED_LIMIT = 3


def _require_owner(actor):
    if not is_owner(actor):
        raise PermissionDenied(_("Solo el propietario puede ver los eventos y las reservas."))


# Un evento sin hora de fin se da por terminado a las 6 horas de empezar.
DEFAULT_DURATION = datetime.timedelta(hours=6)


def _not_finished(now):
    return Q(ends_at__gt=now) | Q(ends_at__isnull=True, starts_at__gt=now - DEFAULT_DURATION)


# --- Público ---------------------------------------------------------------------


def public_events(now=None):
    now = now or timezone.now()
    return Event.objects.filter(_not_finished(now), status=Event.Status.PUBLISHED).order_by("starts_at", "id")


def featured_events(now=None):
    events = public_events(now)
    featured = list(events.filter(is_featured=True)[:FEATURED_LIMIT])
    return featured or list(events[:FEATURED_LIMIT])


def public_event(public_id, now=None):
    return public_events(now).filter(public_id=public_id).first()


def is_bookable(event, now=None):
    now = now or timezone.now()
    return event.status == Event.Status.PUBLISHED and event.accepts_reservations and not event.has_started(now)


def seats_left(event):
    if event.capacity is None:
        return None
    taken = event.reservations.filter(status=Status.CONFIRMED).aggregate(total=Coalesce(Sum("party_size"), 0))["total"]
    return max(event.capacity - taken, 0)


# --- Cliente ---------------------------------------------------------------------


def customer_reservations(customer):
    return Reservation.objects.filter(customer=customer).select_related("event").order_by("-requested_for", "-id")


def customer_reservation(customer, public_id):
    return Reservation.objects.filter(customer=customer, public_id=public_id).select_related("event").first()


def active_reservation_for_event(customer, event):
    return Reservation.objects.filter(customer=customer, event=event, status__in=Reservation.ACTIVE_STATUSES).first()


# --- Propietario -----------------------------------------------------------------


def events_for_management(*, actor, status=""):
    _require_owner(actor)
    queryset = Event.objects.annotate(
        pending=Count("reservations", filter=Q(reservations__status=Status.PENDING)),
        confirmed_people=Coalesce(Sum("reservations__party_size", filter=Q(reservations__status=Status.CONFIRMED)), 0),
    )
    if status:
        queryset = queryset.filter(status=status)
    return queryset.order_by("-starts_at", "-id")


def event_for_owner(*, actor, public_id):
    _require_owner(actor)
    return Event.objects.filter(public_id=public_id).first()


def reservations_for_management(*, actor, status="", start=None, end=None, event=None):
    """Listado sin datos de contacto: nombre del cliente, fecha, personas, evento y estado."""
    _require_owner(actor)
    queryset = Reservation.objects.select_related("event", "customer").only(
        "public_id",
        "requested_for",
        "party_size",
        "status",
        "created_at",
        "event__title",
        "event__public_id",
        "customer__first_name",
        "customer__last_name",
    )
    if status:
        queryset = queryset.filter(status=status)
    queryset = queryset.filter(period_q("requested_for", start, end))
    if event is not None:
        queryset = queryset.filter(event=event)
    return queryset.order_by("requested_for", "id")


def reservation_for_owner(*, actor, public_id):
    _require_owner(actor)
    return (
        Reservation.objects.select_related("event", "customer", "customer__customer_profile", "status_changed_by")
        .filter(public_id=public_id)
        .first()
    )


@dataclass(frozen=True)
class ReservationStats:
    requested: int
    confirmed: int
    pending_now: int
    upcoming_confirmed: int
    upcoming_events: int


def reservation_stats(*, actor, start=None, end=None, now=None):
    """
    Reservas solicitadas en el periodo (por fecha de solicitud) y situación
    actual. Una consulta para las reservas y otra para los eventos.
    """
    _require_owner(actor)
    now = now or timezone.now()
    period = period_q("created_at", start, end)
    upcoming = Q(requested_for__gte=now)
    totals = Reservation.objects.aggregate(
        requested=Count("id", filter=period),
        confirmed=Count("id", filter=period & Q(status__in=[Status.CONFIRMED, Status.COMPLETED])),
        pending_now=Count("id", filter=upcoming & Q(status=Status.PENDING)),
        upcoming_confirmed=Count("id", filter=upcoming & Q(status=Status.CONFIRMED)),
    )
    return ReservationStats(**totals, upcoming_events=public_events(now).filter(starts_at__gte=now).count())
