"""
Borra los tokens de verificación de email caducados hace más de N días.

Pensado para ejecutarse una vez al día con el programador del sistema (ver
docs/despliegue.md). Los tokens guardan el email al que se enviaron; una vez
caducados no sirven para nada, así que no se conservan.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.accounts import services


class Command(BaseCommand):
    help = "Borra los tokens de verificación de email caducados hace más de N días (30 por defecto)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30, help="Antigüedad mínima tras caducar (días).")

    def handle(self, *args, **options):
        try:
            deleted = services.purge_email_tokens(older_than_days=options["days"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Tokens de email borrados: {deleted}")
