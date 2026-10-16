"""Puntos, compras y QR del cliente autenticado (solo lectura)."""
from rest_framework import serializers

from apps.loyalty.models import PointsTransaction
from apps.purchases.models import Purchase


class PointsSummarySerializer(serializers.Serializer):
    balance = serializers.IntegerField(help_text="Saldo actual (suma de todos los movimientos).")
    earned = serializers.IntegerField(help_text="Obtenidos: compras, promociones y ajustes a favor.")
    used = serializers.IntegerField(help_text="Gastados en canjes, descontadas las devoluciones.")
    corrected = serializers.IntegerField(help_text="Restados por compensaciones o ajustes en contra.")
    expired = serializers.IntegerField(help_text="Caducados según la caducidad de los puntos (Fase 14).")


class _PromotionRefSerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    name = serializers.CharField()


class MovementSerializer(serializers.Serializer):
    """Sin motivo interno, autor, regla ni referencias de idempotencia."""

    public_id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=PointsTransaction.Kind.choices)
    kind_display = serializers.CharField(source="get_kind_display")
    points = serializers.IntegerField()
    balance_after = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    promotion = _PromotionRefSerializer(allow_null=True)
    purchase = serializers.UUIDField(source="purchase.public_id", allow_null=True, default=None)


class CustomerPurchaseSerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=8, decimal_places=2, help_text='Euros como texto: "12.50".')
    created_at = serializers.DateTimeField()
    status = serializers.ChoiceField(choices=Purchase.Status.choices)
    status_display = serializers.CharField(source="get_status_display")
    points = serializers.IntegerField(help_text="Puntos que generó la compra (incluidas promociones).")


class QRCodeSerializer(serializers.Serializer):
    payload = serializers.CharField(help_text="Contenido del QR que la app debe dibujar (`CF1:…`).")
    code = serializers.CharField(help_text="El mismo código en grupos de 4, para teclearlo a mano.")
    rotated_at = serializers.DateTimeField(allow_null=True)
