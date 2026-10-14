"""
Formularios y filtros del dashboard. Solo convierten la entrada: las reglas
(permisos, límites, idempotencia, estados válidos) las aplican los servicios de
dominio, que son los que usará también la API.

Los filtros desconocidos o incorrectos se sustituyen por el valor por defecto
en lugar de dar un error, salvo el rango de fechas personalizado, que avisa.
"""
import datetime
import uuid
from dataclasses import dataclass

from django import forms
from django.utils import timezone

from apps.accounts.countries import COUNTRIES
from apps.accounts.selectors import GEO_LEVEL_LABELS
from apps.catalog.models import Product
from apps.loyalty.models import PointsTransaction
from apps.purchases.models import Purchase
from apps.rewards.models import Redemption

# --- Periodo --------------------------------------------------------------------

PERIOD_PRESETS = (
    ("hoy", "Hoy", 1),
    ("7d", "7 días", 7),
    ("30d", "30 días", 30),
    ("90d", "90 días", 90),
    ("365d", "12 meses", 365),
    ("todo", "Todo", None),
)
CUSTOM_PERIOD = "rango"
DEFAULT_PERIOD = "30d"
MAX_RANGE_DAYS = 3660


def _midnight(day):
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time.min))


@dataclass(frozen=True)
class Period:
    key: str
    label: str
    start: datetime.datetime | None
    end: datetime.datetime | None


def preset_period(key, now=None):
    """Periodo predefinido: desde la medianoche local de hace N-1 días hasta ahora."""
    for value, label, days in PERIOD_PRESETS:
        if value == key:
            if days is None:
                return Period(key, label, None, None)
            first_day = timezone.localdate(now) - datetime.timedelta(days=days - 1)
            return Period(key, label, _midnight(first_day), None)
    raise ValueError(key)


class PeriodForm(forms.Form):
    """`periodo` predefinido o `rango` con `desde` y `hasta` (ambos incluidos)."""

    periodo = forms.ChoiceField(
        choices=[(v, label) for v, label, _ in PERIOD_PRESETS] + [(CUSTOM_PERIOD, "Personalizado")],
        required=False,
    )
    desde = forms.DateField(required=False, label="Desde", widget=forms.DateInput(attrs={"type": "date"}))
    hasta = forms.DateField(required=False, label="Hasta", widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, data=None, *, default=DEFAULT_PERIOD):
        super().__init__(data)
        self.default = default

    def clean(self):
        data = super().clean()
        if data.get("periodo") != CUSTOM_PERIOD:
            return data
        since, until = data.get("desde"), data.get("hasta")
        if not since or not until:
            raise forms.ValidationError("Indica las dos fechas del periodo personalizado.")
        if since > until:
            raise forms.ValidationError("La fecha inicial debe ser anterior o igual a la final.")
        if (until - since).days > MAX_RANGE_DAYS:
            raise forms.ValidationError("El periodo personalizado no puede superar 10 años.")
        return data

    def period(self):
        if not self.is_valid():
            return preset_period(self.default)
        key = self.cleaned_data.get("periodo") or self.default
        if key != CUSTOM_PERIOD:
            return preset_period(key)
        since, until = self.cleaned_data["desde"], self.cleaned_data["hasta"]
        label = f"{since:%d/%m/%Y} – {until:%d/%m/%Y}"
        return Period(CUSTOM_PERIOD, label, _midnight(since), _midnight(until + datetime.timedelta(days=1)))


def _choice(data, name, choices, default=""):
    value = (data or {}).get(name, default)
    return value if value in dict(choices) else default


def _text(data, name, max_length=100):
    return " ".join(str((data or {}).get(name, "")).split())[:max_length]


YES_NO = (("", "Todos"), ("si", "Sí"), ("no", "No"))


def yes_no(value):
    return {"si": True, "no": False}.get(value)


# --- Clientes -------------------------------------------------------------------


class CustomerSearchForm(forms.Form):
    """Búsqueda por nombre, apellidos o email. Se envía por POST y se guarda en la sesión (no va en la URL)."""

    q = forms.CharField(label="Buscar cliente", max_length=100, required=False)


@dataclass(frozen=True)
class CustomerFilters:
    verified: str
    active: str
    promo: str
    country: str
    province: str
    city: str
    postal_code: str

    @classmethod
    def from_query(cls, data):
        return cls(
            verified=_choice(data, "verificado", YES_NO),
            active=_choice(data, "activo", YES_NO),
            promo=_choice(data, "promo", YES_NO),
            country=_choice(data, "pais", COUNTRIES),
            province=_text(data, "provincia"),
            city=_text(data, "localidad"),
            postal_code=_text(data, "cp", 12),
        )


GEO_LEVEL_CHOICES = tuple(GEO_LEVEL_LABELS.items())
GEO_BASE_CHOICES = (("altas", "Clientes dados de alta"), ("compras", "Clientes con compras"))


# --- Listados -------------------------------------------------------------------

PURCHASE_STATUS_CHOICES = (("", "Todos"),) + tuple(Purchase.Status.choices)
REDEMPTION_STATUS_CHOICES = (("", "Todos"),) + tuple(Redemption.Status.choices)
MOVEMENT_KIND_CHOICES = (("", "Todos"),) + tuple(PointsTransaction.Kind.choices)
PRODUCT_STATUS_CHOICES = (("", "Todos"),) + tuple(Product.Status.choices)

choice = _choice


# --- Acciones -------------------------------------------------------------------


class AdjustPointsForm(forms.Form):
    points = forms.IntegerField(
        label="Puntos",
        help_text="Positivo para sumar, negativo para restar. El saldo nunca puede quedar en negativo.",
        widget=forms.NumberInput(attrs={"inputmode": "numeric"}),
    )
    reason = forms.CharField(label="Motivo", max_length=200, help_text="Obligatorio. Queda en el historial del cliente.")
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.setdefault("idempotency_key", uuid.uuid4())


class ReverseMovementForm(forms.Form):
    movement = forms.UUIDField(widget=forms.HiddenInput)
    reason = forms.CharField(label="Motivo de la compensación", max_length=200)


class EmployeeCreateForm(forms.Form):
    first_name = forms.CharField(label="Nombre", max_length=150)
    last_name = forms.CharField(label="Apellidos", max_length=150)
    email = forms.EmailField(label="Email de acceso")
    password1 = forms.CharField(
        label="Contraseña inicial",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Al menos 10 caracteres. Pide al empleado que la cambie al entrar.",
    )
    password2 = forms.CharField(
        label="Repite la contraseña", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )

    def clean(self):
        data = super().clean()
        if data.get("password1") and data.get("password1") != data.get("password2"):
            self.add_error("password2", "Las contraseñas no coinciden.")
        return data


class RoleChangeForm(forms.Form):
    ROLE_CHOICES = (("EMPLOYEE", "Empleado"), ("OWNER", "Propietario"))

    role = forms.ChoiceField(label="Nuevo rol", choices=ROLE_CHOICES)
    confirm = forms.BooleanField(
        label="Confirmo el cambio. Un propietario tiene acceso a todos los datos de los clientes y a la configuración.",
    )


class LoyaltyRuleForm(forms.Form):
    points_per_euro = forms.CharField(
        label="Puntos por euro",
        max_length=10,
        help_text="Por ejemplo 1,00. Se aplica a las compras registradas a partir de ahora; no cambia los puntos ya concedidos.",
        widget=forms.TextInput(attrs={"inputmode": "decimal"}),
    )
    note = forms.CharField(label="Motivo", max_length=200, required=False)


class BusinessInfoForm(forms.Form):
    address = forms.CharField(label="Dirección pública del local", max_length=200, required=False)
    opening_hours = forms.CharField(
        label="Horario",
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Una línea por franja: «Días | horario». Vacío: «Pendiente de publicar».",
    )
    email = forms.EmailField(label="Email de contacto", required=False)
    phone = forms.CharField(label="Teléfono de contacto", max_length=20, required=False)
    social_links = forms.CharField(
        label="Redes sociales",
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Una línea por red: «Nombre | https://…». Solo enlaces https.",
    )
    about_text = forms.CharField(
        label="Presentación de la cervecería",
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 6}),
    )
