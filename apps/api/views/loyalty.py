"""Puntos, historial de compras y QR personal del cliente verificado."""
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from apps.loyalty import selectors, services
from apps.purchases import selectors as purchase_selectors

from ..permissions import IsVerifiedCustomer
from ..schema import ERROR
from ..serializers.loyalty import (
    CustomerPurchaseSerializer,
    MovementSerializer,
    PointsSummarySerializer,
    QRCodeSerializer,
)
from .base import ApiView, ListApiView

TAG = "Puntos y QR"


class PointsSummaryView(ApiView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(tags=[TAG], responses={200: PointsSummarySerializer, 403: ERROR}, summary="Mi saldo de puntos")
    def get(self, request):
        return Response(PointsSummarySerializer(selectors.points_summary(request.user)).data)


@extend_schema(tags=[TAG], summary="Mis movimientos de puntos", description="Del más reciente al más antiguo.")
class MovementListView(ListApiView):
    permission_classes = [IsVerifiedCustomer]
    serializer_class = MovementSerializer

    def get_queryset(self):
        return selectors.points_history(self.request.user)


@extend_schema(tags=[TAG], summary="Mis compras registradas", description="Con los puntos que generó cada una.")
class PurchaseListView(ListApiView):
    permission_classes = [IsVerifiedCustomer]
    serializer_class = CustomerPurchaseSerializer

    def get_queryset(self):
        return purchase_selectors.customer_purchases(self.request.user)


def _qr_data(qr):
    return QRCodeSerializer(
        {"payload": services.qr_payload(qr.token), "code": services.format_code(qr.token), "rotated_at": qr.rotated_at}
    ).data


class QRCodeView(ApiView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=[TAG],
        responses={200: QRCodeSerializer, 403: ERROR},
        summary="Mi QR personal",
        description=(
            "Contenido del QR para dibujarlo en la app. Solo identifica al cliente en barra; no autoriza nada. "
            "No lo guardes en registros ni lo envíes a analítica."
        ),
    )
    def get(self, request):
        return Response(_qr_data(services.get_customer_qr(request.user)))


class QRCodeRotateView(ApiView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=[TAG],
        request=None,
        responses={200: QRCodeSerializer, 403: ERROR, 429: ERROR},
        summary="Renovar mi QR",
        description="El código anterior deja de valer. Máximo 5 renovaciones al día.",
    )
    def post(self, request):
        return Response(_qr_data(services.rotate_customer_qr(request.user)))
