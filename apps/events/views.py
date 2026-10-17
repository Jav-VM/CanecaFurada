"""
Vistas de eventos y reservas. Solo presentación: reglas en `services`,
consultas en `selectors`.

- Público (`/eventos/<id>/`): detalle de un evento publicado.
- Cliente (`/cuenta/reservas/...`): exige cliente con email verificado;
  siempre actúa sobre `request.user`. Una reserva ajena da 404.

Las respuestas de cliente no se guardan en caché.
"""
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.utils.translation import gettext as _

from apps.accounts.forms import apply_service_errors
from apps.accounts.models import User
from apps.accounts.permissions import verified_email_required
from apps.web import services as web

from . import selectors, services
from .forms import EventReservationForm, TableReservationForm

PAGE_SIZE = 20


def _require_customer(user):
    if user.role != User.Role.CUSTOMER:
        raise PermissionDenied


def _phone_reservations_redirect(request):
    """Reservas online desactivadas (Fase 17): se reserva por teléfono desde Contacto."""
    messages.info(request, _("Ahora mismo las reservas se hacen por teléfono."))
    return redirect(reverse("web:contact") + "#reservas")


# --- Público ---------------------------------------------------------------------


@require_GET
def event_detail(request, public_id):
    event = selectors.public_event(public_id)
    if event is None:
        raise Http404
    user = request.user
    is_customer = user.is_authenticated and user.role == User.Role.CUSTOMER
    return render(
        request,
        "events/event_detail.html",
        {
            "event": event,
            "bookable": selectors.is_bookable(event),
            "seats_left": selectors.seats_left(event),
            "is_customer": is_customer,
            "own_reservation": selectors.active_reservation_for_event(user, event) if is_customer else None,
        },
    )


# --- Cliente ---------------------------------------------------------------------


@never_cache
@require_GET
@verified_email_required
def my_reservations(request):
    _require_customer(request.user)
    page = Paginator(selectors.customer_reservations(request.user), PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "events/my_reservations.html", {"reservations": page})


def _submit(request, form, *, event=None):
    try:
        result = services.request_reservation(customer=request.user, event=event, **form.service_kwargs())
    except ValidationError as exc:
        apply_service_errors(form, exc, field_map={"requested_for": "date"})
        return None
    if result.created:
        messages.success(request, _("Solicitud enviada. Te avisaremos por email cuando el local la confirme."))
    else:
        messages.info(request, _("Esta solicitud ya estaba enviada."))
    return redirect("events:reservation_detail", public_id=result.reservation.public_id)


@never_cache
@require_http_methods(["GET", "POST"])
@verified_email_required
def reservation_new(request):
    _require_customer(request.user)
    if not web.online_reservations_enabled():
        return _phone_reservations_redirect(request)
    initial = {"idempotency_key": services.new_idempotency_key()}
    form = TableReservationForm(request.POST or None, initial=initial)
    status = 200
    if request.method == "POST":
        if form.is_valid():
            response = _submit(request, form)
            if response is not None:
                return response
        status = 400
    return render(request, "events/reservation_form.html", {"form": form, "event": None}, status=status)


@never_cache
@require_http_methods(["GET", "POST"])
@verified_email_required
def event_reservation_new(request, public_id):
    _require_customer(request.user)
    event = selectors.public_event(public_id)
    if event is None:
        raise Http404
    own = selectors.active_reservation_for_event(request.user, event)
    if own is not None:
        messages.info(request, _("Ya tienes una reserva activa para este evento."))
        return redirect("events:reservation_detail", public_id=own.public_id)
    if not web.online_reservations_enabled():
        return _phone_reservations_redirect(request)
    if not selectors.is_bookable(event):
        messages.error(request, _("Este evento no admite reservas."))
        return redirect("events:event_detail", public_id=event.public_id)
    form = EventReservationForm(request.POST or None, initial={"idempotency_key": services.new_idempotency_key()})
    status = 200
    if request.method == "POST":
        if form.is_valid():
            response = _submit(request, form, event=event)
            if response is not None:
                return response
        status = 400
    context = {"form": form, "event": event, "seats_left": selectors.seats_left(event)}
    return render(request, "events/reservation_form.html", context, status=status)


def _own_or_404(request, public_id):
    reservation = selectors.customer_reservation(request.user, public_id)
    if reservation is None:
        raise Http404
    return reservation


@never_cache
@require_GET
@verified_email_required
def reservation_detail(request, public_id):
    _require_customer(request.user)
    return render(request, "events/reservation_detail.html", {"reservation": _own_or_404(request, public_id)})


@never_cache
@require_POST
@verified_email_required
def reservation_cancel(request, public_id):
    _require_customer(request.user)
    reservation = _own_or_404(request, public_id)
    try:
        result = services.cancel_own_reservation(customer=request.user, reservation=reservation)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        if result.created:
            messages.success(request, _("Reserva cancelada."))
    return redirect("events:reservation_detail", public_id=reservation.public_id)
