"""
Servicios de cuentas y roles.

Son la única vía de negocio para crear usuarios o cambiar roles: las vistas
web, el admin, los comandos y la futura API deben llamarlos en lugar de
modificar los modelos directamente. El rol nunca se toma de datos del cliente
en flujos públicos.
"""
import datetime
import secrets

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext_lazy as _

from apps.core import throttling
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event

from . import emails
from .models import CommunicationPreferenceChange, CustomerProfile, EmailVerificationToken, User
from .normalization import normalize_email_address
from .validators import normalize_phone_number, normalize_text

Role = User.Role
TokenPurpose = EmailVerificationToken.Purpose
Channel = CommunicationPreferenceChange.Channel
Source = CommunicationPreferenceChange.Source

# Campos del perfil que el cliente puede editar (lista blanca contra asignación masiva).
PROFILE_FIELDS = (
    "address_line_1",
    "address_line_2",
    "postal_code",
    "city",
    "province",
    "country",
    "date_of_birth",
    "sex",
    "phone_number",
)


class EmailAlreadyRegistered(ValidationError):
    """
    El email ya pertenece a una cuenta. La web no lo revela (responde igual que
    un registro correcto y avisa al titular por email); la futura API debe
    hacer lo mismo.
    """

    def __init__(self):
        super().__init__({"email": _("Ya existe una cuenta con este email.")}, code="email_taken")


class RateLimited(Exception):
    """Se ha superado el límite de envíos de verificación para la cuenta."""

_CREATION_ACTIONS = {
    Role.OWNER: AuditEvent.Action.OWNER_CREATED,
    Role.EMPLOYEE: AuditEvent.Action.EMPLOYEE_CREATED,
    Role.CUSTOMER: AuditEvent.Action.CUSTOMER_CREATED,
}


def _apply_role_flags(user):
    """El acceso al admin técnico se deriva del rol, nunca de datos externos."""
    is_owner = user.role == Role.OWNER
    user.is_staff = is_owner
    user.is_superuser = is_owner


def _ensure_active_owner(actor):
    """Comprueba en BD (no en el objeto en memoria) que el actor es propietario activo."""
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise PermissionDenied(_("Operación reservada al propietario."))
    if not User.objects.filter(pk=actor.pk, role=Role.OWNER, is_active=True).exists():
        raise PermissionDenied(_("Operación reservada al propietario."))


def _lock_active_owners(actor):
    """
    Bloquea las filas de los propietarios activos, comprueba que `actor` sigue
    siendo uno de ellos y devuelve cuántos hay.

    Serializa los cambios de rol y de activación concurrentes: dos
    propietarios no pueden retirarse a la vez y dejar el sistema sin ninguno.
    Debe llamarse **antes** de bloquear la fila del usuario afectado, y las
    filas se bloquean en orden de pk: con un único orden de bloqueo, dos
    operaciones simultáneas esperan su turno en lugar de interbloquearse.

    El actor se vuelve a comprobar con los bloqueos tomados: si otro
    propietario lo retiró mientras esperaba, ya no está autorizado.
    (`count()` no admite `SELECT ... FOR UPDATE`; por eso se materializan los ids.)
    """
    owner_ids = list(
        User.objects.select_for_update()
        .filter(role=Role.OWNER, is_active=True)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    if actor.pk not in owner_ids:
        raise PermissionDenied(_("Operación reservada al propietario."))
    return len(owner_ids)


def ensure_customer_profile(user):
    """
    Devuelve el perfil del cliente y lo crea si no existe. Es idempotente.

    Debe llamarse dentro de la transacción que da de alta al cliente o le asigna
    el rol CUSTOMER, para que nunca quede un cliente sin perfil.
    """
    profile, _unused = CustomerProfile.objects.get_or_create(user=user)
    return profile


def _create_user(*, role, email, first_name, last_name, password, actor=None, instance=None):
    user = instance if instance is not None else User()
    user.email = normalize_email_address(email)
    user.first_name = first_name
    user.last_name = last_name
    user.role = role
    _apply_role_flags(user)

    user.full_clean(exclude=["password"])
    validate_password(password, user)
    user.set_password(password)

    try:
        with transaction.atomic():
            user.save()
    except IntegrityError as exc:
        # Carrera entre dos altas con el mismo email: la restricción única decide.
        raise EmailAlreadyRegistered() from exc

    if role == Role.CUSTOMER:
        ensure_customer_profile(user)

    record_audit_event(
        action=_CREATION_ACTIONS[role],
        actor=actor,
        target=user,
        metadata={"role": role},
    )
    return user


@transaction.atomic
def create_customer(*, email, first_name, last_name, password):
    """Alta de cliente. Es el único rol que puede crearse sin un actor autorizado."""
    return _create_user(
        role=Role.CUSTOMER,
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=password,
    )


@transaction.atomic
def create_employee(*, actor, email, first_name, last_name, password):
    """Alta de empleado, reservada al propietario."""
    _ensure_active_owner(actor)
    return _create_user(
        role=Role.EMPLOYEE,
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=password,
        actor=actor,
    )


@transaction.atomic
def create_owner(*, email, first_name, last_name, password, actor=None):
    """
    Alta de propietario.

    Sin `actor` solo se permite si todavía no existe ningún propietario
    (procedimiento administrativo inicial `create_owner`). Con `actor`, este
    debe ser un propietario activo.
    """
    if actor is None:
        # Bloquea las filas de propietarios para serializar altas concurrentes.
        if list(User.objects.select_for_update().filter(role=Role.OWNER)):
            raise PermissionDenied(
                _("Ya existe un propietario. Los siguientes deben crearse por un propietario.")
            )
    else:
        _ensure_active_owner(actor)
    return _create_user(
        role=Role.OWNER,
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=password,
        actor=actor,
    )


@transaction.atomic
def create_user_by_owner(*, actor, role, email, first_name, last_name, password, instance=None):
    """Alta de cualquier rol por un propietario (usado por el admin)."""
    _ensure_active_owner(actor)
    if role not in Role.values:
        raise ValidationError({"role": _("Rol no válido.")})
    return _create_user(
        role=role,
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=password,
        actor=actor,
        instance=instance,
    )


@transaction.atomic
def change_role(*, actor, user, new_role):
    """
    Cambia el rol de un usuario. Solo un propietario activo puede hacerlo y
    nunca puede quedar el sistema sin propietarios activos.
    """
    _ensure_active_owner(actor)
    if new_role not in Role.values:
        raise ValidationError({"role": _("Rol no válido.")})

    active_owners = _lock_active_owners(actor)
    target = User.objects.select_for_update().get(pk=user.pk)
    old_role = target.role
    if old_role == new_role:
        return target

    if old_role == Role.OWNER and target.is_active and active_owners <= 1:
        raise ValidationError(_("No se puede retirar el rol al último propietario activo."))

    target.role = new_role
    _apply_role_flags(target)
    target.save(update_fields=["role", "is_staff", "is_superuser"])
    if new_role == Role.CUSTOMER:
        ensure_customer_profile(target)

    record_audit_event(
        action=AuditEvent.Action.ROLE_CHANGED,
        actor=actor,
        target=target,
        metadata={"from": old_role, "to": new_role},
    )
    # Mantiene coherente el objeto recibido por quien llama.
    user.role = target.role
    user.is_staff = target.is_staff
    user.is_superuser = target.is_superuser
    return target


@transaction.atomic
def set_user_active(*, actor, user, is_active):
    """
    Activa o desactiva una cuenta (autorizar o dar de baja a un empleado, por
    ejemplo). Solo un propietario activo; nunca deja el sistema sin propietarios
    activos. Una cuenta desactivada no puede iniciar sesión.
    """
    _ensure_active_owner(actor)
    active_owners = _lock_active_owners(actor)
    target = User.objects.select_for_update().get(pk=user.pk)
    if target.is_active == is_active:
        return target
    if not is_active and target.role == Role.OWNER and active_owners <= 1:
        raise ValidationError(_("No se puede desactivar al último propietario activo."))
    target.is_active = is_active
    target.save(update_fields=["is_active"])
    record_audit_event(
        action=AuditEvent.Action.ACCOUNT_ACTIVATED if is_active else AuditEvent.Action.ACCOUNT_DEACTIVATED,
        actor=actor,
        target=target,
        metadata={"role": target.role},
    )
    user.is_active = target.is_active
    return target


def record_customer_data_access(*, actor, customer):
    """
    Deja constancia de que el propietario abrió la ficha completa de un cliente
    (Fase 9): quién, cuándo y de qué cliente (por `public_id`), sin los datos.
    """
    _ensure_active_owner(actor)
    record_audit_event(action=AuditEvent.Action.CUSTOMER_DATA_VIEWED, actor=actor, target=customer)


# --- Registro público ---------------------------------------------------------


def _coerce_date(value, field):
    """Acepta `date` o texto ISO (API); rechaza fechas imposibles como 2001-02-30."""
    if isinstance(value, datetime.datetime):
        raise ValidationError({field: _("Introduce una fecha válida.")})
    try:
        return models.DateField().to_python(value)
    except ValidationError:
        raise ValidationError({field: _("Introduce una fecha válida.")}) from None


def _apply_profile_data(profile, data):
    """Asigna solo los campos permitidos, normalizados. No guarda."""
    errors = {}
    for name in PROFILE_FIELDS:
        if name not in data:
            continue
        value = data[name]
        try:
            if name == "phone_number":
                value = normalize_phone_number(value)
            elif name == "date_of_birth":
                value = _coerce_date(value, name) if value not in (None, "") else None
            else:
                value = normalize_text(value)
        except ValidationError as exc:
            errors[name] = exc.messages
            continue
        setattr(profile, name, value)
    if errors:
        raise ValidationError(errors)


def _validate_complete_profile(profile):
    errors = {}
    try:
        profile.full_clean(exclude=["user"])
    except ValidationError as exc:
        errors.update(exc.message_dict)
    for name in profile.missing_required_fields():
        errors.setdefault(name, [_("Este campo es obligatorio.")])
    if errors:
        raise ValidationError(errors)


def _validate_registration(profile, email, first_name, last_name, password):
    """Todas las validaciones del registro salvo la unicidad del email, con todos los errores a la vez."""
    errors = {}
    try:
        _validate_complete_profile(profile)
    except ValidationError as exc:
        errors.update(exc.message_dict)
    candidate = User(email=email, first_name=first_name, last_name=last_name, role=Role.CUSTOMER)
    try:
        candidate.full_clean(exclude=["password"], validate_unique=False, validate_constraints=False)
    except ValidationError as exc:
        errors.update(exc.message_dict)
    try:
        validate_password(password, candidate)
    except ValidationError as exc:
        errors.setdefault("password", []).extend(exc.messages)
    if errors:
        raise ValidationError(errors)


# --- Inicio de sesión ---------------------------------------------------------------


def login_throttle_keys(email, ip):
    """Contadores de intentos fallidos de login (web y API comparten los mismos)."""
    return (
        ("login-email", normalize_email_address(email or "") or "-", settings.LOGIN_MAX_FAILURES_PER_EMAIL),
        ("login-ip", ip or "-", settings.LOGIN_MAX_FAILURES_PER_IP),
    )


def login_is_throttled(keys):
    return any(throttling.is_limited(scope, ident, limit) for scope, ident, limit in keys)


def register_login_failure(keys):
    for scope, ident, _unused in keys:
        throttling.register_attempt(scope, ident, settings.LOGIN_FAILURE_WINDOW_SECONDS)


def _record_preference(user, channel, opted_in, source):
    CommunicationPreferenceChange.objects.create(
        user=user, channel=channel, opted_in=opted_in, source=source
    )


def register_customer(
    *,
    email,
    password,
    first_name,
    last_name,
    postal_code,
    country,
    date_of_birth,
    sex,
    city="",
    address_line_1="",
    address_line_2="",
    province="",
    phone_number="",
    promo_email_opt_in=False,
    promo_sms_opt_in=False,
):
    """
    Registro público de un cliente con todos sus datos obligatorios.

    De la dirección solo es obligatorio el código postal (Fase 16). En España la
    provincia se deduce del CP y la localidad debe ser una de las de ese CP
    cuando hay datos (`CustomerProfile.clean`).

    - Siempre crea el rol CUSTOMER (no acepta `role`) con el email pendiente de
      verificación.
    - Valida todos los datos en servidor; nada se guarda si algo falla.
    - Registra el estado inicial de los dos consentimientos promocionales.
    - Emite un token de verificación y envía el email al confirmar la transacción.

    Lanza `EmailAlreadyRegistered` si el email ya existe (ver su docstring).
    """
    with transaction.atomic():
        email = normalize_email_address(email)
        first_name, last_name = normalize_text(first_name), normalize_text(last_name)
        profile = CustomerProfile(
            promo_email_opt_in=bool(promo_email_opt_in),
            promo_sms_opt_in=bool(promo_sms_opt_in),
        )
        _apply_profile_data(
            profile,
            {
                "address_line_1": address_line_1,
                "address_line_2": address_line_2,
                "postal_code": postal_code,
                "city": city,
                "province": province,
                "country": country,
                "date_of_birth": date_of_birth,
                "sex": sex,
                "phone_number": phone_number,
            },
        )
        _validate_registration(profile, email, first_name, last_name, password)

        # Solo con todos los datos válidos se mira si el email existe: así la
        # respuesta a datos no válidos (p. ej. una contraseña débil) no depende
        # de que la cuenta exista.
        if User.objects.filter(email=email).exists():
            # Mismo coste que un alta real (el hash de la contraseña es lo más
            # lento): el tiempo de respuesta tampoco lo revela.
            make_password(password)
            raise EmailAlreadyRegistered()

        user = _create_user(
            role=Role.CUSTOMER,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
        )
        # `_create_user` ya creó (y dejó en caché) el perfil vacío; se completa
        # en la misma transacción.
        stored = user.customer_profile
        for name in (*PROFILE_FIELDS, "promo_email_opt_in", "promo_sms_opt_in"):
            setattr(stored, name, getattr(profile, name))
        stored.save()

        _record_preference(user, Channel.EMAIL, stored.promo_email_opt_in, Source.REGISTRATION)
        _record_preference(user, Channel.SMS, stored.promo_sms_opt_in, Source.REGISTRATION)

        raw_token = _issue_email_token(user, TokenPurpose.VERIFY, user.email, enforce_limits=False)
        _send_token_on_commit(user, user.email, raw_token, is_email_change=False)
    return user


def notify_existing_account(email):
    """
    Avisa al titular de que alguien intentó registrarse con su email, con un
    enlace a la recuperación de contraseña. Limitado a un aviso por día y cuenta.
    """
    user = User.objects.filter(email=normalize_email_address(email), is_active=True).first()
    if user is None or throttling.is_limited("existing-account-notice", user.pk, 1):
        return
    throttling.register_attempt("existing-account-notice", user.pk, 60 * 60 * 24)
    transaction.on_commit(lambda: emails.send_existing_account_notice(user=user, to=user.email))


# --- Verificación de email -----------------------------------------------------


def _issue_email_token(user, purpose, email, *, enforce_limits=True):
    """
    Crea un token nuevo y revoca los pendientes del usuario. Devuelve el token en
    claro (solo para el email). Bloquea la fila del usuario para serializar
    emisiones concurrentes y aplicar los límites de reenvío.
    """
    now = timezone.now()
    User.objects.select_for_update().filter(pk=user.pk).first()
    if enforce_limits:
        recent = EmailVerificationToken.objects.filter(
            user=user, created_at__gte=now - datetime.timedelta(days=1)
        )
        # El intervalo mínimo es por finalidad (verificar no bloquea un cambio
        # de email inmediato); el máximo diario cuenta todos los envíos.
        last = recent.filter(purpose=purpose).order_by("-created_at").first()
        interval = datetime.timedelta(seconds=settings.EMAIL_VERIFICATION_RESEND_INTERVAL_SECONDS)
        if last is not None and now - last.created_at < interval:
            raise RateLimited(_("Espera un minuto antes de solicitar otro email."))
        if recent.count() >= settings.EMAIL_VERIFICATION_MAX_PER_DAY:
            raise RateLimited(_("Has alcanzado el máximo de emails de verificación por hoy."))

    EmailVerificationToken.objects.filter(
        user=user, used_at__isnull=True, revoked_at__isnull=True
    ).update(revoked_at=now)
    raw_token = secrets.token_urlsafe(32)
    EmailVerificationToken.objects.create(
        user=user,
        purpose=purpose,
        email=email,
        token_hash=EmailVerificationToken.hash_token(raw_token),
        created_at=now,
        expires_at=now + datetime.timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_TTL_HOURS),
    )
    return raw_token


def _send_token_on_commit(user, to, raw_token, *, is_email_change):
    first_name = user.first_name
    ttl = settings.EMAIL_VERIFICATION_TOKEN_TTL_HOURS
    transaction.on_commit(
        lambda: emails.send_verification_email(
            user=user,
            to=to,
            first_name=first_name,
            raw_token=raw_token,
            ttl_hours=ttl,
            is_email_change=is_email_change,
        )
    )


@transaction.atomic
def resend_verification_email(user):
    """
    Reenvía el enlace de verificación del email actual. Devuelve False si no hay
    nada que verificar. Lanza `RateLimited` si se supera el límite.
    """
    user = User.objects.select_for_update().get(pk=user.pk)
    if not user.is_active or user.is_email_verified:
        return False
    raw_token = _issue_email_token(user, TokenPurpose.VERIFY, user.email)
    _send_token_on_commit(user, user.email, raw_token, is_email_change=False)
    return True


def request_verification_resend(email):
    """
    Variante pública (sin sesión): no revela si el email existe, está verificado
    o ha superado el límite. Siempre devuelve None.
    """
    user = User.objects.filter(email=normalize_email_address(email)).first()
    if user is None:
        return
    try:
        resend_verification_email(user)
    except RateLimited:
        pass


_TOKEN_ERRORS = {
    "invalid": _("El enlace no es válido."),
    "expired": _("El enlace ha caducado. Solicita uno nuevo."),
    "used": _("Este enlace ya se ha utilizado."),
    "revoked": _("Este enlace ha sido sustituido por uno más reciente."),
    "email_taken": _("Ese email ya no está disponible."),
}


def _token_error(code):
    return ValidationError(_TOKEN_ERRORS[code], code=code)


@transaction.atomic
def confirm_email_token(raw_token):
    """
    Confirma un enlace de verificación o de cambio de email y lo invalida.

    Es la única vía que marca un email como verificado. El consumo del token es
    atómico (UPDATE condicionado), por lo que dos confirmaciones simultáneas no
    pueden tener éxito ambas. Devuelve el usuario.
    """
    if not raw_token or len(raw_token) > 128:
        raise _token_error("invalid")
    token = (
        EmailVerificationToken.objects.select_for_update()
        .filter(token_hash=EmailVerificationToken.hash_token(raw_token))
        .first()
    )
    if token is None:
        raise _token_error("invalid")
    if token.used_at is not None:
        raise _token_error("used")
    if token.revoked_at is not None:
        raise _token_error("revoked")
    now = timezone.now()
    if token.expires_at <= now:
        raise _token_error("expired")

    user = User.objects.select_for_update().get(pk=token.user_id)
    if not user.is_active:
        raise _token_error("invalid")

    claimed = EmailVerificationToken.objects.filter(
        pk=token.pk, used_at__isnull=True, revoked_at__isnull=True
    ).update(used_at=now)
    if claimed != 1:
        raise _token_error("used")

    if token.purpose == TokenPurpose.VERIFY:
        if token.email != user.email:
            # El email cambió después de emitir el enlace.
            raise _token_error("invalid")
        if not user.is_email_verified:
            user.email_verified_at = now
            user.save(update_fields=["email_verified_at"])
            record_audit_event(action=AuditEvent.Action.EMAIL_VERIFIED, actor=user, target=user)
        return user

    # Cambio de email: el nuevo queda verificado porque se acaba de confirmar.
    if User.objects.filter(email=token.email).exclude(pk=user.pk).exists():
        raise _token_error("email_taken")
    old_email, first_name = user.email, user.first_name
    user.email = token.email
    user.email_verified_at = now
    try:
        with transaction.atomic():
            user.save(update_fields=["email", "email_verified_at"])
    except IntegrityError:
        raise _token_error("email_taken") from None
    EmailVerificationToken.objects.filter(
        user=user, used_at__isnull=True, revoked_at__isnull=True
    ).update(revoked_at=now)
    record_audit_event(action=AuditEvent.Action.EMAIL_CHANGED, actor=user, target=user)
    transaction.on_commit(
        lambda: emails.send_email_changed_notice(user=user, to=old_email, first_name=first_name)
    )
    return user


@transaction.atomic
def request_email_change(*, user, new_email, password):
    """
    Solicita cambiar el email. Exige la contraseña actual. El email no cambia
    hasta que se confirma el enlace enviado a la nueva dirección; mientras
    tanto el actual sigue siendo el de acceso.

    Si la nueva dirección ya pertenece a otra cuenta no se envía nada, pero no
    se informa de ello (anti-enumeración). Lanza `RateLimited` si se supera el
    límite de envíos.
    """
    user = User.objects.select_for_update().get(pk=user.pk)
    if not user.is_active:
        raise PermissionDenied
    if not user.check_password(password or ""):
        raise ValidationError({"password": _("La contraseña no es correcta.")})
    new_email = normalize_email_address(new_email or "")
    try:
        validate_email(new_email)
    except ValidationError:
        raise ValidationError({"new_email": _("Introduce un email válido.")}) from None
    if len(new_email) > 254:
        raise ValidationError({"new_email": _("El email es demasiado largo.")})
    if new_email == user.email:
        raise ValidationError({"new_email": _("Ese ya es tu email actual.")})
    if User.objects.filter(email=new_email).exists():
        return
    raw_token = _issue_email_token(user, TokenPurpose.CHANGE, new_email)
    record_audit_event(action=AuditEvent.Action.EMAIL_CHANGE_REQUESTED, actor=user, target=user)
    _send_token_on_commit(user, new_email, raw_token, is_email_change=True)


def purge_email_tokens(*, older_than_days=30, now=None):
    """
    Borra los tokens de verificación caducados hace más de `older_than_days`
    días (usados, revocados o no). Guardan el email al que se enviaron y ya no
    sirven para nada; la auditoría de la verificación queda en `AuditEvent`.
    Devuelve cuántos se han borrado.
    """
    if older_than_days < 1:
        raise ValueError("older_than_days debe ser al menos 1.")
    cutoff = (now or timezone.now()) - datetime.timedelta(days=older_than_days)
    deleted, _unused = EmailVerificationToken.objects.filter(expires_at__lt=cutoff).delete()
    return deleted


def require_verified_email(user):
    """Para operaciones que exigen un email verificado (puntos, canjes, reservas...)."""
    if not (getattr(user, "is_authenticated", False) and user.is_active and user.is_email_verified):
        raise PermissionDenied(_("Debes verificar tu email para usar esta función."))


# --- Contraseña --------------------------------------------------------------------


def record_password_change(*, user, via, channel):
    """
    Deja constancia de un cambio de contraseña (`via`: "change" o "reset";
    `channel`: "web" o "api"), sin la contraseña ni el enlace usado. Cambiar
    la contraseña invalida además las sesiones web de otros dispositivos
    (hash de sesión de Django) y los tokens de la app (`apps.api.tokens`).
    """
    record_audit_event(
        action=AuditEvent.Action.PASSWORD_CHANGED,
        actor=user,
        target=user,
        metadata={"via": via, "channel": channel},
    )


def _set_new_password(user, new_password):
    try:
        validate_password(new_password, user)
    except ValidationError as exc:
        raise ValidationError({"new_password": exc.messages}) from None
    user.set_password(new_password)
    user.save(update_fields=["password"])


@transaction.atomic
def change_password(*, user, current_password, new_password, channel="api"):
    """Cambio de contraseña con la actual (la web usa el formulario nativo de Django)."""
    user = User.objects.select_for_update().get(pk=user.pk)
    if not user.is_active:
        raise PermissionDenied
    if not user.check_password(current_password or ""):
        raise ValidationError({"current_password": _("La contraseña actual no es correcta.")})
    _set_new_password(user, new_password)
    record_password_change(user=user, via="change", channel=channel)
    return user


def _user_from_uidb64(uidb64):
    try:
        pk = urlsafe_base64_decode(uidb64 or "").decode()
        return User.objects.select_for_update().get(pk=pk)
    except (TypeError, ValueError, OverflowError, UnicodeDecodeError, ValidationError, User.DoesNotExist):
        return None


@transaction.atomic
def reset_password_with_token(*, uidb64, token, new_password, channel="api"):
    """
    Restablece la contraseña con el enlace de recuperación nativo de Django
    (`uidb64` y `token` del enlace del email). El token deja de valer en cuanto
    la contraseña cambia, y la fila del usuario se bloquea para que dos usos
    simultáneos del mismo enlace no tengan éxito ambos.
    """
    user = _user_from_uidb64(uidb64)
    if user is None or not user.is_active or not default_token_generator.check_token(user, token or ""):
        raise ValidationError(_("El enlace no es válido o ha caducado. Solicita uno nuevo."), code="invalid_token")
    _set_new_password(user, new_password)
    record_password_change(user=user, via="reset", channel=channel)
    return user


# --- Perfil ----------------------------------------------------------------------


def _require_active_customer(user):
    if not (user.is_active and user.role == Role.CUSTOMER):
        raise PermissionDenied(_("Solo los clientes tienen perfil de cliente."))


@transaction.atomic
def update_customer_profile(*, user, first_name, last_name, **profile_data):
    """
    Modifica los datos personales del cliente autenticado (`user`; nunca un ID
    recibido del cliente). Solo acepta los campos de `PROFILE_FIELDS`.

    Reglas: todos los obligatorios deben quedar completos; la fecha de
    nacimiento puede cambiarse una vez cada
    `ACCOUNTS_DATE_OF_BIRTH_CHANGE_COOLDOWN_DAYS` (protege las promociones de
    cumpleaños); si se borra el teléfono se retira el consentimiento de SMS.
    El email no se modifica aquí (`request_email_change`).
    """
    unknown = set(profile_data) - set(PROFILE_FIELDS)
    if unknown:
        raise ValidationError(_("Campos no permitidos: %(join)s.") % {"join": ', '.join(sorted(unknown))})
    user = User.objects.select_for_update().get(pk=user.pk)
    _require_active_customer(user)
    ensure_customer_profile(user)
    profile = CustomerProfile.objects.select_for_update().get(user=user)
    before = {name: getattr(profile, name) for name in PROFILE_FIELDS}

    _apply_profile_data(profile, profile_data)
    changed = [name for name in PROFILE_FIELDS if getattr(profile, name) != before[name]]

    now = timezone.now()
    if "date_of_birth" in changed and before["date_of_birth"] is not None:
        cooldown = datetime.timedelta(days=settings.ACCOUNTS_DATE_OF_BIRTH_CHANGE_COOLDOWN_DAYS)
        last_change = profile.date_of_birth_changed_at
        if last_change is not None and now - last_change < cooldown:
            raise ValidationError(
                {"date_of_birth": _("La fecha de nacimiento solo puede cambiarse una vez al año.")}
            )
        profile.date_of_birth_changed_at = now

    sms_withdrawn = profile.promo_sms_opt_in and not profile.phone_number
    if sms_withdrawn:
        profile.promo_sms_opt_in = False

    old_names = {"first_name": user.first_name, "last_name": user.last_name}
    user.first_name = normalize_text(first_name)
    user.last_name = normalize_text(last_name)
    user_changed = [name for name, old in old_names.items() if getattr(user, name) != old]
    errors = {}
    try:
        user.full_clean(exclude=["password"])
    except ValidationError as exc:
        errors.update(exc.message_dict)
    try:
        _validate_complete_profile(profile)
    except ValidationError as exc:
        errors.update(exc.message_dict)
    if errors:
        raise ValidationError(errors)

    profile.save()
    user.save(update_fields=["first_name", "last_name"])
    if sms_withdrawn:
        _record_preference(user, Channel.SMS, False, Source.SYSTEM)
    if changed or user_changed:
        # Solo los nombres de los campos, nunca sus valores.
        record_audit_event(
            action=AuditEvent.Action.PROFILE_UPDATED,
            actor=user,
            target=user,
            metadata={"fields": sorted(user_changed + changed)},
        )
    return profile


@transaction.atomic
def set_communication_preferences(*, user, promo_email_opt_in, promo_sms_opt_in, source=Source.PROFILE):
    """
    Cambia los consentimientos promocionales y registra cada cambio en el
    historial. Verificar el email no implica consentimiento: solo cambian aquí.
    """
    user = User.objects.select_for_update().get(pk=user.pk)
    _require_active_customer(user)
    ensure_customer_profile(user)
    profile = CustomerProfile.objects.select_for_update().get(user=user)
    promo_email_opt_in, promo_sms_opt_in = bool(promo_email_opt_in), bool(promo_sms_opt_in)
    if promo_sms_opt_in and not profile.phone_number:
        raise ValidationError(
            {"promo_sms_opt_in": _("Para recibir SMS promocionales indica antes un teléfono móvil.")}
        )
    changes = []
    if profile.promo_email_opt_in != promo_email_opt_in:
        profile.promo_email_opt_in = promo_email_opt_in
        changes.append((Channel.EMAIL, promo_email_opt_in))
    if profile.promo_sms_opt_in != promo_sms_opt_in:
        profile.promo_sms_opt_in = promo_sms_opt_in
        changes.append((Channel.SMS, promo_sms_opt_in))
    if changes:
        profile.save(update_fields=["promo_email_opt_in", "promo_sms_opt_in", "updated_at"])
        for channel, opted_in in changes:
            _record_preference(user, channel, opted_in, source)
    return profile


@transaction.atomic
def withdraw_promotional_consent(*, user, channel, source=Source.UNSUBSCRIBE_LINK):
    """
    Retira el consentimiento de un canal (enlace de baja de un mensaje
    promocional, Fase 10). Idempotente: si ya estaba retirado no registra nada.
    No exige sesión: quien llama ya ha validado el enlace firmado.
    """
    if channel not in Channel.values:
        raise ValidationError(_("Canal no válido."))
    user = User.objects.select_for_update().get(pk=user.pk)
    if user.role != Role.CUSTOMER:
        return None
    profile = CustomerProfile.objects.select_for_update().filter(user=user).first()
    if profile is None:
        return None
    field = "promo_email_opt_in" if channel == Channel.EMAIL else "promo_sms_opt_in"
    if getattr(profile, field):
        setattr(profile, field, False)
        profile.save(update_fields=[field, "updated_at"])
        _record_preference(user, channel, False, source)
    return profile


# --- Comprobaciones antes de enviar promociones ---------------------------------


def _customer_profile_or_none(user):
    if not (user.is_active and user.role == Role.CUSTOMER):
        return None
    try:
        return user.customer_profile
    except CustomerProfile.DoesNotExist:
        return None


def can_receive_promotional_email(user):
    """Cliente activo, email verificado y consentimiento explícito vigente."""
    profile = _customer_profile_or_none(user)
    return bool(profile and user.is_email_verified and profile.promo_email_opt_in)


def can_receive_promotional_sms(user):
    """Cliente activo, teléfono indicado y consentimiento explícito vigente."""
    profile = _customer_profile_or_none(user)
    return bool(profile and profile.phone_number and profile.promo_sms_opt_in)
