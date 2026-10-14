"""
Panel del personal para registrar compras manuales.

Escanear (o teclear) el QR -> confirmar el cliente e introducir el importe ->
ver el resultado. Todo pasa por `services`; las vistas solo traducen errores a
mensajes. Las respuestas no se guardan en caché porque llevan el código del
cliente en un campo oculto, y el código nunca viaja en la URL (no queda en
logs del servidor ni en el historial del navegador).
"""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.models import User
from apps.accounts.permissions import role_required
from apps.loyalty import selectors as loyalty_selectors
from apps.loyalty import services as loyalty

from . import services
from .forms import IdentifyForm, PurchaseForm

staff_required = role_required(User.Role.OWNER, User.Role.EMPLOYEE)

_TOO_MANY = "Demasiados códigos no válidos seguidos. Espera unos minutos antes de volver a intentarlo."
_QR_ERROR_CODES = {"invalid_qr", "email_not_verified"}


def _render_scan(request, form=None, status=200, error=None):
    return render(
        request,
        "purchases/scan.html",
        {
            "form": form or IdentifyForm(),
            "scan_error": error,
            "recent_purchases": services.recent_purchases_by(request.user),
        },
        status=status,
    )


def _render_confirm(request, form, display_name, status=200):
    return render(
        request,
        "purchases/confirm.html",
        {"form": form, "customer_name": display_name},
        status=status,
    )


@never_cache
@require_GET
@staff_required
def scan(request):
    return _render_scan(request)


@never_cache
@require_POST
@staff_required
def identify(request):
    form = IdentifyForm(request.POST)
    if not form.is_valid():
        return _render_scan(request, form, status=400)
    try:
        customer = services.identify_for_purchase(staff=request.user, qr_code=form.cleaned_data["code"])
    except services.TooManyFailedAttempts:
        form.add_error(None, _TOO_MANY)
        return _render_scan(request, form, status=429)
    except ValidationError as exc:
        form.add_error(None, exc)
        return _render_scan(request, form, status=400)
    purchase_form = PurchaseForm(
        initial={
            "code": loyalty.normalize_code(form.cleaned_data["code"]),
            "idempotency_key": services.new_idempotency_key(),
        }
    )
    return _render_confirm(request, purchase_form, customer.display_name)


@never_cache
@require_POST
@staff_required
def register(request):
    form = PurchaseForm(request.POST)
    code = request.POST.get("code", "")
    try:
        if not form.is_valid():
            # Importe no válido: se vuelve a la confirmación con el mismo cliente.
            customer = services.identify_for_purchase(staff=request.user, qr_code=code)
            return _render_confirm(request, form, customer.display_name, status=400)
        result = services.register_purchase(
            staff=request.user,
            qr_code=form.cleaned_data["code"],
            amount=form.cleaned_data["amount"],
            idempotency_key=form.cleaned_data["idempotency_key"],
        )
    except services.TooManyFailedAttempts:
        return _render_scan(request, status=429, error=_TOO_MANY)
    except ValidationError as exc:
        if exc.code in _QR_ERROR_CODES or exc.code == "idempotency_invalid":
            return _render_scan(request, status=400, error=exc.messages[0])
        form.add_error(None, exc)
        try:
            customer = services.identify_for_purchase(staff=request.user, qr_code=code)
        except (ValidationError, services.TooManyFailedAttempts):
            return _render_scan(request, status=400, error=exc.messages[0])
        return _render_confirm(request, form, customer.display_name, status=400)

    if result.created:
        messages.success(request, "Compra registrada.")
    else:
        messages.info(request, "Esta compra ya estaba registrada. No se ha duplicado.")
    return redirect("purchases:detail", public_id=result.purchase.public_id)


@never_cache
@require_GET
@staff_required
def detail(request, public_id):
    purchase = (
        services.visible_purchases(request.user)
        .select_related("customer", "registered_by")
        .filter(public_id=public_id)
        .first()
    )
    if purchase is None:
        # 404 también para compras ajenas: no se revela si existen.
        raise Http404
    return render(
        request,
        "purchases/detail.html",
        {
            "purchase": purchase,
            "customer_name": loyalty.customer_display_name(purchase.customer),
            "points": loyalty_selectors.points_for_purchase(purchase),
        },
    )
