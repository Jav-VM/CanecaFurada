"""
Canjes de recompensas.

Flujo (web hoy, API mañana; ambos llaman a estas funciones):

1. `request_redemption(customer=..., reward=..., idempotency_key=...)`: el
   cliente pide una recompensa. En una transacción, con el cliente y la
   recompensa bloqueados, se vuelve a comprobar todo (cliente activo y
   verificado, recompensa activa, fechas, unidades, saldo y que no tenga ya un
   código pendiente de esa recompensa), se descuentan los puntos en el ledger,
   se resta una unidad y se crea el canje con un código de un solo uso.
2. `lookup_redemption(staff=..., code=...)`: el personal lee el código y ve la
   recompensa, el estado y el nombre corto del cliente. No lo valida.
3. `validate_redemption(staff=..., code=...)`: el personal entrega la
   recompensa. El paso de pendiente a canjeado es un `UPDATE ... WHERE
   status = 'PENDING'`: de dos validaciones simultáneas solo una cambia la fila.
4. `cancel_redemption(...)` (cliente) y `expire_pending_redemptions()` (comando
   `expire_redemptions`): cierran un canje pendiente y devuelven los puntos con
   un movimiento compensatorio y la unidad a la recompensa.

Orden de bloqueo, siempre el mismo para evitar interbloqueos: cliente ->
recompensa -> canje.

Los errores son `ValidationError` con `code` y `PermissionDenied`, que la web
traduce a mensajes y la futura API a 400/403/409.
"""
import datetime
import logging
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.permissions import is_owner, is_staff_member
from apps.core import throttling
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event
from apps.loyalty import ledger
from apps.loyalty import services as loyalty

from . import codes
from .models import Redemption, Reward

logger = logging.getLogger(__name__)

Status = Redemption.Status
_FAILURE_SCOPE = "redemption_code_failure"


# --- Errores --------------------------------------------------------------------


class RewardNotAvailable(ValidationError):
    def __init__(self):
        super().__init__("Esta recompensa no está disponible ahora mismo.", code="reward_unavailable")


class RewardOutOfStock(ValidationError):
    def __init__(self):
        super().__init__("Esta recompensa se ha agotado.", code="out_of_stock")


class PendingRedemptionExists(ValidationError):
    def __init__(self):
        super().__init__(
            "Ya tienes un código pendiente de recoger para esta recompensa. Úsalo o cancélalo antes de pedir otro.",
            code="duplicate_pending",
        )


class InvalidRedemptionCode(ValidationError):
    def __init__(self):
        super().__init__("El código no es válido.", code="invalid_code")


class RedemptionAlreadyUsed(ValidationError):
    def __init__(self, used_at):
        when = timezone.localtime(used_at).strftime("%d/%m/%Y %H:%M")
        super().__init__(f"Este código ya se utilizó el {when}. No se puede volver a usar.", code="code_used")


class RedemptionExpired(ValidationError):
    def __init__(self):
        super().__init__("Este código ha caducado. Los puntos se han devuelto al cliente.", code="code_expired")


class RedemptionNotPending(ValidationError):
    def __init__(self):
        super().__init__("Este canje ya no está pendiente.", code="code_not_pending")


class TooManyFailedAttempts(Exception):
    """Demasiados códigos no válidos seguidos para este miembro del personal."""


@dataclass(frozen=True)
class RedemptionResult:
    redemption: Redemption
    created: bool


@dataclass(frozen=True)
class RedemptionPreview:
    """Lo que ve el personal al leer un código: sin email, teléfono ni saldo del cliente."""

    customer_name: str
    reward_name: str
    points_cost: int
    status: str
    status_display: str
    created_at: datetime.datetime
    expires_at: datetime.datetime
    validated_at: datetime.datetime | None

    @property
    def can_validate(self):
        return self.status == Status.PENDING


# --- Comprobaciones -------------------------------------------------------------


def _is_eligible_customer(user):
    return bool(
        getattr(user, "is_authenticated", False)
        and user.is_active
        and user.role == User.Role.CUSTOMER
        and user.is_email_verified
    )


def ensure_can_redeem(user):
    if not _is_eligible_customer(user):
        raise PermissionDenied("Solo los clientes con el email verificado pueden canjear puntos.")


def ensure_can_validate(staff):
    if not is_staff_member(staff):
        raise PermissionDenied("Solo el personal del local puede validar canjes.")


def parse_idempotency_key(value):
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError("La operación no es válida. Vuelve a intentarlo.", code="idempotency_invalid")


def new_idempotency_key():
    return uuid.uuid4()


# --- Solicitud (cliente) ----------------------------------------------------------


def _new_code():
    # Con ~59 bits una colisión es prácticamente imposible; si ocurriera entre
    # esta comprobación y el INSERT, la restricción única la rechaza.
    while True:
        code = codes.generate_code()
        if not Redemption.objects.filter(code=code).exists():
            return code


def _replay(existing, customer, reward):
    if existing.customer_id != customer.pk or existing.reward_id != reward.pk:
        raise ValidationError("Esta operación ya se registró con otros datos.", code="idempotency_conflict")
    return RedemptionResult(redemption=existing, created=False)


def _create_redemption(customer, reward, key, now):
    with transaction.atomic():
        existing = Redemption.objects.select_for_update().filter(idempotency_key=key).first()
        if existing is not None:
            return _replay(existing, customer, reward)

        # Todo se vuelve a comprobar con las filas bloqueadas.
        customer = ledger.lock_customer(customer)
        ensure_can_redeem(customer)
        reward = Reward.objects.select_for_update().get(pk=reward.pk)
        if not (reward.status == Reward.Status.ACTIVE and reward.is_in_period(now)):
            raise RewardNotAvailable()
        if Redemption.objects.filter(customer=customer, reward=reward, status=Status.PENDING).exists():
            raise PendingRedemptionExists()
        if reward.stock is not None:
            # Resta condicionada: nunca baja de cero aunque fallara el bloqueo.
            if not Reward.objects.filter(pk=reward.pk, stock__gte=1).update(stock=F("stock") - 1):
                raise RewardOutOfStock()

        # Lanza InsufficientPoints si el saldo (recalculado aquí) no alcanza;
        # la excepción deshace también la resta de unidades.
        movement = ledger.spend_points(
            customer=customer, points=reward.points_cost, reason=f"Canje: {reward.name}"[:200]
        )
        redemption = Redemption.objects.create(
            customer=customer,
            reward=reward,
            points_cost=reward.points_cost,
            code=_new_code(),
            created_at=now,
            expires_at=now + datetime.timedelta(days=settings.REWARDS_CODE_VALIDITY_DAYS),
            idempotency_key=key,
            spend_movement=movement,
        )
    return RedemptionResult(redemption=redemption, created=True)


def request_redemption(*, customer, reward, idempotency_key):
    """
    Canjea `reward` para `customer` (el usuario autenticado, nunca un ID
    enviado por el cliente). Un reintento con la misma referencia devuelve el
    canje existente sin descontar otra vez.
    """
    ensure_can_redeem(customer)
    key = parse_idempotency_key(idempotency_key)
    now = timezone.now()
    try:
        result = _create_redemption(customer, reward, key, now)
    except IntegrityError:
        # Otra petición ganó la carrera; la transacción ya se deshizo entera
        # (sin puntos descontados ni unidades restadas).
        existing = Redemption.objects.filter(idempotency_key=key).first()
        if existing is not None:
            return _replay(existing, customer, reward)
        if Redemption.objects.filter(customer=customer, reward=reward, status=Status.PENDING).exists():
            raise PendingRedemptionExists()
        raise
    if result.created:
        logger.info(
            "Canje solicitado %s (recompensa %s, %s puntos)",
            result.redemption.public_id,
            reward.public_id,
            result.redemption.points_cost,
        )
    return result


# --- Cierre con devolución (cancelación y caducidad) -----------------------------------


def _close(redemption, *, status, actor, now):
    """
    Pasa un canje pendiente a cancelado o caducado y devuelve puntos y unidad,
    todo en una transacción. Devuelve `False` si ya no estaba pendiente.
    """
    with transaction.atomic():
        ledger.lock_customer(redemption.customer)
        Reward.objects.select_for_update().filter(pk=redemption.reward_id).first()
        current = Redemption.objects.select_for_update().get(pk=redemption.pk)
        if current.status != Status.PENDING:
            return False
        reason = "Canje cancelado" if status == Status.CANCELLED else "Canje caducado"
        refund = ledger.refund_spent_points(movement=current.spend_movement, actor=actor, reason=reason)
        updated = Redemption.objects.filter(pk=current.pk, status=Status.PENDING).update(
            status=status, closed_at=now, refund_movement=refund.movement
        )
        if not updated:
            # Validado a la vez (si el bloqueo de fila no lo impidió): se deshace la devolución.
            raise _ConcurrentChange
        Reward.objects.filter(pk=current.reward_id, stock__isnull=False).update(stock=F("stock") + 1)
    logger.info("Canje %s %s; puntos devueltos", redemption.public_id, status.lower())
    return True


class _ConcurrentChange(Exception):
    pass


def _close_safely(redemption, *, status, actor, now):
    try:
        return _close(redemption, status=status, actor=actor, now=now)
    except _ConcurrentChange:
        return False


def cancel_redemption(*, customer, redemption):
    """
    El cliente cancela su propio canje pendiente y recupera los puntos.
    Idempotente: cancelar un canje ya cancelado no hace nada.
    """
    ensure_can_redeem(customer)
    if redemption.customer_id != customer.pk:
        raise PermissionDenied("Este canje no es tuyo.")
    if _close_safely(redemption, status=Status.CANCELLED, actor=customer, now=timezone.now()):
        return RedemptionResult(redemption=Redemption.objects.get(pk=redemption.pk), created=True)
    redemption.refresh_from_db()
    if redemption.status == Status.CANCELLED:
        return RedemptionResult(redemption=redemption, created=False)
    raise RedemptionNotPending()


def expire_pending_redemptions(now=None):
    """
    Caduca los canjes pendientes cuyo plazo ha pasado y devuelve los puntos.
    La usa el comando `expire_redemptions`; también se caduca un canje al
    intentar validarlo fuera de plazo. Devuelve cuántos ha caducado.
    """
    now = now or timezone.now()
    expired = 0
    due = Redemption.objects.filter(status=Status.PENDING, expires_at__lte=now).select_related("customer")
    for redemption in due.iterator():
        if _close_safely(redemption, status=Status.EXPIRED, actor=None, now=now):
            expired += 1
    return expired


# --- Validación (personal) -----------------------------------------------------------


def _check_failures(staff):
    if throttling.is_limited(_FAILURE_SCOPE, str(staff.public_id), settings.REWARDS_MAX_CODE_FAILURES):
        raise TooManyFailedAttempts


def _register_failure(staff):
    throttling.register_attempt(
        _FAILURE_SCOPE, str(staff.public_id), settings.REWARDS_CODE_FAILURE_WINDOW_SECONDS
    )
    # Sin el código leído ni datos del cliente.
    logger.info("Código de canje rechazado (personal %s)", staff.public_id)


def _find(staff, raw_code, *, for_update=False):
    code = codes.normalize_code(raw_code)
    redemption = None
    if code is not None:
        queryset = Redemption.objects.select_related("customer", "reward")
        if for_update:
            queryset = queryset.select_for_update()
        redemption = queryset.filter(code=code).first()
    if redemption is None or not (redemption.customer.is_active and redemption.customer.role == User.Role.CUSTOMER):
        # Mismo mensaje si no existe o si la cuenta del cliente ya no está activa.
        _register_failure(staff)
        raise InvalidRedemptionCode()
    return redemption


def _preview(redemption):
    return RedemptionPreview(
        customer_name=loyalty.customer_display_name(redemption.customer),
        reward_name=redemption.reward.name,
        points_cost=redemption.points_cost,
        status=redemption.status,
        status_display=redemption.get_status_display(),
        created_at=redemption.created_at,
        expires_at=redemption.expires_at,
        validated_at=redemption.validated_at,
    )


def lookup_redemption(*, staff, code):
    """
    Datos mínimos de un canje para que el personal lo compruebe. No lo valida;
    solo, si ya venció, lo caduca y devuelve los puntos.
    """
    ensure_can_validate(staff)
    _check_failures(staff)
    redemption = _find(staff, code)
    if redemption.is_expired():
        _close_safely(redemption, status=Status.EXPIRED, actor=None, now=timezone.now())
        redemption.refresh_from_db()
    return _preview(redemption)


def validate_redemption(*, staff, code):
    """
    Marca el canje como entregado por `staff`. Un código usado, caducado o
    cancelado no se acepta; de dos validaciones simultáneas solo gana una.
    """
    ensure_can_validate(staff)
    _check_failures(staff)
    now = timezone.now()
    with transaction.atomic():
        redemption = _find(staff, code, for_update=True)
        if redemption.customer_id == staff.pk:
            raise PermissionDenied("No puedes validar tu propio canje.")
        expired = redemption.is_expired(now)
        if not expired:
            updated = Redemption.objects.filter(pk=redemption.pk, status=Status.PENDING, expires_at__gt=now).update(
                status=Status.USED, validated_by=staff, validated_at=now
            )
            if updated:
                record_audit_event(
                    action=AuditEvent.Action.REDEMPTION_VALIDATED,
                    actor=staff,
                    target=redemption,
                    metadata={"reward": str(redemption.reward.public_id), "points": redemption.points_cost},
                )
    if expired:
        _close_safely(redemption, status=Status.EXPIRED, actor=None, now=now)
        raise RedemptionExpired()
    redemption.refresh_from_db()
    if not updated:
        if redemption.status == Status.USED:
            raise RedemptionAlreadyUsed(redemption.validated_at)
        if redemption.status == Status.EXPIRED:
            raise RedemptionExpired()
        raise RedemptionNotPending()
    logger.info("Canje validado %s (personal %s)", redemption.public_id, staff.public_id)
    return RedemptionResult(redemption=redemption, created=True)


# --- Gestión del catálogo (propietario) ---------------------------------------------


def save_reward(*, actor, reward, changed_fields=()):
    """Crea o modifica una recompensa (solo propietario), validada y auditada."""
    if not is_owner(actor):
        raise PermissionDenied("Solo el propietario puede gestionar las recompensas.")
    creating = reward.pk is None
    reward.full_clean()
    with transaction.atomic():
        reward.save()
        record_audit_event(
            action=AuditEvent.Action.REWARD_SAVED,
            actor=actor,
            target=reward,
            metadata={"created": creating, "fields": sorted(changed_fields), "status": reward.status},
        )
    return reward


# --- Lectura con permisos por objeto ---------------------------------------------------


def visible_redemptions_for_staff(user):
    """El propietario ve todos los canjes validados; un empleado, solo los que validó él."""
    if is_owner(user):
        return Redemption.objects.exclude(validated_by=None)
    if is_staff_member(user):
        return Redemption.objects.filter(validated_by=user)
    return Redemption.objects.none()
