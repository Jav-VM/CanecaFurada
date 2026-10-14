"""
Consultas de recompensas y canjes para la web y la futura API (solo lectura).

Los canjes se piden siempre para un cliente ya resuelto en el servidor (el
usuario autenticado), nunca para un ID enviado por él.
"""
from django.db.models import Q
from django.utils import timezone

from .models import Redemption, Reward


def public_rewards(now=None):
    """Recompensas activas dentro de sus fechas, incluidas las agotadas (se muestran como tales)."""
    now = now or timezone.now()
    return Reward.objects.filter(
        Q(valid_until__isnull=True) | Q(valid_until__gt=now),
        status=Reward.Status.ACTIVE,
        valid_from__lte=now,
    )


def public_reward(public_id, now=None):
    return public_rewards(now).filter(public_id=public_id).first()


def customer_redemptions(customer):
    """Historial de canjes del cliente, del más reciente al más antiguo."""
    return Redemption.objects.filter(customer=customer).select_related("reward").order_by("-created_at", "-id")


def customer_redemption(customer, public_id):
    """Un canje del propio cliente o `None` (también si es de otro: no se revela que existe)."""
    return customer_redemptions(customer).filter(public_id=public_id).first()


def pending_redemption_for(customer, reward):
    return Redemption.objects.filter(customer=customer, reward=reward, status=Redemption.Status.PENDING).first()


def recent_validations_by(staff, limit=10):
    return list(
        Redemption.objects.filter(validated_by=staff).select_related("reward").order_by("-validated_at")[:limit]
    )
