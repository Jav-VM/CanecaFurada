"""
Recompensas y canjes.

- `Reward`: lo que el propietario ofrece a cambio de puntos. No se borra: se
  pausa o se archiva, y los canjes la referencian con `PROTECT`.
- `Redemption`: un canje solicitado por un cliente. Al crearlo se descuentan
  los puntos (movimiento `REDEMPTION` del ledger) y se genera un código de un
  solo uso que el personal valida en barra. Si se cancela o caduca, los puntos
  se devuelven con un movimiento compensatorio; nada se borra ni se edita a mano.

Las reglas están en `services.py` y las consultas en `selectors.py`; aquí solo
los datos y sus invariantes, también en la BD.
"""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from apps.catalog.validators import validate_image_extension, validate_image_file
from apps.core.models import TimeStampedModel

from .codes import CODE_LENGTH, CODE_REGEX


def reward_image_path(instance, filename):
    # Nombre aleatorio: no se publica el nombre original del fichero.
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    ext = "jpg" if ext == "jpeg" else ext
    return f"rewards/{uuid.uuid4().hex}.{ext}"


class Reward(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", _("Borrador")
        ACTIVE = "ACTIVE", pgettext_lazy("recompensa", "Activa")
        PAUSED = "PAUSED", pgettext_lazy("recompensa", "Pausada")
        ARCHIVED = "ARCHIVED", pgettext_lazy("recompensa", "Archivada")

    MAX_POINTS_COST = 100000

    public_id = models.UUIDField(_("identificador"), default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(_("nombre"), max_length=100)
    description = models.TextField(_("descripción"), blank=True, max_length=1000, help_text=_("Texto público."))
    image = models.ImageField(
        _("imagen"),
        upload_to=reward_image_path,
        blank=True,
        width_field="image_width",
        height_field="image_height",
        validators=[validate_image_extension, validate_image_file],
        help_text=_("JPEG, PNG o WebP. Opcional."),
    )
    image_width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    image_height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    points_cost = models.PositiveIntegerField(
        _("coste en puntos"),
        validators=[MinValueValidator(1), MaxValueValidator(MAX_POINTS_COST)],
        help_text=_("Cambiarlo no afecta a los canjes ya solicitados."),
    )
    status = models.CharField(
        _("estado"),
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
        help_text=_("Solo las activas se ven en la web y se pueden canjear."),
    )
    valid_from = models.DateTimeField(_("se puede canjear desde"), default=timezone.now)
    valid_until = models.DateTimeField(
        _("se puede canjear hasta"), null=True, blank=True, help_text=_("Vacío: sin fecha de fin.")
    )
    stock = models.PositiveIntegerField(
        _("unidades disponibles"),
        null=True,
        blank=True,
        help_text=_("Vacío: sin límite. Baja sola con cada canje y sube si un canje se cancela o caduca."),
    )
    position = models.PositiveSmallIntegerField(_("orden"), default=0, help_text=_("De menor a mayor."))

    class Meta:
        verbose_name = _("recompensa")
        verbose_name_plural = _("recompensas")
        ordering = ["position", "points_cost", "name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["DRAFT", "ACTIVE", "PAUSED", "ARCHIVED"]), name="rewards_reward_status_valid"
            ),
            models.CheckConstraint(
                condition=Q(points_cost__gte=1) & Q(points_cost__lte=100000),
                name="rewards_reward_cost_range",
            ),
            models.CheckConstraint(
                condition=Q(valid_until__isnull=True) | Q(valid_until__gt=models.F("valid_from")),
                name="rewards_reward_dates_valid",
            ),
            models.CheckConstraint(
                condition=Q(stock__isnull=True) | Q(stock__gte=0), name="rewards_reward_stock_nonnegative"
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        errors = {}
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            errors["valid_until"] = _("La fecha de fin debe ser posterior a la de inicio.")
        if errors:
            raise ValidationError(errors)

    @property
    def is_unlimited(self):
        return self.stock is None

    @property
    def is_in_stock(self):
        return self.stock is None or self.stock > 0

    def is_in_period(self, now=None):
        now = now or timezone.now()
        return self.valid_from <= now and (self.valid_until is None or now < self.valid_until)

    def is_requestable(self, now=None):
        """Activa, dentro de sus fechas y con unidades. El servicio lo vuelve a comprobar con la fila bloqueada."""
        return self.status == self.Status.ACTIVE and self.is_in_period(now) and self.is_in_stock


class Redemption(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pendiente de recoger")
        USED = "USED", _("Canjeado")
        EXPIRED = "EXPIRED", _("Caducado")
        CANCELLED = "CANCELLED", _("Cancelado")

    CLOSED_STATUSES = (Status.EXPIRED, Status.CANCELLED)

    public_id = models.UUIDField(_("identificador"), default=uuid.uuid4, unique=True, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("cliente"), on_delete=models.PROTECT, related_name="redemptions"
    )
    reward = models.ForeignKey(Reward, verbose_name=_("recompensa"), on_delete=models.PROTECT, related_name="redemptions")
    points_cost = models.PositiveIntegerField(_("puntos descontados"), help_text=_("Copia del coste en el momento del canje."))
    code = models.CharField(_("código"), max_length=CODE_LENGTH, unique=True, editable=False)
    status = models.CharField(
        _("estado"), max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    created_at = models.DateTimeField(_("solicitado el"), default=timezone.now, editable=False, db_index=True)
    expires_at = models.DateTimeField(_("caduca el"), editable=False)
    idempotency_key = models.UUIDField(_("referencia de idempotencia"), unique=True, editable=False)
    spend_movement = models.OneToOneField(
        "loyalty.PointsTransaction",
        verbose_name=_("movimiento del canje"),
        on_delete=models.PROTECT,
        related_name="redemption",
        editable=False,
    )
    refund_movement = models.OneToOneField(
        "loyalty.PointsTransaction",
        verbose_name=_("movimiento de devolución"),
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="refunded_redemption",
        editable=False,
    )
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("validado por"),
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="validated_redemptions",
        editable=False,
    )
    validated_at = models.DateTimeField(_("validado el"), null=True, blank=True, editable=False)
    closed_at = models.DateTimeField(
        _("cancelado o caducado el"), null=True, blank=True, editable=False
    )

    class Meta:
        verbose_name = _("canje")
        verbose_name_plural = _("canjes")
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["customer", "created_at"]),
            models.Index(fields=["status", "expires_at"]),
            models.Index(fields=["validated_by", "validated_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["PENDING", "USED", "EXPIRED", "CANCELLED"]),
                name="rewards_redemption_status_valid",
            ),
            models.CheckConstraint(condition=Q(points_cost__gte=1), name="rewards_redemption_cost_positive"),
            models.CheckConstraint(condition=Q(code__regex=CODE_REGEX), name="rewards_redemption_code_format"),
            models.CheckConstraint(
                condition=Q(expires_at__gt=models.F("created_at")), name="rewards_redemption_expiry_after_creation"
            ),
            # Canjeado <=> con quién y cuándo.
            models.CheckConstraint(
                condition=Q(status="USED", validated_by__isnull=False, validated_at__isnull=False)
                | (~Q(status="USED") & Q(validated_by__isnull=True, validated_at__isnull=True)),
                name="rewards_redemption_validation_consistent",
            ),
            # Cancelado o caducado <=> con devolución de puntos y fecha.
            models.CheckConstraint(
                condition=Q(status__in=["EXPIRED", "CANCELLED"], refund_movement__isnull=False, closed_at__isnull=False)
                | (Q(status__in=["PENDING", "USED"]) & Q(refund_movement__isnull=True, closed_at__isnull=True)),
                name="rewards_redemption_refund_consistent",
            ),
            models.CheckConstraint(
                condition=~Q(validated_by=models.F("customer")), name="rewards_redemption_not_self_validated"
            ),
            # Un solo código pendiente por cliente y recompensa.
            models.UniqueConstraint(
                fields=["customer", "reward"],
                condition=Q(status="PENDING"),
                name="rewards_redemption_one_pending_per_reward",
            ),
        ]

    def __str__(self):
        # Sin el código: el admin, los logs o los errores nunca lo muestran.
        return _("Canje %(public_id)s") % {"public_id": self.public_id}

    def is_expired(self, now=None):
        return self.status == self.Status.PENDING and self.expires_at <= (now or timezone.now())
