"""
Procedimiento administrativo para crear el PRIMER propietario.

- Solo funciona si no existe ningún propietario; los siguientes los crea un
  propietario desde el admin.
- La contraseña nunca se acepta como argumento de línea de comandos (quedaría en
  el historial del shell y en la lista de procesos): se pide con getpass o, en
  modo --noinput, se lee de una variable de entorno.
- No se imprime la contraseña ni datos personales más allá del email indicado.
"""
import os
from getpass import getpass

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.accounts import services

ENV_VARS = {
    "email": "CANECA_OWNER_EMAIL",
    "first_name": "CANECA_OWNER_FIRST_NAME",
    "last_name": "CANECA_OWNER_LAST_NAME",
    "password": "CANECA_OWNER_PASSWORD",
}


class Command(BaseCommand):
    help = "Crea el primer propietario (rol OWNER) de forma segura y auditada."

    def add_arguments(self, parser):
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_false",
            dest="interactive",
            help=(
                "No pedir datos: leerlos de CANECA_OWNER_EMAIL, CANECA_OWNER_FIRST_NAME, "
                "CANECA_OWNER_LAST_NAME y CANECA_OWNER_PASSWORD."
            ),
        )

    def handle(self, *args, interactive=True, **options):
        data = self._read_interactive() if interactive else self._read_env()

        try:
            user = services.create_owner(**data)
        except PermissionDenied as exc:
            raise CommandError(str(exc)) from exc
        except ValidationError as exc:
            raise CommandError("Datos no válidos: " + " ".join(exc.messages)) from exc

        self.stdout.write(self.style.SUCCESS(f"Propietario creado (id público {user.public_id})."))

    def _read_interactive(self):
        email = input("Email: ").strip()
        first_name = input("Nombre: ").strip()
        last_name = input("Apellidos: ").strip()
        password = getpass("Contraseña: ")
        password_confirm = getpass("Repite la contraseña: ")
        if password != password_confirm:
            raise CommandError("Las contraseñas no coinciden.")
        self._require_all(email=email, first_name=first_name, last_name=last_name, password=password)
        return {"email": email, "first_name": first_name, "last_name": last_name, "password": password}

    def _read_env(self):
        data = {field: os.environ.get(var, "").strip() for field, var in ENV_VARS.items()}
        # La contraseña se usa tal cual: los espacios pueden formar parte de ella.
        data["password"] = os.environ.get(ENV_VARS["password"], "")
        missing = [ENV_VARS[field] for field, value in data.items() if not value]
        if missing:
            raise CommandError("Faltan variables de entorno: " + ", ".join(missing))
        return data

    @staticmethod
    def _require_all(**fields):
        missing = [name for name, value in fields.items() if not value]
        if missing:
            raise CommandError("Campos obligatorios vacíos: " + ", ".join(missing))
