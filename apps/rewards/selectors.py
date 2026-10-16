"""
Consultas de recompensas y canjes para la web y la futura API (solo lectura).

Los canjes se piden siempre para un cliente ya resuelto en el servidor (el
usuario autenticado), nunca para un ID enviado por él.
"""
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.permissions import is_owner
from apps.core.querysets import period_q

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


def validations_by(staff, *, since=None):
    """
    Canjes que validó `staff` (panel del personal, Fase 8). Solo los propios,
    también para el propietario: la vista global es del dashboard (Fase 9).
    """
    queryset = Redemption.objects.filter(validated_by=staff)
    if since is not None:
        queryset = queryset.filter(validated_at__gte=since)
    return queryset.select_related("customer", "reward").order_by("-validated_at", "-id")


# --- Dashboard del propietario (Fase 9) ---------------------------------------------


def _require_owner(actor):
    if not is_owner(actor):
        raise PermissionDenied(_("Solo el propietario puede ver todos los canjes."))


@dataclass(frozen=True)
class RedemptionStats:
    requested: int
    used: int
    closed: int
    pending_now: int


def redemption_stats(*, actor, start=None, end=None):
    """
    Canjes del periodo (solo propietario): solicitados, **utilizados**
    (validados en barra en el periodo) y cancelados o caducados; más los
    pendientes de recoger ahora mismo, sin filtrar por fechas. Una sola consulta.
    """
    _require_owner(actor)
    Status = Redemption.Status
    totals = Redemption.objects.aggregate(
        requested=Count("id", filter=period_q("created_at", start, end)),
        used=Count("id", filter=Q(status=Status.USED) & period_q("validated_at", start, end)),
        closed=Count("id", filter=Q(status__in=Redemption.CLOSED_STATUSES) & period_q("closed_at", start, end)),
        pending_now=Count("id", filter=Q(status=Status.PENDING)),
    )
    return RedemptionStats(**totals)


def all_redemptions(*, actor, start=None, end=None, status=None):
    """Canjes solicitados en el periodo (solo propietario). Sin el código: nunca se muestra."""
    _require_owner(actor)
    queryset = Redemption.objects.filter(period_q("created_at", start, end))
    if status:
        queryset = queryset.filter(status=status)
    return (
        queryset.select_related("customer", "reward", "validated_by")
        .defer("code")
        .order_by("-created_at", "-id")
    )


def rewards_overview(*, actor):
    """Todas las recompensas con sus canjes utilizados y pendientes."""
    _require_owner(actor)
    Status = Redemption.Status
    return Reward.objects.annotate(
        used_count=Count("redemptions", filter=Q(redemptions__status=Status.USED)),
        pending_count=Count("redemptions", filter=Q(redemptions__status=Status.PENDING)),
    ).order_by("position", "points_cost", "name")


def validations_by_staff(*, actor, start=None, end=None):
    """Canjes validados por cada miembro del personal en el periodo: `{user_id: número}`."""
    _require_owner(actor)
    queryset = Redemption.objects.filter(period_q("validated_at", start, end), status=Redemption.Status.USED)
    return {row["validated_by"]: row["count"] for row in queryset.values("validated_by").annotate(count=Count("id")).order_by()}
