"""
Autenticación de la app: registro, verificación del email, login, tokens,
cierre de sesión y contraseña. Las respuestas públicas no revelan si una
cuenta existe (registro, reenvío y recuperación responden siempre igual).
"""
from django.conf import settings
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from apps.accounts import services as accounts
from apps.accounts.forms import NotifyingPasswordResetForm
from apps.accounts.normalization import normalize_email_address
from apps.core.http import client_ip, ip_limited

from .. import tokens
from ..exceptions import error_response
from ..schema import DETAIL, ERROR
from ..serializers.accounts import MeSerializer
from ..serializers.auth import (
    EmailSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    RefreshSerializer,
    RegisterSerializer,
    TokenPairSerializer,
    TokenToVerifySerializer,
)
from ..throttling import AnonThrottle, AuthThrottle, UserThrottle
from .base import ApiView, PublicAuthView

REGISTER_DONE = _(
    "Si los datos son correctos, te hemos enviado un email para confirmar tu cuenta. "
    "Revisa tu bandeja de entrada."
)
RESEND_DONE = _("Si existe una cuenta pendiente de verificación con ese email, recibirás un nuevo enlace.")
RESET_DONE = _("Si existe una cuenta con ese email, recibirás un enlace para elegir una contraseña nueva.")
INVALID_LOGIN = _("Email o contraseña incorrectos.")
LOGIN_THROTTLED = _("Demasiados intentos fallidos. Inténtalo de nuevo en unos minutos.")
INVALID_REFRESH = _("La sesión ha caducado o se ha cerrado. Vuelve a iniciar sesión.")

TAG = "Autenticación"


def _accepted(message):
    return Response({"detail": message}, status=status.HTTP_202_ACCEPTED)


class RegisterView(PublicAuthView):
    @extend_schema(
        tags=[TAG],
        request=RegisterSerializer,
        responses={202: DETAIL, 400: ERROR, 429: ERROR},
        summary="Registro de cliente",
        description=(
            "Crea una cuenta de **cliente** (no se puede elegir rol) con el email pendiente de verificar y "
            "envía el enlace de verificación. Si el email ya existe responde igual (202) y avisa al titular."
        ),
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        if ip_limited(request, "register-ip", settings.PUBLIC_FORM_MAX_PER_IP_PER_HOUR):
            return error_response(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited", _("Demasiados intentos desde tu conexión."))
        try:
            accounts.register_customer(**data)
        except accounts.EmailAlreadyRegistered:
            accounts.notify_existing_account(data["email"])
        return _accepted(REGISTER_DONE)


class VerifyEmailView(PublicAuthView):
    @extend_schema(
        tags=[TAG],
        request=TokenToVerifySerializer,
        responses={200: DETAIL, 400: ERROR},
        summary="Confirmar email",
        description=(
            "Confirma el alta o un cambio de email con el token del enlace "
            "(`/cuenta/verificar-email/<token>/`). Errores: `invalid`, `expired`, `used`, `revoked`, `email_taken`."
        ),
    )
    def post(self, request):
        serializer = TokenToVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        accounts.confirm_email_token(serializer.validated_data["token"])
        return Response({"detail": _("Email confirmado.")})


class ResendVerificationView(PublicAuthView):
    @extend_schema(
        tags=[TAG],
        request=EmailSerializer,
        responses={202: DETAIL, 400: ERROR},
        summary="Reenviar verificación (sin sesión)",
        description="Responde siempre igual, exista o no la cuenta.",
    )
    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not ip_limited(request, "resend-ip", settings.PUBLIC_FORM_MAX_PER_IP_PER_HOUR):
            accounts.request_verification_resend(serializer.validated_data["email"])
        return _accepted(RESEND_DONE)


class LoginView(PublicAuthView):
    @extend_schema(
        tags=[TAG],
        request=LoginSerializer,
        responses={200: TokenPairSerializer, 400: ERROR, 401: ERROR, 429: ERROR},
        summary="Iniciar sesión",
        description=(
            "Devuelve `access` (15 min) y `refresh` (30 días) y los datos básicos del usuario (`user`). "
            "Mismo límite de intentos fallidos por email e IP que la web. Una cuenta con el email sin verificar "
            "puede entrar, pero no usar puntos, QR, canjes ni reservas."
        ),
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email, password = serializer.validated_data["email"], serializer.validated_data["password"]
        keys = accounts.login_throttle_keys(email, client_ip(request))
        if accounts.login_is_throttled(keys):
            return error_response(status.HTTP_429_TOO_MANY_REQUESTS, "login_throttled", LOGIN_THROTTLED)
        user = authenticate(request, email=normalize_email_address(email), password=password)
        if user is None:
            accounts.register_login_failure(keys)
            return error_response(status.HTTP_401_UNAUTHORIZED, "invalid_credentials", INVALID_LOGIN)
        return Response({**tokens.issue_tokens(user), "user": MeSerializer(user).data})


class TokenRefreshView(PublicAuthView):
    @extend_schema(
        tags=[TAG],
        request=RefreshSerializer,
        responses={200: TokenPairSerializer, 401: ERROR},
        summary="Renovar tokens",
        description=(
            "Entrega un par nuevo y revoca el `refresh` usado (rotación). Guarda siempre el último `refresh`. "
            "401 `token_not_valid` si caducó, se revocó, la contraseña cambió o la cuenta se desactivó."
        ),
    )
    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            _unused, pair = tokens.rotate_refresh_token(serializer.validated_data["refresh"])
        except tokens.InvalidRefreshToken:
            return error_response(status.HTTP_401_UNAUTHORIZED, "token_not_valid", INVALID_REFRESH)
        return Response(pair)


class LogoutView(ApiView):
    @extend_schema(
        tags=[TAG],
        request=RefreshSerializer,
        responses={204: None, 401: ERROR},
        summary="Cerrar sesión en este dispositivo",
        description="Revoca el `refresh` enviado. El `access` sigue valiendo hasta que caduque (máx. 15 min): bórralo.",
    )
    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens.revoke_refresh_token(user=request.user, raw_token=serializer.validated_data["refresh"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class LogoutAllView(ApiView):
    @extend_schema(
        tags=[TAG],
        request=None,
        responses={204: None, 401: ERROR},
        summary="Cerrar sesión en todos los dispositivos",
        description="Revoca todos los `refresh` de la cuenta (queda auditado).",
    )
    def post(self, request):
        tokens.revoke_all_tokens(user=request.user, reason="logout_all")
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordChangeView(ApiView):
    throttle_classes = [AuthThrottle, AnonThrottle, UserThrottle]

    @extend_schema(
        tags=[TAG],
        request=PasswordChangeSerializer,
        responses={200: TokenPairSerializer, 400: ERROR, 401: ERROR},
        summary="Cambiar contraseña",
        description=(
            "Exige la contraseña actual. Invalida al momento todos los tokens y sesiones anteriores "
            "(también en otros dispositivos y en la web) y devuelve un par nuevo para este dispositivo."
        ),
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = accounts.change_password(user=request.user, **serializer.validated_data)
        tokens.revoke_all_tokens(user=user, reason="password_change")
        return Response(tokens.issue_tokens(user))


class PasswordResetView(PublicAuthView):
    @extend_schema(
        tags=[TAG],
        request=EmailSerializer,
        responses={202: DETAIL, 400: ERROR},
        summary="Recuperar cuenta",
        description=(
            "Envía el enlace de recuperación nativo de Django (`/cuenta/contrasena/restablecer/<uid>/<token>/`). "
            "Responde siempre igual, exista o no la cuenta."
        ),
    )
    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not ip_limited(request, "password-reset-ip", settings.PUBLIC_FORM_MAX_PER_IP_PER_HOUR):
            # El mismo formulario que la web: tokens de Django y envío registrado en notificaciones.
            form = NotifyingPasswordResetForm(data={"email": serializer.validated_data["email"]})
            if form.is_valid():
                form.save(
                    domain_override="Caneca Furada",
                    subject_template_name="emails/password_reset_subject.txt",
                    email_template_name="emails/password_reset_body.txt",
                    extra_email_context={"site_base_url": settings.SITE_BASE_URL},
                )
        return _accepted(RESET_DONE)


class PasswordResetConfirmView(PublicAuthView):
    @extend_schema(
        tags=[TAG],
        request=PasswordResetConfirmSerializer,
        responses={200: DETAIL, 400: ERROR},
        summary="Elegir contraseña nueva con el enlace",
        description=(
            "Para cuando la app abre el enlace del email (enlace universal / App Link). "
            "Error `invalid_token` si el enlace caducó o ya se usó. Invalida todos los tokens anteriores."
        ),
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        accounts.reset_password_with_token(uidb64=data["uid"], token=data["token"], new_password=data["new_password"])
        return Response({"detail": _("Contraseña cambiada. Ya puedes iniciar sesión.")})
