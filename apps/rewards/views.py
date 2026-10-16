"""
Vistas de canjes. Solo presentación: las reglas están en `services` y las
consultas en `selectors`.

- Cliente (`/cuenta/...`): ver una recompensa y canjearla, su historial de
  canjes, el código de cada canje y cancelarlo. Siempre sobre `request.user`.
- Personal (`/panel/canjes/`): leer el código, comprobarlo y validarlo. El
  código nunca viaja en la URL (no queda en logs ni en el historial).

Ninguna respuesta se guarda en caché: llevan códigos o saldos.
"""
import segno
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.accounts.permissions import role_required, verified_email_required
from apps.loyalty import ledger
from apps.loyalty import services as loyalty

from . import codes, selectors, services
from .forms import RedeemForm, RedemptionCodeForm, ValidateRedemptionForm
from .models import Redemption

HISTORY_PAGE_SIZE = 20

staff_required = role_required(User.Role.OWNER, User.Role.EMPLOYEE)


def _require_customer(user):
    if user.role != User.Role.CUSTOMER:
        raise PermissionDenied


# --- Cliente ----------------------------------------------------------------------


def _get_reward(public_id):
    reward = selectors.public_reward(public_id)
    if reward is None:
        raise Http404
    return reward


def _render_reward(request, reward, status=200, error=None):
    balance = ledger.balance(request.user)
    return render(
        request,
        "rewards/reward_detail.html",
        {
            "reward": reward,
            "balance": balance,
            "can_afford": balance >= reward.points_cost,
            "missing_points": max(reward.points_cost - balance, 0),
            "pending": selectors.pending_redemption_for(request.user, reward),
            "form": RedeemForm(initial={"idempotency_key": services.new_idempotency_key()}),
            "error": error,
        },
        status=status,
    )


@never_cache
@require_GET
@verified_email_required
def reward_detail(request, public_id):
    _require_customer(request.user)
    return _render_reward(request, _get_reward(public_id))


@never_cache
@require_POST
@verified_email_required
def redeem(request, public_id):
    _require_customer(request.user)
    reward = selectors.public_reward(public_id)
    form = RedeemForm(request.POST)
    if reward is None:
        # La recompensa dejó de estar disponible entre ver la página y confirmar.
        messages.error(request, services.RewardNotAvailable().messages[0])
        return redirect("web:rewards")
    if not form.is_valid():
        return _render_reward(request, reward, status=400, error=_("La operación no es válida. Vuelve a intentarlo."))
    try:
        result = services.request_redemption(
            customer=request.user, reward=reward, idempotency_key=form.cleaned_data["idempotency_key"]
        )
    except ValidationError as exc:
        return _render_reward(request, reward, status=400, error=exc.messages[0])
    if result.created:
        messages.success(request, _("¡Canje hecho! Enseña este código en la barra para recoger tu recompensa."))
    else:
        messages.info(request, _("Este canje ya estaba hecho. No se han descontado más puntos."))
    return redirect("rewards:redemption_detail", public_id=result.redemption.public_id)


@never_cache
@require_GET
@verified_email_required
def my_redemptions(request):
    _require_customer(request.user)
    page = Paginator(selectors.customer_redemptions(request.user), HISTORY_PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "rewards/my_redemptions.html", {"redemptions": page})


def _get_own_redemption(request, public_id):
    redemption = selectors.customer_redemption(request.user, public_id)
    if redemption is None:
        # 404 también para canjes ajenos: no se revela si existen.
        raise Http404
    return redemption


@never_cache
@require_GET
@verified_email_required
def redemption_detail(request, public_id):
    _require_customer(request.user)
    redemption = _get_own_redemption(request, public_id)
    context = {"redemption": redemption, "is_expired": redemption.is_expired()}
    if redemption.status == Redemption.Status.PENDING and not context["is_expired"]:
        # Data URI de un SVG generado aquí: sin peticiones a terceros.
        context["qr_image"] = segno.make(codes.qr_payload(redemption.code), error="m").svg_data_uri(
            scale=8, border=4, dark="#080808", light="#ffffff"
        )
        context["code_text"] = codes.format_code(redemption.code)
    return render(request, "rewards/redemption_detail.html", context)


@require_POST
@verified_email_required
def cancel(request, public_id):
    _require_customer(request.user)
    redemption = _get_own_redemption(request, public_id)
    try:
        result = services.cancel_redemption(customer=request.user, redemption=redemption)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        if result.created:
            messages.success(request, _("Canje cancelado. Te hemos devuelto %(points_cost)s puntos.") % {"points_cost": redemption.points_cost})
    return redirect("rewards:redemption_detail", public_id=redemption.public_id)


# --- Personal -----------------------------------------------------------------------

_TOO_MANY = _("Demasiados códigos no válidos seguidos. Espera unos minutos antes de volver a intentarlo.")


def _render_scan(request, form=None, status=200, error=None):
    return render(
        request,
        "rewards/staff_scan.html",
        {
            "form": form or RedemptionCodeForm(),
            "scan_error": error,
            "recent_validations": selectors.recent_validations_by(request.user),
        },
        status=status,
    )


@never_cache
@require_GET
@staff_required
def staff_scan(request):
    return _render_scan(request)


@never_cache
@require_POST
@staff_required
def staff_lookup(request):
    form = RedemptionCodeForm(request.POST)
    if not form.is_valid():
        return _render_scan(request, form, status=400)
    try:
        preview = services.lookup_redemption(staff=request.user, code=form.cleaned_data["code"])
    except services.TooManyFailedAttempts:
        return _render_scan(request, form, status=429, error=_TOO_MANY)
    except ValidationError as exc:
        return _render_scan(request, form, status=400, error=exc.messages[0])
    confirm_form = ValidateRedemptionForm(initial={"code": codes.normalize_code(form.cleaned_data["code"])})
    return render(request, "rewards/staff_confirm.html", {"preview": preview, "form": confirm_form})


@never_cache
@require_POST
@staff_required
def staff_validate(request):
    form = ValidateRedemptionForm(request.POST)
    if not form.is_valid():
        return _render_scan(request, status=400, error=_("El código no es válido."))
    try:
        result = services.validate_redemption(staff=request.user, code=form.cleaned_data["code"])
    except services.TooManyFailedAttempts:
        return _render_scan(request, status=429, error=_TOO_MANY)
    except (ValidationError, PermissionDenied) as exc:
        message = exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
        return _render_scan(request, status=400, error=message)
    messages.success(request, _("Canje validado. Entrega la recompensa."))
    return redirect("rewards_panel:detail", public_id=result.redemption.public_id)


@never_cache
@require_GET
@staff_required
def staff_detail(request, public_id):
    redemption = (
        services.visible_redemptions_for_staff(request.user)
        .select_related("customer", "reward", "validated_by")
        .filter(public_id=public_id)
        .first()
    )
    if redemption is None:
        raise Http404
    return render(
        request,
        "rewards/staff_detail.html",
        {"redemption": redemption, "customer_name": loyalty.customer_display_name(redemption.customer)},
    )
