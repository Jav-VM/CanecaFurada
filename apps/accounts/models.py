import uuid

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from .managers import UserManager
from .normalization import normalize_email_address


class User(AbstractBaseUser, PermissionsMixin):
    """
    Usuario de la plataforma.

    - `id`: clave primaria interna (no se expone fuera del backend).
    - `public_id`: identificador estable y no secuencial para URLs, API y app móvil.
    - `email`: credencial de acceso y canal de contacto; no se usa como
      identificador interno de los procesos.

    Los datos personales específicos del cliente (dirección, fecha de nacimiento,
    teléfono, preferencias) no viven aquí: se añadirán en un perfil de cliente
    1:1 en la fase de registro.
    """

    class Role(models.TextChoices):
        OWNER = "OWNER", "Propietario"
        EMPLOYEE = "EMPLOYEE", "Empleado"
        CUSTOMER = "CUSTOMER", "Cliente"

    public_id = models.UUIDField(
        "identificador público", default=uuid.uuid4, unique=True, editable=False
    )
    email = models.EmailField("email", max_length=254, unique=True)
    first_name = models.CharField("nombre", max_length=150)
    last_name = models.CharField("apellidos", max_length=150)
    role = models.CharField(
        "rol", max_length=16, choices=Role.choices, default=Role.CUSTOMER, db_index=True
    )
    is_active = models.BooleanField("activo", default=True)
    is_staff = models.BooleanField(
        "acceso al admin técnico",
        default=False,
        help_text="Solo propietarios. Se deriva del rol.",
    )
    date_joined = models.DateTimeField("fecha de alta", default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
            models.CheckConstraint(
                condition=Q(role__in=["OWNER", "EMPLOYEE", "CUSTOMER"]),
                name="accounts_user_role_valid",
            ),
            models.CheckConstraint(
                condition=Q(is_staff=False) | Q(role="OWNER"),
                name="accounts_user_staff_only_owner",
            ),
            models.CheckConstraint(
                condition=Q(is_superuser=False) | Q(role="OWNER"),
                name="accounts_user_superuser_only_owner",
            ),
        ]

    def __str__(self):
        return self.email

    def clean(self):
        super().clean()
        self.email = normalize_email_address(self.email)

    def save(self, *args, **kwargs):
        self.email = normalize_email_address(self.email)
        super().save(*args, **kwargs)

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.first_name

    @property
    def is_owner(self):
        return self.role == self.Role.OWNER

    @property
    def is_employee(self):
        return self.role == self.Role.EMPLOYEE

    @property
    def is_customer(self):
        return self.role == self.Role.CUSTOMER
