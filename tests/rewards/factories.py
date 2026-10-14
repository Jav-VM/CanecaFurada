"""Recompensas, clientes con puntos y canjes ficticios para los tests de la Fase 7."""
import datetime
import uuid

from django.utils import timezone

from apps.loyalty import ledger
from apps.rewards import services
from apps.rewards.models import Reward
from tests.loyalty.factories import make_customer_with_qr, make_employee, make_owner, make_verified_customer


def make_reward(**overrides):
    """Recompensa activa desde ayer, sin fin ni límite de unidades, de 50 puntos."""
    data = {
        "name": "Caña de la casa",
        "description": "Una caña de cualquier cerveza de la casa.",
        "points_cost": 50,
        "status": Reward.Status.ACTIVE,
        "valid_from": timezone.now() - datetime.timedelta(days=1),
    }
    data.update(overrides)
    return Reward.objects.create(**data)


def give_points(customer, points, owner=None):
    """Saldo inicial mediante un ajuste del propietario (flujo real del ledger)."""
    owner = owner or make_owner(f"owner-{uuid.uuid4().hex[:8]}@example.com")
    ledger.adjust_points(
        actor=owner, customer=customer, points=points, reason="Saldo de prueba", idempotency_key=uuid.uuid4()
    )


def redeem(customer, reward, key=None):
    return services.request_redemption(customer=customer, reward=reward, idempotency_key=key or uuid.uuid4())


__all__ = [
    "give_points",
    "make_customer_with_qr",
    "make_employee",
    "make_owner",
    "make_reward",
    "make_verified_customer",
    "redeem",
]
