"""
Validación y normalización de los datos personales del cliente.

Se usan desde el modelo (`CustomerProfile.clean`), los servicios y los
formularios, de modo que la web y la futura API aplican exactamente las mismas
reglas. Los mensajes de error no repiten el valor recibido.
"""
import datetime
import re

import phonenumbers
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from .countries import COUNTRY_CODES

# Edad máxima plausible: evita años como 1800 o 0001 introducidos por error.
MAX_AGE_YEARS = 120

_WHITESPACE_RE = re.compile(r"\s+")
_GENERIC_POSTAL_CODE_RE = re.compile(r"^[A-Z0-9](?:[A-Z0-9 -]{0,10}[A-Z0-9])$")
# Formatos estrictos para los países más habituales; el resto usa el genérico.
_POSTAL_CODE_BY_COUNTRY = {
    "ES": (re.compile(r"^(?:0[1-9]|[1-4]\d|5[0-2])\d{3}$"), "5 dígitos, por ejemplo 15001"),
    "PT": (re.compile(r"^\d{4}-\d{3}$"), "formato 1234-567"),
}
_ALLOWED_PHONE_TYPES = {
    phonenumbers.PhoneNumberType.MOBILE,
    # Algunos países (p. ej. EE. UU.) no distinguen fijos y móviles.
    phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,
}


def normalize_text(value):
    """Quita espacios exteriores y colapsa los interiores."""
    if value is None:
        return ""
    return _WHITESPACE_RE.sub(" ", str(value)).strip()


def normalize_postal_code(value):
    return normalize_text(value).upper()


def validate_country(value):
    if value not in COUNTRY_CODES:
        raise ValidationError("Selecciona un país válido.", code="invalid_country")


def validate_postal_code(value, country):
    """El formato depende del país; se valida junto con él."""
    strict = _POSTAL_CODE_BY_COUNTRY.get(country)
    if strict is not None:
        pattern, hint = strict
        if not pattern.match(value):
            raise ValidationError(f"Código postal no válido ({hint}).", code="invalid_postal_code")
        return
    if not _GENERIC_POSTAL_CODE_RE.match(value):
        raise ValidationError("Código postal no válido.", code="invalid_postal_code")


def normalize_phone_number(value, region=None):
    """
    Devuelve el móvil en formato E.164 (`+34600000000`) o "" si no se indicó.

    Acepta prefijo internacional (`+351…`, `00351…`); sin prefijo se interpreta
    según `PHONE_DEFAULT_REGION`. Lanza `ValidationError` si el número no es un
    móvil válido.
    """
    value = normalize_text(value)
    if not value:
        return ""
    region = region or settings.PHONE_DEFAULT_REGION
    try:
        number = phonenumbers.parse(value, region)
    except phonenumbers.NumberParseException:
        raise ValidationError("Número de teléfono no válido.", code="invalid_phone") from None
    if not phonenumbers.is_valid_number(number):
        raise ValidationError("Número de teléfono no válido.", code="invalid_phone")
    if phonenumbers.number_type(number) not in _ALLOWED_PHONE_TYPES:
        raise ValidationError("Introduce un número de teléfono móvil.", code="not_mobile")
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def validate_e164(value):
    """Validador de modelo: el valor guardado debe estar ya normalizado."""
    if value and normalize_phone_number(value) != value:
        raise ValidationError("El teléfono debe guardarse en formato E.164.", code="invalid_phone")


def age_on(date_of_birth, today):
    """Edad cumplida en `today`. Quien nació un 29 de febrero cumple el 1 de marzo en años no bisiestos."""
    return today.year - date_of_birth.year - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))


def validate_date_of_birth(value, today=None):
    if not isinstance(value, datetime.date) or isinstance(value, datetime.datetime):
        raise ValidationError("Introduce una fecha válida.", code="invalid_date")
    today = today or timezone.localdate()
    if value > today:
        raise ValidationError("La fecha de nacimiento no puede ser futura.", code="future_date")
    age = age_on(value, today)
    if age > MAX_AGE_YEARS:
        raise ValidationError("Revisa la fecha de nacimiento.", code="implausible_date")
    min_age = settings.ACCOUNTS_MIN_CUSTOMER_AGE
    if age < min_age:
        raise ValidationError(
            f"Debes tener al menos {min_age} años para registrarte.", code="under_min_age"
        )
