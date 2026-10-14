"""Eventos publicados y reservas del cliente autenticado."""
from django.utils import timezone
from rest_framework import serializers

from apps.events import selectors
from apps.events.models import Reservation
from apps.loyalty.services import customer_display_name

from .rewards import absolute_media_url


class EventSerializer(serializers.Serializer):
    """Solo eventos publicados; sin estado de gestión ni fechas internas."""

    public_id = serializers.UUIDField()
    title = serializers.CharField()
    summary = serializers.CharField()
    description = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField(allow_null=True)
    image_url = serializers.SerializerMethodField()
    accepts_reservations = serializers.BooleanField()
    bookable = serializers.SerializerMethodField(help_text="Se puede pedir reserva ahora mismo.")

    def get_image_url(self, event) -> str | None:
        return absolute_media_url(self.context.get("request"), event.image)

    def get_bookable(self, event) -> bool:
        return selectors.is_bookable(event)


class EventDetailSerializer(EventSerializer):
    seats_left = serializers.SerializerMethodField(help_text="Plazas libres; null si no hay límite.")

    def get_seats_left(self, event) -> int | None:
        return selectors.seats_left(event)


class _EventRefSerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    title = serializers.CharField()


class ReservationSerializer(serializers.Serializer):
    """Reserva propia: sin quién cambió el estado ni referencias internas."""

    public_id = serializers.UUIDField()
    event = _EventRefSerializer(allow_null=True)
    requested_for = serializers.DateTimeField()
    party_size = serializers.IntegerField()
    notes = serializers.CharField()
    status = serializers.ChoiceField(choices=Reservation.Status.choices)
    status_display = serializers.CharField(source="get_status_display")
    owner_message = serializers.CharField(help_text="Mensaje del local.")
    created_at = serializers.DateTimeField()
    status_changed_at = serializers.DateTimeField(allow_null=True)
    can_cancel = serializers.SerializerMethodField()

    def get_can_cancel(self, reservation) -> bool:
        return reservation.is_active and reservation.requested_for > timezone.now()


class ReservationCreateSerializer(serializers.Serializer):
    """
    Reserva de un evento (`event`) o de mesa (`requested_for`). Con `event` se
    usa la hora del evento y se ignora `requested_for`. El estado, el cliente y
    el mensaje del local no se pueden enviar.
    """

    event = serializers.UUIDField(required=False, allow_null=True, default=None)
    requested_for = serializers.DateTimeField(
        required=False, allow_null=True, default=None, help_text="ISO 8601 con zona horaria (solo mesa)."
    )
    party_size = serializers.IntegerField(min_value=1, max_value=Reservation.MAX_PARTY_SIZE)
    notes = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class OwnerReservationSerializer(serializers.Serializer):
    """Listado del propietario: sin datos de contacto (como el dashboard)."""

    public_id = serializers.UUIDField()
    event = _EventRefSerializer(allow_null=True)
    requested_for = serializers.DateTimeField()
    party_size = serializers.IntegerField()
    status = serializers.ChoiceField(choices=Reservation.Status.choices)
    status_display = serializers.CharField(source="get_status_display")
    created_at = serializers.DateTimeField()
    customer_name = serializers.SerializerMethodField(help_text="Nombre e inicial del apellido.")

    def get_customer_name(self, reservation) -> str:
        return customer_display_name(reservation.customer)


class ReservationDecisionSerializer(serializers.Serializer):
    message = serializers.CharField(
        max_length=300, required=False, allow_blank=True, default="", help_text="Se muestra al cliente y va en el email."
    )
