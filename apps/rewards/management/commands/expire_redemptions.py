"""
Caduca los canjes pendientes cuyo plazo ha vencido y devuelve los puntos.

Pensado para ejecutarse periódicamente (la programación de tareas llega en la
Fase 10). No es imprescindible para la seguridad: un código vencido nunca se
acepta y se caduca al intentar validarlo; el comando solo devuelve antes los
puntos de los códigos que nadie llegó a presentar.
"""
from django.core.management.base import BaseCommand

from apps.rewards import services


class Command(BaseCommand):
    help = "Caduca los canjes pendientes vencidos y devuelve los puntos a los clientes."

    def handle(self, *args, **options):
        expired = services.expire_pending_redemptions()
        self.stdout.write(f"Canjes caducados: {expired}")
