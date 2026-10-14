"""
Reparte las campañas programadas y envía las notificaciones pendientes.

Pensado para ejecutarse cada pocos minutos con el programador del sistema
(cron o el Programador de tareas de Windows; ver docs/fase-10). Es seguro
lanzarlo varias veces a la vez: cada notificación se reclama con un UPDATE
condicionado y las campañas se bloquean al repartirlas.
"""
from django.core.management.base import BaseCommand

from apps.notifications import campaigns, services


class Command(BaseCommand):
    help = "Reparte las campañas programadas y envía las notificaciones pendientes."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Máximo de notificaciones a enviar en esta ejecución.")

    def handle(self, *args, limit=None, **options):
        created = campaigns.dispatch_queued()
        result = services.process_due(limit=limit)
        self.stdout.write(
            f"Campañas: {created} notificaciones creadas. "
            f"Enviadas: {result.sent}. No enviadas: {result.skipped}. "
            f"Reintento pendiente: {result.retrying}. Fallidas: {result.failed}. "
            f"Recuperadas: {result.requeued}. Interrumpidas: {result.interrupted}."
        )
