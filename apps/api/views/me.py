"""
Cuenta del usuario autenticado: datos generales, perfil personal,
preferencias de comunicación y cambio de email. Nunca reciben un
identificador de usuario: actúan siempre sobre `request.user`.
"""
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from apps.accounts import services as accounts
from apps.accounts.models import CustomerProfile

from ..permissions import IsCustomer
from ..schema import DETAIL, ERROR
from ..serializers.accounts import EmailChangeSerializer, MeSerializer, PreferencesSerializer, ProfileSerializer
from ..throttling import AnonThrottle, AuthThrottle, UserThrottle
from .base import ApiView

TAG = "Mi cuenta"
EMAIL_CHANGE_DONE = (
    "Si la dirección está disponible, te hemos enviado un enlace para confirmarla. "
    "Tu email actual seguirá siendo el de acceso hasta que lo confirmes."
)


def _profile_of(user):
    return CustomerProfile.objects.filter(user=user).first() or CustomerProfile(user=user)


class MeView(ApiView):
    @extend_schema(
        tags=[TAG],
        responses={200: MeSerializer, 401: ERROR},
        summary="Mis datos básicos",
        description="Sin dirección, fecha de nacimiento, teléfono ni preferencias (ver `/me/profile/`).",
    )
    def get(self, request):
        return Response(MeSerializer(request.user).data)


class ProfileView(ApiView):
    permission_classes = [IsCustomer]

    @extend_schema(tags=[TAG], responses={200: ProfileSerializer, 403: ERROR}, summary="Mi perfil de cliente")
    def get(self, request):
        return Response(ProfileSerializer(ProfileSerializer.data_for(request.user, _profile_of(request.user))).data)

    @extend_schema(
        tags=[TAG],
        request=ProfileSerializer(partial=True),
        responses={200: ProfileSerializer, 400: ERROR, 403: ERROR},
        summary="Modificar mi perfil",
        description=(
            "Solo se cambian los campos enviados. El email se cambia en `/me/email/change/`. "
            "Los obligatorios deben quedar completos; la fecha de nacimiento se puede cambiar una vez al año."
        ),
    )
    def patch(self, request):
        serializer = ProfileSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        user = request.user
        profile_data = {name: data[name] for name in accounts.PROFILE_FIELDS if name in data}
        profile = accounts.update_customer_profile(
            user=user,
            first_name=data.get("first_name", user.first_name),
            last_name=data.get("last_name", user.last_name),
            **profile_data,
        )
        user.refresh_from_db(fields=["first_name", "last_name"])
        return Response(ProfileSerializer(ProfileSerializer.data_for(user, profile)).data)


class PreferencesView(ApiView):
    permission_classes = [IsCustomer]

    def _response(self, profile):
        return Response(
            PreferencesSerializer(
                {"promo_email_opt_in": profile.promo_email_opt_in, "promo_sms_opt_in": profile.promo_sms_opt_in}
            ).data
        )

    @extend_schema(tags=[TAG], responses={200: PreferencesSerializer, 403: ERROR}, summary="Mis preferencias de comunicación")
    def get(self, request):
        return self._response(_profile_of(request.user))

    @extend_schema(
        tags=[TAG],
        request=PreferencesSerializer(partial=True),
        responses={200: PreferencesSerializer, 400: ERROR, 403: ERROR},
        summary="Cambiar mis preferencias",
        description="Cada cambio queda en el historial de consentimientos. Los SMS requieren un teléfono en el perfil.",
    )
    def patch(self, request):
        serializer = PreferencesSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        current = _profile_of(request.user)
        values = {
            "promo_email_opt_in": current.promo_email_opt_in,
            "promo_sms_opt_in": current.promo_sms_opt_in,
            **serializer.validated_data,
        }
        return self._response(accounts.set_communication_preferences(user=request.user, **values))


class EmailChangeView(ApiView):
    throttle_classes = [AuthThrottle, AnonThrottle, UserThrottle]

    @extend_schema(
        tags=[TAG],
        request=EmailChangeSerializer,
        responses={202: DETAIL, 400: ERROR, 429: ERROR},
        summary="Cambiar mi email",
        description=(
            "Exige la contraseña. Envía un enlace a la nueva dirección; el email no cambia hasta confirmarlo "
            "(`POST /auth/email/verify/`). No revela si la nueva dirección ya está en uso."
        ),
    )
    def post(self, request):
        serializer = EmailChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        accounts.request_email_change(user=request.user, **serializer.validated_data)
        return Response({"detail": EMAIL_CHANGE_DONE}, status=status.HTTP_202_ACCEPTED)


class ResendMyVerificationView(ApiView):
    throttle_classes = [AuthThrottle, AnonThrottle, UserThrottle]

    @extend_schema(
        tags=[TAG],
        request=None,
        responses={202: DETAIL, 200: DETAIL, 429: ERROR},
        summary="Reenviarme el enlace de verificación",
    )
    def post(self, request):
        if accounts.resend_verification_email(request.user):
            return Response({"detail": "Te hemos enviado un nuevo enlace de verificación."}, status=status.HTTP_202_ACCEPTED)
        return Response({"detail": "Tu email ya está verificado."})

