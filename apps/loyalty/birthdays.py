"""
Flujo de las promociones de cumpleaños (Fase 10).

`run_birthday_promotions(day)` lo ejecuta el comando diario
`run_birthday_promotions` (nunca una petición web):

1. **Detecta** los cumpleaños del día (`accounts.birthdays`: el 29 de febrero
   se celebra el 28 en los años no bisiestos).
2. Comprueba que hay una promoción de cumpleaños **activa** (de puntos fijos).
3. Comprueba **cliente activo y email verificado** (la verificación es
   requisito del programa de puntos, no consentimiento publicitario).
4. Comprueba que **no se ha generado ya** la promoción de ese año y las
   reglas anti-abuso (`promotions.birthday_year_for`).
5. **Crea el beneficio**: movimiento `BIRTHDAY_GIFT` en el ledger
   (`ledger.grant_birthday_gift`). El regalo no depende del consentimiento
   publicitario: condicionarlo a aceptar publicidad pondría en duda que ese
   consentimiento sea libre.
6. **Comprueba las preferencias** y, solo si el cliente ha autorizado el canal,
   encola el aviso (email; SMS solo si además hay proveedor configurado y
   teléfono válido). El consentimiento se vuelve a comprobar justo antes de
   enviar (`notifications.services.deliver`).
7. **Registra el resultado**: el movimiento del ledger, las notificaciones y un
   evento de auditoría con los totales (sin datos personales).

Duplicados: la restricción única (cliente, año) del ledger y la `dedup_key`
de cada aviso hacen que repetir el comando el mismo día, o lanzarlo dos veces
a la vez, no regale ni avise dos veces.
"""
import datetime
from dataclasses import asdict, dataclass

from django.utils import timezone

from apps.accounts import services as accounts
from apps.accounts.birthdays import profiles_with_birthday_on
from apps.accounts.models import User
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event
from apps.notifications import services as notifications
from apps.notifications.models import Channel, Notification

from . import ledger, promotions

MAX_DAYS_BACK = 7


@dataclass
class BirthdayRunResult:
    day: str
    promotion: bool = False
    birthdays: int = 0
    granted: int = 0
    not_eligible: int = 0
    email_queued: int = 0
    sms_queued: int = 0


def _notify(customer, movement, channel):
    _, created = notifications.enqueue(
        kind=Notification.Kind.BIRTHDAY,
        recipient=customer,
        channel=channel,
        context={"points": movement.points, "year": movement.birthday_year},
        dedup_key=f"birthday:{customer.public_id}:{movement.birthday_year}:{channel}",
    )
    return created


def run_birthday_promotions(*, day=None, at=None):
    at = at or timezone.now()
    day = day or timezone.localdate(at)
    result = BirthdayRunResult(day=day.isoformat())
    promotion = promotions.active_birthday_promotion(at)
    if promotion is None or promotion.bonus_type != promotion.BonusType.FIXED_POINTS:
        return result
    result.promotion = True
    profiles = (
        profiles_with_birthday_on(day)
        .filter(user__role=User.Role.CUSTOMER, user__is_active=True)
        .select_related("user")
        .order_by("id")
    )
    for profile in profiles:
        customer = profile.user
        result.birthdays += 1
        movement = ledger.grant_birthday_gift(customer=customer, promotion=promotion, day=day, at=at)
        if movement is None:
            result.not_eligible += 1
            continue
        result.granted += 1
        if accounts.can_receive_promotional_email(customer):
            result.email_queued += int(_notify(customer, movement, Channel.EMAIL))
        if notifications.sms_available() and accounts.can_receive_promotional_sms(customer):
            result.sms_queued += int(_notify(customer, movement, Channel.SMS))
    record_audit_event(action=AuditEvent.Action.BIRTHDAY_PROMOTIONS_RUN, metadata=asdict(result))
    return result


def days_to_process(*, days_back=0, today=None):
    """Hoy y, para recuperar ejecuciones perdidas, hasta `MAX_DAYS_BACK` días anteriores."""
    today = today or timezone.localdate()
    days_back = max(0, min(int(days_back), MAX_DAYS_BACK))
    return [today - datetime.timedelta(days=offset) for offset in range(days_back, -1, -1)]
