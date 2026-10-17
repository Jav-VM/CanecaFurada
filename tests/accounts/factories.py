"""Datos ficticios para tests. Nunca usar datos personales reales."""
import datetime
import re

from django.utils import timezone

from apps.accounts.models import User

PASSWORD = "Contrasena-Ficticia-2026"

# Teléfonos de rangos reservados/ficticios con formato válido.
VALID_MOBILE = "600 000 001"
VALID_MOBILE_E164 = "+34600000001"


def adult_birth_date(years=30):
    today = timezone.localdate()
    return datetime.date(today.year - years, 6, 15)


def registration_data(**overrides):
    """Datos completos y válidos del registro público (ficticios)."""
    data = {
        "email": "nueva@example.com",
        "password": PASSWORD,
        "first_name": "Lúa",
        "last_name": "Ficticia Exemplo",
        "address_line_1": "Rúa Ficticia 1, 2º",
        "address_line_2": "",
        "postal_code": "15001",
        "city": "A Coruña",
        "province": "A Coruña",
        "country": "ES",
        "date_of_birth": adult_birth_date(),
        "sex": "UNDISCLOSED",
        "phone_number": "",
        "promo_email_opt_in": False,
        "promo_sms_opt_in": False,
        # Fase 25: aceptación de la privacidad y de las condiciones del programa.
        "accept_terms": True,
    }
    data.update(overrides)
    return data


def registration_post_data(**overrides):
    """Los mismos datos con los nombres del formulario web."""
    data = registration_data()
    password = data.pop("password")
    data["date_of_birth"] = data["date_of_birth"].isoformat()
    data.update({"password1": password, "password2": password})
    for key in ("promo_email_opt_in", "promo_sms_opt_in"):
        if not data[key]:
            data.pop(key)
    data.update(overrides)
    return {key: value for key, value in data.items() if value is not None}


_TOKEN_RE = re.compile(r"/cuenta/verificar-email/([A-Za-z0-9_-]+)/")


def token_from_email(message):
    match = _TOKEN_RE.search(message.body)
    assert match, "El email no contiene enlace de verificación"
    return match.group(1)


def make_user(email="cliente@example.com", role=User.Role.CUSTOMER, **extra):
    extra.setdefault("first_name", "Ana")
    extra.setdefault("last_name", "Pérez Ficticia")
    if role == User.Role.OWNER:
        return User.objects.create_superuser(email=email, password=PASSWORD, **extra)
    return User.objects.create_user(email=email, password=PASSWORD, role=role, **extra)
