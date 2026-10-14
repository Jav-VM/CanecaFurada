"""
Compras registradas por el personal.

Una compra es un registro inmutable de lo que el empleado (o propietario)
anotó en barra: cliente, quién la registró, importe, fecha y hora, origen,
estado y referencia de idempotencia. No es una factura ni la caja del local.

Se crea solo mediante `services.register_purchase`, dentro de una transacción.
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

MIN_AMOUNT = Decimal("0.01")


class Purchase(models.Model):
    class Source(models.TextChoices):
        MANUAL = "MANUAL", "Manual (panel del personal)"
        # Reservado para la futura integración con el TPV. No hay ningún flujo
        # que lo use: `services` rechaza los orígenes no habilitados.
        POS = "POS", "TPV"

    class Status(models.TextChoices):
        COMPLETED = "COMPLETED", "Registrada"
        # Reservado para anulaciones (fase posterior): una compra no se borra
        # ni se edita, se anula.
        VOIDED = "VOIDED", "Anulada"

    public_id = models.UUIDField(
        "identificador", default=uuid.uuid4, unique=True, editable=False
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="cliente",
        on_delete=models.PROTECT,
        related_name="purchases",
    )
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="registrada por",
        on_delete=models.PROTECT,
        related_name="registered_purchases",
    )
    amount = models.DecimalField(
        "importe (€)",
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(MIN_AMOUNT)],
    )
    created_at = models.DateTimeField("fecha y hora", auto_now_add=True, db_index=True)
    source = models.CharField("origen", max_length=10, choices=Source.choices, default=Source.MANUAL)
    status = models.CharField(
        "estado", max_length=10, choices=Status.choices, default=Status.COMPLETED, db_index=True
    )
    idempotency_key = models.UUIDField(
        "referencia de idempotencia",
        unique=True,
        editable=False,
        help_text="La genera el servidor al mostrar el formulario; un reenvío no crea otra compra.",
    )
    external_reference = models.CharField(
        "referencia externa",
        max_length=64,
        blank=True,
        editable=False,
        help_text="Reservado para el identificador del ticket del TPV.",
    )

    class Meta:
        verbose_name = "compra"
        verbose_name_plural = "compras"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["customer", "created_at"]),
            models.Index(fields=["registered_by", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=MIN_AMOUNT), name="purchases_amount_positive"),
            models.CheckConstraint(condition=Q(source__in=["MANUAL", "POS"]), name="purchases_source_valid"),
            models.CheckConstraint(
                condition=Q(status__in=["COMPLETED", "VOIDED"]), name="purchases_status_valid"
            ),
            models.CheckConstraint(
                condition=~Q(customer=models.F("registered_by")), name="purchases_not_self_registered"
            ),
            # Un mismo ticket del TPV no puede registrarse dos veces.
            models.UniqueConstraint(
                fields=["source", "external_reference"],
                condition=~Q(external_reference=""),
                name="purchases_unique_external_reference",
            ),
        ]

    def __str__(self):
        return f"Compra {self.public_id}"
