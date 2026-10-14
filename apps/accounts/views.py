"""
Vistas web de cuentas. Solo validan la entrada, comprueban permisos y llaman a
`services`; ninguna recibe identificadores de usuario: siempre actúan sobre
`request.user`, lo que impide acceder a perfiles ajenos (IDOR).
"""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from apps.core import throttling

from . import services
from .forms import (
    CommunicationPreferencesForm,
    EmailChangeForm,
    ProfileForm,
    RegistrationForm,
    ResendVerificationForm,
    ThrottledAuthenticationForm,
    apply_service_errors,
)
from .models import CustomerProfile, User
from .permissions import role_required

_HOUR = 60 * 60


def _ip_limited(request, scope):
    """Cuenta un intento por IP y devuelve True si se supera el límite horario."""
    ip = request.META.get("REMOTE_ADDR", "-")
    limit = settings.PUBLIC_FORM_MAX_PER_IP_PER_HOUR
    if throttling.is_limited(scope, ip, limit):
        return True
    throttling.register_attempt(scope, ip, _HOUR)
    return False


# --- Registro y verificación -----------------------------------------------------


@never_cache
@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:home")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if _ip_limited(request, "register-ip"):
            form.add_error(None, "Demasiados intentos desde tu conexión. Inténtalo más tarde.")
        else:
            try:
                services.register_customer(**form.service_kwargs())
            except services.EmailAlreadyRegistered:
                # Misma respuesta que un registro correcto: no se revela si el email existe.
                services.notify_existing_account(form.cleaned_data["email"])
                return redirect("accounts:register_done")
            except ValidationError as exc:
                apply_service_errors(
                    form, exc, field_map={"password": "password1"}, fallback_field="password1"
                )
            else:
                return redirect("accounts:register_done")
    return render(request, "accounts/register.html", {"form": form})


def register_done(request):
    return render(request, "accounts/register_done.html")


@never_cache
@require_http_methods(["GET", "POST"])
def verify_email(request, token):
    """
    GET muestra un botón de confirmación y POST consume el token: así los
    analizadores de enlaces del correo no gastan el enlace al visitarlo.
    Los errores se muestran con estado 200 para no registrar el token en los
    logs de peticiones 4xx.
    """
    if request.method == "GET":
        return render(request, "accounts/verify_email_confirm.html")
    try:
        user = services.confirm_email_token(token)
    except ValidationError as exc:
        return render(
            request,
            "accounts/verify_email_result.html",
            {"success": False, "error": exc.messages[0], "error_code": exc.code},
        )
    return render(request, "accounts/verify_email_result.html", {"success": True, "verified_user": user})


@never_cache
@require_http_methods(["GET", "POST"])
def resend_verification(request):
    """Reenvío público por email: respuesta idéntica exista o no la cuenta."""
    form = ResendVerificationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not _ip_limited(request, "resend-ip"):
            services.request_verification_resend(form.cleaned_data["email"])
        messages.info(
            request,
            "Si existe una cuenta pendiente de verificación con ese email, recibirás un nuevo enlace.",
        )
        return redirect("accounts:login")
    return render(request, "accounts/resend_verification.html", {"form": form})


@login_required
@require_POST
def resend_verification_self(request):
    try:
        sent = services.resend_verification_email(request.user)
    except services.RateLimited as exc:
        messages.error(request, str(exc))
    else:
        if sent:
            messages.success(request, "Te hemos enviado un nuevo enlace de verificación.")
        else:
            messages.info(request, "Tu email ya está verificado.")
    return redirect("accounts:home")


# --- Cuenta y perfil -----------------------------------------------------------


@login_required
def home(request):
    """Destino tras el login: cada rol a su página."""
    user = request.user
    if user.role == User.Role.CUSTOMER:
        return redirect("accounts:profile")
    if user.role == User.Role.OWNER:
        return redirect("admin:index")
    return redirect("staff:home")


def _profile_initial(user, profile):
    initial = {"first_name": user.first_name, "last_name": user.last_name}
    for name in services.PROFILE_FIELDS:
        initial[name] = getattr(profile, name)
    return initial


@never_cache
@role_required(User.Role.CUSTOMER)
@require_http_methods(["GET", "POST"])
def profile(request):
    user = request.user
    customer_profile = CustomerProfile.objects.filter(user=user).first() or CustomerProfile(user=user)
    if request.method == "POST":
        form = ProfileForm(request.POST)
        if form.is_valid():
            data = dict(form.cleaned_data)
            try:
                services.update_customer_profile(
                    user=user, first_name=data.pop("first_name"), last_name=data.pop("last_name"), **data
                )
            except ValidationError as exc:
                apply_service_errors(form, exc)
            else:
                messages.success(request, "Datos actualizados.")
                return redirect("accounts:profile")
    else:
        form = ProfileForm(initial=_profile_initial(user, customer_profile))
    preferences_form = CommunicationPreferencesForm(
        initial={
            "promo_email_opt_in": customer_profile.promo_email_opt_in,
            "promo_sms_opt_in": customer_profile.promo_sms_opt_in,
        }
    )
    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "preferences_form": preferences_form,
            "customer_profile": customer_profile,
            "missing_fields": customer_profile.missing_required_fields(),
        },
    )


@role_required(User.Role.CUSTOMER)
@require_POST
def preferences(request):
    form = CommunicationPreferencesForm(request.POST)
    if form.is_valid():
        try:
            services.set_communication_preferences(user=request.user, **form.cleaned_data)
        except ValidationError as exc:
            for error in exc.messages:
                messages.error(request, error)
        else:
            messages.success(request, "Preferencias de comunicación guardadas.")
    return redirect(reverse("accounts:profile") + "#preferencias")


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def email_change(request):
    form = EmailChangeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.request_email_change(user=request.user, **form.cleaned_data)
        except services.RateLimited as exc:
            form.add_error(None, str(exc))
        except ValidationError as exc:
            apply_service_errors(form, exc)
        else:
            messages.success(
                request,
                "Si la dirección está disponible, te hemos enviado un enlace para confirmarla. "
                "Tu email actual seguirá siendo el de acceso hasta que lo confirmes.",
            )
            return redirect("accounts:home")
    return render(request, "accounts/email_change.html", {"form": form})


# --- Autenticación (vistas de Django con plantillas y reglas propias) -------------


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = ThrottledAuthenticationForm
    redirect_authenticated_user = True


class PasswordResetView(auth_views.PasswordResetView):
    """Responde igual exista o no la cuenta (comportamiento nativo de Django)."""

    template_name = "accounts/password_reset_form.html"
    email_template_name = "emails/password_reset_body.txt"
    subject_template_name = "emails/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")

    @property
    def extra_email_context(self):
        # El enlace usa SITE_BASE_URL, no la cabecera Host de la petición.
        return {"site_base_url": settings.SITE_BASE_URL}

    def form_valid(self, form):
        if _ip_limited(self.request, "password-reset-ip"):
            return redirect(self.success_url)
        return super().form_valid(form)


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:home")

    def form_valid(self, form):
        messages.success(self.request, "Contraseña cambiada.")
        return super().form_valid(form)
