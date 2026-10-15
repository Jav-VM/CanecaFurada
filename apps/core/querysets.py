"""Utilidades de consulta compartidas por los selectores de los distintos módulos."""
from django.db.models import Q


def period_q(field, start=None, end=None):
    """
    Condición del periodo `[start, end)` sobre el campo de fecha `field`: el
    inicio se incluye y el final no. Sin límites devuelve `Q()`, que no filtra.

    Sirve tanto para `filter()` como para el `filter` de un agregado
    (`Count("id", filter=period_q(...))`), lo que permite calcular varias
    cifras de un periodo en una sola consulta.
    """
    condition = Q()
    if start is not None:
        condition &= Q(**{f"{field}__gte": start})
    if end is not None:
        condition &= Q(**{f"{field}__lt": end})
    return condition
