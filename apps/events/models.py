"""
Eventos y reservas (Fase 10).

- `Event`: lo que organiza el local. El propietario lo crea, edita, publica y
  archiva; nada se borra (las reservas lo referencian con `PROTECT`).
- `Reservation`: solicitud de un cliente con email verificado, de mesa o para
  un evento que admite reservas. Se confirma a mano. Estados y transiciones:

      PENDING ──► CONFIRMED ──► COMPLETED
         │            │
         ├──► REJECTED └──► CANCELLED
         └──► CANCELLED

  `REJECTED`, `CANCELLED` y `COMPLETED` son finales. Las transiciones las
  valida `services.py` con la fila bloqueada; aquí solo los datos y sus
  invariantes (también en BD).

Privacidad: la reserva no copia datos personales; el contacto se toma del
perfil del cliente y solo lo ve el propietario en el detalle de la reserva
(consulta auditada). Las notas del cliente no se envían por email.
"""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.catalog.validators import validate_image_extension, validate_image_file
from apps.core.models import TimeStampedModel


def event_image_path(instance, filename):
    # Nombre aleatorio: no se publica el nombre original del fichero.
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    ext = "jpg" if ext == "jpeg" else ext
    return f"events/{uuid.uuid4().hex}.{ext}"


class Event(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        PUBLISHED = "PUBLISHED", "Publicado"
        ARCHIVED = "ARCHIVED", "Archivado"

    MAX_CAPACITY = 1000

    public_id = models.UUIDField("identificador", default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField("título", max_length=120)
    summary = models.CharField("resumen", max_length=300, blank=True, help_text="Una o dos frases para el listado.")
    description = models.TextField("descripción", max_length=3000, blank=True)
    starts_at = models.DateTimeField("empieza")
    ends_at = models.DateTimeField("termina", null=True, blank=True)
    image = models.ImageField(
        "imagen",
        upload_to=event_image_path,
        blank=True,
        width_field="image_width",
        height_field="image_height",
        validators=[validate_image_extension, validate_image_file],
        help_text="JPEG, PNG o WebP. Opcional.",
    )
    image_width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    image_height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    status = models.CharField("estado", max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    is_featured = models.BooleanField("destacado en el inicio", default=False)
    accepts_reservations = models.BooleanField("admite reservas", default=False)
    capacity = models.PositiveIntegerField(
        "plazas",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_CAPACITY)],
        help_text="Personas en reservas confirmadas. Vacío: sin límite.",
    )
    published_at = models.DateTimeField("publicado el", null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "evento"
        verbose_name_plural = "eventos"
        ordering = ["starts_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["DRAFT", "PUBLISHED", "ARCHIVED"]), name="events_event_status_valid"
            ),
            models.CheckConstraint(
                condition=Q(ends_at__isnull=True) | Q(ends_at__gt=models.F("starts_at")),
                name="events_event_dates_valid",
            ),
            models.CheckConstraint(
                condition=Q(capacity__isnull=True) | (Q(capacity__gte=1) & Q(capacity__lte=1000)),
                name="events_event_capacity_range",
            ),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        self.title = " ".join((self.title or "").split())
        self.summary = " ".join((self.summary or "").split())
        self.description = (self.description or "").strip()
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "La hora de fin debe ser posterior a la de inicio."})

    def has_started(self, now=None):
        return self.starts_at <= (now or timezone.now())


class Reservation(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente de confirmar"
        CONFIRMED = "CONFIRMED", "Confirmada"
        REJECTED = "REJECTED", "Rechazada"
        CANCELLED = "CANCELLED", "Cancelada"
        COMPLETED = "COMPLETED", "Completada"

    ACTIVE_STATUSES = (Status.PENDING, Status.CONFIRMED)
    TRANSITIONS = {
        Status.PENDING: {Status.CONFIRMED, Status.REJECTED, Status.CANCELLED},
        Status.CONFIRMED: {Status.CANCELLED, Status.COMPLETED},
    }
    MAX_PARTY_SIZE = 50

    public_id = models.UUIDField("identificador", default=uuid.uuid4, unique=True, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="cliente", on_delete=models.PROTECT, related_name="reservations"
    )
    event = models.ForeignKey(
        Event, verbose_name="evento", null=True, blank=True, on_delete=models.PROTECT, related_name="reservations"
    )
    requested_for = models.DateTimeField("fecha y hora", db_index=True)
    party_size = models.PositiveSmallIntegerField(
        "personas", validators=[MinValueValidator(1), MaxValueValidator(MAX_PARTY_SIZE)]
    )
    notes = models.CharField(
        "comentarios del cliente",
        max_length=300,
        blank=True,
        help_text="Solo los ve el propietario. No se envían por email.",
    )
    status = models.CharField("estado", max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    owner_message = models.CharField(
        "mensaje del local", max_length=300, blank=True, help_text="Se muestra al cliente y va en el email."
    )
    status_changed_at = models.DateTimeField("último cambio de estado", null=True, blank=True)
    status_changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="cambiado por",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    idempotency_key = models.UUIDField("referencia de idempotencia", unique=True)
    created_at = models.DateTimeField("solicitada", default=timezone.now, db_index=True)
    updated_at = models.DateTimeField("actualizada", auto_now=True)

    class Meta:
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        ordering = ["-requested_for", "-id"]
        indexes = [models.Index(fields=["customer", "status"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["PENDING", "CONFIRMED", "REJECTED", "CANCELLED", "COMPLETED"]),
                name="events_reservation_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(party_size__gte=1) & Q(party_size__lte=50), name="events_reservation_party_size_range"
            ),
            models.CheckConstraint(
                condition=Q(status="PENDING") | Q(status_changed_at__isnull=False),
                name="events_reservation_decision_dated",
            ),
            # Una sola reserva activa por cliente y evento.
            models.UniqueConstraint(
                fields=["customer", "event"],
                condition=Q(status__in=["PENDING", "CONFIRMED"], event__isnull=False),
                name="events_reservation_one_active_per_event",
            ),
        ]

    def __str__(self):
        return f"Reserva {self.public_id}"

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    def can_transition_to(self, status):
        return status in self.TRANSITIONS.get(self.status, set())
