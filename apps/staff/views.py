"""
Panel del personal (Fase 8): inicio, perfil del empleado y consulta de
resultados. Solo presentación y solo lectura: las operaciones (registrar
compras, validar canjes) siguen en `apps.purchases` y `apps.rewards`, y las
consultas en sus `selectors`.

Cada empleado ve únicamente sus propias operaciones y, de cada cliente, solo
el nombre abreviado («Lúa F.»): nunca email, teléfono, dirección, fecha de
nacimiento, saldo ni historial. Ninguna respuesta se guarda en caché.
"""
from django.core.paginator import Paginator
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.accounts.models import User
from apps.accounts.permissions import role_required
from apps.loyalty import services as loyalty
from apps.purchases import selectors as purchase_selectors
from apps.rewards import selectors as reward_selectors

from .forms import ResultsFilterForm, period_start

RESULTS_PAGE_SIZE = 20

staff_required = role_required(User.Role.OWNER, User.Role.EMPLOYEE)


def _summary(staff, since):
    purchases_count, purchases_amount = purchase_selectors.staff_purchases_summary(staff, since=since)
    return {
        "purchases_count": purchases_count,
        "purchases_amount": purchases_amount,
        "validations_count": reward_selectors.validations_by(staff, since=since).count(),
    }


@never_cache
@require_GET
@staff_required
def home(request):
    return render(request, "staff/home.html", {"today": _summary(request.user, period_start("hoy"))})


@never_cache
@require_GET
@staff_required
def profile(request):
    # Solo lectura: el nombre y el rol los cambia el propietario desde el admin.
    return render(request, "staff/profile.html")


@never_cache
@require_GET
@staff_required
def results(request):
    kind, period = ResultsFilterForm(request.GET).values()
    since = period_start(period)
    if kind == "canjes":
        queryset = reward_selectors.validations_by(request.user, since=since)
    else:
        queryset = purchase_selectors.purchases_registered_by(request.user, since=since)
    page = Paginator(queryset, RESULTS_PAGE_SIZE).get_page(request.GET.get("page"))
    rows = [(item, loyalty.customer_display_name(item.customer)) for item in page]
    return render(
        request,
        "staff/results.html",
        {
            "kind": kind,
            "period": period,
            "kind_choices": ResultsFilterForm.KIND_CHOICES,
            "period_choices": ResultsFilterForm.PERIOD_CHOICES,
            "page": page,
            "rows": rows,
            "summary": _summary(request.user, since),
        },
    )
