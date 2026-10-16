"""
Caducidad de los puntos (Fase 14): política vigente y cálculo FIFO.

Reglas:
- La política (`PointsExpiryPolicy`) está versionada: la vigente es la última
  en vigor. Sin política, o con `months` vacío, los puntos no caducan.
- Cada **crédito** (movimiento positivo: compra, promoción, cumpleaños, ajuste
  a favor) caduca en `max(created_at, counts_from) + months`. `counts_from` lo
  fija `set_policy`: al activar la caducidad o acortar el plazo es "ahora", de
  modo que nadie pierde puntos de golpe; al alargarlo (o cambiar solo los días
  de aviso) se conserva, porque las fechas solo se retrasan.
- Los **débitos** (canjes, ajustes en contra, compensaciones, caducidades) se
  consumen de los créditos más antiguos primero (FIFO).
- Un movimiento y su compensación (`REVERSAL`) se anulan y no cuentan: una
  compra compensada no deja puntos y un canje cancelado devuelve los puntos
  con su fecha de caducidad original.
- Puntos que caducan en `at` = créditos vencidos en `at` − débitos, si es
  positivo. Lo ya caducado es un débito más, así que repetir el cálculo da 0:
  la caducidad es idempotente y nunca supera el saldo.

Aquí no se escribe en el ledger: `ledger.expire_points` aplica el resultado
con el cliente bloqueado y `expirations.py` recorre los clientes.
"""
import calendar
import datetime
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.permissions import is_owner
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event

from .models import PointsExpiryPolicy, PointsTransaction

Kind = PointsTransaction.Kind
# Campos que necesita el cálculo: los movimientos se leen sin el resto.
MOVEMENT_FIELDS = ("id", "kind", "points", "created_at", "reverses_id")


def add_months(value, months):
    """`value` + `months` meses; el día se recorta al último del mes (31/01 + 1 = 28/02 o 29/02)."""
    month_index = value.month - 1 + months
    year, month = value.year + month_index // 12, month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


# --- Política -------------------------------------------------------------------------


def current_policy(at=None):
    """Última versión en vigor (con o sin caducidad), o `None` si nunca se ha configurado."""
    at = at or timezone.now()
    return PointsExpiryPolicy.objects.filter(valid_from__lte=at).order_by("-valid_from", "-id").first()


def active_policy(at=None):
    """La política vigente si los puntos caducan; `None` si no caducan."""
    policy = current_policy(at)
    return policy if policy is not None and policy.months is not None else None


def policy_history(limit=10):
    return list(PointsExpiryPolicy.objects.select_related("created_by").order_by("-valid_from", "-id")[:limit])


def _parse_int(value, field, minimum, maximum, message):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValidationError({field: message})
    return value


@transaction.atomic
def set_policy(*, actor, months, warn_days=PointsExpiryPolicy.DEFAULT_WARN_DAYS, note=""):
    """
    Nueva versión de la caducidad (solo propietario). `months=None` la quita.
    Devuelve `(política, creada)`; sin cambios no se crea otra versión.
    No modifica movimientos: se aplican en la siguiente ejecución de `expire_points`.
    """
    if not is_owner(actor):
        raise PermissionDenied(_("Solo el propietario puede cambiar la caducidad de los puntos."))
    if months is not None:
        months = _parse_int(
            months, "months", 1, PointsExpiryPolicy.MAX_MONTHS,
            _("Indica entre 1 y %(MAX_MONTHS)s meses.") % {"MAX_MONTHS": PointsExpiryPolicy.MAX_MONTHS},
        )
    warn_days = _parse_int(
        warn_days, "warn_days", 1, PointsExpiryPolicy.MAX_WARN_DAYS,
        _("Indica entre 1 y %(MAX_WARN_DAYS)s días.") % {"MAX_WARN_DAYS": PointsExpiryPolicy.MAX_WARN_DAYS},
    )
    now = timezone.now()
    # Bloquea la versión vigente: dos cambios simultáneos se aplican uno tras otro.
    previous = PointsExpiryPolicy.objects.select_for_update().filter(valid_from__lte=now).order_by("-valid_from", "-id").first()
    previous_months = previous.months if previous else None
    if previous_months == months and (months is None or previous.warn_days == warn_days):
        return previous, False
    if months is None:
        counts_from = None
    elif previous_months is not None and months >= previous_months:
        # Alargar el plazo o cambiar el aviso: ninguna fecha se adelanta.
        counts_from = previous.counts_from
    else:
        # Activar o acortar: el nuevo plazo empieza a contar ahora.
        counts_from = now
    policy = PointsExpiryPolicy(
        months=months,
        warn_days=warn_days,
        counts_from=counts_from,
        valid_from=now,
        note=(note or "").strip(),
        created_by=actor,
    )
    policy.full_clean()
    policy.save()
    # Sin el motivo: es texto libre.
    record_audit_event(
        action=AuditEvent.Action.POINTS_EXPIRY_POLICY_CREATED,
        actor=actor,
        target=policy,
        metadata={
            "months": months,
            "warn_days": warn_days,
            "previous_months": previous_months,
            "counts_from": counts_from.isoformat() if counts_from else None,
        },
    )
    return policy, True


# --- Cálculo FIFO ---------------------------------------------------------------------


@dataclass(frozen=True)
class Lot:
    """Puntos de un crédito que siguen sin consumir y cuándo caducan."""

    expires_at: datetime.datetime
    points: int


def customer_movements(customer):
    return list(PointsTransaction.objects.filter(customer=customer).only(*MOVEMENT_FIELDS).order_by("created_at", "id"))


def _effective(movements):
    """Quita cada compensación y el movimiento compensado: entre los dos suman cero."""
    present = {m.pk for m in movements}
    reversals = {m.pk: m.reverses_id for m in movements if m.kind == Kind.REVERSAL and m.reverses_id in present}
    cancelled = set(reversals) | set(reversals.values())
    return [m for m in movements if m.pk not in cancelled]


def remaining_lots(movements, policy):
    """
    Créditos con puntos sin consumir, del que caduca antes al que caduca
    después. Sin política activa, lista vacía (nada caduca).
    """
    if policy is None or policy.months is None:
        return []
    effective = _effective(movements)
    debits = -sum(m.points for m in effective if m.points < 0)
    lots = []
    for movement in sorted((m for m in effective if m.points > 0), key=lambda m: (m.created_at, m.pk)):
        consumed = min(debits, movement.points)
        debits -= consumed
        if movement.points > consumed:
            start = max(movement.created_at, policy.counts_from)
            lots.append(Lot(expires_at=add_months(start, policy.months), points=movement.points - consumed))
    return lots


def expirable_points(movements, policy, at):
    """Puntos que deberían haber caducado en `at` y aún no se han descontado."""
    return sum(lot.points for lot in remaining_lots(movements, policy) if lot.expires_at <= at)


@dataclass(frozen=True)
class UpcomingExpiry:
    expires_at: datetime.datetime
    points: int

    @property
    def date(self):
        return timezone.localdate(self.expires_at)


def next_expiry(movements, policy):
    """
    Próximo vencimiento: fecha del primer lote sin consumir y puntos que
    caducan ese mismo día (hora local). `None` si no caduca nada.
    """
    lots = remaining_lots(movements, policy)
    if not lots:
        return None
    first_day = timezone.localdate(lots[0].expires_at)
    points = sum(lot.points for lot in lots if timezone.localdate(lot.expires_at) == first_day)
    return UpcomingExpiry(expires_at=lots[0].expires_at, points=points)


def customer_next_expiry(customer, at=None):
    """Próximo vencimiento del cliente según la política vigente (para «Mis puntos»)."""
    policy = active_policy(at)
    if policy is None:
        return None
    return next_expiry(customer_movements(customer), policy)


def credits_cutoff(policy, until):
    """
    Fecha límite de creación de los créditos que pueden haber vencido en
    `until`, con un día de margen por el recorte de fin de mes. Sirve para
    preseleccionar clientes en SQL; el cálculo exacto lo hace `remaining_lots`.
    `None` si con esta política nada puede vencer todavía.
    """
    if add_months(policy.counts_from, policy.months) > until:
        return None
    return add_months(until, -policy.months) + datetime.timedelta(days=1)
