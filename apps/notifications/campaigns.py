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

Fase 19:
- **Destinatarios** `ALL` (todos los clientes con consentimiento) o `SELECTED`
  (los elegidos en el dashboard, guardados en `CampaignRecipient`). De los
  seleccionados solo reciben el mensaje los que tienen consentimiento.
- **Puntos de regalo**: al repartir, cada destinatario (`ALL`) o cada
  seleccionado (`SELECTED`, tenga o no consentimiento) activo y con email
  verificado recibe los puntos una sola vez (`ledger.grant_campaign_gift`),
  en la misma transacción que el reparto. «Sin caducidad» los marca
  `never_expires`.
- **Imagen** opcional, solo en email.
- `create_and_queue`: guarda y programa a la vez («Crear y enviar»).
- `send_copy_to_selection` (Fase 24): copia una campaña ya creada para los
  clientes seleccionados y la programa, con clave de idempotencia.
"""
import os

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files import File
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from apps.accounts.models import CustomerProfile, User
from apps.accounts.permissions import is_owner
from apps.core.i18n import site_text
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event
from apps.loyalty import ledger

from . import services
from .models import Campaign, CampaignRecipient, Channel, Notification

Status = Campaign.Status
Audience = Campaign.Audience
GIFT_REASON = gettext_lazy("Regalo de la campaña «%(name)s»")
EDITABLE_FIELDS = ("name", "channel", "subject", "body", "audience", "gift_points", "gift_points_expire")


def _require_owner(actor):
    if not is_owner(actor):
        raise PermissionDenied(_("Solo el propietario gestiona las campañas."))


def _audit(actor, campaign, **metadata):
    record_audit_event(action=AuditEvent.Action.CAMPAIGN_UPDATED, actor=actor, target=campaign, metadata=metadata)


def _validate(campaign):
    campaign.name = " ".join((campaign.name or "").split())
    campaign.subject = " ".join((campaign.subject or "").split())
    campaign.body = (campaign.body or "").strip()
    errors = {}
    if not campaign.name:
        errors["name"] = _("Escribe el nombre de la campaña.")
    if not campaign.subject:
        errors["subject"] = _("Escribe el asunto.")
    if not campaign.body:
        errors["body"] = _("Escribe el mensaje.")
    if campaign.channel == Channel.SMS:
        # El SMS no lleva asunto ni imagen: el asunto solo identifica el envío.
        campaign.image = None
        if len(campaign.body) > Campaign.MAX_SMS_BODY:
            errors["body"] = _("Un SMS admite como máximo %(MAX_SMS_BODY)s caracteres.") % {"MAX_SMS_BODY": Campaign.MAX_SMS_BODY}
    elif len(campaign.body) > Campaign.MAX_EMAIL_BODY:
        errors["body"] = _("El mensaje admite como máximo %(MAX_EMAIL_BODY)s caracteres.") % {"MAX_EMAIL_BODY": Campaign.MAX_EMAIL_BODY}
    if campaign.gift_points is not None and not 1 <= campaign.gift_points <= Campaign.MAX_GIFT_POINTS:
        errors["gift_points"] = _("Los puntos de regalo van de 1 a %(MAX)s.") % {"MAX": Campaign.MAX_GIFT_POINTS}
    if campaign.audience not in Audience.values:
        errors["audience"] = _("Elige los destinatarios.")
    if errors:
        raise ValidationError(errors)
    campaign.full_clean(exclude=["created_by"])


def selectable_customers(public_ids):
    """Clientes (solo rol cliente) entre los `public_id` recibidos; el resto se ignora."""
    return User.objects.filter(role=User.Role.CUSTOMER, public_id__in=list(public_ids))


def _clean_value(name, value):
    if name == "gift_points":
        return value or None
    if name == "gift_points_expire":
        return bool(value)
    return value or ""


@transaction.atomic
def save_campaign(*, actor, campaign, data, recipients=None, image=None, clear_image=False):
    """
    Crea o modifica una campaña en borrador (lista blanca de campos).

    `recipients`: `public_id` de los clientes elegidos, obligatorio con
    destinatarios `SELECTED`; se recalculan aquí (solo clientes). En una
    campaña ya guardada, `None` conserva los que tenía.
    """
    _require_owner(actor)
    if campaign.pk is not None:
        campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
        if campaign.status != Status.DRAFT:
            raise ValidationError(_("Solo se pueden modificar las campañas en borrador."))
    else:
        campaign.created_by = actor
    for name in EDITABLE_FIELDS:
        if name in data:
            setattr(campaign, name, _clean_value(name, data[name]))
    if image:
        campaign.image = image
    elif clear_image:
        campaign.image = None
    selected = None
    if campaign.audience == Audience.SELECTED:
        if recipients is not None:
            selected = list(selectable_customers(recipients).values_list("pk", flat=True))
        elif campaign.pk is not None:
            selected = list(campaign.selected_recipients.values_list("customer_id", flat=True))
        if not selected:
            raise ValidationError({"audience": _("No hay clientes seleccionados. Elígelos en Clientes.")})
    _validate(campaign)
    created = campaign.pk is None
    campaign.save()
    if campaign.audience == Audience.SELECTED:
        campaign.selected_recipients.exclude(customer_id__in=selected).delete()
        CampaignRecipient.objects.bulk_create(
            [CampaignRecipient(campaign=campaign, customer_id=pk) for pk in selected], ignore_conflicts=True
        )
    else:
        campaign.selected_recipients.all().delete()
    _audit(
        actor,
        campaign,
        event="created" if created else "edited",
        channel=campaign.channel,
        audience=campaign.audience,
        selected=len(selected) if selected is not None else None,
        gift_points=campaign.gift_points,
    )
    return campaign


@transaction.atomic
def create_and_queue(*, actor, campaign, data, recipients=None, image=None, clear_image=False):
    """«Crear y enviar»: guarda y programa en una sola transacción (o nada)."""
    campaign = save_campaign(
        actor=actor, campaign=campaign, data=data, recipients=recipients, image=image, clear_image=clear_image
    )
    return queue_campaign(actor=actor, campaign=campaign)


SELECTION_COPY_SUFFIX = " (seleccionados)"


@transaction.atomic
def send_copy_to_selection(*, actor, source_public_id, recipients, idempotency_key):
    """
    «Enviar una campaña ya creada» a los clientes seleccionados (Fase 24).

    Crea una campaña nueva con las condiciones actuales de la elegida (canal, asunto,
    texto, imagen y puntos de regalo), solo para `recipients`, y la programa con
    `create_and_queue` (mismas validaciones; todo o nada). La original no cambia.
    `idempotency_key` evita que un doble envío cree dos copias o regale dos veces.
    """
    _require_owner(actor)
    existing = Campaign.objects.filter(copy_key=idempotency_key).first()
    if existing is not None:
        return existing
    source = Campaign.objects.filter(public_id=source_public_id).first()
    if source is None:
        raise ValidationError(_("Campaña desconocida."))
    data = {name: getattr(source, name) for name in EDITABLE_FIELDS}
    data["name"] = f"{source.name[: 100 - len(SELECTION_COPY_SUFFIX)]}{SELECTION_COPY_SUFFIX}"
    data["audience"] = Audience.SELECTED
    try:
        with transaction.atomic():
            campaign = Campaign(copy_key=idempotency_key)
            if source.image:
                with source.image.open("rb") as content:
                    image = File(content, name=os.path.basename(source.image.name))
                    campaign = create_and_queue(actor=actor, campaign=campaign, data=data, recipients=recipients, image=image)
            else:
                campaign = create_and_queue(actor=actor, campaign=campaign, data=data, recipients=recipients)
    except IntegrityError:
        # Otro envío con la misma clave se ha adelantado: se devuelve su copia.
        existing = Campaign.objects.filter(copy_key=idempotency_key).first()
        if existing is None:
            raise
        return existing
    _audit(
        actor,
        campaign,
        event="copied_to_selection",
        source=str(source.public_id),
        selected=campaign.selected_recipients.count(),
        gift_points=campaign.gift_points,
    )
    return campaign


@transaction.atomic
def queue_campaign(*, actor, campaign):
    """Programa el envío. El reparto lo hace `process_notifications`, no esta petición."""
    _require_owner(actor)
    campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
    if campaign.status == Status.QUEUED:
        return campaign
    if campaign.status != Status.DRAFT:
        raise ValidationError(_("Esta campaña ya no se puede programar."))
    if campaign.channel == Channel.SMS and not services.sms_available():
        raise ValidationError(_("No hay ningún proveedor de SMS configurado: la campaña no puede enviarse por SMS."))
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
        raise ValidationError(_("Una campaña ya repartida no se puede cancelar."))
    campaign.status = Status.CANCELLED
    campaign.save(update_fields=["status", "updated_at"])
    _audit(actor, campaign, event="cancelled")
    return campaign


def eligible_recipients(channel, customer_ids=None):
    """
    Clientes activos con email verificado y consentimiento vigente del canal.
    Con `customer_ids`, solo entre esos (campañas a clientes seleccionados).
    """
    profiles = CustomerProfile.objects.filter(
        user__is_active=True, user__role=User.Role.CUSTOMER, user__email_verified_at__isnull=False
    )
    if channel == Channel.EMAIL:
        profiles = profiles.filter(promo_email_opt_in=True)
    else:
        profiles = profiles.filter(promo_sms_opt_in=True).exclude(phone_number="")
    if customer_ids is not None:
        profiles = profiles.filter(user_id__in=customer_ids)
    return User.objects.filter(pk__in=profiles.values("user_id")).order_by("pk")


def gift_candidates(customer_ids):
    """Seleccionados que pueden recibir puntos: clientes activos con email verificado."""
    return User.objects.filter(
        pk__in=customer_ids, role=User.Role.CUSTOMER, is_active=True, email_verified_at__isnull=False
    ).order_by("pk")


def _grant_gifts(campaign, customers):
    reason = site_text(GIFT_REASON, name=campaign.name)
    granted = 0
    for user in customers.iterator():
        movement = ledger.grant_campaign_gift(
            customer=user,
            campaign_public_id=campaign.public_id,
            points=campaign.gift_points,
            never_expires=not campaign.gift_points_expire,
            reason=reason,
        )
        granted += movement is not None
    return granted



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
            selected = None
            if campaign.audience == Audience.SELECTED:
                selected = list(campaign.selected_recipients.values_list("customer_id", flat=True))
            recipients = eligible_recipients(campaign.channel, selected)
            for user in recipients.iterator():
                _unused, created = services.enqueue(
                    kind=Notification.Kind.CAMPAIGN,
                    recipient=user,
                    channel=campaign.channel,
                    campaign=campaign,
                    dedup_key=f"campaign:{campaign.public_id}:{user.public_id}",
                )
                count += int(created)
            if campaign.gift_points:
                gifted = gift_candidates(selected) if selected is not None else recipients
                campaign.gifted_count = _grant_gifts(campaign, gifted)
            campaign.status = Status.DISPATCHED
            campaign.dispatched_at = now or timezone.now()
            campaign.recipients_count = Notification.objects.filter(campaign=campaign).count()
            campaign.save(update_fields=["status", "dispatched_at", "recipients_count", "gifted_count", "updated_at"])
            _audit(None, campaign, event="dispatched", recipients=campaign.recipients_count, gifted=campaign.gifted_count)
            created_total += count
    return created_total
