"""
Utilidades de fecha de nacimiento para las futuras promociones de cumpleaños.

Política del 29 de febrero: en los años no bisiestos el cumpleaños promocional
se celebra el 28 de febrero (sigue en el mismo mes). El envío de promociones
(Fase de notificaciones) debe además comprobar
`services.can_receive_promotional_email` / `can_receive_promotional_sms`.
"""
import calendar
import datetime

from django.db.models import Q

from .models import CustomerProfile


def birthday_in_year(date_of_birth, year):
    """Fecha en la que se celebra el cumpleaños en `year`."""
    if date_of_birth.month == 2 and date_of_birth.day == 29 and not calendar.isleap(year):
        return datetime.date(year, 2, 28)
    return date_of_birth.replace(year=year)


def profiles_with_birthday_on(day):
    """Perfiles cuyo cumpleaños promocional cae en `day` (incluye 29-F en años no bisiestos)."""
    condition = Q(date_of_birth__month=day.month, date_of_birth__day=day.day)
    if day.month == 2 and day.day == 28 and not calendar.isleap(day.year):
        condition |= Q(date_of_birth__month=2, date_of_birth__day=29)
    return CustomerProfile.objects.filter(condition)
