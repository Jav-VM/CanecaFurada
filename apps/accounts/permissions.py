"""
Comprobaciones de rol reutilizables.

Se basan en el usuario autenticado del servidor, nunca en datos enviados por el
cliente. La futura API (DRF) definirá clases de permiso que reutilicen
`has_role`.
"""
from functools import wraps

from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .models import User


def has_role(user, *roles):
    return bool(
        user is not None
        and getattr(user, "is_authenticated", False)
        and user.is_active
        and user.role in roles
    )


def is_owner(user):
    return has_role(user, User.Role.OWNER)


def is_staff_member(user):
    """Personal del local: propietario o empleado."""
    return has_role(user, User.Role.OWNER, User.Role.EMPLOYEE)


def role_required(*roles):
    """
    Decorador para vistas de función: redirige al login si no hay sesión y
    responde 403 si el rol no está permitido.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not has_role(request.user, *roles):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def verified_email_required(view_func):
    """
    Para vistas que exigen email verificado (puntos, canjes, reservas...):
    sin sesión redirige al login; con email pendiente responde 403.
    """

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not (request.user.is_active and request.user.is_email_verified):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped


class RoleRequiredMixin(AccessMixin):
    """Equivalente a `role_required` para vistas basadas en clases."""

    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not has_role(request.user, *self.allowed_roles):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
