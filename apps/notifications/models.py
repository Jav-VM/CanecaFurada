"""
Registro de notificaciones y campañas promocionales (Fase 10).

- `Notification`: cada mensaje que el sistema intenta enviar, con su estado.
  Es el registro de lo que se ha enviado de verdad: `SENT` solo se marca
  cuando el proveedor (SMTP o SMS) ha aceptado el mensaje.
  * No guarda el destinatario en claro (se toma del usuario al enviar) ni el
    cuerpo del mensaje.
  * `context` solo admite datos no sensibles para volver a componer el
    mensaje en un reintento. Los mensajes con tokens (verificación de email,
    recuperación de la cuenta) se envían al momento y **nunca** guardan
    contexto: si fallan, el usuario pide otro enlace.
  * `dedup_key` (única) impide generar dos veces la misma notificación
    (cumpleaños de un año, una campaña a un cliente, un cambio de estado de
    una reserva).
- `Campaign`: comunicación promocional redactada por el propietario. Se
  encola desde el dashboard y la reparte `process_notifications`, nunca la
  petición web.

Las reglas están en `services.py` y `campaigns.py`.
"""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class Channel(models.TextChoices):
    EMAIL = "EMAIL", _("Email")
    SMS = "SMS", "SMS"


class Campaign(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", _("Borrador")
        QUEUED = "QUEUED", _("Programada para envío")
        DISPATCHED = "DISPATCHED", _("Repartida")
        CANCELLED = "CANCELLED", _("Cancelada")

    MAX_EMAIL_BODY = 2000
    MAX_SMS_BODY = 320

    public_id = models.UUIDField(_("identificador"), default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(_("nombre interno"), max_length=100)
    channel = models.CharField(_("canal"), max_length=8, choices=Channel.choices, default=Channel.EMAIL)
    subject = models.CharField(_("asunto"), max_length=120, blank=True, help_text=_("Solo email."))
    body = models.TextField(
        _("mensaje"),
        max_length=MAX_EMAIL_BODY,
        help_text=_("Texto plano. No incluyas datos personales de clientes ni de empleados."),
    )
    status = models.CharField(_("estado"), max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("creada por"), on_delete=models.PROTECT, related_name="+"
    )
    queued_at = models.DateTimeField(_("programada el"), null=True, blank=True)
    dispatched_at = models.DateTimeField(_("repartida el"), null=True, blank=True)
    recipients_count = models.PositiveIntegerField(_("destinatarios"), null=True, blank=True)

    class Meta:
        verbose_name = _("campaña promocional")
        verbose_name_plural = _("campañas promocionales")
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["DRAFT", "QUEUED", "DISPATCHED", "CANCELLED"]),
                name="notifications_campaign_status_valid",
            ),
            models.CheckConstraint(condition=Q(channel__in=["EMAIL", "SMS"]), name="notifications_campaign_channel_valid"),
            models.CheckConstraint(condition=~Q(channel="EMAIL") | ~Q(subject=""), name="notifications_campaign_email_subject"),
        ]

    def __str__(self):
        return self.name


class Notification(models.Model):
    class Kind(models.TextChoices):
        EMAIL_VERIFICATION = "EMAIL_VERIFICATION", _("Verificación del email")
        EMAIL_CHANGE = "EMAIL_CHANGE", _("Confirmación de cambio de email")
        EMAIL_CHANGED_NOTICE = "EMAIL_CHANGED_NOTICE", _("Aviso de email cambiado")
        EXISTING_ACCOUNT = "EXISTING_ACCOUNT", _("Aviso de cuenta existente")
        PASSWORD_RESET = "PASSWORD_RESET", _("Recuperación de la cuenta")
        RESERVATION_RECEIVED = "RESERVATION_RECEIVED", _("Reserva recibida")
        RESERVATION_CONFIRMED = "RESERVATION_CONFIRMED", _("Reserva confirmada")
        RESERVATION_REJECTED = "RESERVATION_REJECTED", _("Reserva rechazada")
        RESERVATION_CANCELLED = "RESERVATION_CANCELLED", _("Reserva cancelada")
        RESERVATION_OWNER_ALERT = "RESERVATION_OWNER_ALERT", _("Aviso de reserva al propietario")
        CAMPAIGN = "CAMPAIGN", _("Campaña promocional")
        BIRTHDAY = "BIRTHDAY", _("Promoción de cumpleaños")
        # Fase 14: informa del estado de la cuenta, sin publicidad (transaccional).
        POINTS_EXPIRING = "POINTS_EXPIRING", _("Aviso de puntos que van a caducar")

    class Category(models.TextChoices):
        TRANSACTIONAL = "TRANSACTIONAL", _("Transaccional")
        PROMOTIONAL = "PROMOTIONAL", _("Promocional")

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pendiente")
        SENDING = "SENDING", _("Enviando")
        SENT = "SENT", _("Enviada")
        FAILED = "FAILED", _("Fallida")
        SKIPPED = "SKIPPED", _("No enviada")

    # Comunicaciones comerciales: exigen consentimiento vigente al enviarse.
    PROMOTIONAL_KINDS = ("CAMPAIGN", "BIRTHDAY")
    # Llevan un enlace con token: se envían al momento y no guardan contexto.
    SENSITIVE_KINDS = ("EMAIL_VERIFICATION", "EMAIL_CHANGE", "PASSWORD_RESET")

    public_id = models.UUIDField(_("identificador"), default=uuid.uuid4, unique=True, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("destinatario"),
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(_("tipo"), max_length=32, choices=Kind.choices)
    category = models.CharField(_("categoría"), max_length=16, choices=Category.choices)
    channel = models.CharField(_("canal"), max_length=8, choices=Channel.choices, default=Channel.EMAIL)
    status = models.CharField(_("estado"), max_length=8, choices=Status.choices, default=Status.PENDING, db_index=True)
    context = models.JSONField(_("datos del mensaje"), default=dict, blank=True, help_text=_("Sin tokens ni datos personales."))
    dedup_key = models.CharField(_("clave de idempotencia"), max_length=120, null=True, blank=True, unique=True)
    campaign = models.ForeignKey(
        Campaign, verbose_name=_("campaña"), null=True, blank=True, on_delete=models.PROTECT, related_name="notifications"
    )
    attempts = models.PositiveSmallIntegerField(_("intentos"), default=0)
    next_attempt_at = models.DateTimeField(_("próximo intento"), null=True, blank=True)
    last_error = models.CharField(
        _("último error"), max_length=100, blank=True, help_text=_("Tipo de error o motivo de no envío; nunca el mensaje.")
    )
    sent_at = models.DateTimeField(_("enviada el"), null=True, blank=True)
    created_at = models.DateTimeField(_("creada"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("actualizada"), auto_now=True)

    class Meta:
        verbose_name = _("notificación")
        verbose_name_plural = _("notificaciones")
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "next_attempt_at"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["PENDING", "SENDING", "SENT", "FAILED", "SKIPPED"]),
                name="notifications_status_valid",
            ),
            models.CheckConstraint(condition=Q(channel__in=["EMAIL", "SMS"]), name="notifications_channel_valid"),
            # La categoría se deriva del tipo: una promoción nunca pasa por transaccional.
            models.CheckConstraint(
                condition=(
                    Q(kind__in=["CAMPAIGN", "BIRTHDAY"], category="PROMOTIONAL")
                    | (~Q(kind__in=["CAMPAIGN", "BIRTHDAY"]) & Q(category="TRANSACTIONAL"))
                ),
                name="notifications_category_matches_kind",
            ),
            models.CheckConstraint(
                condition=Q(status="SENT", sent_at__isnull=False) | (~Q(status="SENT") & Q(sent_at__isnull=True)),
                name="notifications_sent_at_matches_status",
            ),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.get_status_display()} · {self.public_id}"

    @property
    def is_promotional(self):
        return self.category == self.Category.PROMOTIONAL
