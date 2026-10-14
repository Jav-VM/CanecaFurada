"""
Servicios de cuentas y roles.

Son la única vía de negocio para crear usuarios o cambiar roles: las vistas
web, el admin, los comandos y la futura API deben llamarlos en lugar de
modificar los modelos directamente. El rol nunca se toma de datos del cliente
en flujos públicos.
"""
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from apps.core.models import AuditEvent
from apps.core.services import record_audit_event

from .models import User
from .normalization import normalize_email_address

Role = User.Role

_CREATION_ACTIONS = {
    Role.OWNER: AuditEvent.Action.OWNER_CREATED,
    Role.EMPLOYEE: AuditEvent.Action.EMPLOYEE_CREATED,
    Role.CUSTOMER: AuditEvent.Action.CUSTOMER_CREATED,
}


def _apply_role_flags(user):
    """El acceso al admin técnico se deriva del rol, nunca de datos externos."""
    is_owner = user.role == Role.OWNER
    user.is_staff = is_owner
    user.is_superuser = is_owner


def _ensure_active_owner(actor):
    """Comprueba en BD (no en el objeto en memoria) que el actor es propietario activo."""
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Operación reservada al propietario.")
    if not User.objects.filter(pk=actor.pk, role=Role.OWNER, is_active=True).exists():
        raise PermissionDenied("Operación reservada al propietario.")


def _create_user(*, role, email, first_name, last_name, password, actor=None, instance=None):
    user = instance if instance is not None else User()
    user.email = normalize_email_address(email)
    user.first_name = first_name
    user.last_name = last_name
    user.role = role
    _apply_role_flags(user)

    user.full_clean(exclude=["password"])
    validate_password(password, user)
    user.set_password(password)

    try:
        with transaction.atomic():
            user.save()
    except IntegrityError as exc:
        # Carrera entre dos altas con el mismo email: la restricción única decide.
        raise ValidationError({"email": "Ya existe una cuenta con este email."}) from exc

    record_audit_event(
        action=_CREATION_ACTIONS[role],
        actor=actor,
        target=user,
        metadata={"role": role},
    )
    return user


@transaction.atomic
def create_customer(*, email, first_name, last_name, password):
    """Alta de cliente. Es el único rol que puede crearse sin un actor autorizado."""
    return _create_user(
        role=Role.CUSTOMER,
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=password,
    )


@transaction.atomic
def create_employee(*, actor, email, first_name, last_name, password):
    """Alta de empleado, reservada al propietario."""
    _ensure_active_owner(actor)
    return _create_user(
        role=Role.EMPLOYEE,
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=password,
        actor=actor,
    )


@transaction.atomic
def create_owner(*, email, first_name, last_name, password, actor=None):
    """
    Alta de propietario.

    Sin `actor` solo se permite si todavía no existe ningún propietario
    (procedimiento administrativo inicial `create_owner`). Con `actor`, este
    debe ser un propietario activo.
    """
    if actor is None:
        # Bloquea las filas de propietarios para serializar altas concurrentes.
        if list(User.objects.select_for_update().filter(role=Role.OWNER)):
            raise PermissionDenied(
                "Ya existe un propietario. Los siguientes deben crearse por un propietario."
            )
    else:
        _ensure_active_owner(actor)
    return _create_user(
        role=Role.OWNER,
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=password,
        actor=actor,
    )


@transaction.atomic
def create_user_by_owner(*, actor, role, email, first_name, last_name, password, instance=None):
    """Alta de cualquier rol por un propietario (usado por el admin)."""
    _ensure_active_owner(actor)
    if role not in Role.values:
        raise ValidationError({"role": "Rol no válido."})
    return _create_user(
        role=role,
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=password,
        actor=actor,
        instance=instance,
    )


@transaction.atomic
def change_role(*, actor, user, new_role):
    """
    Cambia el rol de un usuario. Solo un propietario activo puede hacerlo y
    nunca puede quedar el sistema sin propietarios activos.
    """
    _ensure_active_owner(actor)
    if new_role not in Role.values:
        raise ValidationError({"role": "Rol no válido."})

    target = User.objects.select_for_update().get(pk=user.pk)
    old_role = target.role
    if old_role == new_role:
        return target

    if old_role == Role.OWNER:
        active_owners = list(
            User.objects.select_for_update()
            .filter(role=Role.OWNER, is_active=True)
            .values_list("pk", flat=True)
        )
        if target.is_active and len(active_owners) <= 1:
            raise ValidationError("No se puede retirar el rol al último propietario activo.")

    target.role = new_role
    _apply_role_flags(target)
    target.save(update_fields=["role", "is_staff", "is_superuser"])

    record_audit_event(
        action=AuditEvent.Action.ROLE_CHANGED,
        actor=actor,
        target=target,
        metadata={"from": old_role, "to": new_role},
    )
    # Mantiene coherente el objeto recibido por quien llama.
    user.role = target.role
    user.is_staff = target.is_staff
    user.is_superuser = target.is_superuser
    return target
