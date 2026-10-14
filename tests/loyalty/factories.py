"""Clientes ficticios con QR, compras y promociones para los tests de las Fases 5+."""
import datetime
import uuid

from django.utils import timezone

from apps.accounts import services as accounts
from apps.accounts.models import User
from apps.loyalty import services as loyalty
from tests.accounts.factories import PASSWORD, make_user, registration_data


def make_verified_customer(email="cliente@example.com", **overrides):
    """Cliente con perfil completo (datos ficticios) y email verificado."""
    data = registration_data(email=email, **overrides)
    user = accounts.register_customer(**data)
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    return user


def make_customer_with_qr(email="cliente@example.com", **overrides):
    user = make_verified_customer(email, **overrides)
    return user, loyalty.get_customer_qr(user).token


def make_employee(email="empleado@example.com", **extra):
    return make_user(email, role=User.Role.EMPLOYEE, **extra)


def make_owner(email="owner@example.com", **extra):
    return make_user(email, role=User.Role.OWNER, **extra)


def buy(staff, token, amount="12.50"):
    """Registra una compra por el flujo real (servicio de compras + ledger)."""
    from apps.purchases import services as purchases

    return purchases.register_purchase(
        staff=staff, qr_code=token, amount=amount, idempotency_key=uuid.uuid4()
    ).purchase


def make_promotion(**overrides):
    """Promoción activa desde ayer, sin fin, de 10 puntos fijos."""
    from apps.loyalty.models import Promotion

    data = {
        "name": "Promoción ficticia",
        "kind": Promotion.Kind.PURCHASE,
        "bonus_type": Promotion.BonusType.FIXED_POINTS,
        "fixed_points": 10,
        "starts_at": timezone.now() - datetime.timedelta(days=1),
        "status": Promotion.Status.ACTIVE,
    }
    data.update(overrides)
    return Promotion.objects.create(**data)


__all__ = [
    "PASSWORD",
    "buy",
    "make_customer_with_qr",
    "make_employee",
    "make_owner",
    "make_promotion",
    "make_verified_customer",
]
