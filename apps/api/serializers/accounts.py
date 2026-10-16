"""
Cuenta del usuario autenticado.

- `MeSerializer`: respuesta general (también tras el login). **Sin** dirección,
  fecha de nacimiento, teléfono ni preferencias.
- `ProfileSerializer`: datos personales del propio cliente, solo en
  `/me/profile/` (para verlos y editarlos).
- `PreferencesSerializer`: consentimientos promocionales, solo en `/me/preferences/`.
"""
from rest_framework import serializers

from apps.accounts.models import CustomerProfile, User


class MeSerializer(serializers.Serializer):
    public_id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    role = serializers.ChoiceField(choices=User.Role.choices, read_only=True)
    email_verified = serializers.BooleanField(source="is_email_verified", read_only=True)
    profile_complete = serializers.SerializerMethodField(
        help_text="Solo clientes: faltan datos obligatorios del perfil si es false. `null` para el personal."
    )

    def get_profile_complete(self, user) -> bool | None:
        if user.role != User.Role.CUSTOMER:
            return None
        profile = CustomerProfile.objects.filter(user=user).first()
        return bool(profile) and not profile.missing_required_fields()


class ProfileSerializer(serializers.Serializer):
    """Para `PATCH` todos los campos son opcionales; los no enviados no cambian."""

    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    date_of_birth = serializers.DateField(
        help_text="AAAA-MM-DD. Solo se puede cambiar una vez al año (protege las promociones de cumpleaños)."
    )
    sex = serializers.ChoiceField(choices=CustomerProfile.Sex.choices)
    phone_number = serializers.CharField(max_length=32, allow_blank=True, help_text="Vacío para borrarlo.")
    address_line_1 = serializers.CharField(max_length=200, allow_blank=True)
    address_line_2 = serializers.CharField(max_length=200, allow_blank=True)
    postal_code = serializers.CharField(max_length=12)
    city = serializers.CharField(
        max_length=100, allow_blank=True, help_text="Obligatoria si el CP tiene localidades conocidas."
    )
    province = serializers.CharField(max_length=100, allow_blank=True, help_text="En España se deduce del CP.")
    country = serializers.CharField(max_length=2, help_text="ISO 3166-1 alfa-2.")
    missing_fields = serializers.ListField(child=serializers.CharField(), read_only=True)

    @staticmethod
    def data_for(user, profile):
        data = {"first_name": user.first_name, "last_name": user.last_name}
        for name in (
            "date_of_birth", "sex", "phone_number", "address_line_1", "address_line_2",
            "postal_code", "city", "province", "country",
        ):
            data[name] = getattr(profile, name)
        data["missing_fields"] = profile.missing_required_fields()
        return data


class PreferencesSerializer(serializers.Serializer):
    promo_email_opt_in = serializers.BooleanField(help_text="Acepta emails promocionales.")
    promo_sms_opt_in = serializers.BooleanField(help_text="Acepta SMS promocionales (requiere teléfono).")


class EmailChangeSerializer(serializers.Serializer):
    new_email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
