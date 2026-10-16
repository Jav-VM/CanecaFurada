"""
Conversión de importes a puntos.

Reglas:
- Los puntos se calculan **solo en el servidor** a partir del importe de la
  compra guardado en la BD; nunca se aceptan puntos enviados por un cliente.
- Importes y tasas son `Decimal`; nunca se calcula con `float`.
- **Redondeo:** el resultado se trunca hacia abajo a puntos enteros
  (`ROUND_DOWN`). 12,50 € × 1 punto/€ = 12 puntos; 0,99 € = 0 puntos.
- La tasa vigente es la última `LoyaltyRule` en vigor; sin reglas se usa
  `LOYALTY_DEFAULT_POINTS_PER_EURO`. Las reglas no se editan: se añade otra.
"""
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.permissions import is_owner
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event

from .models import LoyaltyRule

POINTS_ROUNDING = ROUND_DOWN


@dataclass(frozen=True)
class Rate:
    points_per_euro: Decimal
    rule: LoyaltyRule | None


def round_points(value):
    """Decimal → puntos enteros, truncando hacia abajo."""
    if not isinstance(value, Decimal) or not value.is_finite():
        raise TypeError("Los puntos se calculan con Decimal finitos.")
    return int(value.to_integral_value(rounding=POINTS_ROUNDING))


def calculate_points(amount, points_per_euro):
    if not isinstance(amount, Decimal) or not isinstance(points_per_euro, Decimal):
        raise TypeError("Importe y tasa deben ser Decimal.")
    if amount < 0 or points_per_euro < 0:
        raise ValueError("Importe y tasa no pueden ser negativos.")
    return round_points(amount * points_per_euro)


def current_rule(at=None):
    at = at or timezone.now()
    return LoyaltyRule.objects.filter(valid_from__lte=at).order_by("-valid_from", "-id").first()


def rule_history(limit=10):
    """Últimas reglas de conversión, de la más reciente a la más antigua."""
    return list(LoyaltyRule.objects.select_related("created_by").order_by("-valid_from", "-id")[:limit])


def current_rate(at=None):
    rule = current_rule(at)
    if rule is not None:
        return Rate(points_per_euro=rule.points_per_euro, rule=rule)
    return Rate(points_per_euro=Decimal(settings.LOYALTY_DEFAULT_POINTS_PER_EURO), rule=None)


def _parse_rate(value):
    if isinstance(value, float):
        value = repr(value)
    try:
        rate = Decimal(str(value).strip().replace(",", ".")) if value is not None else None
    except InvalidOperation:
        rate = None
    if rate is None or not rate.is_finite():
        raise ValidationError({"points_per_euro": _("Introduce un número válido, por ejemplo 1,00.")})
    return rate


@transaction.atomic
def create_rule(*, actor, points_per_euro, valid_from=None, note=""):
    """Nueva conversión (solo propietario). No modifica reglas anteriores ni puntos concedidos."""
    if not is_owner(actor):
        raise PermissionDenied(_("Solo el propietario puede cambiar la conversión de puntos."))
    rule = LoyaltyRule(
        points_per_euro=_parse_rate(points_per_euro),
        valid_from=valid_from or timezone.now(),
        note=(note or "").strip(),
        created_by=actor,
    )
    rule.full_clean()
    rule.save()
    record_audit_event(
        action=AuditEvent.Action.LOYALTY_RULE_CREATED,
        actor=actor,
        target=rule,
        metadata={"points_per_euro": str(rule.points_per_euro), "valid_from": rule.valid_from.isoformat()},
    )
    return rule
