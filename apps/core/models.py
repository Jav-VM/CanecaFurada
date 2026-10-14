from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """Base abstracta con fechas de creación y modificación."""

    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        abstract = True


class AuditEvent(models.Model):
    """
    Registro inmutable de operaciones sensibles.

    No debe contener datos personales, contraseñas ni tokens: el objetivo se
    identifica por su `public_id` y `metadata` solo admite datos técnicos
    (por ejemplo, rol anterior y nuevo).
    """

    class Action(models.TextChoices):
        OWNER_CREATED = "OWNER_CREATED", "Propietario creado"
        EMPLOYEE_CREATED = "EMPLOYEE_CREATED", "Empleado creado"
        CUSTOMER_CREATED = "CUSTOMER_CREATED", "Cliente creado"
        ROLE_CHANGED = "ROLE_CHANGED", "Rol modificado"
        ACCOUNT_ACTIVATED = "ACCOUNT_ACTIVATED", "Cuenta activada"
        ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED", "Cuenta desactivada"
        EMAIL_VERIFIED = "EMAIL_VERIFIED", "Email verificado"
        EMAIL_CHANGE_REQUESTED = "EMAIL_CHANGE_REQUESTED", "Cambio de email solicitado"
        EMAIL_CHANGED = "EMAIL_CHANGED", "Email modificado"
        PROFILE_UPDATED = "PROFILE_UPDATED", "Perfil modificado"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="actor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        help_text="Vacío cuando la acción la ejecuta un procedimiento administrativo (CLI).",
    )
    action = models.CharField("acción", max_length=40, choices=Action.choices)
    target_public_id = models.UUIDField("identificador del objetivo", null=True, blank=True)
    metadata = models.JSONField("metadatos", default=dict, blank=True)
    created_at = models.DateTimeField("fecha", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "evento de auditoría"
        verbose_name_plural = "eventos de auditoría"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["action", "created_at"])]

    def __str__(self):
        return f"{self.get_action_display()} · {self.created_at:%Y-%m-%d %H:%M}"
