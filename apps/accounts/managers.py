from django.contrib.auth.base_user import BaseUserManager

from .normalization import normalize_email_address


class UserManager(BaseUserManager):
    """
    Manager de bajo nivel. Los flujos de negocio (registro, alta de empleados,
    cambios de rol) deben usar `apps.accounts.services`, que añaden permisos y
    auditoría.
    """

    use_in_migrations = True

    @classmethod
    def normalize_email(cls, email):
        return normalize_email_address(email)

    def get_by_natural_key(self, username):
        # Inicio de sesión insensible a mayúsculas, coherente con la normalización.
        return self.get(**{self.model.USERNAME_FIELD: normalize_email_address(username)})

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("El email es obligatorio.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", self.model.Role.CUSTOMER)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        # Un superusuario técnico siempre es propietario: las restricciones de BD
        # impiden is_staff/is_superuser en cualquier otro rol.
        extra_fields["role"] = self.model.Role.OWNER
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        return self._create_user(email, password, **extra_fields)
