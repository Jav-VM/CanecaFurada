"""
Tokens de la app móvil (JWT de `djangorestframework-simplejwt`).

- **Access** (15 min por defecto): va en `Authorization: Bearer <access>` en
  cada petición. No se guarda en el servidor.
- **Refresh** (30 días por defecto): solo sirve para pedir un par nuevo en
  `POST /api/v1/auth/token/refresh/`. Es rotatorio: cada uso lo invalida (lista
  negra) y entrega otro.

Revocación:
- `revoke_refresh_token` (cerrar sesión en este dispositivo) y
  `revoke_all_tokens` (en todos) ponen los refresh en la lista negra.
- **Cambio de contraseña** por cualquier vía (web, API, admin, recuperación):
  todos los tokens llevan la reclamación `pwv`, un HMAC de Django
  (`salted_hmac` con `SECRET_KEY`) del hash de la contraseña. Si la contraseña
  cambia deja de coincidir y tanto el access como el refresh se rechazan al
  momento, sin esperar a que caduquen.
- **Cuenta desactivada**: se rechazan en cada petición (`CHECK_USER_IS_ACTIVE`).

El token se identifica con el `public_id` del usuario (`sub`), nunca con la PK
interna. Los tokens no contienen el rol ni datos personales: el rol se lee de
la base de datos en cada petición.
"""
from django.db import transaction
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event

PASSWORD_VERSION_CLAIM = "pwv"
_SALT = "apps.api.tokens.password-version"


class InvalidRefreshToken(Exception):
    """Refresh no válido, caducado, revocado o de una cuenta que ya no puede entrar."""


def password_version(user):
    return salted_hmac(_SALT, user.password, algorithm="sha256").hexdigest()[:32]


def password_version_matches(user, payload):
    claim = payload.get(PASSWORD_VERSION_CLAIM)
    return isinstance(claim, str) and constant_time_compare(claim, password_version(user))


def _pair(refresh):
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "token_type": "Bearer",
        "access_expires_in": int(api_settings.ACCESS_TOKEN_LIFETIME.total_seconds()),
        "refresh_expires_in": int(api_settings.REFRESH_TOKEN_LIFETIME.total_seconds()),
    }


def issue_tokens(user):
    """Par access + refresh para un usuario ya autenticado."""
    refresh = RefreshToken.for_user(user)
    refresh[PASSWORD_VERSION_CLAIM] = password_version(user)
    return _pair(refresh)


def _user_for(refresh):
    user = User.objects.filter(public_id=refresh.payload.get(api_settings.USER_ID_CLAIM)).first()
    if user is None or not user.is_active or not password_version_matches(user, refresh.payload):
        raise InvalidRefreshToken
    return user


def _parse(raw_token):
    if not isinstance(raw_token, str) or not raw_token or len(raw_token) > 2000:
        raise InvalidRefreshToken
    try:
        return RefreshToken(raw_token)  # comprueba firma, tipo, caducidad y lista negra
    except TokenError:
        raise InvalidRefreshToken from None


def rotate_refresh_token(raw_token):
    """
    Entrega un par nuevo e invalida el refresh usado. La fila del token se
    bloquea: dos renovaciones simultáneas con el mismo refresh no pueden
    obtener ambas un par válido.
    """
    refresh = _parse(raw_token)
    user = _user_for(refresh)
    jti = refresh.payload[api_settings.JTI_CLAIM]
    with transaction.atomic():
        outstanding = OutstandingToken.objects.select_for_update().filter(jti=jti).first()
        if outstanding is None or BlacklistedToken.objects.filter(token=outstanding).exists():
            raise InvalidRefreshToken
        BlacklistedToken.objects.create(token=outstanding)
        refresh.set_jti()
        refresh.set_exp()
        refresh.set_iat()
        refresh.outstand()
    return user, _pair(refresh)


def revoke_refresh_token(*, user, raw_token):
    """
    Cierra la sesión del dispositivo que presenta su refresh. Idempotente: un
    token ya revocado, caducado o ajeno no se toca y no se informa de ello.
    """
    try:
        refresh = _parse(raw_token)
    except InvalidRefreshToken:
        return False
    if str(refresh.payload.get(api_settings.USER_ID_CLAIM)) != str(user.public_id):
        return False
    refresh.blacklist()
    return True


@transaction.atomic
def revoke_all_tokens(*, user, reason):
    """Revoca todos los refresh vigentes del usuario (cerrar sesión en todos los dispositivos)."""
    outstanding = OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True)
    revoked = 0
    for token in outstanding:
        _unused, created = BlacklistedToken.objects.get_or_create(token=token)
        revoked += int(created)
    record_audit_event(
        action=AuditEvent.Action.API_SESSIONS_REVOKED,
        actor=user,
        target=user,
        metadata={"reason": reason, "tokens": revoked},
    )
    return revoked
