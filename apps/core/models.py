from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    """Base abstracta con fechas de creación y modificación."""

    created_at = models.DateTimeField(_("creado"), auto_now_add=True)
    updated_at = models.DateTimeField(_("actualizado"), auto_now=True)

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
        OWNER_CREATED = "OWNER_CREATED", _("Propietario creado")
        EMPLOYEE_CREATED = "EMPLOYEE_CREATED", _("Empleado creado")
        CUSTOMER_CREATED = "CUSTOMER_CREATED", _("Cliente creado")
        ROLE_CHANGED = "ROLE_CHANGED", _("Rol modificado")
        ACCOUNT_ACTIVATED = "ACCOUNT_ACTIVATED", _("Cuenta activada")
        ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED", _("Cuenta desactivada")
        EMAIL_VERIFIED = "EMAIL_VERIFIED", _("Email verificado")
        EMAIL_CHANGE_REQUESTED = "EMAIL_CHANGE_REQUESTED", _("Cambio de email solicitado")
        EMAIL_CHANGED = "EMAIL_CHANGED", _("Email modificado")
        PROFILE_UPDATED = "PROFILE_UPDATED", _("Perfil modificado")
        PRODUCT_STATUS_CHANGED = "PRODUCT_STATUS_CHANGED", _("Publicación de producto modificada")
        PRODUCT_AVAILABILITY_CHANGED = "PRODUCT_AVAILABILITY_CHANGED", _("Disponibilidad de producto modificada")
        QR_ROTATED = "QR_ROTATED", _("QR personal renovado")
        LOYALTY_RULE_CREATED = "LOYALTY_RULE_CREATED", _("Conversión de puntos modificada")
        PROMOTION_SAVED = "PROMOTION_SAVED", _("Promoción creada o modificada")
        POINTS_ADJUSTED = "POINTS_ADJUSTED", _("Ajuste manual de puntos")
        POINTS_REVERSED = "POINTS_REVERSED", _("Movimiento de puntos compensado")
        REWARD_SAVED = "REWARD_SAVED", _("Recompensa creada o modificada")
        REDEMPTION_VALIDATED = "REDEMPTION_VALIDATED", _("Canje validado")
        CUSTOMER_DATA_VIEWED = "CUSTOMER_DATA_VIEWED", _("Ficha de cliente consultada")
        SITE_CONTENT_UPDATED = "SITE_CONTENT_UPDATED", _("Contenido del local modificado")
        EVENT_SAVED = "EVENT_SAVED", _("Evento creado o modificado")
        RESERVATION_STATUS_CHANGED = "RESERVATION_STATUS_CHANGED", _("Estado de reserva modificado")
        RESERVATION_DATA_VIEWED = "RESERVATION_DATA_VIEWED", _("Reserva consultada con datos de contacto")
        CAMPAIGN_UPDATED = "CAMPAIGN_UPDATED", _("Campaña promocional modificada")
        BIRTHDAY_PROMOTIONS_RUN = "BIRTHDAY_PROMOTIONS_RUN", _("Promociones de cumpleaños procesadas")
        # Fase 11: auditoría y API.
        PASSWORD_CHANGED = "PASSWORD_CHANGED", _("Contraseña cambiada")
        API_SESSIONS_REVOKED = "API_SESSIONS_REVOKED", _("Sesiones de la app cerradas")
        # Fase 14: caducidad de puntos y regalo de cumpleaños configurables.
        POINTS_EXPIRY_POLICY_CREATED = "POINTS_EXPIRY_POLICY_CREATED", _("Caducidad de puntos modificada")
        POINTS_EXPIRY_RUN = "POINTS_EXPIRY_RUN", _("Caducidad de puntos procesada")
        BIRTHDAY_SETTINGS_UPDATED = "BIRTHDAY_SETTINGS_UPDATED", _("Regalo de cumpleaños modificado")
        # Fase 24: productos, categorías, estilos y cartas de grifos creados o editados desde el dashboard.
        CATALOG_SAVED = "CATALOG_SAVED", _("Carta modificada")

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("actor"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        help_text=_("Vacío cuando la acción la ejecuta un procedimiento administrativo (CLI)."),
    )
    action = models.CharField(_("acción"), max_length=40, choices=Action.choices)
    target_public_id = models.UUIDField(_("identificador del objetivo"), null=True, blank=True)
    metadata = models.JSONField(_("metadatos"), default=dict, blank=True)
    created_at = models.DateTimeField(_("fecha"), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("evento de auditoría")
        verbose_name_plural = _("eventos de auditoría")
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["action", "created_at"])]

    def __str__(self):
        return f"{self.get_action_display()} · {self.created_at:%Y-%m-%d %H:%M}"
