"""Datos ficticios para tests. Nunca usar datos personales reales."""
from apps.accounts.models import User

PASSWORD = "Contrasena-Ficticia-2026"


def make_user(email="cliente@example.com", role=User.Role.CUSTOMER, **extra):
    extra.setdefault("first_name", "Ana")
    extra.setdefault("last_name", "Pérez Ficticia")
    if role == User.Role.OWNER:
        return User.objects.create_superuser(email=email, password=PASSWORD, **extra)
    return User.objects.create_user(email=email, password=PASSWORD, role=role, **extra)
