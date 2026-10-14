"""
Consultas de puntos para la web y la futura API (solo lectura).

Los datos se piden siempre para un cliente ya resuelto en el servidor (el
usuario autenticado), nunca para un ID enviado por el cliente.

Definiciones del resumen:
- **Saldo:** suma de todos los movimientos.
- **Obtenidos:** suma de los movimientos positivos (compras, promociones,
  ajustes a favor y compensaciones a favor).
- **Utilizados:** puntos gastados en canjes (Fase 7; hoy siempre 0).
- **Corregidos:** resto de movimientos negativos (compensaciones y ajustes en
  contra). Saldo = obtenidos − utilizados − corregidos.
"""
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce

from apps.accounts.permissions import is_owner

from .models import PointsTransaction

Kind = PointsTransaction.Kind


@dataclass(frozen=True)
class PointsSummary:
    balance: int
    earned: int
    used: int
    corrected: int


def points_summary(customer):
    totals = PointsTransaction.objects.filter(customer=customer).aggregate(
        balance=Coalesce(Sum("points"), 0),
        earned=Coalesce(Sum("points", filter=Q(points__gt=0)), 0),
        used=Coalesce(Sum("points", filter=Q(kind=Kind.REDEMPTION)), 0),
        corrected=Coalesce(Sum("points", filter=Q(points__lt=0) & ~Q(kind=Kind.REDEMPTION)), 0),
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
        .select_related("promotion", "purchase")
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
    movements = PointsTransaction.objects.all()
    if start is not None:
        movements = movements.filter(created_at__gte=start)
    if end is not None:
        movements = movements.filter(created_at__lt=end)
    period = movements.aggregate(
        issued=Coalesce(Sum("points", filter=Q(points__gt=0)), 0),
        used=Coalesce(Sum("points", filter=Q(kind=Kind.REDEMPTION)), 0),
        corrected=Coalesce(Sum("points", filter=Q(points__lt=0) & ~Q(kind=Kind.REDEMPTION)), 0),
    )
    overall = PointsTransaction.objects.aggregate(
        outstanding=Coalesce(Sum("points"), 0), customers=Count("customer", distinct=True)
    )
    return PointsStats(
        issued=period["issued"],
        used=-period["used"],
        corrected=-period["corrected"],
        outstanding=overall["outstanding"],
        customers_with_points=overall["customers"],
    )
