"""
Autenticación de la API: JWT en la cabecera `Authorization: Bearer <access>`.

No hay autenticación por sesión ni por cookies en la API, así que tampoco hay
superficie CSRF: un navegador no envía la cabecera `Authorization` por su
cuenta. Además de lo que comprueba simplejwt (firma, caducidad, tipo y cuenta
activa), se exige que el token se emitiera con la contraseña vigente
(`tokens.password_version_matches`).
"""
from django.utils.translation import gettext as _
from rest_framework_simplejwt.authentication import JWTAuthentication as BaseJWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from . import tokens


class JWTAuthentication(BaseJWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if not tokens.password_version_matches(user, validated_token):
            raise AuthenticationFailed(_("La sesión ya no es válida. Vuelve a iniciar sesión."), code="token_revoked")
        return user
