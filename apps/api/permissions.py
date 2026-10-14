"""
Permisos DRF: envoltorios de `apps.accounts.permissions`, sin lógica propia.

Se evalúan siempre con el usuario cargado de la base de datos en la petición
(el token solo lleva su `public_id`), nunca con un rol enviado por el cliente.
Los servicios de dominio vuelven a comprobar los permisos por su cuenta.
"""
from django.conf import settings
from rest_framework.permissions import BasePermission

from apps.accounts.models import User
from apps.accounts.permissions import has_role, is_owner


class HasRole(BasePermission):
    allowed_roles = ()
    message = "No tienes permiso para realizar esta acción."

    def has_permission(self, request, view):
        return has_role(request.user, *self.allowed_roles)


class IsCustomer(HasRole):
    allowed_roles = (User.Role.CUSTOMER,)
    message = "Esta función es solo para clientes."


class IsVerifiedCustomer(IsCustomer):
    """Cliente activo con el email verificado (puntos, QR, canjes y reservas)."""

    message = "Debes verificar tu email para usar esta función."
    code = "email_not_verified"

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_email_verified


class IsStaffMember(HasRole):
    allowed_roles = (User.Role.OWNER, User.Role.EMPLOYEE)
    message = "Solo el personal del local puede realizar esta acción."


class IsOwner(HasRole):
    allowed_roles = (User.Role.OWNER,)
    message = "Solo el propietario puede realizar esta acción."


class CanReadApiDocs(BasePermission):
    """Esquema y documentación: públicos en desarrollo o si `API_DOCS_PUBLIC`; si no, solo el propietario."""

    def has_permission(self, request, view):
        return settings.API_DOCS_PUBLIC or is_owner(request.user)
