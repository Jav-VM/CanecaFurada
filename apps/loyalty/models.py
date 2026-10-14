from django.conf import settings
from django.db import models

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
