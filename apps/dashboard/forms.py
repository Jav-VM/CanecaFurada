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
from django.utils.translation import gettext_lazy as _

from apps.accounts.countries import COUNTRIES
from apps.accounts.selectors import GEO_LEVEL_LABELS
from apps.catalog.models import BeerStyle, Category, Product, TapMenu
from apps.catalog.validators import validate_image_extension, validate_image_file
from apps.events.models import Event, Reservation
from apps.core.i18n import lazy_format
from apps.loyalty.birthday_settings import PLACEHOLDER
from apps.loyalty.models import BirthdayMessage, PointsExpiryPolicy, PointsTransaction, Promotion
from apps.notifications.models import Campaign, Channel, Notification
from apps.purchases.models import Purchase
from apps.rewards.models import Redemption, Reward

# --- Periodo --------------------------------------------------------------------

PERIOD_PRESETS = (
    ("hoy", _("Hoy"), 1),
    ("7d", _("7 días"), 7),
    ("30d", _("30 días"), 30),
    ("90d", _("90 días"), 90),
    ("365d", _("12 meses"), 365),
    ("todo", _("Todo"), None),
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
        choices=[(v, label) for v, label, _unused in PERIOD_PRESETS] + [(CUSTOM_PERIOD, _("Personalizado"))],
        required=False,
    )
    desde = forms.DateField(required=False, label=_("Desde"), widget=forms.DateInput(attrs={"type": "date"}))
    hasta = forms.DateField(required=False, label=_("Hasta"), widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, data=None, *, default=DEFAULT_PERIOD):
        super().__init__(data)
        self.default = default

    def clean(self):
        data = super().clean()
        if data.get("periodo") != CUSTOM_PERIOD:
            return data
        since, until = data.get("desde"), data.get("hasta")
        if not since or not until:
            raise forms.ValidationError(_("Indica las dos fechas del periodo personalizado."))
        if since > until:
            raise forms.ValidationError(_("La fecha inicial debe ser anterior o igual a la final."))
        if (until - since).days > MAX_RANGE_DAYS:
            raise forms.ValidationError(_("El periodo personalizado no puede superar 10 años."))
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


YES_NO = (("", _("Todos")), ("si", _("Sí")), ("no", _("No")))
# Fase 19: clientes con o sin compras registradas.
SPENT_CHOICES = (("", _("Todos")), ("con", _("Con compras")), ("sin", _("Sin gasto (ninguna compra)")))


def yes_no(value):
    return {"si": True, "no": False}.get(value)


# --- Clientes -------------------------------------------------------------------


class CustomerSearchForm(forms.Form):
    """Búsqueda por nombre, apellidos o email. Se envía por POST y se guarda en la sesión (no va en la URL)."""

    q = forms.CharField(label=_("Buscar cliente"), max_length=100, required=False)


@dataclass(frozen=True)
class CustomerFilters:
    verified: str
    active: str
    promo: str
    country: str
    province: str
    city: str
    postal_code: str
    spent: str = ""

    @property
    def spent_value(self):
        return {"con": True, "sin": False}.get(self.spent)

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
            spent=_choice(data, "gasto", SPENT_CHOICES),
        )


GEO_LEVEL_CHOICES = tuple(GEO_LEVEL_LABELS.items())
GEO_BASE_CHOICES = (("altas", _("Clientes dados de alta")), ("compras", _("Clientes con compras")))


# --- Listados -------------------------------------------------------------------

PURCHASE_STATUS_CHOICES = (("", _("Todos")),) + tuple(Purchase.Status.choices)
REDEMPTION_STATUS_CHOICES = (("", _("Todos")),) + tuple(Redemption.Status.choices)
MOVEMENT_KIND_CHOICES = (("", _("Todos")),) + tuple(PointsTransaction.Kind.choices)
PRODUCT_STATUS_CHOICES = (("", _("Todos")),) + tuple(Product.Status.choices)
EVENT_STATUS_CHOICES = (("", _("Todos")),) + tuple(Event.Status.choices)
RESERVATION_STATUS_CHOICES = (("", _("Todos")),) + tuple(Reservation.Status.choices)
RESERVATION_WHEN_CHOICES = (("proximas", _("Próximas")), ("hoy", _("Hoy")), ("pasadas", _("Pasadas")), ("todas", _("Todas")))
NOTIFICATION_STATUS_CHOICES = (("", _("Todos")),) + tuple(Notification.Status.choices)
NOTIFICATION_KIND_CHOICES = (("", _("Todos")),) + tuple(Notification.Kind.choices)

choice = _choice


# --- Acciones -------------------------------------------------------------------


class AdjustPointsForm(forms.Form):
    points = forms.IntegerField(
        label=_("Puntos"),
        help_text=_("Positivo para sumar, negativo para restar. El saldo nunca puede quedar en negativo."),
        widget=forms.NumberInput(attrs={"inputmode": "numeric"}),
    )
    reason = forms.CharField(label=_("Motivo"), max_length=200, help_text=_("Obligatorio. Queda en el historial del cliente."))
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.setdefault("idempotency_key", uuid.uuid4())


class ReverseMovementForm(forms.Form):
    movement = forms.UUIDField(widget=forms.HiddenInput)
    reason = forms.CharField(label=_("Motivo de la compensación"), max_length=200)


class EmployeeCreateForm(forms.Form):
    first_name = forms.CharField(label=_("Nombre"), max_length=150)
    last_name = forms.CharField(label=_("Apellidos"), max_length=150)
    email = forms.EmailField(label=_("Email de acceso"))
    password1 = forms.CharField(
        label=_("Contraseña inicial"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=_("Al menos 10 caracteres. Pide al empleado que la cambie al entrar."),
    )
    password2 = forms.CharField(
        label=_("Repite la contraseña"), strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )

    def clean(self):
        data = super().clean()
        if data.get("password1") and data.get("password1") != data.get("password2"):
            self.add_error("password2", _("Las contraseñas no coinciden."))
        return data


class RoleChangeForm(forms.Form):
    ROLE_CHOICES = (("EMPLOYEE", _("Empleado")), ("OWNER", _("Propietario")))

    role = forms.ChoiceField(label=_("Nuevo rol"), choices=ROLE_CHOICES)
    confirm = forms.BooleanField(
        label=_("Confirmo el cambio. Un propietario tiene acceso a todos los datos de los clientes y a la configuración."),
    )


class LoyaltyRuleForm(forms.Form):
    points_per_euro = forms.CharField(
        label=_("Puntos por euro"),
        max_length=10,
        help_text=_("Por ejemplo 1,00. Se aplica a las compras registradas a partir de ahora; no cambia los puntos ya concedidos."),
        widget=forms.TextInput(attrs={"inputmode": "decimal"}),
    )
    note = forms.CharField(label=_("Motivo"), max_length=200, required=False)


class PointsExpiryForm(forms.Form):
    """Caducidad de los puntos (Fase 14). Desde cuándo cuenta el plazo lo decide el servicio."""

    enabled = forms.BooleanField(label=_("Los puntos caducan"), required=False)
    months = forms.IntegerField(
        label=_("Meses de validez"),
        required=False,
        min_value=1,
        max_value=PointsExpiryPolicy.MAX_MONTHS,
        help_text=_("Cada punto caduca estos meses después de ganarlo. Se gastan primero los más antiguos."),
    )
    warn_days = forms.IntegerField(
        label=_("Días de aviso"),
        min_value=1,
        max_value=PointsExpiryPolicy.MAX_WARN_DAYS,
        initial=PointsExpiryPolicy.DEFAULT_WARN_DAYS,
        help_text=_("Con cuántos días de antelación se avisa por email al cliente."),
    )
    note = forms.CharField(label=_("Motivo"), max_length=200, required=False)

    def clean(self):
        data = super().clean()
        if data.get("enabled") and not data.get("months"):
            self.add_error("months", _("Indica cuántos meses son válidos los puntos."))
        return data


class BirthdayGiftForm(forms.Form):
    """Regalo y aviso de cumpleaños (Fase 14). Los textos vacíos usan el mensaje por defecto."""

    active = forms.BooleanField(label=_("Regalar puntos por el cumpleaños"), required=False)
    points = forms.IntegerField(
        label=_("Puntos de regalo"), min_value=1, max_value=Promotion.MAX_FIXED_POINTS
    )
    email_subject = forms.CharField(
        label=_("Asunto del email"),
        max_length=BirthdayMessage.MAX_SUBJECT,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": _("¡Feliz cumpleaños de parte de Caneca Furada!")}),
    )
    email_body = forms.CharField(
        label=_("Mensaje del email"),
        max_length=BirthdayMessage.MAX_EMAIL_BODY,
        required=False,
        widget=forms.Textarea(attrs={"rows": 6, "placeholder": _("Vacío: se envía el mensaje por defecto.")}),
        help_text=(
            lazy_format(_("Texto plano. Escribe %(PLACEHOLDER)s donde quieras mostrar los puntos regalados. Se añade siempre el enlace de baja. No incluyas datos personales."), {"PLACEHOLDER": PLACEHOLDER})
        ),
    )
    sms_body = forms.CharField(
        label=_("Mensaje SMS"),
        max_length=BirthdayMessage.MAX_SMS_BODY,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": _("¡Feliz cumpleaños! Te hemos regalado {puntos} puntos.")}),
        help_text=lazy_format(_("Una línea. Va precedido de «Caneca Furada:» y seguido del enlace de baja. Admite %(PLACEHOLDER)s."), {"PLACEHOLDER": PLACEHOLDER}),
    )


class OnlineReservationsForm(forms.Form):
    """Interruptor de las reservas online (Fase 17)."""

    enabled = forms.BooleanField(
        label=_("Reservas online activadas"),
        required=False,
        help_text=_("Desactivadas, los botones de reserva llevan a Contacto con el aviso de reservar por teléfono."),
    )


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    """Varias imágenes en un solo campo (Fase 21). Cada una pasa la validación de `ImageField`."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleImageInput(attrs={"accept": "image/jpeg,image/png,image/webp"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else [data]
        return [super(MultipleImageField, self).clean(item, initial) for item in files if item]


class PageBlockForm(forms.Form):
    """Textos de una sección o artículo (Fase 21). Vacío: el texto por defecto de la sección."""

    eyebrow = forms.CharField(label=_("Antetítulo"), max_length=80, required=False)
    title = forms.CharField(label=_("Título"), max_length=120, required=False)
    body = forms.CharField(
        label=_("Texto"),
        max_length=5000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 8}),
        help_text=_("Texto plano: deja una línea en blanco entre párrafos. Se muestra tal cual en gallego y en castellano."),
    )
    images = MultipleImageField(
        label=_("Añadir imágenes"),
        required=False,
        validators=[validate_image_extension, validate_image_file],
        help_text=_("JPEG, PNG o WebP. Una imagen se muestra junto al texto; dos o más, en un carrusel en su lugar."),
    )

    def __init__(self, *args, defaults=("", "", None), images=True, article=False, **kwargs):
        super().__init__(*args, **kwargs)
        eyebrow, title, body = defaults
        for name, value in (("eyebrow", eyebrow), ("title", title), ("body", body)):
            if value:
                self.fields[name].widget.attrs["placeholder"] = str(value)
        if article:
            self.fields["title"].required = True
        if not images:
            del self.fields["images"]


class BusinessInfoForm(forms.Form):
    address = forms.CharField(label=_("Dirección pública del local"), max_length=200, required=False)
    # Fase 23: lo valida el modelo (solo enlaces de Google Maps).
    maps_url = forms.CharField(
        label=_("Enlace a Google Maps"),
        max_length=300,
        required=False,
        widget=forms.TextInput(attrs={"inputmode": "url", "autocomplete": "off", "spellcheck": "false"}),
        help_text=_("La dirección de Contacto y del pie lleva a este enlace. En Google Maps: «Compartir» → «Copiar enlace». Vacío: el enlace de siempre."),
    )
    opening_hours = forms.CharField(
        label=_("Horario"),
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text=_("Una línea por franja: «Días | horario». Vacío: «Pendiente de publicar»."),
    )
    email = forms.EmailField(label=_("Email de contacto"), required=False)
    phone = forms.CharField(label=_("Teléfono de contacto"), max_length=20, required=False)
    social_links = forms.CharField(
        label=_("Redes sociales"),
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text=_("Una línea por red: «Nombre | https://…». Solo enlaces https."),
    )
    about_text = forms.CharField(
        label=_("Presentación de la cervecería"),
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 6}),
    )
    hero_text = forms.CharField(
        label=_("Texto de bienvenida del inicio"),
        required=False,
        max_length=300,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text=_("Frase bajo el lema en la portada. Vacío: el texto genérico de la marca."),
    )
    announcement = forms.CharField(
        label=_("Aviso destacado"),
        required=False,
        max_length=200,
        help_text=_("Se muestra en una franja al principio del inicio (cierre por vacaciones, novedades…). Vacío: sin aviso."),
    )
    # Fase 25: titular del sitio para el aviso legal y la política de privacidad.
    legal_name = forms.CharField(label=_("Titular (nombre o razón social)"), max_length=200, required=False)
    tax_id = forms.CharField(label=_("NIF/CIF del titular"), max_length=12, required=False)
    legal_address = forms.CharField(label=_("Domicilio del titular"), max_length=300, required=False)
    legal_email = forms.EmailField(
        label=_("Email de contacto legal"),
        required=False,
        help_text=_("Para ejercer los derechos de protección de datos. Vacío: se usa el email de contacto."),
    )
    registry_data = forms.CharField(
        label=_("Datos registrales"),
        max_length=300,
        required=False,
        help_text=_("Solo si la empresa está inscrita (Registro Mercantil: tomo, folio, hoja)."),
    )


class LegalDocumentForm(forms.Form):
    """Texto de un documento legal (Fase 25). Lo valida y versiona `apps.web.legal.save_document`."""

    body = forms.CharField(
        label=_("Texto"),
        max_length=30000,
        widget=forms.Textarea(attrs={"rows": 24}),
        help_text=_("Texto plano: deja una línea en blanco entre párrafos. Revísalo con tu asesor antes de publicarlo; se muestra tal cual en gallego y en castellano."),
    )


# --- Eventos, reservas y comunicaciones (Fase 10) -------------------------------

_DATETIME_WIDGET = {"type": "datetime-local"}


class EventForm(forms.ModelForm):
    """Solo convierte la entrada: `events.services.save_event` valida y guarda."""

    class Meta:
        model = Event
        fields = (
            "title",
            "summary",
            "description",
            "starts_at",
            "ends_at",
            "image",
            "is_featured",
            "accepts_reservations",
            "capacity",
        )
        widgets = {
            "starts_at": forms.DateTimeInput(attrs=_DATETIME_WIDGET, format="%Y-%m-%dT%H:%M"),
            "ends_at": forms.DateTimeInput(attrs=_DATETIME_WIDGET, format="%Y-%m-%dT%H:%M"),
            "description": forms.Textarea(attrs={"rows": 6}),
        }

    def service_data(self):
        data = {name: self.cleaned_data.get(name) for name in self.Meta.fields}
        if data["image"] is False:  # «Eliminar» en el campo de imagen
            data["image"] = ""
        elif data["image"] is None:
            data.pop("image")
        return data


class ReservationActionForm(forms.Form):
    ACTIONS = (("confirmar", _("Confirmar")), ("rechazar", _("Rechazar")), ("cancelar", _("Cancelar")), ("completar", _("Completar")))

    accion = forms.ChoiceField(choices=ACTIONS)
    mensaje = forms.CharField(
        label=_("Mensaje para el cliente"),
        required=False,
        max_length=300,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text=_("Opcional. Se muestra al cliente y va en el email. No incluyas datos personales."),
    )


class CampaignForm(forms.Form):
    """
    Formulario único de campaña (Fase 19). Obligatorios: nombre, asunto y
    texto. Los destinatarios seleccionados no llegan por el formulario: salen
    de la sesión (Clientes) o de la campaña guardada.
    """

    name = forms.CharField(label=_("Nombre"), max_length=100, help_text=_("Solo lo ves tú."))
    subject = forms.CharField(
        label=_("Asunto"), max_length=120, help_text=_("Asunto del email. En SMS solo sirve para identificar el envío.")
    )
    # Sin valor: todos los clientes con consentimiento (el comportamiento anterior a la Fase 19).
    audience = forms.ChoiceField(
        label=_("Destinatarios"), choices=Campaign.Audience.choices, widget=forms.RadioSelect, required=False
    )
    channel = forms.ChoiceField(label=_("Canal"), choices=Channel.choices, required=False)
    body = forms.CharField(
        label=_("Texto"),
        max_length=Campaign.MAX_EMAIL_BODY,
        widget=forms.Textarea(attrs={"rows": 8}),
        help_text=(
            lazy_format(_("Texto plano. Email: hasta %(MAX_EMAIL_BODY)s caracteres; SMS: hasta %(MAX_SMS_BODY)s. Se añade siempre el enlace de baja. No incluyas datos personales."), {"MAX_EMAIL_BODY": Campaign.MAX_EMAIL_BODY, "MAX_SMS_BODY": Campaign.MAX_SMS_BODY})
        ),
    )
    image = forms.ImageField(
        label=_("Imagen"),
        required=False,
        validators=[validate_image_extension, validate_image_file],
        help_text=_("Opcional. JPEG, PNG o WebP. Solo se envía por email."),
    )
    clear_image = forms.BooleanField(label=_("Quitar la imagen actual"), required=False)
    gift_points = forms.IntegerField(
        label=_("Puntos de regalo"),
        required=False,
        min_value=1,
        max_value=Campaign.MAX_GIFT_POINTS,
        help_text=_("Opcional. Se suman al saldo de cada destinatario al repartir la campaña, una sola vez."),
    )
    gift_points_expire = forms.TypedChoiceField(
        label=_("Caducidad de los puntos de regalo"),
        choices=(("si", _("Caducan según la configuración de caducidad")), ("no", _("No caducan nunca"))),
        coerce=lambda value: value == "si",
        initial="si",
        required=False,
        empty_value=True,
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, initial=None, **kwargs):
        initial = dict(initial or {})
        if "gift_points_expire" in initial:
            initial["gift_points_expire"] = "si" if initial["gift_points_expire"] else "no"
        super().__init__(*args, initial=initial, **kwargs)

    def clean_channel(self):
        return self.cleaned_data.get("channel") or Channel.EMAIL

    def clean_audience(self):
        return self.cleaned_data.get("audience") or Campaign.Audience.ALL


def reservation_period(key, now=None):
    """(inicio, fin, orden descendente) de la fecha de la reserva según el filtro."""
    now = now or timezone.now()
    today = _midnight(timezone.localdate(now))
    if key == "hoy":
        return today, today + datetime.timedelta(days=1), False
    if key == "pasadas":
        return None, now, True
    if key == "todas":
        return None, None, True
    return today, None, False


# --- Fichas de la carta, recompensas y promociones (Fase 24) ----------------------
# Sustituyen a los formularios del admin. Solo convierten la entrada: valida y guarda
# el servicio de cada dominio. El estado (publicar, activar, archivar…) no está aquí:
# se cambia con los botones de cada listado.


class _ImageServiceDataMixin:
    """`service_data()` como en `EventForm`: «Eliminar» deja la imagen vacía y sin fichero nuevo no se toca."""

    def service_data(self):
        data = {name: self.cleaned_data.get(name) for name in self.Meta.fields}
        if "image" in data:
            if data["image"] is False:
                data["image"] = ""
            elif "image" not in self.changed_data:
                data.pop("image")
        return data


class ProductForm(_ImageServiceDataMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "category", "kind", "name", "description", "style", "abv", "brewery",
            "price", "serving", "image", "position", "is_featured",
        )
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "slug", "description", "position", "is_published")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
        help_texts = {"slug": _("Vacío: se genera a partir del nombre. Se usa como ancla en la carta (/carta/#identificador).")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False

    def service_data(self):
        return {name: self.cleaned_data.get(name) for name in self.Meta.fields}


class BeerStyleForm(forms.ModelForm):
    class Meta:
        model = BeerStyle
        fields = ("name",)

    def service_data(self):
        return {"name": self.cleaned_data.get("name")}


class TapMenuForm(_ImageServiceDataMixin, forms.ModelForm):
    class Meta:
        model = TapMenu
        fields = ("title", "image", "text_alternative", "is_published")
        widgets = {"text_alternative": forms.Textarea(attrs={"rows": 6})}


class RewardForm(forms.ModelForm):
    class Meta:
        model = Reward
        fields = ("name", "description", "image", "points_cost", "stock", "valid_from", "valid_until", "position")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "valid_from": forms.DateTimeInput(attrs=_DATETIME_WIDGET, format="%Y-%m-%dT%H:%M"),
            "valid_until": forms.DateTimeInput(attrs=_DATETIME_WIDGET, format="%Y-%m-%dT%H:%M"),
        }


class PromotionForm(forms.ModelForm):
    class Meta:
        model = Promotion
        fields = (
            "name", "description", "kind", "bonus_type", "fixed_points", "multiplier", "min_purchase_amount",
            "starts_at", "ends_at", "max_uses_per_customer", "max_total_uses",
        )
        widgets = {
            "starts_at": forms.DateTimeInput(attrs=_DATETIME_WIDGET, format="%Y-%m-%dT%H:%M"),
            "ends_at": forms.DateTimeInput(attrs=_DATETIME_WIDGET, format="%Y-%m-%dT%H:%M"),
        }
