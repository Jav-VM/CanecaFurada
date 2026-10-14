"""Eventos y reservas ficticios para los tests de la Fase 10."""
import datetime
import uuid

from django.utils import timezone

from apps.events import services
from apps.events.models import Event


def make_event(**overrides):
    """Evento publicado dentro de 7 días, con reservas y 10 plazas."""
    data = {
        "title": "Cata de otoño",
        "summary": "Cata guiada de cervezas de temporada.",
        "starts_at": timezone.now() + datetime.timedelta(days=7),
        "status": Event.Status.PUBLISHED,
        "accepts_reservations": True,
        "capacity": 10,
    }
    data.update(overrides)
    return Event.objects.create(**data)


def table_time(days=3, hour=21):
    """Fecha de reserva de mesa válida (dentro de unos días, a una hora fija)."""
    day = timezone.localdate() + datetime.timedelta(days=days)
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time(hour, 0)))


def reserve(customer, *, event=None, party_size=2, key=None, requested_for=None, notes=""):
    if event is None and requested_for is None:
        requested_for = table_time()
    return services.request_reservation(
        customer=customer,
        event=event,
        party_size=party_size,
        requested_for=requested_for,
        notes=notes,
        idempotency_key=key or uuid.uuid4(),
    )
