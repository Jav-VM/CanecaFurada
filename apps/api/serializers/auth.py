"""Entrada y salida de registro, inicio de sesión, tokens, verificación y contraseña."""
from rest_framework import serializers

from apps.accounts.countries import DEFAULT_COUNTRY


def password_field(**kwargs):
    return serializers.CharField(
        write_only=True, trim_whitespace=False, max_length=128, style={"input_type": "password"}, **kwargs
    )


class RegisterSerializer(serializers.Serializer):
    """Registro público: siempre crea un cliente (no existe ningún campo de rol)."""

    email = serializers.EmailField(max_length=254)
    password = password_field(help_text="Mínimo 10 caracteres; no común ni solo números.")
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    date_of_birth = serializers.DateField(help_text="AAAA-MM-DD. Edad mínima configurable (18 por defecto).")
    phone_number = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    address_line_1 = serializers.CharField(max_length=200)
    address_line_2 = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    postal_code = serializers.CharField(max_length=12)
    city = serializers.CharField(max_length=100)
    province = serializers.CharField(max_length=100)
    country = serializers.CharField(max_length=2, default=DEFAULT_COUNTRY, help_text="ISO 3166-1 alfa-2.")
    promo_email_opt_in = serializers.BooleanField(default=False)
    promo_sms_opt_in = serializers.BooleanField(default=False)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = password_field()


class TokenPairSerializer(serializers.Serializer):
    """Solo salida (documentación)."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    token_type = serializers.CharField()
    access_expires_in = serializers.IntegerField(help_text="Segundos.")
    refresh_expires_in = serializers.IntegerField(help_text="Segundos.")


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField(max_length=2000, write_only=True)


class TokenToVerifySerializer(serializers.Serializer):
    token = serializers.CharField(max_length=128, help_text="Último segmento del enlace del email.")


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = password_field()
    new_password = password_field()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=64, help_text="Segmento `uidb64` del enlace del email.")
    token = serializers.CharField(max_length=128, help_text="Segmento `token` del enlace del email.")
    new_password = password_field()
