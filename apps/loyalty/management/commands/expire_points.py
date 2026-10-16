"""
Avisa de los puntos que van a caducar y descuenta los ya vencidos (Fase 14).

Ejecutar una vez al día (cron; ver docs/fase-14) y, después,
`process_notifications` para enviar los avisos. Repetirlo no duplica avisos
ni caducidades. Sin caducidad configurada no hace nada.

`--at` (solo con DEBUG) simula otra fecha para probar en desarrollo.
"""
import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.loyalty import expirations


class Command(BaseCommand):
    help = "Avisa de los puntos que van a caducar y descuenta los vencidos según la caducidad configurada."

    def add_arguments(self, parser):
        parser.add_argument("--at", help="Solo desarrollo (DEBUG): procesa como si fuera esta fecha (AAAA-MM-DD).")

    def handle(self, *args, at=None, **options):
        moment = None
        if at:
            if not settings.DEBUG:
                raise CommandError("--at solo está disponible en desarrollo (DEBUG=True).")
            try:
                day = datetime.date.fromisoformat(at)
            except ValueError:
                raise CommandError("Fecha no válida: usa AAAA-MM-DD.") from None
            moment = timezone.make_aware(datetime.datetime.combine(day, datetime.time(4, 15)))
        result = expirations.run(at=moment)
        if not result.policy:
            self.stdout.write("Los puntos no caducan: no hay nada que procesar.")
            return
        self.stdout.write(
            f"Avisos encolados {result.warned}, clientes con puntos caducados {result.expired_customers}, "
            f"puntos caducados {result.expired_points}."
        )
