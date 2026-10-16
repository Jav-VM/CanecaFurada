"""
Registro de compras manuales.

Flujo (web hoy, API mañana; ambos llaman a estas funciones):

1. `identify_for_purchase(staff=..., qr_code=...)`: el personal escanea el QR y
   obtiene solo el nombre corto del cliente para confirmar que es él.
2. `register_purchase(staff=..., qr_code=..., amount=..., idempotency_key=...)`:
   registra la compra.

El servidor valida en cada paso, sin fiarse de nada que envíe el navegador:
personal autenticado y activo (empleado o propietario), origen habilitado,
importe, referencia de idempotencia, QR válido de un cliente activo con email
verificado y, si la operación ya existía, que coincida y siga vigente.

La compra se crea en una transacción con la fila del cliente bloqueada. La
referencia de idempotencia (UUID generado por el servidor al mostrar el
formulario) es única en la BD: un doble envío o un reintento devuelve la
compra ya registrada en lugar de crear otra.
"""
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils.translation import gettext as _

from apps.accounts.permissions import is_owner, is_staff_member
from apps.core import throttling
from apps.loyalty import ledger
from apps.loyalty import services as loyalty
from apps.loyalty.models import CustomerQRCode

from .models import Purchase

logger = logging.getLogger(__name__)

_FAILURE_SCOPE = "purchase_qr_failure"


class TooManyFailedAttempts(Exception):
    """Demasiados códigos no válidos seguidos para este miembro del personal."""


@dataclass(frozen=True)
class IdentifiedCustomer:
    display_name: str


@dataclass(frozen=True)
class RegistrationResult:
    purchase: Purchase
    created: bool


def ensure_can_register_purchases(staff):
    if not is_staff_member(staff):
        raise PermissionDenied(_("Solo el personal del local puede registrar compras."))


def parse_amount(value):
    """Importe en euros con hasta dos decimales, entre 0,01 y el máximo configurado."""
    if isinstance(value, float):
        value = repr(value)  # no se calcula con float: se parte de su representación en texto
    try:
        amount = Decimal(str(value).strip().replace(",", ".")) if value is not None else None
    except InvalidOperation:
        amount = None
    if amount is None or not amount.is_finite():
        raise ValidationError(_("Introduce un importe válido, por ejemplo 12,50."), code="amount_invalid")
    if amount.as_tuple().exponent < -2:
        raise ValidationError(_("El importe admite como máximo dos decimales."), code="amount_decimals")
    if amount < Decimal("0.01"):
        raise ValidationError(_("El importe debe ser mayor que cero."), code="amount_min")
    if amount > settings.PURCHASES_MAX_AMOUNT:
        raise ValidationError(
            _("El importe supera el máximo permitido (%(max)s €)."),
            code="amount_max",
            params={"max": settings.PURCHASES_MAX_AMOUNT},
        )
    return amount.quantize(Decimal("0.01"))


def parse_idempotency_key(value):
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError(_("La operación no es válida. Vuelve a escanear el código."), code="idempotency_invalid")


def _check_failures(staff):
    if throttling.is_limited(_FAILURE_SCOPE, str(staff.public_id), settings.PURCHASES_MAX_QR_FAILURES):
        raise TooManyFailedAttempts


def _register_failure(staff):
    throttling.register_attempt(_FAILURE_SCOPE, str(staff.public_id), settings.PURCHASES_QR_FAILURE_WINDOW_SECONDS)
    # Sin el código leído ni datos del cliente.
    logger.info("Código QR rechazado (personal %s)", staff.public_id)


def _identify(staff, qr_code, *, for_update=False):
    try:
        return loyalty.identify_customer(qr_code, for_update=for_update)
    except (loyalty.InvalidQRCode, loyalty.CustomerNotEligible):
        _register_failure(staff)
        raise


def identify_for_purchase(*, staff, qr_code):
    ensure_can_register_purchases(staff)
    _check_failures(staff)
    customer = _identify(staff, qr_code)
    return IdentifiedCustomer(display_name=loyalty.customer_display_name(customer))


def new_idempotency_key():
    return uuid.uuid4()


def on_purchase_registered(purchase):
    """
    Se ejecuta dentro de la misma transacción que crea la compra: genera los
    puntos y las bonificaciones de promociones en el ledger, de modo que compra
    y puntos se confirman o se deshacen juntos. Los puntos los calcula el
    servidor a partir del importe guardado; nada llega del navegador.
    """
    ledger.award_points_for_purchase(purchase)


def _current_token(customer):
    try:
        return customer.qr_code.token
    except CustomerQRCode.DoesNotExist:
        return None


def _replay(existing, *, staff, qr_code, amount, source):
    token = loyalty.normalize_code(qr_code)
    same_customer = token is not None and token == _current_token(existing.customer)
    if not (
        existing.registered_by_id == staff.pk
        and existing.amount == amount
        and existing.source == source
        and same_customer
    ):
        raise ValidationError(
            _("Esta operación ya se registró con otros datos. Vuelve a escanear el código."),
            code="idempotency_conflict",
        )
    if existing.status != Purchase.Status.COMPLETED:
        raise ValidationError(_("Esta operación ya no está vigente."), code="operation_not_completed")
    return RegistrationResult(purchase=existing, created=False)


def register_purchase(*, staff, qr_code, amount, idempotency_key, source=Purchase.Source.MANUAL):
    ensure_can_register_purchases(staff)
    if source not in settings.PURCHASES_ENABLED_SOURCES:
        raise ValidationError(_("Este origen de compras no está habilitado."), code="source_disabled")
    amount = parse_amount(amount)
    key = parse_idempotency_key(idempotency_key)
    _check_failures(staff)

    with transaction.atomic():
        existing = (
            Purchase.objects.select_for_update().select_related("customer").filter(idempotency_key=key).first()
        )
        if existing is not None:
            return _replay(existing, staff=staff, qr_code=qr_code, amount=amount, source=source)

        # Se vuelve a comprobar el QR y el estado del cliente dentro de la transacción.
        customer = _identify(staff, qr_code, for_update=True)
        try:
            with transaction.atomic():
                purchase = Purchase.objects.create(
                    customer=customer,
                    registered_by=staff,
                    amount=amount,
                    source=source,
                    idempotency_key=key,
                )
        except IntegrityError:
            # Otra petición con la misma referencia ganó la carrera.
            existing = Purchase.objects.select_related("customer").filter(idempotency_key=key).first()
            if existing is None:
                raise
            return _replay(existing, staff=staff, qr_code=qr_code, amount=amount, source=source)

        on_purchase_registered(purchase)

    logger.info("Compra registrada %s (origen %s, personal %s)", purchase.public_id, source, staff.public_id)
    return RegistrationResult(purchase=purchase, created=True)


# --- Lectura -------------------------------------------------------------------


def visible_purchases(user):
    """El propietario ve todas; un empleado, solo las que registró él."""
    if is_owner(user):
        return Purchase.objects.all()
    if is_staff_member(user):
        return Purchase.objects.filter(registered_by=user)
    return Purchase.objects.none()


def recent_purchases_by(staff, limit=10):
    return list(Purchase.objects.filter(registered_by=staff).select_related("customer")[:limit])
