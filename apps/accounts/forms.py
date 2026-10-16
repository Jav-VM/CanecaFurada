"""
Formularios web de cuentas.

Solo convierten y presentan la entrada: las reglas de negocio (formato de
dirección, teléfono, fecha de nacimiento, contraseña, unicidad del email) las
aplican los servicios, que también usará la futura API. Son `forms.Form` con
campos explícitos: no existe ningún campo de rol, estado o verificación que
pueda asignarse desde el navegador.
"""
from django import forms
from django.conf import settings
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.core.http import client_ip

from . import postal, services, validators
from .countries import COUNTRIES, DEFAULT_COUNTRY
from .models import CustomerProfile

_DATE_WIDGET = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


def _text(label, max_length, required=True, **attrs):
    return forms.CharField(
        label=label,
        max_length=max_length,
        required=required,
        widget=forms.TextInput(attrs=attrs),
    )


class PersonalDataFieldsMixin(forms.Form):
    first_name = _text(_("Nombre"), 150, autocomplete="given-name")
    last_name = _text(_("Apellidos"), 150, autocomplete="family-name")
    date_of_birth = forms.DateField(
        label=_("Fecha de nacimiento"),
        widget=_DATE_WIDGET,
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        help_text=_("Solo la usaremos para tu edad y tus promociones de cumpleaños."),
    )
    sex = forms.ChoiceField(label=_("Sexo"), choices=CustomerProfile.Sex.choices, widget=forms.RadioSelect)
    phone_number = _text(_("Teléfono móvil"), 32, required=False, autocomplete="tel", type="tel")
    country = forms.ChoiceField(label=_("País"), choices=COUNTRIES, initial=DEFAULT_COUNTRY)
    postal_code = _text(_("Código postal"), 12, autocomplete="postal-code", inputmode="numeric")
    # Obligatoria solo si el CP tiene localidades conocidas (lo decide `clean`).
    city = _text(_("Localidad"), 100, required=False, autocomplete="address-level2")
    address_line_1 = _text(_("Dirección"), 200, required=False, autocomplete="address-line1")
    address_line_2 = _text(_("Dirección (línea 2)"), 200, required=False, autocomplete="address-line2")

    sections = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone_number"].help_text = (
            _("Con prefijo internacional si no es español (p. ej. +351…).")
        )
        self.fields["city"].help_text = _(
            "Si tu código postal aparece en la lista, elige tu localidad (datos de %(source)s)."
        ) % {"source": postal.SOURCE_NOTE}
        # Aviso inmediato de edad (JS); el servidor lo vuelve a comprobar al enviar.
        self.fields["date_of_birth"].widget.attrs.update(
            {
                "data-min-age": settings.ACCOUNTS_MIN_CUSTOMER_AGE,
                "data-min-age-message": validators.UNDER_MIN_AGE_MESSAGE,
            }
        )
        self.fields["city"].widget.attrs.update(
            {
                "data-locality-for": self.add_prefix("postal_code"),
                "data-localities-url": reverse("accounts:localities"),
                "data-choose-text": _("Elige tu localidad"),
            }
        )

    def grouped_fields(self):
        """Secciones visuales del formulario para la plantilla: [(título, [campos])]."""
        return [(title, [self[name] for name in names]) for title, names in self.sections]

    # Validación temprana para mostrar todos los errores de una vez. Reutiliza
    # los validadores de dominio; el servicio vuelve a aplicarlos igualmente.
    def clean_phone_number(self):
        return validators.normalize_phone_number(self.cleaned_data.get("phone_number"))

    def clean_date_of_birth(self):
        value = self.cleaned_data["date_of_birth"]
        validators.validate_date_of_birth(value)
        return value

    def clean(self):
        cleaned = super().clean()
        postal_code, country = cleaned.get("postal_code"), cleaned.get("country")
        if postal_code and country:
            postal_code = validators.normalize_postal_code(postal_code)
            try:
                validators.validate_postal_code(postal_code, country)
                cleaned["city"] = postal.canonical_locality(country, postal_code, cleaned.get("city"))
            except ValidationError as exc:
                self.add_error("city" if exc.code in ("locality_required", "invalid_locality") else "postal_code", exc)
        return cleaned

    def locality_options(self):
        """Localidades del CP enviado, para pintar el desplegable sin JS tras un error."""
        source = self.data if self.is_bound else self.initial
        country = source.get(self.add_prefix("country") if self.is_bound else "country") or DEFAULT_COUNTRY
        postal_code = source.get(self.add_prefix("postal_code") if self.is_bound else "postal_code")
        return postal.localities_for(country, validators.normalize_postal_code(postal_code))


class RegistrationForm(PersonalDataFieldsMixin):
    email = forms.EmailField(
        label=_("Email"), max_length=254, widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )
    password1 = forms.CharField(
        label=_("Contraseña"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=_("Mínimo 10 caracteres; no uses una contraseña común ni solo números."),
    )
    password2 = forms.CharField(
        label=_("Repite la contraseña"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    promo_email_opt_in = forms.BooleanField(
        label=_("Quiero recibir promociones y novedades por email."), required=False
    )
    promo_sms_opt_in = forms.BooleanField(
        label=_("Quiero recibir promociones por SMS (requiere teléfono móvil)."), required=False
    )

    sections = (
        (_("Datos personales"), ("first_name", "last_name", "date_of_birth", "sex", "phone_number")),
        (_("Dónde vives"), ("country", "postal_code", "city")),
        (_("Acceso a la cuenta"), ("email", "password1", "password2")),
        (_("Preferencias de comunicación"), ("promo_email_opt_in", "promo_sms_opt_in")),
    )

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", _("Las contraseñas no coinciden."))
        return cleaned

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # El registro solo pide CP y localidad; la calle se puede añadir después en el perfil.
        del self.fields["address_line_1"], self.fields["address_line_2"]

    def service_kwargs(self):
        data = self.cleaned_data
        kwargs = {name: data[name] for name in self.fields if name not in ("password1", "password2")}
        kwargs["password"] = data["password1"]
        return kwargs


class ProfileForm(PersonalDataFieldsMixin):
    sections = (
        (_("Datos personales"), ("first_name", "last_name", "date_of_birth", "sex", "phone_number")),
        (_("Dónde vives"), ("country", "postal_code", "city", "address_line_1", "address_line_2")),
    )


class CommunicationPreferencesForm(forms.Form):
    promo_email_opt_in = forms.BooleanField(
        label=_("Quiero recibir promociones y novedades por email."), required=False
    )
    promo_sms_opt_in = forms.BooleanField(
        label=_("Quiero recibir promociones por SMS (requiere teléfono móvil)."), required=False
    )


class EmailChangeForm(forms.Form):
    new_email = forms.EmailField(
        label=_("Nuevo email"), max_length=254, widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )
    password = forms.CharField(
        label=_("Contraseña actual"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


class ResendVerificationForm(forms.Form):
    email = forms.EmailField(label=_("Email"), max_length=254)


def apply_service_errors(form, exc, field_map=None, fallback_field=None):
    """Traslada un `ValidationError` del servicio a los campos del formulario."""
    field_map = field_map or {}
    if hasattr(exc, "error_dict"):
        for field, messages in exc.message_dict.items():
            target = field_map.get(field, field)
            form.add_error(target if target in form.fields else None, messages)
    else:
        form.add_error(fallback_field, exc.messages)


_THROTTLED = _("Demasiados intentos fallidos. Inténtalo de nuevo en unos minutos.")


class LoginThrottleMixin:
    """
    Límite de intentos fallidos por email y por IP para un formulario de login
    de Django. Web, admin y API comparten los mismos contadores
    (`services.login_throttle_keys`): fallar en uno cuenta para todos.
    """

    def clean(self):
        ip = client_ip(self.request) if self.request else "-"
        keys = services.login_throttle_keys(self.data.get("username", ""), ip)
        if services.login_is_throttled(keys):
            raise ValidationError(self.error_messages["throttled"], code="throttled")
        try:
            return super().clean()
        except ValidationError:
            services.register_login_failure(keys)
            raise


class ThrottledAuthenticationForm(LoginThrottleMixin, AuthenticationForm):
    """Login web. El mensaje es el mismo exista o no la cuenta."""

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": _("Email o contraseña incorrectos."),
        "throttled": _THROTTLED,
    }


class ThrottledAdminAuthenticationForm(LoginThrottleMixin, AdminAuthenticationForm):
    """
    Login del admin técnico (`admin.site.login_form`, en `config/urls.py`). Sin
    él, el login del admin no tenía límite de intentos y la cuenta del
    propietario es superusuario.
    """

    error_messages = {**AdminAuthenticationForm.error_messages, "throttled": _THROTTLED}


class NotifyingPasswordResetForm(PasswordResetForm):
    """
    Recuperación de la cuenta nativa de Django (tokens y caducidad de Django)
    cuyo email sale por el sistema de notificaciones (Fase 10): queda
    registrado como `PASSWORD_RESET` sin guardar el enlace ni el token.
    """

    def send_mail(
        self, subject_template_name, email_template_name, context, from_email, to_email, html_email_template_name=None
    ):
        from . import emails

        emails.send_password_reset(
            user=context["user"],
            to=to_email,
            subject_template=subject_template_name,
            body_template=email_template_name,
            context=context,
        )
