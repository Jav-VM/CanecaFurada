"""
Ledger de puntos: única vía para escribir movimientos.

- `award_points_for_purchase(purchase)`: puntos de una compra y bonificaciones
  de promociones. La llama `purchases.services.on_purchase_registered` dentro
  de la transacción que crea la compra: compra y puntos se confirman o se
  deshacen juntos.
- `adjust_points(...)`: ajuste manual del propietario (positivo o negativo)
  con motivo y referencia de idempotencia.
- `reverse_movement(...)`: movimiento compensatorio de otro (p. ej. una compra
  anulada en el futuro). Nunca se editan ni se borran movimientos.
- `spend_points(...)` / `refund_spent_points(...)`: descuento de un canje y su
  devolución si se cancela o caduca (Fase 7, desde `apps.rewards.services`).
- `grant_birthday_gift(...)`: regalo de cumpleaños sin compra (Fase 10, desde
  `birthdays.run_birthday_promotions`).
- `expire_points(...)`: descuenta los puntos vencidos según la política de
  caducidad (Fase 14, desde `expirations.run_expirations`).

Concurrencia: cada escritura bloquea la fila del cliente (`select_for_update`)
y recalcula el saldo dentro de la transacción, de modo que dos operaciones
simultáneas del mismo cliente se serializan y el saldo nunca queda negativo
(también hay un `CHECK` en la BD). Los duplicados los impiden las
restricciones únicas del modelo (una acumulación por compra, una bonificación
por promoción y compra, un cumpleaños por cliente y año, idempotencia única).
"""
import logging
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from apps.accounts.models import User
from apps.accounts.permissions import is_owner
from apps.core.i18n import site_text
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event

from . import conversion, expiry, promotions
from .models import PointsTransaction, Promotion

logger = logging.getLogger(__name__)

Kind = PointsTransaction.Kind


class InsufficientPoints(ValidationError):
    def __init__(self):
        super().__init__(_("El cliente no tiene puntos suficientes para esta operación."), code="insufficient_points")


@dataclass(frozen=True)
class MovementResult:
    movement: PointsTransaction
    created: bool


def balance(customer):
    """Saldo actual: suma de todos los movimientos del cliente."""
    return PointsTransaction.objects.filter(customer=customer).aggregate(total=Sum("points"))["total"] or 0


def _lock_customer(customer):
    return User.objects.select_for_update().get(pk=customer.pk)


def _append(customer, **fields):
    """Añade un movimiento con el saldo resultante. El cliente debe estar bloqueado."""
    new_balance = balance(customer) + fields["points"]
    if new_balance < 0:
        raise InsufficientPoints()
    return PointsTransaction.objects.create(customer=customer, balance_after=new_balance, **fields)


def award_points_for_purchase(purchase):
    """
    Movimientos de una compra registrada: los puntos base según la conversión
    vigente en el momento de la compra y las bonificaciones de promociones.
    Idempotente: si la compra ya tiene sus movimientos, los devuelve.
    """
    with transaction.atomic():
        if purchase.status != purchase.Status.COMPLETED:
            return []
        customer = _lock_customer(purchase.customer)
        if customer.role != User.Role.CUSTOMER:
            return []
        existing = list(
            PointsTransaction.objects.filter(
                purchase=purchase, kind__in=[Kind.EARN_PURCHASE, Kind.PROMOTION_BONUS]
            ).order_by("id")
        )
        if existing:
            return existing

        rate = conversion.current_rate(purchase.created_at)
        base_points = conversion.calculate_points(purchase.amount, rate.points_per_euro)
        movements = []
        if base_points > 0:
            movements.append(
                _append(
                    customer,
                    kind=Kind.EARN_PURCHASE,
                    points=base_points,
                    purchase=purchase,
                    rule=rate.rule,
                    base_amount=purchase.amount,
                    points_per_euro=rate.points_per_euro,
                    created_by=purchase.registered_by,
                )
            )
        purchase.customer = customer
        for bonus in promotions.bonuses_for_purchase(purchase, base_points=base_points):
            movements.append(
                _append(
                    customer,
                    kind=Kind.PROMOTION_BONUS,
                    points=bonus.points,
                    purchase=purchase,
                    promotion=bonus.promotion,
                    birthday_year=bonus.birthday_year,
                    base_amount=purchase.amount,
                    created_by=purchase.registered_by,
                )
            )
    if movements:
        logger.info(
            "Puntos de la compra %s: %s movimiento(s), %s puntos",
            purchase.public_id,
            len(movements),
            sum(m.points for m in movements),
        )
    return movements


# --- Operaciones administrativas ----------------------------------------------------


def _require_owner(actor):
    if not is_owner(actor):
        raise PermissionDenied(_("Solo el propietario puede corregir puntos."))


def _parse_reason(reason):
    reason = (reason or "").strip() if isinstance(reason, str) else ""
    if not reason:
        raise ValidationError({"reason": _("Indica el motivo.")})
    if len(reason) > 200:
        raise ValidationError({"reason": _("El motivo admite como máximo 200 caracteres.")})
    return reason


def _parse_adjustment(points):
    if isinstance(points, bool):
        points = None
    elif isinstance(points, str):
        points = points.strip()
        points = int(points) if points.lstrip("+-").isdigit() else None
    elif not isinstance(points, int):
        points = None
    if not points:
        raise ValidationError({"points": _("Indica un número entero de puntos distinto de cero.")})
    if abs(points) > settings.LOYALTY_MAX_ADJUSTMENT_POINTS:
        raise ValidationError(
            {"points": _("El ajuste no puede superar %(LOYALTY_MAX_ADJUSTMENT_POINTS)s puntos.") % {"LOYALTY_MAX_ADJUSTMENT_POINTS": settings.LOYALTY_MAX_ADJUSTMENT_POINTS}}
        )
    return points


def _parse_key(value):
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError(_("La operación no es válida. Vuelve a intentarlo."), code="idempotency_invalid")


def _replay_adjustment(existing, customer, points):
    if existing.kind != Kind.ADJUSTMENT or existing.customer_id != customer.pk or existing.points != points:
        raise ValidationError(_("Esta operación ya se registró con otros datos."), code="idempotency_conflict")
    return MovementResult(movement=existing, created=False)


def adjust_points(*, actor, customer, points, reason, idempotency_key):
    """
    Ajuste manual (solo propietario). Positivo o negativo; no puede dejar el
    saldo en negativo. Un reintento con la misma referencia no duplica.
    """
    _require_owner(actor)
    points = _parse_adjustment(points)
    reason = _parse_reason(reason)
    key = _parse_key(idempotency_key)
    with transaction.atomic():
        existing = PointsTransaction.objects.select_for_update().filter(idempotency_key=key).first()
        if existing is not None:
            return _replay_adjustment(existing, customer, points)
        customer = _lock_customer(customer)
        if customer.role != User.Role.CUSTOMER:
            raise ValidationError(_("Solo los clientes tienen puntos."), code="not_customer")
        try:
            with transaction.atomic():
                movement = _append(
                    customer,
                    kind=Kind.ADJUSTMENT,
                    points=points,
                    created_by=actor,
                    reason=reason,
                    idempotency_key=key,
                )
        except IntegrityError:
            existing = PointsTransaction.objects.filter(idempotency_key=key).first()
            if existing is None:
                raise
            return _replay_adjustment(existing, customer, points)
        # Sin el motivo: es texto libre y podría contener datos personales.
        record_audit_event(
            action=AuditEvent.Action.POINTS_ADJUSTED,
            actor=actor,
            target=customer,
            metadata={"points": points, "movement": str(movement.public_id)},
        )
    return MovementResult(movement=movement, created=True)


def _compensate(movement, *, actor, reason):
    """Movimiento de signo contrario a `movement`, una sola vez (`OneToOne` en BD)."""
    original = PointsTransaction.objects.select_for_update().get(pk=movement.pk)
    if original.kind == Kind.REVERSAL:
        raise ValidationError(_("Una compensación no se compensa: registra un ajuste."), code="reversal_of_reversal")
    existing = PointsTransaction.objects.filter(reverses=original).first()
    if existing is not None:
        return MovementResult(movement=existing, created=False)
    customer = _lock_customer(original.customer)
    try:
        with transaction.atomic():
            reversal = _append(
                customer,
                kind=Kind.REVERSAL,
                points=-original.points,
                reverses=original,
                created_by=actor,
                reason=reason,
            )
    except IntegrityError:
        existing = PointsTransaction.objects.filter(reverses=original).first()
        if existing is None:
            raise
        return MovementResult(movement=existing, created=False)
    return MovementResult(movement=reversal, created=True)


def reverse_movement(*, actor, movement, reason):
    """
    Compensa un movimiento con otro de signo contrario (solo propietario).
    Idempotente: un movimiento solo se compensa una vez (`OneToOne` en BD).
    """
    _require_owner(actor)
    reason = _parse_reason(reason)
    if movement.kind == Kind.REDEMPTION:
        # Devolverlo aquí dejaría el canje pendiente o usado con los puntos
        # devueltos: los canjes se devuelven cancelándolos o al caducar.
        raise ValidationError(
            _("Los puntos de un canje se devuelven cancelando el canje, no compensando el movimiento."),
            code="redemption_reversal",
        )
    if movement.kind == Kind.EXPIRATION:
        # Compensarla dejaría esos puntos "sin consumir" y volverían a caducar en
        # la siguiente ejecución: los puntos caducados se devuelven con un ajuste.
        raise ValidationError(
            _("Los puntos caducados no se compensan: devuélvelos con un ajuste manual a favor."),
            code="expiration_reversal",
        )
    with transaction.atomic():
        result = _compensate(movement, actor=actor, reason=reason)
        if not result.created:
            return result
        reversal, customer = result.movement, result.movement.customer
        original = reversal.reverses
        record_audit_event(
            action=AuditEvent.Action.POINTS_REVERSED,
            actor=actor,
            target=customer,
            metadata={"points": reversal.points, "movement": str(reversal.public_id), "reverses": str(original.public_id)},
        )
    return MovementResult(movement=reversal, created=True)


# --- Canjes (Fase 7) ------------------------------------------------------------------
#
# Los usa `apps.rewards.services`, que comprueba antes los permisos y las reglas
# del canje. Deben llamarse dentro de su transacción, con el cliente ya bloqueado
# por `lock_customer`, para que el canje y el movimiento se confirmen juntos.


def lock_customer(customer):
    """Bloquea la fila del cliente hasta el final de la transacción en curso."""
    return _lock_customer(customer)


def spend_points(*, customer, points, reason):
    """
    Descuenta `points` (> 0) con un movimiento `REDEMPTION`. Lanza
    `InsufficientPoints` si el saldo, recalculado dentro de la transacción, no
    alcanza. `customer` debe venir de `lock_customer`.
    """
    if isinstance(points, bool) or not isinstance(points, int) or points <= 0:
        raise ValueError("Los puntos de un canje deben ser un entero positivo.")
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("spend_points debe llamarse dentro de una transacción.")
    return _append(customer, kind=Kind.REDEMPTION, points=-points, reason=reason)


def refund_spent_points(*, movement, actor=None, reason):
    """
    Devuelve los puntos de un movimiento `REDEMPTION` (canje cancelado o
    caducado) con una compensación. `actor` es `None` cuando lo hace el sistema.
    Idempotente: un canje solo se devuelve una vez.
    """
    if movement.kind != Kind.REDEMPTION:
        raise ValueError("Solo se devuelven movimientos de canje.")
    with transaction.atomic():
        return _compensate(movement, actor=actor, reason=reason)


# --- Cumpleaños (Fase 10) --------------------------------------------------------------


def grant_birthday_gift(*, customer, promotion, day, at=None):
    """
    Regala los puntos fijos de `promotion` (de cumpleaños) a `customer` por su
    cumpleaños del día `day`. Devuelve el movimiento creado o `None` si no le
    corresponde: cliente no activo o sin email verificado, promoción no
    vigente o agotada, anti-abuso de la fecha (`promotions.birthday_year_for`)
    o regalo de ese año ya concedido.

    Todo se comprueba con el cliente y la promoción bloqueados. Aunque dos
    ejecuciones coincidan, la restricción única (cliente, año) impide un
    segundo regalo.
    """
    at = at or timezone.now()
    with transaction.atomic():
        customer = _lock_customer(customer)
        if not (customer.role == User.Role.CUSTOMER and customer.is_active and customer.is_email_verified):
            return None
        promo = Promotion.objects.select_for_update().get(pk=promotion.pk)
        if not (
            promo.kind == Promotion.Kind.BIRTHDAY
            and promo.bonus_type == Promotion.BonusType.FIXED_POINTS
            and promotions.active_promotions(at).filter(pk=promo.pk).exists()
        ):
            return None
        if promo.max_total_uses is not None:
            uses = PointsTransaction.objects.filter(promotion=promo, kind=Kind.BIRTHDAY_GIFT).count()
            if uses >= promo.max_total_uses:
                return None
        year = promotions.birthday_year_for(customer, at, 0, day=day)
        if year is None:
            return None
        try:
            with transaction.atomic():
                movement = _append(
                    customer,
                    kind=Kind.BIRTHDAY_GIFT,
                    points=promo.fixed_points,
                    promotion=promo,
                    birthday_year=year,
                    reason=site_text(gettext_lazy("Regalo de cumpleaños %(year)s"), year=year),
                )
        except IntegrityError:
            # Otra ejecución lo concedió a la vez.
            return None
    logger.info("Regalo de cumpleaños %s: %s puntos", movement.public_id, movement.points)
    return movement


# --- Caducidad (Fase 14) ---------------------------------------------------------------


def expire_points(*, customer, policy, at=None):
    """
    Descuenta con un movimiento `EXPIRATION` los puntos de `customer` vencidos
    en `at` según `policy` (FIFO, `expiry.expirable_points`). Devuelve el
    movimiento o `None` si no caduca nada.

    Se calcula con el cliente bloqueado, así que una compra o un canje
    simultáneos se serializan con la caducidad. Idempotente: lo caducado
    cuenta como consumido y una segunda ejecución no descuenta nada.
    """
    at = at or timezone.now()
    with transaction.atomic():
        customer = _lock_customer(customer)
        points = expiry.expirable_points(expiry.customer_movements(customer), policy, at)
        if points <= 0:
            return None
        movement = _append(customer, kind=Kind.EXPIRATION, points=-points, reason=site_text(gettext_lazy("Puntos caducados")))
    logger.info("Caducidad %s: %s puntos", movement.public_id, movement.points)
    return movement
