import hashlib
import uuid

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel

from . import postal, validators
from .countries import COUNTRY_NAMES, DEFAULT_COUNTRY
from .managers import UserManager
from .normalization import normalize_email_address


class User(AbstractBaseUser, PermissionsMixin):
    """
    Usuario de la plataforma.

    - `id`: clave primaria interna (no se expone fuera del backend).
    - `public_id`: identificador estable y no secuencial para URLs, API y app móvil.
    - `email`: credencial de acceso y canal de contacto; no se usa como
      identificador interno de los procesos.

    Los datos personales específicos del cliente (dirección, fecha de nacimiento,
    teléfono, preferencias) no viven aquí, sino en `CustomerProfile`.
    """

    class Role(models.TextChoices):
        OWNER = "OWNER", _("Propietario")
        EMPLOYEE = "EMPLOYEE", _("Empleado")
        CUSTOMER = "CUSTOMER", _("Cliente")

    public_id = models.UUIDField(
        _("identificador público"), default=uuid.uuid4, unique=True, editable=False
    )
    email = models.EmailField(_("email"), max_length=254, unique=True)
    first_name = models.CharField(_("nombre"), max_length=150)
    last_name = models.CharField(_("apellidos"), max_length=150)
    role = models.CharField(
        _("rol"), max_length=16, choices=Role.choices, default=Role.CUSTOMER, db_index=True
    )
    is_active = models.BooleanField(_("activo"), default=True)
    email_verified_at = models.DateTimeField(
        _("email verificado el"),
        null=True,
        blank=True,
        help_text=_("Vacío mientras el email actual no se haya confirmado con un enlace."),
    )
    is_staff = models.BooleanField(
        _("acceso al admin técnico"),
        default=False,
        help_text=_("Solo propietarios. Se deriva del rol."),
    )
    date_joined = models.DateTimeField(_("fecha de alta"), default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name = _("usuario")
        verbose_name_plural = _("usuarios")
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
            models.CheckConstraint(
                condition=Q(role__in=["OWNER", "EMPLOYEE", "CUSTOMER"]),
                name="accounts_user_role_valid",
            ),
            models.CheckConstraint(
                condition=Q(is_staff=False) | Q(role="OWNER"),
                name="accounts_user_staff_only_owner",
            ),
            models.CheckConstraint(
                condition=Q(is_superuser=False) | Q(role="OWNER"),
                name="accounts_user_superuser_only_owner",
            ),
        ]

    def __str__(self):
        return self.email

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._loaded_email = instance.__dict__.get("email")
        instance._loaded_email_verified_at = instance.__dict__.get("email_verified_at")
        return instance

    def refresh_from_db(self, *args, **kwargs):
        super().refresh_from_db(*args, **kwargs)
        self._loaded_email = self.__dict__.get("email")
        self._loaded_email_verified_at = self.__dict__.get("email_verified_at")

    def clean(self):
        super().clean()
        self.email = normalize_email_address(self.email)

    def save(self, *args, **kwargs):
        self.email = normalize_email_address(self.email)
        self._reset_verification_if_email_changed(kwargs)
        super().save(*args, **kwargs)
        self._loaded_email = self.email
        self._loaded_email_verified_at = self.email_verified_at

    def _reset_verification_if_email_changed(self, save_kwargs):
        """
        Invariante: un email nuevo nunca hereda la verificación del anterior.

        Si el email cambia y quien guarda no fija a la vez una nueva fecha de
        verificación (solo lo hace `services.confirm_email_token`), la
        verificación se anula. Cubre el admin y cualquier otro `save()`;
        `QuerySet.update()` no pasa por aquí y no debe usarse para cambiar emails.
        """
        loaded_email = getattr(self, "_loaded_email", None)
        if self.pk is None or loaded_email is None or self.email == loaded_email:
            return
        update_fields = save_kwargs.get("update_fields")
        if update_fields is not None and "email" not in update_fields:
            return  # este guardado no persiste el email
        if self.email_verified_at != getattr(self, "_loaded_email_verified_at", None):
            return
        self.email_verified_at = None
        if update_fields is not None:
            save_kwargs["update_fields"] = {*update_fields, "email_verified_at"}

    @property
    def is_email_verified(self):
        return self.email_verified_at is not None

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.first_name

    @property
    def is_owner(self):
        return self.role == self.Role.OWNER

    @property
    def is_employee(self):
        return self.role == self.Role.EMPLOYEE

    @property
    def is_customer(self):
        return self.role == self.Role.CUSTOMER


class CustomerProfile(TimeStampedModel):
    """
    Perfil 1:1 de los clientes con sus datos personales.

    Lo crean los servicios de cuentas en la misma transacción que el alta del
    cliente o el paso al rol CUSTOMER (`services.ensure_customer_profile`). El
    `OneToOneField` impide perfiles duplicados en la base de datos.

    Los campos personales admiten vacío en BD porque los clientes anteriores a
    la Fase 2 (y quien pasa a cliente desde otro rol) no los tienen; el registro
    público y la edición del perfil los exigen (`REQUIRED_FIELDS`).

    Desde la Fase 16 de la dirección solo se exige el código postal: la
    provincia se deduce de él (España) y la localidad se elige entre las del CP
    cuando hay datos (`postal`). Calle y línea 2 son opcionales.
    """

    class Sex(models.TextChoices):
        MALE = "MALE", _("Hombre")
        FEMALE = "FEMALE", _("Mujer")
        UNDISCLOSED = "UNDISCLOSED", _("Prefiero no decirlo")

    # Fase 25: el sexo es opcional (minimización de datos); la fecha de nacimiento sigue
    # siendo obligatoria (mayoría de edad y regalo de cumpleaños).
    REQUIRED_FIELDS = (
        "postal_code",
        "country",
        "date_of_birth",
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("usuario"),
        on_delete=models.CASCADE,
        related_name="customer_profile",
    )
    address_line_1 = models.CharField(
        _("dirección"), max_length=200, blank=True, help_text=_("Calle, número, piso.")
    )
    address_line_2 = models.CharField(_("dirección (línea 2)"), max_length=200, blank=True)
    postal_code = models.CharField(_("código postal"), max_length=12, blank=True)
    city = models.CharField(_("localidad"), max_length=100, blank=True)
    province = models.CharField(
        _("provincia"), max_length=100, blank=True, help_text=_("Provincia, estado o región.")
    )
    # Código ISO 3166-1 alfa-2. La lista (`countries.COUNTRIES`) se valida en
    # `clean()` y no como `choices` para no generar migraciones al actualizarla.
    country = models.CharField(
        _("país"), max_length=2, default=DEFAULT_COUNTRY, blank=True, help_text=_("Código ISO 3166-1.")
    )
    date_of_birth = models.DateField(_("fecha de nacimiento"), null=True, blank=True)
    # Vacío solo en los clientes anteriores a la Fase 16; el registro lo exige.
    sex = models.CharField(_("sexo"), max_length=12, choices=Sex.choices, blank=True)
    date_of_birth_changed_at = models.DateTimeField(
        _("última modificación de la fecha de nacimiento"),
        null=True,
        blank=True,
        help_text=_("Limita los cambios posteriores (promociones de cumpleaños)."),
    )
    phone_number = models.CharField(
        _("teléfono móvil"),
        max_length=16,
        blank=True,
        validators=[validators.validate_e164],
        help_text=_("Opcional. Formato internacional E.164. No está verificado."),
    )
    promo_email_opt_in = models.BooleanField(_("acepta emails promocionales"), default=False)
    # Fase 25: aceptación de la política de privacidad y de las condiciones del programa al
    # registrarse, con la versión de cada texto (para poder demostrarla). Vacío en cuentas anteriores.
    terms_accepted_at = models.DateTimeField(_("textos legales aceptados el"), null=True, blank=True, editable=False)
    privacy_version = models.PositiveIntegerField(_("versión de la privacidad aceptada"), null=True, blank=True, editable=False)
    terms_version = models.PositiveIntegerField(_("versión de las condiciones aceptada"), null=True, blank=True, editable=False)
    promo_sms_opt_in = models.BooleanField(_("acepta SMS promocionales"), default=False)

    class Meta:
        verbose_name = _("perfil de cliente")
        verbose_name_plural = _("perfiles de cliente")
        constraints = [
            models.CheckConstraint(
                condition=Q(promo_sms_opt_in=False) | ~Q(phone_number=""),
                name="accounts_profile_sms_opt_in_requires_phone",
            ),
            models.CheckConstraint(
                condition=Q(sex__in=["", "MALE", "FEMALE", "UNDISCLOSED"]),
                name="accounts_profile_sex_valid",
            ),
        ]

    def __str__(self):
        return _("Perfil de cliente %(public_id)s") % {"public_id": self.user.public_id}

    def clean(self):
        super().clean()
        for name in ("address_line_1", "address_line_2", "city", "province"):
            setattr(self, name, validators.normalize_text(getattr(self, name)))
        self.postal_code = validators.normalize_postal_code(self.postal_code)
        errors = {}
        if self.country:
            try:
                validators.validate_country(self.country)
            except ValidationError as exc:
                errors["country"] = exc.messages
        if self.postal_code and self.country and "country" not in errors:
            try:
                validators.validate_postal_code(self.postal_code, self.country)
            except ValidationError as exc:
                errors["postal_code"] = exc.messages
        if self.postal_code and "postal_code" not in errors and "country" not in errors:
            self.province = postal.province_for(self.country, self.postal_code) or self.province
            try:
                self.city = postal.canonical_locality(self.country, self.postal_code, self.city)
            except ValidationError as exc:
                errors["city"] = exc.messages
        if self.date_of_birth is not None:
            try:
                validators.validate_date_of_birth(self.date_of_birth)
            except ValidationError as exc:
                errors["date_of_birth"] = exc.messages
        if self.promo_sms_opt_in and not self.phone_number:
            errors["promo_sms_opt_in"] = [_("Para recibir SMS promocionales indica un teléfono móvil.")]
        if errors:
            raise ValidationError(errors)

    def get_country_display(self):
        return COUNTRY_NAMES.get(self.country, self.country)

    def missing_required_fields(self):
        return [name for name in self.REQUIRED_FIELDS if getattr(self, name) in (None, "")]


class EmailVerificationToken(models.Model):
    """
    Enlace de confirmación de email: alta (`VERIFY`) o cambio de email (`CHANGE`).

    Solo se guarda el hash SHA-256 del token; el valor en claro únicamente viaja
    en el email. Es de un solo uso (`used_at`), caduca (`expires_at`) y se
    revoca al emitir otro para el mismo usuario (`revoked_at`).
    """

    class Purpose(models.TextChoices):
        VERIFY = "VERIFY", _("Verificación del email")
        CHANGE = "CHANGE", _("Cambio de email")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("usuario"),
        on_delete=models.CASCADE,
        related_name="email_tokens",
    )
    purpose = models.CharField(_("finalidad"), max_length=16, choices=Purpose.choices)
    email = models.EmailField(_("email a confirmar"), max_length=254)
    token_hash = models.CharField(_("hash del token"), max_length=64, unique=True)
    created_at = models.DateTimeField(_("creado"), default=timezone.now)
    expires_at = models.DateTimeField(_("caduca"))
    used_at = models.DateTimeField(_("usado"), null=True, blank=True)
    revoked_at = models.DateTimeField(_("revocado"), null=True, blank=True)

    class Meta:
        verbose_name = _("token de verificación de email")
        verbose_name_plural = _("tokens de verificación de email")
        indexes = [models.Index(fields=["user", "created_at"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(purpose__in=["VERIFY", "CHANGE"]),
                name="accounts_emailtoken_purpose_valid",
            ),
        ]

    def __str__(self):
        return f"{self.get_purpose_display()} · {self.created_at:%Y-%m-%d %H:%M}"

    @staticmethod
    def hash_token(raw_token):
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class CommunicationPreferenceChange(models.Model):
    """
    Historial inmutable de cambios del consentimiento promocional.

    Permite demostrar cuándo y por qué vía se dio o retiró cada consentimiento.
    No se edita ni se borra: el estado vigente está en `CustomerProfile`.
    """

    class Channel(models.TextChoices):
        EMAIL = "EMAIL", _("Email promocional")
        SMS = "SMS", _("SMS promocional")

    class Source(models.TextChoices):
        REGISTRATION = "REGISTRATION", _("Registro")
        PROFILE = "PROFILE", _("Perfil del cliente")
        SYSTEM = "SYSTEM", _("Automático (teléfono eliminado)")
        UNSUBSCRIBE_LINK = "UNSUBSCRIBE", _("Enlace de baja de un mensaje")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("cliente"),
        on_delete=models.CASCADE,
        related_name="communication_preference_changes",
    )
    channel = models.CharField(_("canal"), max_length=8, choices=Channel.choices)
    opted_in = models.BooleanField(_("consiente"))
    source = models.CharField(_("origen"), max_length=16, choices=Source.choices)
    created_at = models.DateTimeField(_("fecha"), default=timezone.now, db_index=True)

    class Meta:
        verbose_name = _("cambio de preferencia de comunicación")
        verbose_name_plural = _("cambios de preferencias de comunicación")
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(channel__in=["EMAIL", "SMS"]),
                name="accounts_prefchange_channel_valid",
            ),
        ]

    def __str__(self):
        state = "alta" if self.opted_in else "baja"
        return f"{self.get_channel_display()}: {state} · {self.created_at:%Y-%m-%d %H:%M}"
