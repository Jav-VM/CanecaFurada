"""
`{% sort_th sort "clave" _("Título") "num" %}`: cabecera de columna con las
flechas para ordenar (Fase 18). Conserva el resto de la consulta (filtros,
periodo) y vuelve a la primera página.
"""
from django import template

from apps.dashboard.sorting import ASC, DESC

register = template.Library()


def _url(request, sort, key, direction):
    query = request.GET.copy()
    query.pop("page", None)
    query[sort.order_param] = key
    query[sort.dir_param] = direction
    return f"?{query.urlencode()}"


@register.inclusion_tag("dashboard/_sort_th.html", takes_context=True)
def sort_th(context, sort, key, label, css_class=""):
    request = context["request"]
    active = sort.key == key
    return {
        "label": label,
        "css_class": css_class,
        "aria_sort": ("descending" if sort.descending else "ascending") if active else "",
        "asc_url": _url(request, sort, key, ASC),
        "desc_url": _url(request, sort, key, DESC),
        "asc_active": active and not sort.descending,
        "desc_active": active and sort.descending,
    }
