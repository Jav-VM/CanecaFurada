"""
Consultas de compras (solo lectura) para la web y la futura API.

**Compras registradas ≠ facturación.** Una compra registrada es lo que el
personal anotó al escanear el QR de un cliente del programa. No incluye las
ventas a quien no enseña su QR ni las que no se anotaron, así que no equivale a
la facturación total del local. El sistema no conoce esa cifra (no hay
integración con la caja ni el TPV) y nunca la estima a partir de las compras.
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce

from apps.accounts.permissions import is_owner
from apps.core.querysets import period_q

from .models import Purchase

REGISTERED_PURCHASES_LABEL = "Compras registradas en el programa de fidelización"
NOT_REVENUE_NOTE = (
    "Solo incluye las compras que el personal registró con el QR de un cliente. "
    "No es la facturación total del local."
)


def customer_purchases(customer):
    """Historial de compras del cliente con los puntos que generó cada una."""
    return (
        Purchase.objects.filter(customer=customer)
        .annotate(points=Coalesce(Sum("points_transactions__points"), 0))
        .order_by("-created_at", "-id")
    )


@dataclass(frozen=True)
class RegisteredPurchasesStats:
    purchases_count: int
    customers_count: int
    registered_amount: Decimal
    average_amount: Decimal | None
    label: str = REGISTERED_PURCHASES_LABEL
    note: str = NOT_REVENUE_NOTE
    # Siempre `None`: la facturación total no se conoce (sin caja/TPV integrados).
    business_revenue: Decimal | None = None


def registered_purchases_stats(*, actor, start=None, end=None):
    """Totales de compras registradas vigentes (no anuladas) en `[start, end)`. Solo propietario."""
    if not is_owner(actor):
        raise PermissionDenied("Solo el propietario puede ver las estadísticas.")
    purchases = Purchase.objects.filter(period_q("created_at", start, end), status=Purchase.Status.COMPLETED)
    totals = purchases.aggregate(
        count=Count("id"),
        customers=Count("customer", distinct=True),
        amount=Coalesce(Sum("amount"), Decimal("0.00")),
    )
    count = totals["count"]
    amount = Decimal(totals["amount"]).quantize(Decimal("0.01"))
    average = (amount / count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if count else None
    return RegisteredPurchasesStats(
        purchases_count=count,
        customers_count=totals["customers"],
        registered_amount=amount,
        average_amount=average,
    )


def purchases_registered_by(staff, *, since=None):
    """
    Compras que registró `staff` (panel del personal, Fase 8), con sus puntos.

    Solo las propias, también para el propietario: la vista global de compras
    es del dashboard (Fase 9). Carga el cliente para mostrar su nombre abreviado.
    """
    queryset = Purchase.objects.filter(registered_by=staff)
    if since is not None:
        queryset = queryset.filter(created_at__gte=since)
    return (
        queryset.select_related("customer")
        .annotate(points=Coalesce(Sum("points_transactions__points"), 0))
        .order_by("-created_at", "-id")
    )


def staff_purchases_summary(staff, *, since):
    """Número e importe de las compras vigentes (no anuladas) que registró `staff` desde `since`."""
    totals = Purchase.objects.filter(
        registered_by=staff, status=Purchase.Status.COMPLETED, created_at__gte=since
    ).aggregate(count=Count("id"), amount=Coalesce(Sum("amount"), Decimal("0.00")))
    return totals["count"], Decimal(totals["amount"]).quantize(Decimal("0.01"))


# --- Dashboard del propietario (Fase 9) ---------------------------------------------


def _require_owner(actor):
    if not is_owner(actor):
        raise PermissionDenied("Solo el propietario puede ver todas las compras.")


def all_purchases(*, actor, start=None, end=None, registered_by=None, status=None):
    """Todas las compras registradas (solo propietario), con sus puntos, cliente y empleado."""
    _require_owner(actor)
    queryset = Purchase.objects.filter(period_q("created_at", start, end))
    if registered_by is not None:
        queryset = queryset.filter(registered_by=registered_by)
    if status:
        queryset = queryset.filter(status=status)
    return (
        queryset.select_related("customer", "registered_by")
        .only(
            "public_id", "amount", "created_at", "status", "source",
            "customer__public_id", "customer__first_name", "customer__last_name",
            "registered_by__first_name", "registered_by__last_name",
        )
        .annotate(points=Coalesce(Sum("points_transactions__points"), 0))
        .order_by("-created_at", "-id")
    )


def purchases_by_staff(*, actor, start=None, end=None):
    """Número e importe de compras vigentes por miembro del personal en el periodo."""
    _require_owner(actor)
    queryset = Purchase.objects.filter(period_q("created_at", start, end), status=Purchase.Status.COMPLETED)
    rows = (
        queryset.values("registered_by")
        .annotate(count=Count("id"), amount=Coalesce(Sum("amount"), Decimal("0.00")))
        .order_by()
    )
    return {row["registered_by"]: (row["count"], Decimal(row["amount"]).quantize(Decimal("0.01"))) for row in rows}


def customer_ids_with_purchases(*, actor, start=None, end=None):
    """Clientes con al menos una compra vigente en el periodo (para filtrar estadísticas)."""
    _require_owner(actor)
    queryset = Purchase.objects.filter(period_q("created_at", start, end), status=Purchase.Status.COMPLETED)
    return queryset.values("customer").distinct()
