"""
Operaciones del personal (empleados y propietario) en barra, con los mismos
servicios que el panel web `/panel/`: identificar al cliente por su QR,
registrar una compra y comprobar/validar un canje. Del cliente solo se
devuelve el nombre corto.
"""
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from apps.loyalty import selectors as loyalty_selectors
from apps.loyalty.services import customer_display_name
from apps.purchases import services as purchases
from apps.rewards import services as rewards

from ..permissions import IsStaffMember
from ..schema import ERROR, IDEMPOTENCY_KEY
from ..serializers.staff import (
    IdentifiedCustomerSerializer,
    PurchaseCreateSerializer,
    QRCodeInputSerializer,
    RedemptionCodeSerializer,
    RedemptionPreviewSerializer,
    StaffPurchaseSerializer,
    ValidatedRedemptionSerializer,
)
from .base import ApiView, idempotency_key

TAG = "Personal"


class StaffView(ApiView):
    permission_classes = [IsStaffMember]


class IdentifyCustomerView(StaffView):
    @extend_schema(
        tags=[TAG],
        request=QRCodeInputSerializer,
        responses={200: IdentifiedCustomerSerializer, 400: ERROR, 403: ERROR, 429: ERROR},
        summary="Identificar al cliente por su QR",
        description="Errores: `invalid_qr`, `email_not_verified` (400); demasiados códigos no válidos (429).",
    )
    def post(self, request):
        serializer = QRCodeInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = purchases.identify_for_purchase(staff=request.user, qr_code=serializer.validated_data["qr_code"])
        return Response(IdentifiedCustomerSerializer({"display_name": customer.display_name}).data)


class RegisterPurchaseView(StaffView):
    @extend_schema(
        tags=[TAG],
        request=PurchaseCreateSerializer,
        parameters=[IDEMPOTENCY_KEY],
        responses={201: StaffPurchaseSerializer, 200: StaffPurchaseSerializer, 400: ERROR, 403: ERROR, 409: ERROR, 429: ERROR},
        summary="Registrar una compra",
        description=(
            "El servidor vuelve a validar el QR y el cliente y calcula los puntos. Errores: `amount_*`, `invalid_qr`, "
            "`email_not_verified`, `idempotency_invalid` (400); `idempotency_conflict` (409)."
        ),
    )
    def post(self, request):
        serializer = PurchaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = purchases.register_purchase(
            staff=request.user,
            qr_code=serializer.validated_data["qr_code"],
            amount=serializer.validated_data["amount"],
            idempotency_key=idempotency_key(request),
        )
        purchase = result.purchase
        data = {
            "public_id": purchase.public_id,
            "amount": purchase.amount,
            "created_at": purchase.created_at,
            "source": purchase.source,
            "status": purchase.status,
            "points": loyalty_selectors.points_for_purchase(purchase),
            "customer_name": customer_display_name(purchase.customer),
        }
        return Response(
            StaffPurchaseSerializer(data).data,
            status=status.HTTP_201_CREATED if result.created else status.HTTP_200_OK,
        )


class LookupRedemptionView(StaffView):
    @extend_schema(
        tags=[TAG],
        request=RedemptionCodeSerializer,
        responses={200: RedemptionPreviewSerializer, 400: ERROR, 403: ERROR, 429: ERROR},
        summary="Comprobar un código de canje",
        description="No lo valida. Error `invalid_code` (400).",
    )
    def post(self, request):
        serializer = RedemptionCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        preview = rewards.lookup_redemption(staff=request.user, code=serializer.validated_data["code"])
        data = {**preview.__dict__, "can_validate": preview.can_validate}
        return Response(RedemptionPreviewSerializer(data).data)


class ValidateRedemptionView(StaffView):
    @extend_schema(
        tags=[TAG],
        request=RedemptionCodeSerializer,
        responses={200: ValidatedRedemptionSerializer, 400: ERROR, 403: ERROR, 409: ERROR, 429: ERROR},
        summary="Validar (entregar) un canje",
        description=(
            "Solo una validación tiene éxito aunque lleguen dos a la vez. Errores: `invalid_code`, `code_expired` "
            "(400); `code_used`, `code_not_pending` (409); 403 si el canje es del propio empleado."
        ),
    )
    def post(self, request):
        serializer = RedemptionCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        redemption = rewards.validate_redemption(staff=request.user, code=serializer.validated_data["code"]).redemption
        data = {
            "public_id": redemption.public_id,
            "reward": redemption.reward,
            "points_cost": redemption.points_cost,
            "status": redemption.status,
            "validated_at": redemption.validated_at,
            "customer_name": customer_display_name(redemption.customer),
        }
        return Response(ValidatedRedemptionSerializer(data).data)
