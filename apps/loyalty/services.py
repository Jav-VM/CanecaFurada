"""
QR personal del cliente: emisión, renovación e identificación.

- `get_customer_qr(user)`: el código del propio cliente (lo crea la primera vez).
- `rotate_customer_qr(user)`: genera un token nuevo e invalida el anterior.
- `identify_customer(raw_code)`: devuelve el cliente al que pertenece un código
  leído del QR o tecleado. Solo identifica; quien llama debe comprobar los
  permisos de la operación (p. ej. `apps.purchases.services`).

Los errores tienen mensajes genéricos: no revelan nombre, email ni otros datos
del cliente, y no distinguen "no existe" de "cuenta inactiva".
"""
import base64
import re
import secrets

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core import throttling
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event

from .models import CustomerQRCode

# Prefijo de versión del contenido del QR. Permite cambiar el formato en el
# futuro y descartar enseguida QR ajenos (webs, wifi...) sin consultar la BD.
QR_PAYLOAD_PREFIX = "CF1:"
TOKEN_LENGTH = 32
_TOKEN_RE = re.compile(r"^[A-Z2-7]{32}$")
_SEPARATORS_RE = re.compile(r"[\s\-]+")


class InvalidQRCode(ValidationError):
    def __init__(self):
        super().__init__("El código no es válido o la cuenta no está activa.", code="invalid_qr")


class CustomerNotEligible(ValidationError):
    def __init__(self):
        super().__init__(
            "El cliente tiene que verificar su email antes de poder sumar compras.",
            code="email_not_verified",
        )


class RotationRateLimited(Exception):
    """Demasiadas renovaciones del QR en poco tiempo."""


def generate_token():
    # 20 bytes aleatorios -> 32 caracteres en base32 (A-Z, 2-7), sin relleno.
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii")


def qr_payload(token):
    return f"{QR_PAYLOAD_PREFIX}{token}"


def format_code(token):
    """Versión legible para teclearlo a mano: grupos de 4 caracteres."""
    return " ".join(token[i : i + 4] for i in range(0, len(token), 4))


def mask_code(token):
    """Para soporte o depuración: nunca se muestra el token completo."""
    return f"{token[:4]}…" if token else "…"


def normalize_code(raw):
    """
    Acepta el contenido del QR (`CF1:XXXX…`) o el código tecleado (con
    espacios, guiones o en minúsculas). Devuelve el token o `None`.
    """
    if not isinstance(raw, str) or len(raw) > 100:
        return None
    value = _SEPARATORS_RE.sub("", raw).upper()
    if value.startswith(QR_PAYLOAD_PREFIX):
        value = value[len(QR_PAYLOAD_PREFIX) :]
    return value if _TOKEN_RE.match(value) else None


def _require_verified_customer(user):
    if not (
        getattr(user, "is_authenticated", False)
        and user.is_active
        and user.role == User.Role.CUSTOMER
    ):
        raise PermissionDenied("Solo los clientes tienen código QR.")
    if not user.is_email_verified:
        raise PermissionDenied("Debes verificar tu email para usar tu código QR.")


def get_customer_qr(user):
    _require_verified_customer(user)
    try:
        return user.qr_code
    except CustomerQRCode.DoesNotExist:
        pass
    try:
        with transaction.atomic():
            return CustomerQRCode.objects.create(user=user, token=generate_token())
    except IntegrityError:
        # Dos peticiones simultáneas: se queda el que ganó la carrera.
        return CustomerQRCode.objects.get(user=user)


@transaction.atomic
def rotate_customer_qr(user):
    _require_verified_customer(user)
    scope_id = str(user.public_id)
    if throttling.is_limited("qr_rotate", scope_id, settings.LOYALTY_QR_MAX_ROTATIONS_PER_DAY):
        raise RotationRateLimited
    qr = get_customer_qr(user)
    qr = CustomerQRCode.objects.select_for_update().get(pk=qr.pk)
    qr.token = generate_token()
    qr.rotated_at = timezone.now()
    qr.save(update_fields=["token", "rotated_at", "updated_at"])
    throttling.register_attempt("qr_rotate", scope_id, 24 * 60 * 60)
    record_audit_event(action=AuditEvent.Action.QR_ROTATED, actor=user, target=user)
    return qr


def identify_customer(raw_code, *, for_update=False):
    """
    Cliente activo al que pertenece el código. Lanza `InvalidQRCode` si el
    código no existe, no pertenece a un cliente o la cuenta está inactiva, y
    `CustomerNotEligible` si el email no está verificado.
    """
    token = normalize_code(raw_code)
    if token is None:
        raise InvalidQRCode()
    users = User.objects.all()
    if for_update:
        users = users.select_for_update()
    user = users.filter(qr_code__token=token).first()
    if user is None or not user.is_active or user.role != User.Role.CUSTOMER:
        raise InvalidQRCode()
    if not user.is_email_verified:
        raise CustomerNotEligible()
    return user


def customer_display_name(user):
    """Lo mínimo para que el empleado confirme la identidad: «Lúa F.»."""
    initial = f" {user.last_name.strip()[0]}." if user.last_name.strip() else ""
    return f"{user.first_name.strip()}{initial}"
