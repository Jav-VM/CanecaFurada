"""
Campañas promocionales del propietario (Fase 10).

Flujo: el propietario redacta la campaña (`DRAFT`) y la programa
(`QUEUED`) desde el dashboard; la petición web responde al momento. El
comando `process_notifications` la reparte (`DISPATCHED`): crea una
notificación por cliente que **en ese momento** tiene el consentimiento del
canal (y, siempre, el email verificado), y las envía por lotes. Antes de
cada envío se vuelve a comprobar el consentimiento (`services.deliver`), así
que quien se da de baja entre medias no la recibe.

Nunca se envía a empleados ni propietarios, ni a cuentas desactivadas. Un
cliente recibe cada campaña una sola vez (`dedup_key`). Todo cambio queda
auditado sin el texto de la campaña.
"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import CustomerProfile, User
from apps.accounts.permissions import is_owner
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event

from . import services
from .models import Campaign, Channel, Notification

Status = Campaign.Status
EDITABLE_FIELDS = ("name", "channel", "subject", "body")


def _require_owner(actor):
    if not is_owner(actor):
        raise PermissionDenied("Solo el propietario gestiona las campañas.")


def _audit(actor, campaign, **metadata):
    record_audit_event(action=AuditEvent.Action.CAMPAIGN_UPDATED, actor=actor, target=campaign, metadata=metadata)


def _validate(campaign):
    campaign.name = " ".join((campaign.name or "").split())
    campaign.subject = " ".join((campaign.subject or "").split())
    campaign.body = (campaign.body or "").strip()
    errors = {}
    if not campaign.body:
        errors["body"] = "Escribe el mensaje."
    if campaign.channel == Channel.SMS:
        campaign.subject = ""
        if len(campaign.body) > Campaign.MAX_SMS_BODY:
            errors["body"] = f"Un SMS admite como máximo {Campaign.MAX_SMS_BODY} caracteres."
    else:
        if not campaign.subject:
            errors["subject"] = "Escribe el asunto del email."
        if len(campaign.body) > Campaign.MAX_EMAIL_BODY:
            errors["body"] = f"El mensaje admite como máximo {Campaign.MAX_EMAIL_BODY} caracteres."
    if errors:
        raise ValidationError(errors)
    campaign.full_clean(exclude=["created_by"])


@transaction.atomic
def save_campaign(*, actor, campaign, data):
    """Crea o modifica una campaña en borrador (lista blanca de campos)."""
    _require_owner(actor)
    if campaign.pk is not None:
        campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
        if campaign.status != Status.DRAFT:
            raise ValidationError("Solo se pueden modificar las campañas en borrador.")
    else:
        campaign.created_by = actor
    for name in EDITABLE_FIELDS:
        if name in data:
            setattr(campaign, name, data[name] or "")
    _validate(campaign)
    created = campaign.pk is None
    campaign.save()
    _audit(actor, campaign, event="created" if created else "edited", channel=campaign.channel)
    return campaign


@transaction.atomic
def queue_campaign(*, actor, campaign):
    """Programa el envío. El reparto lo hace `process_notifications`, no esta petición."""
    _require_owner(actor)
    campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
    if campaign.status == Status.QUEUED:
        return campaign
    if campaign.status != Status.DRAFT:
        raise ValidationError("Esta campaña ya no se puede programar.")
    if campaign.channel == Channel.SMS and not services.sms_available():
        raise ValidationError("No hay ningún proveedor de SMS configurado: la campaña no puede enviarse por SMS.")
    _validate(campaign)
    campaign.status = Status.QUEUED
    campaign.queued_at = timezone.now()
    campaign.save(update_fields=["status", "queued_at", "updated_at"])
    _audit(actor, campaign, event="queued", channel=campaign.channel)
    return campaign


@transaction.atomic
def cancel_campaign(*, actor, campaign):
    _require_owner(actor)
    campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
    if campaign.status == Status.CANCELLED:
        return campaign
    if campaign.status not in (Status.DRAFT, Status.QUEUED):
        raise ValidationError("Una campaña ya repartida no se puede cancelar.")
    campaign.status = Status.CANCELLED
    campaign.save(update_fields=["status", "updated_at"])
    _audit(actor, campaign, event="cancelled")
    return campaign


def eligible_recipients(channel):
    """Clientes activos con email verificado y consentimiento vigente del canal."""
    profiles = CustomerProfile.objects.filter(
        user__is_active=True, user__role=User.Role.CUSTOMER, user__email_verified_at__isnull=False
    )
    if channel == Channel.EMAIL:
        profiles = profiles.filter(promo_email_opt_in=True)
    else:
        profiles = profiles.filter(promo_sms_opt_in=True).exclude(phone_number="")
    return User.objects.filter(pk__in=profiles.values("user_id")).order_by("pk")


def dispatch_queued(now=None):
    """Reparte las campañas programadas. Devuelve el número de notificaciones creadas."""
    created_total = 0
    for campaign_id in Campaign.objects.filter(status=Status.QUEUED).order_by("queued_at").values_list("pk", flat=True):
        with transaction.atomic():
            campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
            if campaign.status != Status.QUEUED:
                continue
            if campaign.channel == Channel.SMS and not services.sms_available():
                # Se queda programada hasta que haya proveedor (o el propietario la cancele).
                continue
            count = 0
            for user in eligible_recipients(campaign.channel).iterator():
                _, created = services.enqueue(
                    kind=Notification.Kind.CAMPAIGN,
                    recipient=user,
                    channel=campaign.channel,
                    campaign=campaign,
                    dedup_key=f"campaign:{campaign.public_id}:{user.public_id}",
                )
                count += int(created)
            campaign.status = Status.DISPATCHED
            campaign.dispatched_at = now or timezone.now()
            campaign.recipients_count = Notification.objects.filter(campaign=campaign).count()
            campaign.save(update_fields=["status", "dispatched_at", "recipients_count", "updated_at"])
            _audit(None, campaign, event="dispatched", recipients=campaign.recipients_count)
            created_total += count
    return created_total
