import datetime
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TimeStampedModel


class CustomerQRCode(TimeStampedModel):
    """
    Código personal del cliente que se muestra como QR.

    El token es aleatorio (160 bits de `secrets`), opaco y no contiene ni
    deriva de datos personales ni del saldo. Solo **identifica** al cliente:
    no autoriza ninguna operación por sí solo (registrar una compra exige un
    empleado o propietario autenticado y validaciones del servidor).

    Se guarda en claro porque hay que poder volver a dibujar el QR; por eso
    nunca se escribe en logs, auditoría, URLs ni mensajes de error, y el
    cliente puede renovarlo si cree que alguien lo ha copiado.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="cliente",
        on_delete=models.CASCADE,
        related_name="qr_code",
    )
    token = models.CharField("token", max_length=32, unique=True, editable=False)
    rotated_at = models.DateTimeField("renovado el", null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "código QR de cliente"
        verbose_name_plural = "códigos QR de cliente"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(token__regex=r"^[A-Z2-7]{32}$"),
                name="loyalty_qr_token_format",
            ),
        ]

    def __str__(self):
        # Sin el token: el admin, los logs o los errores nunca lo muestran.
        return f"QR de cliente #{self.pk}"


# --- Puntos (Fase 6) -------------------------------------------------------------


class LoyaltyRule(models.Model):
    """
    Conversión de importe a puntos.

    Versionada: las reglas no se editan ni se borran, se añade una nueva con su
    fecha de entrada en vigor. La vigente es la última con `valid_from` pasado.
    Cada movimiento del ledger guarda una copia de la tasa aplicada, así que
    cambiar la conversión nunca altera los puntos ya concedidos.
    """

    MIN_RATE = Decimal("0.01")
    MAX_RATE = Decimal("100.00")

    public_id = models.UUIDField("identificador", default=uuid.uuid4, unique=True, editable=False)
    points_per_euro = models.DecimalField(
        "puntos por euro",
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(MIN_RATE), MaxValueValidator(MAX_RATE)],
        help_text="Puntos por cada euro de compra. El resultado se redondea hacia abajo a puntos enteros.",
    )
    valid_from = models.DateTimeField("en vigor desde", default=timezone.now, db_index=True)
    note = models.CharField("motivo", max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="creada por",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
    )
    created_at = models.DateTimeField("creada", auto_now_add=True)

    class Meta:
        verbose_name = "regla de conversión de puntos"
        verbose_name_plural = "reglas de conversión de puntos"
        ordering = ["-valid_from", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(points_per_euro__gte=Decimal("0.01")) & Q(points_per_euro__lte=Decimal("100.00")),
                name="loyalty_rule_rate_range",
            ),
        ]

    def __str__(self):
        return f"{self.points_per_euro} puntos/€ desde {timezone.localtime(self.valid_from):%d/%m/%Y %H:%M}"

    def clean(self):
        super().clean()
        # Una regla nueva no puede aplicarse a compras ya registradas. Margen de
        # unos minutos para "en vigor desde ahora" en el formulario del admin.
        if self._state.adding and self.valid_from and self.valid_from < timezone.now() - datetime.timedelta(minutes=5):
            raise ValidationError({"valid_from": "La nueva conversión no puede entrar en vigor en el pasado."})


class PointsExpiryPolicy(models.Model):
    """
    Caducidad de los puntos (Fase 14).

    Versionada como `LoyaltyRule`: no se edita ni se borra, cada cambio añade
    una versión y la vigente es la última. `months` vacío = los puntos no
    caducan. Cada punto caduca `months` meses después de ganarse, pero nunca
    antes de `counts_from` + `months`: así activar la caducidad o acortar el
    plazo no hace perder puntos de golpe. `counts_from` lo calcula el servicio
    (`expiry.set_policy`), nunca el formulario. Reglas en `expiry.py`.
    """

    MAX_MONTHS = 60
    MAX_WARN_DAYS = 60
    DEFAULT_WARN_DAYS = 15

    public_id = models.UUIDField("identificador", default=uuid.uuid4, unique=True, editable=False)
    months = models.PositiveSmallIntegerField(
        "meses de validez",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_MONTHS)],
        help_text="Vacío: los puntos no caducan.",
    )
    warn_days = models.PositiveSmallIntegerField(
        "días de aviso",
        default=DEFAULT_WARN_DAYS,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_WARN_DAYS)],
        help_text="Con cuántos días de antelación se avisa por email de los puntos que van a caducar.",
    )
    counts_from = models.DateTimeField("el plazo cuenta desde", null=True, blank=True, editable=False)
    valid_from = models.DateTimeField("en vigor desde", default=timezone.now, db_index=True, editable=False)
    note = models.CharField("motivo", max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="creada por",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
    )
    created_at = models.DateTimeField("creada", auto_now_add=True)

    class Meta:
        verbose_name = "política de caducidad de puntos"
        verbose_name_plural = "políticas de caducidad de puntos"
        ordering = ["-valid_from", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(months__isnull=True) | (Q(months__gte=1) & Q(months__lte=60)),
                name="loyalty_expiry_months_range",
            ),
            models.CheckConstraint(
                condition=Q(warn_days__gte=1) & Q(warn_days__lte=60), name="loyalty_expiry_warn_days_range"
            ),
            # Con caducidad tiene que saberse desde cuándo cuenta el plazo.
            models.CheckConstraint(
                condition=Q(months__isnull=True) | Q(counts_from__isnull=False),
                name="loyalty_expiry_counts_from_required",
            ),
        ]

    def __str__(self):
        if self.months is None:
            return f"Sin caducidad desde {timezone.localtime(self.valid_from):%d/%m/%Y %H:%M}"
        return f"{self.months} meses desde {timezone.localtime(self.valid_from):%d/%m/%Y %H:%M}"

    @property
    def is_active(self):
        return self.months is not None


class Promotion(TimeStampedModel):
    """
    Promoción configurable que da puntos extra al registrar una compra.

    - `PURCHASE`: cualquier compra que cumpla las condiciones dentro de las fechas.
    - `BIRTHDAY`: desde la Fase 10, regalo de puntos fijos el día del
      cumpleaños (comando `run_birthday_promotions`, movimiento `BIRTHDAY_GIFT`),
      sin necesidad de comprar; como máximo una promoción de cumpleaños por
      cliente y año (restricción única en el ledger), aunque cambie su fecha de
      nacimiento. Solo admite puntos fijos.

    Las reglas de aplicación están en `promotions.py`; aquí solo los datos y
    sus invariantes (también en BD).
    """

    class Kind(models.TextChoices):
        PURCHASE = "PURCHASE", "Por compra"
        BIRTHDAY = "BIRTHDAY", "Cumpleaños"

    class BonusType(models.TextChoices):
        FIXED_POINTS = "FIXED_POINTS", "Puntos fijos"
        MULTIPLIER = "MULTIPLIER", "Multiplicador de los puntos de la compra"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        ACTIVE = "ACTIVE", "Activa"
        PAUSED = "PAUSED", "Pausada"
        ENDED = "ENDED", "Finalizada"

    MAX_FIXED_POINTS = 10000
    MAX_MULTIPLIER = Decimal("10.00")
    MAX_BIRTHDAY_WINDOW_DAYS = 31

    public_id = models.UUIDField("identificador", default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField("nombre", max_length=100)
    description = models.CharField(
        "descripción para el cliente", max_length=300, blank=True, help_text="Texto público, sin datos personales."
    )
    kind = models.CharField("tipo", max_length=10, choices=Kind.choices, default=Kind.PURCHASE)
    bonus_type = models.CharField("bonificación", max_length=16, choices=BonusType.choices)
    fixed_points = models.PositiveIntegerField(
        "puntos fijos",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_FIXED_POINTS)],
    )
    multiplier = models.DecimalField(
        "multiplicador",
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("1.01")), MaxValueValidator(MAX_MULTIPLIER)],
        help_text="Por ejemplo 2,00 = puntos dobles: se suman los puntos de la compra × (multiplicador − 1).",
    )
    min_purchase_amount = models.DecimalField(
        "importe mínimo de la compra (€)",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    starts_at = models.DateTimeField("empieza")
    ends_at = models.DateTimeField("termina", null=True, blank=True, help_text="Vacío: sin fecha de fin.")
    max_uses_per_customer = models.PositiveIntegerField(
        "usos máximos por cliente",
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Vacío: sin límite. Las de cumpleaños son siempre una por cliente y año.",
    )
    max_total_uses = models.PositiveIntegerField(
        "usos máximos en total", null=True, blank=True, validators=[MinValueValidator(1)]
    )
    birthday_window_days = models.PositiveSmallIntegerField(
        "días de margen alrededor del cumpleaños",
        default=7,
        validators=[MaxValueValidator(MAX_BIRTHDAY_WINDOW_DAYS)],
        help_text="Sin uso desde la Fase 10: el regalo de cumpleaños se concede el mismo día.",
    )
    status = models.CharField(
        "estado", max_length=8, choices=Status.choices, default=Status.DRAFT, db_index=True
    )

    class Meta:
        verbose_name = "promoción"
        verbose_name_plural = "promociones"
        ordering = ["-starts_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(kind__in=["PURCHASE", "BIRTHDAY"]), name="loyalty_promo_kind_valid"),
            models.CheckConstraint(
                condition=Q(status__in=["DRAFT", "ACTIVE", "PAUSED", "ENDED"]), name="loyalty_promo_status_valid"
            ),
            # `isnull=False` explícito: en SQL `NULL >= 1` es desconocido y un
            # CHECK desconocido se da por cumplido.
            models.CheckConstraint(
                condition=(
                    Q(
                        bonus_type="FIXED_POINTS",
                        fixed_points__isnull=False,
                        fixed_points__gte=1,
                        fixed_points__lte=10000,
                        multiplier__isnull=True,
                    )
                    | Q(
                        bonus_type="MULTIPLIER",
                        multiplier__isnull=False,
                        multiplier__gt=Decimal("1.00"),
                        multiplier__lte=Decimal("10.00"),
                        fixed_points__isnull=True,
                    )
                ),
                name="loyalty_promo_bonus_valid",
            ),
            models.CheckConstraint(
                condition=Q(ends_at__isnull=True) | Q(ends_at__gt=models.F("starts_at")),
                name="loyalty_promo_dates_valid",
            ),
            models.CheckConstraint(
                condition=Q(min_purchase_amount__isnull=True) | Q(min_purchase_amount__gte=Decimal("0.01")),
                name="loyalty_promo_min_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(max_uses_per_customer__isnull=True) | Q(max_uses_per_customer__gte=1),
                name="loyalty_promo_customer_limit_positive",
            ),
            models.CheckConstraint(
                condition=Q(max_total_uses__isnull=True) | Q(max_total_uses__gte=1),
                name="loyalty_promo_total_limit_positive",
            ),
            models.CheckConstraint(
                condition=Q(birthday_window_days__lte=31), name="loyalty_promo_birthday_window_range"
            ),
            models.CheckConstraint(
                condition=~Q(kind="BIRTHDAY") | Q(bonus_type="FIXED_POINTS"),
                name="loyalty_promo_birthday_fixed_points",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        errors = {}
        if self.bonus_type == self.BonusType.FIXED_POINTS:
            if not self.fixed_points:
                errors["fixed_points"] = "Indica los puntos que da la promoción."
            if self.multiplier is not None:
                errors["multiplier"] = "Deja vacío el multiplicador en una promoción de puntos fijos."
        elif self.bonus_type == self.BonusType.MULTIPLIER:
            if self.multiplier is None:
                errors["multiplier"] = "Indica el multiplicador."
            if self.fixed_points is not None:
                errors["fixed_points"] = "Deja vacíos los puntos fijos en una promoción con multiplicador."
        if self.kind == self.Kind.BIRTHDAY and self.bonus_type != self.BonusType.FIXED_POINTS:
            errors["bonus_type"] = "Las promociones de cumpleaños regalan puntos fijos: no admiten multiplicador."
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            errors["ends_at"] = "La fecha de fin debe ser posterior a la de inicio."
        if errors:
            raise ValidationError(errors)


class PointsTransaction(models.Model):
    """
    Movimiento del ledger de puntos. Inmutable: no se edita ni se borra.

    El saldo del cliente es la suma de sus movimientos (`balance_after` guarda
    además el saldo resultante para auditarlo). Los errores se corrigen con un
    movimiento compensatorio (`REVERSAL`) o un ajuste (`ADJUSTMENT`), nunca
    modificando filas. Los puntos los calcula siempre el servidor.
    """

    class Kind(models.TextChoices):
        EARN_PURCHASE = "EARN_PURCHASE", "Compra"
        PROMOTION_BONUS = "PROMOTION_BONUS", "Promoción"
        ADJUSTMENT = "ADJUSTMENT", "Ajuste manual"
        REVERSAL = "REVERSAL", "Compensación"
        # Canje de una recompensa (Fase 7, `ledger.spend_points`).
        REDEMPTION = "REDEMPTION", "Canje"
        # Regalo de cumpleaños sin compra (Fase 10, `ledger.grant_birthday_gift`).
        BIRTHDAY_GIFT = "BIRTHDAY_GIFT", "Regalo de cumpleaños"
        # Puntos vencidos según la política de caducidad (Fase 14, `ledger.expire_points`).
        EXPIRATION = "EXPIRATION", "Puntos caducados"

    public_id = models.UUIDField("identificador", default=uuid.uuid4, unique=True, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="cliente",
        on_delete=models.PROTECT,
        related_name="points_transactions",
    )
    kind =models.CharField("tipo", max_length=16, choices=Kind.choices)
    points = models.IntegerField("puntos")
    balance_after = models.IntegerField("saldo resultante")
    purchase = models.ForeignKey(
        "purchases.Purchase",
        verbose_name="compra",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="points_transactions",
    )
    promotion = models.ForeignKey(
        Promotion,
        verbose_name="promoción",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="points_transactions",
    )
    birthday_year = models.PositiveSmallIntegerField(
        "año del cumpleaños",
        null=True,
        blank=True,
        help_text="Solo en promociones de cumpleaños: impide más de una por cliente y año.",
    )
    reverses = models.OneToOneField(
        "self",
        verbose_name="compensa a",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversal",
    )
    rule = models.ForeignKey(
        LoyaltyRule,
        verbose_name="regla de conversión",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    base_amount = models.DecimalField("importe base (€)", max_digits=8, decimal_places=2, null=True, blank=True)
    points_per_euro = models.DecimalField(
        "puntos por euro aplicados", max_digits=6, decimal_places=2, null=True, blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="registrado por",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    reason = models.CharField("motivo", max_length=200, blank=True)
    idempotency_key = models.UUIDField("referencia de idempotencia", null=True, blank=True, unique=True)
    created_at = models.DateTimeField("fecha", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "movimiento de puntos"
        verbose_name_plural = "movimientos de puntos"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["customer", "created_at"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    kind__in=[
                        "EARN_PURCHASE",
                        "PROMOTION_BONUS",
                        "ADJUSTMENT",
                        "REVERSAL",
                        "REDEMPTION",
                        "BIRTHDAY_GIFT",
                        "EXPIRATION",
                    ]
                ),
                name="loyalty_points_kind_valid",
            ),
            models.CheckConstraint(condition=~Q(points=0), name="loyalty_points_nonzero"),
            models.CheckConstraint(condition=Q(balance_after__gte=0), name="loyalty_points_balance_nonnegative"),
            models.CheckConstraint(
                condition=~Q(kind="EARN_PURCHASE")
                | Q(purchase__isnull=False, promotion__isnull=True, points__gt=0),
                name="loyalty_points_earn_shape",
            ),
            models.CheckConstraint(
                condition=~Q(kind="PROMOTION_BONUS")
                | Q(purchase__isnull=False, promotion__isnull=False, points__gt=0),
                name="loyalty_points_promotion_shape",
            ),
            models.CheckConstraint(
                condition=~Q(kind="REVERSAL") | Q(reverses__isnull=False),
                name="loyalty_points_reversal_shape",
            ),
            models.CheckConstraint(
                condition=~Q(kind="ADJUSTMENT") | (Q(created_by__isnull=False) & ~Q(reason="")),
                name="loyalty_points_adjustment_shape",
            ),
            models.CheckConstraint(
                condition=~Q(kind="REDEMPTION") | Q(points__lt=0), name="loyalty_points_redemption_negative"
            ),
            models.CheckConstraint(
                condition=Q(birthday_year__isnull=True) | Q(kind__in=["PROMOTION_BONUS", "BIRTHDAY_GIFT"]),
                name="loyalty_points_birthday_only_promotion",
            ),
            models.CheckConstraint(
                condition=~Q(kind="BIRTHDAY_GIFT")
                | Q(purchase__isnull=True, promotion__isnull=False, birthday_year__isnull=False, points__gt=0),
                name="loyalty_points_birthday_gift_shape",
            ),
            models.CheckConstraint(
                condition=~Q(kind="EXPIRATION") | Q(purchase__isnull=True, promotion__isnull=True, points__lt=0),
                name="loyalty_points_expiration_shape",
            ),
            # Una compra genera como máximo un movimiento de puntos base...
            models.UniqueConstraint(
                fields=["purchase"], condition=Q(kind="EARN_PURCHASE"), name="loyalty_points_one_earn_per_purchase"
            ),
            # ...y como máximo una bonificación por promoción.
            models.UniqueConstraint(
                fields=["promotion", "purchase"],
                condition=Q(kind="PROMOTION_BONUS"),
                name="loyalty_points_one_bonus_per_promotion_purchase",
            ),
            # Una sola promoción de cumpleaños por cliente y año.
            models.UniqueConstraint(
                fields=["customer", "birthday_year"],
                condition=Q(birthday_year__isnull=False),
                name="loyalty_points_one_birthday_per_year",
            ),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} {self.points:+d} · {self.public_id}"


class BirthdayMessage(models.Model):
    """
    Textos del aviso de cumpleaños que edita el propietario (Fase 14).

    Una sola fila (id = 1, también restringido en la BD). Un campo vacío
    significa "usar el texto por defecto" de `templates/notifications/birthday_*`.
    El único marcador admitido es `{puntos}` y se sustituye sin el motor de
    plantillas (`birthday_settings.render_text`). El enlace de baja lo añade
    siempre la plantilla: no forma parte del texto editable.
    """

    SINGLETON_ID = 1
    MAX_SUBJECT = 120
    MAX_EMAIL_BODY = 2000
    MAX_SMS_BODY = 200

    email_subject = models.CharField("asunto del email", max_length=MAX_SUBJECT, blank=True)
    email_body = models.TextField("mensaje del email", max_length=MAX_EMAIL_BODY, blank=True)
    sms_body = models.CharField("mensaje SMS", max_length=MAX_SMS_BODY, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="modificado por",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
    )
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        verbose_name = "aviso de cumpleaños"
        verbose_name_plural = "aviso de cumpleaños"
        constraints = [models.CheckConstraint(condition=Q(id=1), name="loyalty_birthdaymessage_singleton")]

    def __str__(self):
        return "Aviso de cumpleaños"

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_ID
        super().save(*args, **kwargs)
