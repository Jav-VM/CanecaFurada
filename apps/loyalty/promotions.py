"""
Promociones: qué bonificaciones corresponden a una compra y base de las
promociones de cumpleaños.

No escribe en el ledger: `ledger.award_points_for_purchase` llama a
`bonuses_for_purchase` dentro de su transacción (cliente bloqueado) y crea los
movimientos. Las restricciones únicas del ledger impiden duplicados aunque
algo fallara aquí.

Reglas de aplicación de una promoción a una compra:
- Estado `ACTIVE` y la fecha de la compra dentro de `[starts_at, ends_at)`.
- Importe de la compra ≥ `min_purchase_amount` (si lo tiene).
- Sin superar `max_total_uses` ni `max_uses_per_customer` (los usos
  compensados siguen contando: no se recupera un uso anulando la compra).
- Se acumulan todas las promociones aplicables (orden: inicio e id).

Cumpleaños (`BIRTHDAY`), además:
- Fecha de nacimiento del perfil (validada en el registro y en el perfil) y
  la compra hasta `birthday_window_days` días antes o después del cumpleaños.
  29 de febrero: en años no bisiestos se celebra el 28 (`accounts.birthdays`).
- Una por cliente y año del cumpleaños (restricción única en BD), aunque haya
  varias promociones de cumpleaños activas.
- Anti-abuso de la fecha de nacimiento: no se aplica si la fecha cambió hace
  menos de `LOYALTY_BIRTHDAY_DOB_STABLE_DAYS` días, ni si el cliente recibió
  otra de cumpleaños hace menos de `LOYALTY_BIRTHDAY_MIN_DAYS_BETWEEN_BONUSES`.
  El perfil ya limita los cambios de fecha a uno cada 365 días.
"""
import datetime
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts import services as accounts
from apps.accounts.birthdays import birthday_in_year, profiles_with_birthday_on
from apps.accounts.models import CustomerProfile, User
from apps.accounts.permissions import is_owner
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event

from .conversion import round_points
from .models import PointsTransaction, Promotion


class Channel:
    EMAIL = "EMAIL"
    SMS = "SMS"


@dataclass(frozen=True)
class Bonus:
    promotion: Promotion
    points: int
    birthday_year: int | None = None


@dataclass(frozen=True)
class BirthdayRecipient:
    customer: User
    birthday: datetime.date
    promotion: Promotion


def active_promotions(at=None):
    at = at or timezone.now()
    return Promotion.objects.filter(status=Promotion.Status.ACTIVE, starts_at__lte=at).filter(
        Q(ends_at__isnull=True) | Q(ends_at__gt=at)
    )


def birthday_occurrence(date_of_birth, day, window_days):
    """El cumpleaños (de `day.year` o los años vecinos) a ≤ `window_days` días de `day`, o `None`."""
    for year in (day.year - 1, day.year, day.year + 1):
        birthday = birthday_in_year(date_of_birth, year)
        if abs((day - birthday).days) <= window_days:
            return birthday
    return None


def birthday_year_for(customer, at, window_days):
    """
    Año del cumpleaños que el cliente puede celebrar en el momento `at`, o
    `None` si no le corresponde (sin fecha, fuera de la ventana, fecha cambiada
    hace poco o promoción ya recibida en ese año o hace poco).
    """
    profile = CustomerProfile.objects.filter(user=customer).only("date_of_birth", "date_of_birth_changed_at").first()
    if profile is None or profile.date_of_birth is None:
        return None
    changed_at = profile.date_of_birth_changed_at
    if changed_at and at - changed_at < datetime.timedelta(days=settings.LOYALTY_BIRTHDAY_DOB_STABLE_DAYS):
        return None
    birthday = birthday_occurrence(profile.date_of_birth, timezone.localdate(at), window_days)
    if birthday is None:
        return None
    previous = PointsTransaction.objects.filter(customer=customer, birthday_year__isnull=False)
    if previous.filter(birthday_year=birthday.year).exists():
        return None
    last = previous.order_by("-created_at").values_list("created_at", flat=True).first()
    if last and at - last < datetime.timedelta(days=settings.LOYALTY_BIRTHDAY_MIN_DAYS_BETWEEN_BONUSES):
        return None
    return birthday.year


def _bonus_points(promotion, base_points):
    if promotion.bonus_type == Promotion.BonusType.FIXED_POINTS:
        return promotion.fixed_points or 0
    return round_points(base_points * (promotion.multiplier - 1))


def bonuses_for_purchase(purchase, *, base_points):
    """
    Bonificaciones que corresponden a `purchase`. Llamar dentro de una
    transacción con la fila del cliente bloqueada: bloquea además las
    promociones para respetar `max_total_uses` con compras simultáneas.
    """
    at = purchase.created_at
    customer = purchase.customer
    bonuses = []
    birthday_taken = False
    promos = active_promotions(at).select_for_update().order_by("starts_at", "id")
    for promo in promos:
        if promo.min_purchase_amount is not None and purchase.amount < promo.min_purchase_amount:
            continue
        uses = PointsTransaction.objects.filter(promotion=promo, kind=PointsTransaction.Kind.PROMOTION_BONUS)
        if promo.max_total_uses is not None and uses.count() >= promo.max_total_uses:
            continue
        if promo.max_uses_per_customer is not None and uses.filter(customer=customer).count() >= promo.max_uses_per_customer:
            continue
        birthday_year = None
        if promo.kind == Promotion.Kind.BIRTHDAY:
            if birthday_taken:
                continue
            birthday_year = birthday_year_for(customer, at, promo.birthday_window_days)
            if birthday_year is None:
                continue
        points = _bonus_points(promo, base_points)
        if points <= 0:
            continue
        if birthday_year is not None:
            birthday_taken = True
        bonuses.append(Bonus(promotion=promo, points=points, birthday_year=birthday_year))
    return bonuses


@transaction.atomic
def save_promotion(*, actor, promotion, changed_fields=()):
    """Crea o modifica una promoción (solo propietario) y lo deja auditado."""
    if not is_owner(actor):
        raise PermissionDenied("Solo el propietario gestiona las promociones.")
    created = promotion.pk is None
    promotion.full_clean()
    promotion.save()
    record_audit_event(
        action=AuditEvent.Action.PROMOTION_SAVED,
        actor=actor,
        target=promotion,
        metadata={"created": created, "status": promotion.status, "fields": sorted(changed_fields)},
    )
    return promotion


def birthday_promotion_recipients(*, channel, at=None):
    """
    Clientes a los que se podría avisar en el día de `at` de su promoción de
    cumpleaños. **No envía nada**: el envío (con registro de notificaciones,
    reintentos e idempotencia) es de la Fase 10, que debe volver a comprobar
    el consentimiento justo antes de enviar cada mensaje.

    Filtra: hay una promoción de cumpleaños activa; el cumpleaños cae hoy
    (29-F → 28-F en años no bisiestos); cliente activo con email verificado;
    consentimiento vigente para el canal; y aún puede recibir la promoción del
    año (sin duplicados ni fecha cambiada hace poco).
    """
    if channel == Channel.EMAIL:
        can_receive = accounts.can_receive_promotional_email
    elif channel == Channel.SMS:
        can_receive = accounts.can_receive_promotional_sms
    else:
        raise ValueError(f"Canal desconocido: {channel}")
    at = at or timezone.now()
    promotion = active_promotions(at).filter(kind=Promotion.Kind.BIRTHDAY).order_by("starts_at", "id").first()
    if promotion is None:
        return []
    recipients = []
    profiles = profiles_with_birthday_on(timezone.localdate(at)).select_related("user").order_by("id")
    for profile in profiles:
        user = profile.user
        # El email verificado se exige en ambos canales: sin él no se acumulan puntos.
        if not (user.is_email_verified and can_receive(user)):
            continue
        if birthday_year_for(user, at, 0) is None:
            continue
        recipients.append(
            BirthdayRecipient(
                customer=user,
                birthday=birthday_occurrence(profile.date_of_birth, timezone.localdate(at), 0),
                promotion=promotion,
            )
        )
    return recipients
