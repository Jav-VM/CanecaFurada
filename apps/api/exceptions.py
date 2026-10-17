"""
Errores de la API con un formato único:

    {"code": "insufficient_points", "detail": "Mensaje legible.", "fields": {...}}

- `code`: identificador estable para la app (no cambia con el texto).
- `detail`: mensaje en español que se puede mostrar al usuario.
- `fields`: solo en errores de validación, `{campo: [mensajes]}`;
  `non_field_errors` para los generales.

Traducción de los errores de dominio (los servicios no conocen HTTP):
- `django.core.exceptions.ValidationError` → 400, o 409 si su `code` indica
  un conflicto con el estado actual, o 429 si indica un límite.
- `PermissionDenied` → 403; `Http404` → 404.
- Límites propios de los servicios (`RateLimited`, `RotationRateLimited`,
  `TooManyFailedAttempts`) → 429.

Nunca se incluyen trazas, consultas SQL, tokens ni datos personales.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.accounts.services import RateLimited
from apps.loyalty.services import RotationRateLimited
from apps.purchases.services import TooManyFailedAttempts as PurchaseAttemptsExceeded
from apps.rewards.services import TooManyFailedAttempts as RedemptionAttemptsExceeded

# Códigos de dominio que significan "choca con el estado actual" (409).
CONFLICT_CODES = frozenset(
    {
        "idempotency_conflict",
        "duplicate_pending",
        "code_used",
        "code_not_pending",
        "already_reserved",
        "event_full",
        "invalid_transition",
        "operation_not_completed",
        "reservations_disabled",
    }
)
TOO_MANY_CODES = frozenset({"rate_limited"})

_RATE_LIMIT_EXCEPTIONS = (RateLimited, RotationRateLimited, PurchaseAttemptsExceeded, RedemptionAttemptsExceeded)
_RATE_LIMIT_MESSAGE = _("Demasiados intentos. Espera unos minutos antes de volver a intentarlo.")

_DEFAULT_CODES = {
    status.HTTP_401_UNAUTHORIZED: "not_authenticated",
    status.HTTP_403_FORBIDDEN: "permission_denied",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_429_TOO_MANY_REQUESTS: "throttled",
}


def error_response(status_code, code, detail, fields=None, headers=None):
    body = {"code": code, "detail": str(detail)}
    if fields:
        body["fields"] = fields
    return Response(body, status=status_code, headers=headers)


def _strings(value):
    """Convierte los detalles de DRF (ErrorDetail, listas, dicts anidados) en texto plano."""
    if isinstance(value, dict):
        return {key: _strings(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_strings(item) for item in value]
    return str(value)


def _from_django_validation(exc):
    if hasattr(exc, "error_dict"):
        fields = {
            ("non_field_errors" if name == "__all__" else name): messages
            for name, messages in exc.message_dict.items()
        }
        codes = [error.code for errors in exc.error_dict.values() for error in errors]
    else:
        fields = None
        codes = [error.code for error in exc.error_list]
    code = next((c for c in codes if c), "invalid")
    if code in CONFLICT_CODES:
        status_code = status.HTTP_409_CONFLICT
    elif code in TOO_MANY_CODES:
        status_code = status.HTTP_429_TOO_MANY_REQUESTS
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    return error_response(status_code, code, exc.messages[0] if exc.messages else _("Datos no válidos."), fields)


def _code_for(exc, data, status_code):
    if isinstance(data, dict) and isinstance(data.get("code"), str):
        return data["code"]
    if isinstance(exc, exceptions.APIException):
        codes = exc.get_codes()
        if isinstance(codes, str):
            return codes
    return _DEFAULT_CODES.get(status_code, "error")


def exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        return _from_django_validation(exc)
    if isinstance(exc, _RATE_LIMIT_EXCEPTIONS):
        return error_response(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited", str(exc) or _RATE_LIMIT_MESSAGE)

    response = drf_exception_handler(exc, context)
    if response is None:
        return None  # error inesperado: 500 genérico de Django, sin detalles

    data = response.data
    if isinstance(exc, exceptions.ValidationError):
        fields = _strings(data) if isinstance(data, dict) else {"non_field_errors": _strings(data)}
        response.data = {"code": "invalid", "detail": _("Revisa los datos enviados."), "fields": fields}
        return response

    detail = data.get("detail") if isinstance(data, dict) else data
    response.data = {"code": _code_for(exc, data, response.status_code), "detail": _strings(detail or _("Error."))}
    return response
