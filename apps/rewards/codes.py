"""
Códigos de canje.

12 caracteres elegidos con `secrets` de un alfabeto de 31 símbolos sin los que
se confunden al leerlos o dictarlos (0/O, 1/I/L): unos 59 bits de azar, de modo
que no se pueden adivinar ni deducir de otros códigos. No contienen datos del
cliente ni de la recompensa.

El código se guarda en claro porque el cliente debe poder volver a verlo; por
eso nunca se escribe en logs, auditoría, URLs ni mensajes de error.
"""
from django.utils.translation import gettext_lazy as _
import re
import secrets

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 12
CODE_REGEX = r"^[A-HJKMNP-Z2-9]{12}$"
# Prefijo del contenido del QR del canje. Es distinto del QR personal
# (`CF1:`), así que leer uno en el panel del otro se rechaza sin consultar la BD.
QR_PAYLOAD_PREFIX = "CFR1:"

_CODE_RE = re.compile(CODE_REGEX)
_SEPARATORS_RE = re.compile(r"[\s\-]+")


def generate_code():
    return "".join(secrets.choice(ALPHABET) for _unused in range(CODE_LENGTH))


def format_code(code):
    """Versión legible: «ABCD-EFGH-JKMN»."""
    return "-".join(code[i : i + 4] for i in range(0, len(code), 4))


def qr_payload(code):
    return f"{QR_PAYLOAD_PREFIX}{code}"


def normalize_code(raw):
    """
    Acepta el contenido del QR (`CFR1:…`) o el código tecleado (con espacios,
    guiones o en minúsculas). Devuelve el código o `None`.
    """
    if not isinstance(raw, str) or len(raw) > 100:
        return None
    value = _SEPARATORS_RE.sub("", raw).upper()
    if value.startswith(QR_PAYLOAD_PREFIX):
        value = value[len(QR_PAYLOAD_PREFIX) :]
    return value if _CODE_RE.match(value) else None
