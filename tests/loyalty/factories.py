"""Clientes ficticios con QR para los tests de las Fases 5+."""
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


__all__ = ["PASSWORD", "make_customer_with_qr", "make_employee", "make_owner", "make_verified_customer"]
