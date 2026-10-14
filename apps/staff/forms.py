"""
Filtros de la consulta de resultados. Solo convierten la entrada: un valor
desconocido se sustituye por el de por defecto en lugar de dar un error.
"""
import datetime

from django import forms
from django.utils import timezone

PERIOD_DAYS = {"hoy": 1, "7d": 7, "30d": 30}


def period_start(period, now=None):
    """Inicio (medianoche local) del periodo: hoy, últimos 7 o 30 días incluido hoy."""
    today = timezone.localdate(now)
    first_day = today - datetime.timedelta(days=PERIOD_DAYS[period] - 1)
    return timezone.make_aware(datetime.datetime.combine(first_day, datetime.time.min))


class ResultsFilterForm(forms.Form):
    KIND_CHOICES = [("compras", "Compras"), ("canjes", "Canjes")]
    PERIOD_CHOICES = [("hoy", "Hoy"), ("7d", "7 días"), ("30d", "30 días")]

    tipo = forms.ChoiceField(choices=KIND_CHOICES, required=False)
    periodo = forms.ChoiceField(choices=PERIOD_CHOICES, required=False)

    def values(self):
        data = self.cleaned_data if self.is_valid() else {}
        return data.get("tipo") or "compras", data.get("periodo") or "hoy"
