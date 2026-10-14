"""
Regala los puntos de cumpleaños del día y encola los avisos autorizados.

Ejecutar una vez al día (cron o Programador de tareas; ver docs/fase-10) y,
después, `process_notifications` para enviar los avisos. Repetirlo no duplica
regalos ni avisos. `--days-back N` (máximo 7) recupera los días en que no se
ejecutó.
"""
import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.loyalty import birthdays


class Command(BaseCommand):
    help = "Concede los regalos de cumpleaños del día y encola sus avisos (solo a quien lo ha autorizado)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days-back",
            type=int,
            default=0,
            help=f"Procesa también los N días anteriores (máximo {birthdays.MAX_DAYS_BACK}).",
        )
        parser.add_argument("--date", help="Procesa solo este día (AAAA-MM-DD, no futuro).")

    def handle(self, *args, days_back=0, date=None, **options):
        if date:
            try:
                day = datetime.date.fromisoformat(date)
            except ValueError:
                raise CommandError("Fecha no válida: usa AAAA-MM-DD.") from None
            if day > timezone.localdate():
                raise CommandError("No se procesan cumpleaños futuros.")
            days = [day]
        else:
            days = birthdays.days_to_process(days_back=days_back)
        for day in days:
            result = birthdays.run_birthday_promotions(day=day)
            if not result.promotion:
                self.stdout.write(f"{result.day}: no hay ninguna promoción de cumpleaños activa.")
                continue
            self.stdout.write(
                f"{result.day}: cumpleaños {result.birthdays}, regalos {result.granted}, "
                f"sin derecho o ya concedidos {result.not_eligible}, avisos por email {result.email_queued}, "
                f"por SMS {result.sms_queued}."
            )
