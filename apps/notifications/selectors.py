"""Lecturas de notificaciones y campañas para el dashboard (solo propietario)."""
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.utils.translation import gettext_lazy as _

from apps.accounts.permissions import is_owner

from . import campaigns, sms
from .models import Campaign, Channel, Notification

# Backends de email que no envían nada (desarrollo y tests).
_SIMULATED_EMAIL_BACKENDS = {
    "django.core.mail.backends.console.EmailBackend": _("Consola (desarrollo): los emails no se envían, se muestran en la terminal."),
    "django.core.mail.backends.locmem.EmailBackend": _("Memoria (tests): los emails no se envían."),
    "django.core.mail.backends.filebased.EmailBackend": _("Fichero (desarrollo): los emails no se envían."),
    "django.core.mail.backends.dummy.EmailBackend": _("Nulo: los emails no se envían."),
}


def _require_owner(actor):
    if not is_owner(actor):
        raise PermissionDenied(_("Solo el propietario puede ver las comunicaciones."))


@dataclass(frozen=True)
class ChannelStatus:
    email_real: bool
    email_note: str
    sms_configured: bool


def channel_status(*, actor):
    """Estado real de los canales, para no presentar envíos simulados como reales."""
    _require_owner(actor)
    note = _SIMULATED_EMAIL_BACKENDS.get(settings.EMAIL_BACKEND)
    return ChannelStatus(
        email_real=note is None,
        email_note=note or _("Proveedor configurado por variables de entorno (EMAIL_*)."),
        sms_configured=sms.is_configured(),
    )


def campaigns_for_owner(*, actor):
    _require_owner(actor)
    return Campaign.objects.annotate(
        sent=Count("notifications", filter=Q(notifications__status=Notification.Status.SENT)),
        skipped=Count("notifications", filter=Q(notifications__status=Notification.Status.SKIPPED)),
        failed=Count("notifications", filter=Q(notifications__status=Notification.Status.FAILED)),
    ).order_by("-created_at", "-id")


def campaign_for_owner(*, actor, public_id):
    _require_owner(actor)
    return Campaign.objects.filter(public_id=public_id).first()


def potential_recipients(*, actor, channel):
    """Cuántos clientes recibirían hoy una campaña por `channel`."""
    _require_owner(actor)
    if channel == Channel.SMS and not sms.is_configured():
        return 0
    return campaigns.eligible_recipients(channel).count()


def notification_log(*, actor, status="", kind=""):
    """Registro de notificaciones sin destinatarios ni contenido."""
    _require_owner(actor)
    queryset = Notification.objects.all()
    if status:
        queryset = queryset.filter(status=status)
    if kind:
        queryset = queryset.filter(kind=kind)
    return queryset.only(
        "public_id", "kind", "category", "channel", "status", "attempts", "last_error", "created_at", "sent_at"
    ).order_by("-created_at", "-id")


def notification_counts(*, actor):
    _require_owner(actor)
    rows = Notification.objects.values("status").annotate(total=Count("id"))
    return {row["status"]: row["total"] for row in rows}
