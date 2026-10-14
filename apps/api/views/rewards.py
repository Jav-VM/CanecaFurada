"""Recompensas publicadas y canjes del cliente verificado."""
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.rewards import selectors, services

from ..permissions import IsVerifiedCustomer
from ..schema import ERROR, IDEMPOTENCY_KEY
from ..serializers.rewards import RedemptionDetailSerializer, RedemptionSerializer, RewardSerializer
from .base import ApiView, ListApiView, idempotency_key

TAG = "Recompensas y canjes"


@extend_schema(tags=[TAG], summary="Recompensas disponibles", description="Públicas: activas y dentro de sus fechas.")
class RewardListView(ListApiView):
    permission_classes = [AllowAny]
    serializer_class = RewardSerializer

    def get_queryset(self):
        return selectors.public_rewards()


def _public_reward(public_id):
    reward = selectors.public_reward(public_id)
    if reward is None:
        raise Http404
    return reward


class RewardDetailView(ApiView):
    permission_classes = [AllowAny]

    @extend_schema(tags=[TAG], responses={200: RewardSerializer, 404: ERROR}, summary="Una recompensa")
    def get(self, request, public_id):
        return Response(RewardSerializer(_public_reward(public_id), context={"request": request}).data)


class RedeemView(ApiView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=[TAG],
        request=None,
        parameters=[IDEMPOTENCY_KEY],
        responses={201: RedemptionDetailSerializer, 200: RedemptionDetailSerializer, 400: ERROR, 403: ERROR, 404: ERROR, 409: ERROR},
        summary="Canjear una recompensa",
        description=(
            "Descuenta los puntos y devuelve el canje con su código de un solo uso. Errores: `insufficient_points`, "
            "`reward_unavailable`, `out_of_stock` (400); `duplicate_pending`, `idempotency_conflict` (409)."
        ),
    )
    def post(self, request, public_id):
        reward = _public_reward(public_id)
        result = services.request_redemption(
            customer=request.user, reward=reward, idempotency_key=idempotency_key(request)
        )
        return Response(
            RedemptionDetailSerializer(result.redemption).data,
            status=status.HTTP_201_CREATED if result.created else status.HTTP_200_OK,
        )


@extend_schema(tags=[TAG], summary="Mis canjes", description="Sin códigos: el código solo está en el detalle.")
class MyRedemptionListView(ListApiView):
    permission_classes = [IsVerifiedCustomer]
    serializer_class = RedemptionSerializer

    def get_queryset(self):
        return selectors.customer_redemptions(self.request.user)


def _own_redemption(request, public_id):
    redemption = selectors.customer_redemption(request.user, public_id)
    if redemption is None:
        raise Http404  # también si es de otro cliente: no se revela que existe
    return redemption


class MyRedemptionDetailView(ApiView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=[TAG],
        responses={200: RedemptionDetailSerializer, 404: ERROR},
        summary="Uno de mis canjes",
        description="Incluye `code` y `qr_payload` solo si está pendiente y vigente.",
    )
    def get(self, request, public_id):
        return Response(RedemptionDetailSerializer(_own_redemption(request, public_id)).data)


class MyRedemptionCancelView(ApiView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=[TAG],
        request=None,
        responses={200: RedemptionDetailSerializer, 404: ERROR, 409: ERROR},
        summary="Cancelar uno de mis canjes",
        description="Devuelve los puntos. Idempotente. 409 `code_not_pending` si ya se usó o caducó.",
    )
    def post(self, request, public_id):
        result = services.cancel_redemption(customer=request.user, redemption=_own_redemption(request, public_id))
        return Response(RedemptionDetailSerializer(result.redemption).data)
