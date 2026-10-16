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

from apps.core.models import TimeStampedModel


class Channel(models.TextChoices):
    EMAIL = "EMAIL", "Email"
    SMS = "SMS", "SMS"


class Campaign(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        QUEUED = "QUEUED", "Programada para envío"
        DISPATCHED = "DISPATCHED", "Repartida"
        CANCELLED = "CANCELLED", "Cancelada"

    MAX_EMAIL_BODY = 2000
    MAX_SMS_BODY = 320

    public_id = models.UUIDField("identificador", default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField("nombre interno", max_length=100)
    channel = models.CharField("canal", max_length=8, choices=Channel.choices, default=Channel.EMAIL)
    subject = models.CharField("asunto", max_length=120, blank=True, help_text="Solo email.")
    body = models.TextField(
        "mensaje",
        max_length=MAX_EMAIL_BODY,
        help_text="Texto plano. No incluyas datos personales de clientes ni de empleados.",
    )
    status = models.CharField("estado", max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="creada por", on_delete=models.PROTECT, related_name="+"
    )
    queued_at = models.DateTimeField("programada el", null=True, blank=True)
    dispatched_at = models.DateTimeField("repartida el", null=True, blank=True)
    recipients_count = models.PositiveIntegerField("destinatarios", null=True, blank=True)

    class Meta:
        verbose_name = "campaña promocional"
        verbose_name_plural = "campañas promocionales"
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
        EMAIL_VERIFICATION = "EMAIL_VERIFICATION", "Verificación del email"
        EMAIL_CHANGE = "EMAIL_CHANGE", "Confirmación de cambio de email"
        EMAIL_CHANGED_NOTICE = "EMAIL_CHANGED_NOTICE", "Aviso de email cambiado"
        EXISTING_ACCOUNT = "EXISTING_ACCOUNT", "Aviso de cuenta existente"
        PASSWORD_RESET = "PASSWORD_RESET", "Recuperación de la cuenta"
        RESERVATION_RECEIVED = "RESERVATION_RECEIVED", "Reserva recibida"
        RESERVATION_CONFIRMED = "RESERVATION_CONFIRMED", "Reserva confirmada"
        RESERVATION_REJECTED = "RESERVATION_REJECTED", "Reserva rechazada"
        RESERVATION_CANCELLED = "RESERVATION_CANCELLED", "Reserva cancelada"
        RESERVATION_OWNER_ALERT = "RESERVATION_OWNER_ALERT", "Aviso de reserva al propietario"
        CAMPAIGN = "CAMPAIGN", "Campaña promocional"
        BIRTHDAY = "BIRTHDAY", "Promoción de cumpleaños"
        # Fase 14: informa del estado de la cuenta, sin publicidad (transaccional).
        POINTS_EXPIRING = "POINTS_EXPIRING", "Aviso de puntos que van a caducar"

    class Category(models.TextChoices):
        TRANSACTIONAL = "TRANSACTIONAL", "Transaccional"
        PROMOTIONAL = "PROMOTIONAL", "Promocional"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        SENDING = "SENDING", "Enviando"
        SENT = "SENT", "Enviada"
        FAILED = "FAILED", "Fallida"
        SKIPPED = "SKIPPED", "No enviada"

    # Comunicaciones comerciales: exigen consentimiento vigente al enviarse.
    PROMOTIONAL_KINDS = ("CAMPAIGN", "BIRTHDAY")
    # Llevan un enlace con token: se envían al momento y no guardan contexto.
    SENSITIVE_KINDS = ("EMAIL_VERIFICATION", "EMAIL_CHANGE", "PASSWORD_RESET")

    public_id = models.UUIDField("identificador", default=uuid.uuid4, unique=True, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="destinatario",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField("tipo", max_length=32, choices=Kind.choices)
    category = models.CharField("categoría", max_length=16, choices=Category.choices)
    channel = models.CharField("canal", max_length=8, choices=Channel.choices, default=Channel.EMAIL)
    status = models.CharField("estado", max_length=8, choices=Status.choices, default=Status.PENDING, db_index=True)
    context = models.JSONField("datos del mensaje", default=dict, blank=True, help_text="Sin tokens ni datos personales.")
    dedup_key = models.CharField("clave de idempotencia", max_length=120, null=True, blank=True, unique=True)
    campaign = models.ForeignKey(
        Campaign, verbose_name="campaña", null=True, blank=True, on_delete=models.PROTECT, related_name="notifications"
    )
    attempts = models.PositiveSmallIntegerField("intentos", default=0)
    next_attempt_at = models.DateTimeField("próximo intento", null=True, blank=True)
    last_error = models.CharField(
        "último error", max_length=100, blank=True, help_text="Tipo de error o motivo de no envío; nunca el mensaje."
    )
    sent_at = models.DateTimeField("enviada el", null=True, blank=True)
    created_at = models.DateTimeField("creada", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("actualizada", auto_now=True)

    class Meta:
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"
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
