"""
Operaciones del propietario expuestas en la API v1, limitadas a las que una
app móvil necesita de verdad:

- estadísticas agregadas (sin datos personales), con los mismos selectores que
  el dashboard;
- reservas: listado sin datos de contacto y confirmar, rechazar, cancelar o
  completar.

La gestión completa (clientes, empleados, puntos, catálogo, contenidos,
campañas) sigue en el dashboard web y el admin. Todos los selectores y
servicios vuelven a comprobar que el actor es propietario.
"""
import datetime

from django.http import Http404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.response import Response

from apps.accounts import selectors as account_selectors
from apps.events import selectors as event_selectors
from apps.events import services as event_services
from apps.events.models import Reservation
from apps.loyalty import selectors as loyalty_selectors
from apps.purchases import selectors as purchase_selectors
from apps.rewards import selectors as reward_selectors

from ..permissions import IsOwner
from ..schema import ERROR
from ..serializers.events import OwnerReservationSerializer, ReservationDecisionSerializer
from ..serializers.owner import OwnerStatsSerializer, PeriodQuerySerializer
from .base import ApiView, ListApiView

TAG = "Propietario"
DEFAULT_PERIOD_DAYS = 30

PERIOD_PARAMETERS = [
    OpenApiParameter("date_from", type=datetime.date, description="Desde (incluido), AAAA-MM-DD."),
    OpenApiParameter("date_to", type=datetime.date, description="Hasta (incluido), AAAA-MM-DD."),
]


def _midnight(day):
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time.min))


def _period(request, *, default_days=None):
    """Fechas locales `[date_from, date_to]` → `[start, end)` con zona horaria."""
    serializer = PeriodQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    date_from = serializer.validated_data.get("date_from")
    date_to = serializer.validated_data.get("date_to")
    if default_days is not None:
        date_to = date_to or timezone.localdate()
        date_from = date_from or date_to - datetime.timedelta(days=default_days - 1)
        if date_from > date_to:
            raise serializers.ValidationError("La fecha inicial debe ser anterior o igual a la final.")
    start = _midnight(date_from) if date_from else None
    end = _midnight(date_to + datetime.timedelta(days=1)) if date_to else None
    return date_from, date_to, start, end


class OwnerStatsView(ApiView):
    permission_classes = [IsOwner]

    @extend_schema(
        tags=[TAG],
        parameters=PERIOD_PARAMETERS,
        responses={200: OwnerStatsSerializer, 400: ERROR, 403: ERROR},
        summary="Estadísticas del periodo",
        description=(
            "Totales agregados, sin datos personales. Por defecto, los últimos 30 días. "
            "Las compras registradas **no** son la facturación del local (`business_revenue` es siempre null)."
        ),
    )
    def get(self, request):
        date_from, date_to, start, end = _period(request, default_days=DEFAULT_PERIOD_DAYS)
        actor, span = request.user, {"start": start, "end": end}
        data = {
            "period": {"date_from": date_from, "date_to": date_to},
            "customers": account_selectors.customer_counts(actor=actor, **span).__dict__,
            "purchases": purchase_selectors.registered_purchases_stats(actor=actor, **span).__dict__,
            "points": loyalty_selectors.points_stats(actor=actor, **span).__dict__,
            "redemptions": reward_selectors.redemption_stats(actor=actor, **span).__dict__,
            "reservations": event_selectors.reservation_stats(actor=actor, **span).__dict__,
        }
        return Response(OwnerStatsSerializer(data).data)


@extend_schema(
    tags=[TAG],
    summary="Reservas",
    description="Sin datos de contacto del cliente (solo nombre corto). Ordenadas por fecha de la reserva.",
    parameters=[
        OpenApiParameter("status", enum=Reservation.Status.values, description="Filtra por estado."),
        *PERIOD_PARAMETERS,
    ],
)
class OwnerReservationListView(ListApiView):
    permission_classes = [IsOwner]
    serializer_class = OwnerReservationSerializer

    def get_queryset(self):
        status = self.request.query_params.get("status", "")
        if status and status not in Reservation.Status.values:
            raise serializers.ValidationError({"status": "Estado no válido."})
        _, _, start, end = _period(self.request)
        return event_selectors.reservations_for_management(actor=self.request.user, status=status, start=start, end=end)


_TRANSITIONS = {
    "confirm": event_services.confirm_reservation,
    "reject": event_services.reject_reservation,
    "cancel": event_services.cancel_reservation,
    "complete": event_services.complete_reservation,
}


class OwnerReservationTransitionView(ApiView):
    permission_classes = [IsOwner]

    @extend_schema(
        tags=[TAG],
        request=ReservationDecisionSerializer,
        responses={200: OwnerReservationSerializer, 400: ERROR, 403: ERROR, 404: ERROR, 409: ERROR},
        summary="Cambiar el estado de una reserva",
        description=(
            "`action`: `confirm`, `reject`, `cancel` o `complete`. El cliente recibe el aviso por email. "
            "`message` no aplica a `complete`. Errores: `invalid_transition`, `event_full` (409); `in_the_past`, "
            "`too_early` (400)."
        ),
    )
    def post(self, request, public_id, action):
        handler = _TRANSITIONS.get(action)
        reservation = event_selectors.reservation_for_owner(actor=request.user, public_id=public_id)
        if handler is None or reservation is None:
            raise Http404
        serializer = ReservationDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        kwargs = {"actor": request.user, "reservation": reservation}
        if action != "complete":
            kwargs["message"] = serializer.validated_data["message"]
        result = handler(**kwargs)
        return Response(OwnerReservationSerializer(result.reservation).data)
