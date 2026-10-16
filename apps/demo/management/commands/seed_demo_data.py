"""
Carga datos de demostración ficticios (Fase 13). Solo desarrollo y tests.

    python manage.py seed_demo_data            # carga (si ya están, no hace nada)
    python manage.py seed_demo_data --reset    # borra lo de demo y vuelve a cargar
    python manage.py seed_demo_data --clean    # solo borra lo de demo

- Rechaza cualquier configuración que no sea la de desarrollo con DEBUG=True
  o la de tests (`guard.py`); en producción la app ni siquiera está instalada.
- Exige una base de datos sin datos ajenos a la demo, para no mezclarlos.
- Todo se crea con los servicios reales; no se envía ningún email (backend en
  memoria) ni se imprimen contraseñas, tokens ni códigos.

Ver docs/fase-13-datos-demo.md.
"""
import datetime
import logging
import os

from django.core.management.base import BaseCommand, CommandError
from django.test.utils import override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.demo import cleanup, data, guard, selectors
from apps.demo.builder import DemoBuilder

PASSWORD_ENV = "CANECA_DEMO_PASSWORD"
ROLE_LABELS = {User.Role.OWNER: "propietario", User.Role.EMPLOYEE: "empleado", User.Role.CUSTOMER: "cliente"}


class Command(BaseCommand):
    help = "Carga datos de demostración ficticios (solo desarrollo y tests)."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--reset", action="store_true", help="Borra los datos de demostración y los vuelve a cargar.")
        group.add_argument("--clean", action="store_true", help="Solo borra los datos de demostración.")
        parser.add_argument(
            "--reference-date",
            help="Fecha de referencia AAAA-MM-DD (por defecto, hoy). Todas las fechas se calculan a partir de ella.",
        )
        parser.add_argument(
            "--noinput", "--no-input", action="store_false", dest="interactive", help="No pedir confirmación."
        )

    def handle(self, *args, reset=False, clean=False, reference_date=None, interactive=True, **options):
        try:
            guard.check_environment()
        except guard.DemoEnvironmentError as exc:
            raise CommandError(str(exc)) from exc
        reference = self._reference_date(reference_date)

        self.stdout.write(f"Base de datos: {guard.database_label()}")
        if interactive:
            action = "borrar" if clean else "borrar y volver a cargar" if reset else "cargar"
            answer = input(f"Se van a {action} los datos de demostración. Escribe «si» para continuar: ")
            if answer.strip().lower() not in ("si", "sí"):
                raise CommandError("Cancelado.")

        # Ningún email sale del proceso (ni a la consola: llevarían enlaces con tokens).
        with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SMS_BACKEND=""):
            if clean or reset:
                self._clean()
            if clean:
                return
            if selectors.demo_data_present():
                self.stdout.write("Los datos de demostración ya están cargados: no se ha cambiado nada (usa --reset).")
                self._summary()
                return
            foreign = selectors.foreign_data_counts()
            if foreign:
                detail = ", ".join(f"{label}: {count}" for label, count in foreign.items())
                raise CommandError(
                    "La base de datos tiene datos que no son de demostración "
                    f"({detail}). Usa una base de datos nueva para la demo (ver docs/fase-13-datos-demo.md)."
                )
            self._load(reference, options.get("verbosity", 1))
        self._summary()

    def _reference_date(self, value):
        today = timezone.localdate()
        if not value:
            return today
        try:
            reference = datetime.date.fromisoformat(value)
        except ValueError as exc:
            raise CommandError("--reference-date debe tener el formato AAAA-MM-DD.") from exc
        if reference > today:
            raise CommandError("--reference-date no puede ser futura.")
        return reference

    def _clean(self):
        try:
            deleted = cleanup.clean()
        except cleanup.DemoCleanupBlocked as exc:
            raise CommandError(str(exc)) from exc
        if deleted:
            self.stdout.write("Datos de demostración borrados: " + ", ".join(f"{k} {v}" for k, v in deleted.items()))
        else:
            self.stdout.write("No había datos de demostración que borrar.")

    def _load(self, reference, verbosity):
        password = os.environ.get(PASSWORD_ENV) or data.DEFAULT_PASSWORD
        self.stdout.write(f"Cargando datos de demostración (referencia {reference:%d/%m/%Y})...")
        # Cada servicio registra sus operaciones (solo identificadores públicos);
        # con cientos de ellas la salida no se lee. `-v 2` las muestra.
        if verbosity < 2:
            logging.disable(logging.INFO)
        try:
            steps = DemoBuilder(reference_date=reference, password=password).build()
        except Exception as exc:
            try:
                cleanup.clean()
            except Exception as cleanup_exc:  # noqa: BLE001 - se informa de los dos errores
                raise CommandError(
                    f"La carga falló ({exc}) y no se pudo deshacer ({cleanup_exc}). Ejecuta --clean."
                ) from exc
            raise CommandError(f"La carga falló y se ha deshecho: {exc}") from exc
        finally:
            logging.disable(logging.NOTSET)
        self.stdout.write(self.style.SUCCESS(f"Datos de demostración cargados ({steps} operaciones)."))

    def _summary(self):
        self.stdout.write("\nRegistros de demostración:")
        for label, count in selectors.demo_counts().items():
            self.stdout.write(f"  {label:<24}{count:>5}")
        self.stdout.write("\nCuentas (solo desarrollo; contraseña en docs/fase-13-datos-demo.md):")
        order = {User.Role.OWNER: 0, User.Role.EMPLOYEE: 1, User.Role.CUSTOMER: 2}
        for user in sorted(selectors.demo_users(), key=lambda u: (order[u.role], u.email)):
            state = "inactiva" if not user.is_active else "verificada" if user.is_email_verified else "pendiente de verificar"
            self.stdout.write(f"  {ROLE_LABELS[user.role]:<12}{user.email:<40}{state}")
