"""
Vistas del cliente: QR personal y puntos. Solo presentación: las reglas están
en `services`, `ledger` y `selectors`.
"""
import segno
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.accounts.permissions import verified_email_required
from apps.purchases import selectors as purchase_selectors

from . import selectors, services


def _require_customer(user):
    if user.role != User.Role.CUSTOMER:
        raise PermissionDenied


@never_cache
@verified_email_required
def my_qr(request):
    _require_customer(request.user)
    qr = services.get_customer_qr(request.user)
    # Data URI de un SVG generado aquí: no hay peticiones a terceros ni HTML sin escapar.
    image = segno.make(services.qr_payload(qr.token), error="m").svg_data_uri(
        scale=8, border=4, dark="#080808", light="#ffffff"
    )
    return render(
        request,
        "loyalty/my_qr.html",
        {"qr_image": image, "qr_code_text": services.format_code(qr.token), "qr_rotated_at": qr.rotated_at},
    )


HISTORY_PAGE_SIZE = 20


@never_cache
@verified_email_required
def my_points(request):
    """Saldo, historial de movimientos y de compras del cliente autenticado (nunca de otro)."""
    _require_customer(request.user)
    customer = request.user
    movements = Paginator(selectors.points_history(customer), HISTORY_PAGE_SIZE).get_page(request.GET.get("page"))
    purchases = Paginator(
        purchase_selectors.customer_purchases(customer), HISTORY_PAGE_SIZE
    ).get_page(request.GET.get("compras"))
    return render(
        request,
        "loyalty/my_points.html",
        {
            "summary": selectors.points_summary(customer),
            "movements": movements,
            "purchases": purchases,
        },
    )


@require_POST
@verified_email_required
def rotate(request):
    _require_customer(request.user)
    try:
        services.rotate_customer_qr(request.user)
    except services.RotationRateLimited:
        messages.error(request, "Has renovado tu código demasiadas veces hoy. Inténtalo mañana.")
    else:
        messages.success(request, "Tu código QR se ha renovado. El anterior ya no sirve.")
    return redirect("loyalty:my_qr")
