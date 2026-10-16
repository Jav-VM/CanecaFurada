"""Estadísticas agregadas del propietario (sin datos personales)."""
import datetime

from rest_framework import serializers

MAX_RANGE_DAYS = 3660


class PeriodQuerySerializer(serializers.Serializer):
    """`from` y `to` incluidos (AAAA-MM-DD). Por defecto, los últimos 30 días."""

    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, attrs):
        start, end = attrs.get("date_from"), attrs.get("date_to")
        if start and end and start > end:
            raise serializers.ValidationError("La fecha inicial debe ser anterior o igual a la final.")
        if start and end and (end - start) > datetime.timedelta(days=MAX_RANGE_DAYS):
            raise serializers.ValidationError("El periodo no puede superar 10 años.")
        return attrs


class _CustomersStats(serializers.Serializer):
    total = serializers.IntegerField()
    active = serializers.IntegerField()
    verified = serializers.IntegerField()
    promo_email = serializers.IntegerField(help_text="Clientes activos con consentimiento de email promocional.")
    new_in_period = serializers.IntegerField()


class _PurchasesStats(serializers.Serializer):
    label = serializers.CharField()
    note = serializers.CharField(help_text="Las compras registradas no son la facturación del local.")
    purchases_count = serializers.IntegerField()
    customers_count = serializers.IntegerField()
    registered_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_amount = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    business_revenue = serializers.DecimalField(
        max_digits=12, decimal_places=2, allow_null=True, help_text="Siempre null: no se conoce."
    )


class _PointsStats(serializers.Serializer):
    issued = serializers.IntegerField()
    used = serializers.IntegerField()
    corrected = serializers.IntegerField()
    expired = serializers.IntegerField(help_text="Puntos caducados en el periodo.")
    outstanding = serializers.IntegerField(help_text="Saldo pendiente de todos los clientes (sin filtro de fechas).")
    customers_with_points = serializers.IntegerField()


class _RedemptionStats(serializers.Serializer):
    requested = serializers.IntegerField()
    used = serializers.IntegerField()
    closed = serializers.IntegerField()
    pending_now = serializers.IntegerField()


class _ReservationStats(serializers.Serializer):
    requested = serializers.IntegerField()
    confirmed = serializers.IntegerField()
    pending_now = serializers.IntegerField()
    upcoming_confirmed = serializers.IntegerField()
    upcoming_events = serializers.IntegerField()


class _Period(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()


class OwnerStatsSerializer(serializers.Serializer):
    period = _Period()
    customers = _CustomersStats()
    purchases = _PurchasesStats()
    points = _PointsStats()
    redemptions = _RedemptionStats()
    reservations = _ReservationStats()
