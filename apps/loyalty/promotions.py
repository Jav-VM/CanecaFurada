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

Cumpleaños (`BIRTHDAY`), desde la Fase 10:
- No se aplican al registrar compras: regalan sus puntos fijos el día del
  cumpleaños (`birthdays.run_birthday_promotions`, comando
  `run_birthday_promotions`, movimiento `BIRTHDAY_GIFT`).
- 29 de febrero: en años no bisiestos se celebra el 28 (`accounts.birthdays`).
- Una por cliente y año del cumpleaños (restricción única en BD), aunque haya
  varias promociones de cumpleaños activas.
- Anti-abuso de la fecha de nacimiento (`birthday_year_for`): no se concede si
  la fecha cambió hace menos de `LOYALTY_BIRTHDAY_DOB_STABLE_DAYS` días, ni si
  el cliente recibió otra de cumpleaños hace menos de
  `LOYALTY_BIRTHDAY_MIN_DAYS_BETWEEN_BONUSES`. El perfil ya limita los cambios
  de fecha a uno cada 365 días.
"""
import datetime
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.birthdays import birthday_in_year
from apps.accounts.models import CustomerProfile
from apps.accounts.permissions import is_owner
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event

from .conversion import round_points
from .models import PointsTransaction, Promotion


@dataclass(frozen=True)
class Bonus:
    promotion: Promotion
    points: int
    birthday_year: int | None = None


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


def active_birthday_promotion(at=None):
    """Promoción de cumpleaños vigente (la más antigua si hubiera varias), o `None`."""
    return active_promotions(at).filter(kind=Promotion.Kind.BIRTHDAY).order_by("starts_at", "id").first()


def birthday_year_for(customer, at, window_days, day=None):
    """
    Año del cumpleaños que el cliente puede celebrar el día `day` (por defecto,
    el de `at`), o `None` si no le corresponde (sin fecha, fuera de la ventana,
    fecha cambiada hace poco o promoción ya recibida en ese año o hace poco).
    """
    profile = CustomerProfile.objects.filter(user=customer).only("date_of_birth", "date_of_birth_changed_at").first()
    if profile is None or profile.date_of_birth is None:
        return None
    changed_at = profile.date_of_birth_changed_at
    if changed_at and at - changed_at < datetime.timedelta(days=settings.LOYALTY_BIRTHDAY_DOB_STABLE_DAYS):
        return None
    birthday = birthday_occurrence(profile.date_of_birth, day or timezone.localdate(at), window_days)
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
    # Las de cumpleaños se regalan el día del cumpleaños, no en la compra (Fase 10).
    promos = active_promotions(at).filter(kind=Promotion.Kind.PURCHASE).select_for_update().order_by("starts_at", "id")
    for promo in promos:
        if promo.min_purchase_amount is not None and purchase.amount < promo.min_purchase_amount:
            continue
        uses = PointsTransaction.objects.filter(promotion=promo, kind=PointsTransaction.Kind.PROMOTION_BONUS)
        if promo.max_total_uses is not None and uses.count() >= promo.max_total_uses:
            continue
        if promo.max_uses_per_customer is not None and uses.filter(customer=customer).count() >= promo.max_uses_per_customer:
            continue
        points = _bonus_points(promo, base_points)
        if points <= 0:
            continue
        bonuses.append(Bonus(promotion=promo, points=points))
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


# Estados a los que el propietario puede pasar una promoción desde el dashboard.
MANAGEABLE_STATUSES = (Promotion.Status.ACTIVE, Promotion.Status.PAUSED, Promotion.Status.ENDED)


def set_promotion_status(*, actor, promotion, status):
    """Activa, pausa o finaliza una promoción (solo propietario), validada y auditada."""
    if not is_owner(actor):
        raise PermissionDenied("Solo el propietario gestiona las promociones.")
    if status not in MANAGEABLE_STATUSES:
        raise ValidationError("Estado de promoción no válido.")
    with transaction.atomic():
        locked = Promotion.objects.select_for_update().get(pk=promotion.pk)
        if locked.status == status:
            return locked
        locked.status = status
        return save_promotion(actor=actor, promotion=locked, changed_fields=["status"])
