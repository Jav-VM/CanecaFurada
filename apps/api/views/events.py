"""Eventos publicados y reservas del cliente verificado."""
from django.core.exceptions import ValidationError
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.events import selectors, services

from ..permissions import IsVerifiedCustomer
from ..schema import ERROR, IDEMPOTENCY_KEY
from ..serializers.events import (
    EventDetailSerializer,
    EventSerializer,
    ReservationCreateSerializer,
    ReservationSerializer,
)
from .base import ApiView, ListApiView, idempotency_key

TAG = "Eventos y reservas"


@extend_schema(tags=[TAG], summary="Eventos publicados", description="Publicados y no terminados, por fecha.")
class EventListView(ListApiView):
    permission_classes = [AllowAny]
    serializer_class = EventSerializer

    def get_queryset(self):
        return selectors.public_events()


class EventDetailView(ApiView):
    permission_classes = [AllowAny]

    @extend_schema(tags=[TAG], responses={200: EventDetailSerializer, 404: ERROR}, summary="Un evento")
    def get(self, request, public_id):
        event = selectors.public_event(public_id)
        if event is None:
            raise Http404
        return Response(EventDetailSerializer(event, context={"request": request}).data)


class MyReservationListView(ListApiView):
    permission_classes = [IsVerifiedCustomer]
    serializer_class = ReservationSerializer

    def get_queryset(self):
        return selectors.customer_reservations(self.request.user)

    @extend_schema(tags=[TAG], summary="Mis reservas")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=[TAG],
        request=ReservationCreateSerializer,
        parameters=[IDEMPOTENCY_KEY],
        responses={201: ReservationSerializer, 200: ReservationSerializer, 400: ERROR, 403: ERROR, 409: ERROR, 429: ERROR},
        summary="Solicitar una reserva",
        description=(
            "De un evento (`event`) o de mesa (`requested_for`). Queda pendiente hasta que el local la confirme "
            "(se avisa por email). Errores: `event_not_bookable`, `too_many_active` (400); `already_reserved`, "
            "`event_full` (409); `rate_limited` (429)."
        ),
    )
    def post(self, request):
        serializer = ReservationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        event = None
        if data["event"] is not None:
            event = selectors.public_event(data["event"])
            if event is None:
                raise ValidationError(
                    {"event": ValidationError("Este evento no existe o ya no está publicado.", code="event_not_found")}
                )
        result = services.request_reservation(
            customer=request.user,
            event=event,
            requested_for=None if event is not None else data["requested_for"],
            party_size=data["party_size"],
            notes=data["notes"],
            idempotency_key=idempotency_key(request),
        )
        return Response(
            ReservationSerializer(result.reservation).data,
            status=status.HTTP_201_CREATED if result.created else status.HTTP_200_OK,
        )


def _own_reservation(request, public_id):
    reservation = selectors.customer_reservation(request.user, public_id)
    if reservation is None:
        raise Http404
    return reservation


class MyReservationDetailView(ApiView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(tags=[TAG], responses={200: ReservationSerializer, 404: ERROR}, summary="Una de mis reservas")
    def get(self, request, public_id):
        return Response(ReservationSerializer(_own_reservation(request, public_id)).data)


class MyReservationCancelView(ApiView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=[TAG],
        request=None,
        responses={200: ReservationSerializer, 400: ERROR, 404: ERROR, 409: ERROR},
        summary="Cancelar una de mis reservas",
        description="Pendiente o confirmada y antes de su hora. Idempotente.",
    )
    def post(self, request, public_id):
        result = services.cancel_own_reservation(customer=request.user, reservation=_own_reservation(request, public_id))
        return Response(ReservationSerializer(result.reservation).data)
