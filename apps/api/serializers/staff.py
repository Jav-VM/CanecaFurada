"""
Operaciones del personal en barra: identificar al cliente por su QR, registrar
compras y comprobar/validar canjes. Los códigos van siempre en el cuerpo de un
POST, nunca en la URL. Del cliente solo se devuelve el nombre corto.
"""
from rest_framework import serializers

from apps.purchases.models import Purchase
from apps.rewards.models import Redemption


class QRCodeInputSerializer(serializers.Serializer):
    qr_code = serializers.CharField(max_length=100, help_text="Contenido leído del QR (`CF1:…`) o código tecleado.")


class IdentifiedCustomerSerializer(serializers.Serializer):
    display_name = serializers.CharField(help_text="Nombre e inicial del apellido, para confirmar en barra.")


class PurchaseCreateSerializer(QRCodeInputSerializer):
    amount = serializers.CharField(
        max_length=20, help_text='Importe en euros con hasta dos decimales: "12.50". El servidor calcula los puntos.'
    )


class StaffPurchaseSerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=8, decimal_places=2)
    created_at = serializers.DateTimeField()
    source = serializers.ChoiceField(choices=Purchase.Source.choices)
    status = serializers.ChoiceField(choices=Purchase.Status.choices)
    points = serializers.IntegerField()
    customer_name = serializers.CharField()


class RedemptionCodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=100, help_text="Contenido del QR del canje (`CFR1:…`) o código tecleado.")


class RedemptionPreviewSerializer(serializers.Serializer):
    """Sin email, teléfono ni saldo del cliente."""

    customer_name = serializers.CharField()
    reward_name = serializers.CharField()
    points_cost = serializers.IntegerField()
    status = serializers.ChoiceField(choices=Redemption.Status.choices)
    status_display = serializers.CharField()
    created_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    validated_at = serializers.DateTimeField(allow_null=True)
    can_validate = serializers.BooleanField()


class ValidatedRedemptionSerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    reward_name = serializers.CharField(source="reward.name")
    points_cost = serializers.IntegerField()
    status = serializers.ChoiceField(choices=Redemption.Status.choices)
    validated_at = serializers.DateTimeField()
    customer_name = serializers.CharField()
