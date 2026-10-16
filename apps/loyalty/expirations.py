"""
Ejecución diaria de la caducidad de puntos (Fase 14).

La lanza el comando `expire_points` (nunca una petición web):

1. **Avisos** (`send_expiry_warnings`): a cada cliente activo con email
   verificado cuyo próximo vencimiento cae en los próximos `warn_days` días se
   le encola un email transaccional `POINTS_EXPIRING` (informa del estado de su
   cuenta, sin publicidad). Uno por vencimiento (`dedup_key`).
2. **Caducidad** (`run_expirations`): a cada cliente con puntos vencidos se le
   descuentan con un movimiento `EXPIRATION` (`ledger.expire_points`).

Las dos fases preseleccionan clientes en SQL (`expiry.credits_cutoff`) y hacen
el cálculo exacto cliente a cliente. Repetir el comando no duplica avisos ni
caducidades. Se audita un resumen con recuentos, sin datos personales.
"""
import datetime
from dataclasses import asdict, dataclass

from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event
from apps.notifications import services as notifications
from apps.notifications.models import Channel, Notification

from . import expiry, ledger


@dataclass
class ExpiryRunResult:
    policy: bool = False
    warned: int = 0
    expired_customers: int = 0
    expired_points: int = 0


def _candidates(policy, until):
    """Clientes con algún crédito anterior a la fecha límite (preselección, no cálculo exacto)."""
    cutoff = expiry.credits_cutoff(policy, until)
    if cutoff is None:
        return User.objects.none()
    return (
        User.objects.filter(points_transactions__points__gt=0, points_transactions__created_at__lte=cutoff)
        .distinct()
        .order_by("id")
    )


def send_expiry_warnings(*, policy, at, result):
    # Por días naturales: avisa de lo que vence hasta el final del día `warn_days` (hora local).
    last_day = timezone.localdate(at) + datetime.timedelta(days=policy.warn_days)
    until = timezone.make_aware(datetime.datetime.combine(last_day, datetime.time.max))
    customers = _candidates(policy, until).filter(
        role=User.Role.CUSTOMER, is_active=True, email_verified_at__isnull=False
    )
    for customer in customers:
        upcoming = expiry.next_expiry(expiry.customer_movements(customer), policy)
        # Lo ya vencido caduca en esta misma ejecución: no tiene sentido avisar.
        if upcoming is None or not at < upcoming.expires_at <= until:
            continue
        _, created = notifications.enqueue(
            kind=Notification.Kind.POINTS_EXPIRING,
            recipient=customer,
            channel=Channel.EMAIL,
            context={"points": upcoming.points, "expires_on": upcoming.date.strftime("%d/%m/%Y")},
            dedup_key=f"points_expiring:{customer.public_id}:{upcoming.date.isoformat()}",
        )
        result.warned += int(created)


def run_expirations(*, policy, at, result):
    for customer in _candidates(policy, at):
        movement = ledger.expire_points(customer=customer, policy=policy, at=at)
        if movement is not None:
            result.expired_customers += 1
            result.expired_points -= movement.points


def run(*, at=None):
    """Avisos y caducidades del día. Sin caducidad activa no hace nada."""
    at = at or timezone.now()
    result = ExpiryRunResult()
    policy = expiry.active_policy(at)
    if policy is None:
        return result
    result.policy = True
    send_expiry_warnings(policy=policy, at=at, result=result)
    run_expirations(policy=policy, at=at, result=result)
    record_audit_event(action=AuditEvent.Action.POINTS_EXPIRY_RUN, metadata=asdict(result))
    return result
