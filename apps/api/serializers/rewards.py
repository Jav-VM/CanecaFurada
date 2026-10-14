"""Recompensas (públicas) y canjes del cliente autenticado."""
from rest_framework import serializers

from apps.rewards import codes
from apps.rewards.models import Redemption


def absolute_media_url(request, file_field):
    if not file_field:
        return None
    url = file_field.url
    return request.build_absolute_uri(url) if request is not None else url


class RewardSerializer(serializers.Serializer):
    """Sin estado de gestión, orden ni número de unidades: solo si quedan."""

    public_id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()
    image_url = serializers.SerializerMethodField()
    image_width = serializers.IntegerField(allow_null=True)
    image_height = serializers.IntegerField(allow_null=True)
    points_cost = serializers.IntegerField()
    valid_until = serializers.DateTimeField(allow_null=True)
    in_stock = serializers.BooleanField(source="is_in_stock")

    def get_image_url(self, reward) -> str | None:
        return absolute_media_url(self.context.get("request"), reward.image)


class _RewardRefSerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    name = serializers.CharField()


class RedemptionSerializer(serializers.Serializer):
    """Listado: nunca incluye el código."""

    public_id = serializers.UUIDField()
    reward = _RewardRefSerializer()
    points_cost = serializers.IntegerField()
    status = serializers.ChoiceField(choices=Redemption.Status.choices)
    status_display = serializers.CharField(source="get_status_display")
    created_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    validated_at = serializers.DateTimeField(allow_null=True)
    closed_at = serializers.DateTimeField(allow_null=True)


class RedemptionDetailSerializer(RedemptionSerializer):
    """Detalle del propio canje: el código y el contenido del QR solo mientras se puede recoger."""

    is_expired = serializers.SerializerMethodField()
    code = serializers.SerializerMethodField(help_text="Solo si está pendiente y vigente; si no, null.")
    qr_payload = serializers.SerializerMethodField(help_text="Contenido del QR (`CFR1:…`) o null.")

    def _collectable(self, redemption):
        return redemption.status == Redemption.Status.PENDING and not redemption.is_expired()

    def get_is_expired(self, redemption) -> bool:
        return redemption.is_expired()

    def get_code(self, redemption) -> str | None:
        return codes.format_code(redemption.code) if self._collectable(redemption) else None

    def get_qr_payload(self, redemption) -> str | None:
        return codes.qr_payload(redemption.code) if self._collectable(redemption) else None
