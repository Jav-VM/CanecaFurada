"""
Consultas de puntos para la web y la futura API (solo lectura).

Los datos se piden siempre para un cliente ya resuelto en el servidor (el
usuario autenticado), nunca para un ID enviado por el cliente.

Definiciones del resumen:
- **Saldo:** suma de todos los movimientos.
- **Obtenidos:** suma de los movimientos positivos (compras, promociones,
  ajustes a favor y compensaciones a favor).
- **Utilizados:** puntos gastados en canjes, descontadas las devoluciones de
  canjes cancelados o caducados (Fase 7).
- **Obtenidos** no incluye esas devoluciones.
- **Corregidos:** resto de movimientos negativos (compensaciones y ajustes en
  contra). Saldo = obtenidos − utilizados − corregidos.
"""
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce

from apps.accounts.permissions import is_owner
from apps.core.querysets import period_q

from .models import PointsTransaction, Promotion

Kind = PointsTransaction.Kind

# Canjes y sus devoluciones forman "utilizados"; el resto, obtenidos o corregidos.
_REDEMPTION_FLOW = Q(kind=Kind.REDEMPTION) | Q(kind=Kind.REVERSAL, reverses__kind=Kind.REDEMPTION)


def _totals():
    return {
        "earned": Coalesce(Sum("points", filter=Q(points__gt=0) & ~_REDEMPTION_FLOW), 0),
        "used": Coalesce(Sum("points", filter=_REDEMPTION_FLOW), 0),
        "corrected": Coalesce(Sum("points", filter=Q(points__lt=0) & ~_REDEMPTION_FLOW), 0),
    }


@dataclass(frozen=True)
class PointsSummary:
    balance: int
    earned: int
    used: int
    corrected: int


def points_summary(customer):
    totals = PointsTransaction.objects.filter(customer=customer).aggregate(
        balance=Coalesce(Sum("points"), 0), **_totals()
    )
    return PointsSummary(
        balance=totals["balance"],
        earned=totals["earned"],
        used=-totals["used"],
        corrected=-totals["corrected"],
    )


def points_history(customer):
    """Movimientos del cliente, del más reciente al más antiguo."""
    return (
        PointsTransaction.objects.filter(customer=customer)
        .select_related("promotion", "purchase", "reverses")
        .order_by("-created_at", "-id")
    )


def points_for_purchase(purchase):
    return purchase.points_transactions.aggregate(total=Coalesce(Sum("points"), 0))["total"]


@dataclass(frozen=True)
class PointsStats:
    issued: int
    used: int
    corrected: int
    outstanding: int
    customers_with_points: int


def points_stats(*, actor, start=None, end=None):
    """
    Puntos del programa en un periodo (solo propietario). `outstanding` es el
    saldo pendiente total de todos los clientes, sin filtrar por fechas.
    """
    if not is_owner(actor):
        raise PermissionDenied("Solo el propietario puede ver las estadísticas.")
    period = PointsTransaction.objects.filter(period_q("created_at", start, end)).aggregate(**_totals())
    overall = PointsTransaction.objects.aggregate(
        outstanding=Coalesce(Sum("points"), 0), customers=Count("customer", distinct=True)
    )
    return PointsStats(
        issued=period["earned"],
        used=-period["used"],
        corrected=-period["corrected"],
        outstanding=overall["outstanding"],
        customers_with_points=overall["customers"],
    )


# --- Dashboard del propietario (Fase 9) ---------------------------------------------


def all_movements(*, actor, start=None, end=None, kind=None):
    """Movimientos del ledger de todos los clientes (solo propietario), del más reciente al más antiguo."""
    if not is_owner(actor):
        raise PermissionDenied("Solo el propietario puede ver todos los movimientos de puntos.")
    movements = PointsTransaction.objects.filter(period_q("created_at", start, end))
    if kind:
        movements = movements.filter(kind=kind)
    return movements.select_related("customer", "promotion", "created_by").order_by("-created_at", "-id")


def reversible_ids(movements):
    """
    Ids de los movimientos que el propietario puede compensar desde el
    dashboard: no se compensan compensaciones ni canjes (los canjes se
    devuelven cancelándolos o al caducar) ni movimientos ya compensados.
    """
    candidates = [m.pk for m in movements if m.kind not in (Kind.REVERSAL, Kind.REDEMPTION)]
    reversed_ids = set(
        PointsTransaction.objects.filter(reverses__in=candidates).values_list("reverses_id", flat=True)
    )
    return {pk for pk in candidates if pk not in reversed_ids}


def promotions_overview(*, actor):
    """Promociones con el número de bonificaciones concedidas."""
    if not is_owner(actor):
        raise PermissionDenied("Solo el propietario puede ver las promociones.")
    return Promotion.objects.annotate(
        uses=Count(
            "points_transactions",
            filter=Q(points_transactions__kind__in=[Kind.PROMOTION_BONUS, Kind.BIRTHDAY_GIFT]),
        )
    ).order_by("-starts_at", "-id")
