"""
Formularios web de cuentas.

Solo convierten y presentan la entrada: las reglas de negocio (formato de
dirección, teléfono, fecha de nacimiento, contraseña, unicidad del email) las
aplican los servicios, que también usará la futura API. Son `forms.Form` con
campos explícitos: no existe ningún campo de rol, estado o verificación que
pueda asignarse desde el navegador.
"""
from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.core.exceptions import ValidationError

from apps.core.http import client_ip

from . import services, validators
from .countries import COUNTRIES, DEFAULT_COUNTRY

_DATE_WIDGET = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


def _text(label, max_length, required=True, **attrs):
    return forms.CharField(
        label=label,
        max_length=max_length,
        required=required,
        widget=forms.TextInput(attrs=attrs),
    )


class PersonalDataFieldsMixin(forms.Form):
    first_name = _text("Nombre", 150, autocomplete="given-name")
    last_name = _text("Apellidos", 150, autocomplete="family-name")
    date_of_birth = forms.DateField(
        label="Fecha de nacimiento",
        widget=_DATE_WIDGET,
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        help_text="Solo la usaremos para tu edad y tus promociones de cumpleaños.",
    )
    phone_number = _text("Teléfono móvil", 32, required=False, autocomplete="tel", type="tel")
    address_line_1 = _text("Dirección", 200, autocomplete="address-line1")
    address_line_2 = _text("Dirección (línea 2)", 200, required=False, autocomplete="address-line2")
    postal_code = _text("Código postal", 12, autocomplete="postal-code")
    city = _text("Localidad", 100, autocomplete="address-level2")
    province = _text("Provincia", 100, autocomplete="address-level1")
    country = forms.ChoiceField(label="País", choices=COUNTRIES, initial=DEFAULT_COUNTRY)

    sections = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone_number"].help_text = (
            "Con prefijo internacional si no es español (p. ej. +351…)."
        )
        self.fields["province"].help_text = "Provincia, estado o región."

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
            try:
                validators.validate_postal_code(validators.normalize_postal_code(postal_code), country)
            except ValidationError as exc:
                self.add_error("postal_code", exc)
        return cleaned


class RegistrationForm(PersonalDataFieldsMixin):
    email = forms.EmailField(
        label="Email", max_length=254, widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )
    password1 = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Mínimo 10 caracteres; no uses una contraseña común ni solo números.",
    )
    password2 = forms.CharField(
        label="Repite la contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    promo_email_opt_in = forms.BooleanField(
        label="Quiero recibir promociones y novedades por email.", required=False
    )
    promo_sms_opt_in = forms.BooleanField(
        label="Quiero recibir promociones por SMS (requiere teléfono móvil).", required=False
    )

    sections = (
        ("Datos personales", ("first_name", "last_name", "date_of_birth", "phone_number")),
        (
            "Dirección postal",
            ("address_line_1", "address_line_2", "postal_code", "city", "province", "country"),
        ),
        ("Acceso a la cuenta", ("email", "password1", "password2")),
        ("Preferencias de comunicación", ("promo_email_opt_in", "promo_sms_opt_in")),
    )

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        return cleaned

    def service_kwargs(self):
        data = self.cleaned_data
        kwargs = {name: data[name] for name in self.fields if name not in ("password1", "password2")}
        kwargs["password"] = data["password1"]
        return kwargs


class ProfileForm(PersonalDataFieldsMixin):
    sections = (
        ("Datos personales", ("first_name", "last_name", "date_of_birth", "phone_number")),
        (
            "Dirección postal",
            ("address_line_1", "address_line_2", "postal_code", "city", "province", "country"),
        ),
    )


class CommunicationPreferencesForm(forms.Form):
    promo_email_opt_in = forms.BooleanField(
        label="Quiero recibir promociones y novedades por email.", required=False
    )
    promo_sms_opt_in = forms.BooleanField(
        label="Quiero recibir promociones por SMS (requiere teléfono móvil).", required=False
    )


class EmailChangeForm(forms.Form):
    new_email = forms.EmailField(
        label="Nuevo email", max_length=254, widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )
    password = forms.CharField(
        label="Contraseña actual",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


class ResendVerificationForm(forms.Form):
    email = forms.EmailField(label="Email", max_length=254)


def apply_service_errors(form, exc, field_map=None, fallback_field=None):
    """Traslada un `ValidationError` del servicio a los campos del formulario."""
    field_map = field_map or {}
    if hasattr(exc, "error_dict"):
        for field, messages in exc.message_dict.items():
            target = field_map.get(field, field)
            form.add_error(target if target in form.fields else None, messages)
    else:
        form.add_error(fallback_field, exc.messages)


_THROTTLED = "Demasiados intentos fallidos. Inténtalo de nuevo en unos minutos."


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
        "invalid_login": "Email o contraseña incorrectos.",
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
