"""Vista del cliente con su QR personal. Solo presentación: las reglas están en `services`."""
import segno
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.accounts.permissions import verified_email_required

from . import services


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
