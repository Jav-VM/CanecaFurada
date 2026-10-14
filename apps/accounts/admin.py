"""
Admin técnico de usuarios (solo propietarios tienen acceso: is_staff se deriva
del rol OWNER).

El rol no se edita en el formulario de cambio: se modifica con acciones que
llaman a `services.change_role`, que valida permisos, protege al último
propietario y deja auditoría. Las altas pasan por
`services.create_user_by_owner`. No se permite borrar usuarios desde el admin.
"""
from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm
from django.core.exceptions import PermissionDenied, ValidationError

from . import services
from .models import User


class UserAdminCreationForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "role")


class UserAdminChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "is_active")

    def clean_is_active(self):
        is_active = self.cleaned_data["is_active"]
        user = self.instance
        if user.pk and user.is_owner and not is_active:
            others = User.objects.filter(role=User.Role.OWNER, is_active=True).exclude(pk=user.pk)
            if not others.exists():
                raise forms.ValidationError("No se puede desactivar al último propietario activo.")
        return is_active


def _change_role_action(new_role, description):
    def action(modeladmin, request, queryset):
        changed = 0
        for user in queryset:
            try:
                services.change_role(actor=request.user, user=user, new_role=new_role)
                changed += 1
            except (PermissionDenied, ValidationError) as exc:
                messages.error(request, f"{user}: {'; '.join(getattr(exc, 'messages', [str(exc)]))}")
        if changed:
            messages.success(request, f"Rol actualizado en {changed} usuario(s).")

    action.__name__ = f"make_{new_role.lower()}"
    action.short_description = description
    return action


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm

    list_display = ("email", "first_name", "last_name", "role", "is_active", "date_joined")
    list_filter = ("role", "is_active")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("-date_joined",)
    readonly_fields = ("public_id", "role", "is_staff", "is_superuser", "last_login", "date_joined")

    fieldsets = (
        (None, {"fields": ("public_id", "email", "password")}),
        ("Datos personales", {"fields": ("first_name", "last_name")}),
        ("Rol y estado", {"fields": ("role", "is_active", "is_staff", "is_superuser")}),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "role", "password1", "password2"),
            },
        ),
    )
    filter_horizontal = ()

    actions = [
        _change_role_action(User.Role.EMPLOYEE, "Cambiar rol a Empleado"),
        _change_role_action(User.Role.CUSTOMER, "Cambiar rol a Cliente"),
        _change_role_action(User.Role.OWNER, "Cambiar rol a Propietario"),
    ]

    def get_readonly_fields(self, request, obj=None):
        # En el alta el rol se elige en el formulario; después solo por acciones.
        if obj is None:
            return ()
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        if change:
            super().save_model(request, obj, form, change)
            return
        services.create_user_by_owner(
            actor=request.user,
            role=form.cleaned_data["role"],
            email=form.cleaned_data["email"],
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"],
            password=form.cleaned_data["password1"],
            instance=obj,
        )

    def has_delete_permission(self, request, obj=None):
        # Se desactivan cuentas en lugar de borrarlas para conservar el historial.
        return False
