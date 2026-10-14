"""
Dashboard del propietario (Fase 9). Solo presentación.

Todas las vistas exigen el rol de propietario en el servidor
(`role_required(OWNER)`): sin sesión → login; empleado o cliente → 403. Las
lecturas pasan por los `selectors` de cada dominio, que vuelven a comprobar el
rol, y las escrituras por sus servicios (permisos, validación, transacción y
auditoría). Aquí solo se traducen filtros y errores. Ninguna respuesta se
guarda en caché.

Privacidad: los listados muestran solo los campos necesarios; la ficha del
cliente muestra sus datos completos y su consulta queda auditada. La búsqueda
por nombre o email se envía por POST y se guarda en la sesión para que no
aparezca en la URL ni en los logs del servidor.
"""
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts import selectors as accounts_selectors
from apps.accounts import services as accounts
from apps.accounts.countries import COUNTRIES, COUNTRY_NAMES
from apps.accounts.models import CustomerProfile, User
from apps.accounts.permissions import role_required
from apps.catalog import selectors as catalog_selectors
from apps.catalog import services as catalog
from apps.catalog.models import Category, Product
from apps.loyalty import conversion, ledger, promotions
from apps.loyalty import selectors as loyalty_selectors
from apps.loyalty.models import PointsTransaction, Promotion
from apps.purchases import selectors as purchase_selectors
from apps.rewards import selectors as reward_selectors
from apps.rewards import services as rewards
from apps.rewards.models import Reward
from apps.web import services as web

from . import forms
from .forms import CustomerFilters, PeriodForm, choice, yes_no

PAGE_SIZE = 25
CUSTOMER_QUERY_SESSION_KEY = "dashboard_customer_query"

# (clave, etiqueta, nombre de URL). Eventos y Reservas llegan en la Fase 10.
SECTIONS = (
    ("resumen", "Resumen", "dashboard:home"),
    ("clientes", "Clientes", "dashboard:customers"),
    ("empleados", "Empleados", "dashboard:employees"),
    ("compras", "Compras", "dashboard:purchases"),
    ("puntos", "Puntos", "dashboard:points"),
    ("recompensas", "Recompensas", "dashboard:rewards"),
    ("carta", "Carta", "dashboard:menu"),
    ("cervezas", "Cervezas", "dashboard:beers"),
    ("eventos", "Eventos", "dashboard:events"),
    ("reservas", "Reservas", "dashboard:reservations"),
    ("promociones", "Promociones", "dashboard:promotions"),
    ("contenido", "Contenido", "dashboard:content"),
    ("configuracion", "Configuración", "dashboard:settings"),
)

owner_required = role_required(User.Role.OWNER)


# --- Utilidades -------------------------------------------------------------------


def _render(request, template, section, context=None, status=200):
    context = dict(context or {})
    context.update({"section": section, "sections": SECTIONS})
    return render(request, f"dashboard/{template}", context, status=status)


def _period(request, default=forms.DEFAULT_PERIOD):
    form = PeriodForm(request.GET or None, default=default)
    return form, form.period()


def _page(request, queryset):
    return Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page"))


def _error(request, exc):
    messages.error(request, " ".join(exc.messages))


def _apply_errors(form, exc):
    """Lleva los errores de un servicio a los campos del formulario."""
    if hasattr(exc, "error_dict"):
        for field, errors in exc.message_dict.items():
            form.add_error(field if field in form.fields else None, errors)
    else:
        form.add_error(None, exc.messages)


def _form_errors(request, form):
    for errors in form.errors.values():
        messages.error(request, errors[0])
        return


# --- Resumen ----------------------------------------------------------------------


@never_cache
@require_GET
@owner_required
def home(request):
    actor = request.user
    period_form, period = _period(request)
    span = {"start": period.start, "end": period.end}
    return _render(
        request,
        "home.html",
        "resumen",
        {
            "period_form": period_form,
            "period": period,
            "customers": accounts_selectors.customer_counts(actor=actor, **span),
            "purchases": purchase_selectors.registered_purchases_stats(actor=actor, **span),
            "points": loyalty_selectors.points_stats(actor=actor, **span),
            "redemptions": reward_selectors.redemption_stats(actor=actor, **span),
            "zones": accounts_selectors.geographic_distribution(actor=actor, level="localidad", limit=5),
        },
    )


# --- Clientes ---------------------------------------------------------------------


@never_cache
@require_http_methods(["GET", "POST"])
@owner_required
def customers(request):
    if request.method == "POST":
        form = forms.CustomerSearchForm(request.POST)
        query = form.cleaned_data["q"] if form.is_valid() and "limpiar" not in request.POST else ""
        request.session[CUSTOMER_QUERY_SESSION_KEY] = " ".join(query.split())
        return redirect(request.get_full_path())

    query = request.session.get(CUSTOMER_QUERY_SESSION_KEY, "")
    filters = CustomerFilters.from_query(request.GET)
    period_form, period = _period(request, default="todo")
    queryset = accounts_selectors.search_customers(
        actor=request.user,
        query=query,
        verified=yes_no(filters.verified),
        active=yes_no(filters.active),
        promo_email=yes_no(filters.promo),
        start=period.start,
        end=period.end,
        country=filters.country,
        province=filters.province,
        city=filters.city,
        postal_code=filters.postal_code,
    )
    page = _page(request, queryset)
    return _render(
        request,
        "customers.html",
        "clientes",
        {
            "search_form": forms.CustomerSearchForm(initial={"q": query}),
            "query": query,
            "filters": filters,
            "period_form": period_form,
            "period": period,
            "page": page,
            "yes_no": forms.YES_NO,
            "countries": COUNTRIES,
        },
    )


def _customer_or_404(request, public_id):
    customer = accounts_selectors.customer_for_owner(actor=request.user, public_id=public_id)
    if customer is None:
        raise Http404
    return customer


@never_cache
@require_GET
@owner_required
def customer_detail(request, public_id):
    actor = request.user
    customer = _customer_or_404(request, public_id)
    accounts.record_customer_data_access(actor=actor, customer=customer)
    try:
        profile = customer.customer_profile
    except CustomerProfile.DoesNotExist:
        profile = None
    movements = list(loyalty_selectors.points_history(customer)[:20])
    return _render(
        request,
        "customer_detail.html",
        "clientes",
        {
            "customer": customer,
            "profile": profile,
            "country_name": COUNTRY_NAMES.get(profile.country, profile.country) if profile else "",
            "preference_history": accounts_selectors.preference_history(actor=actor, customer=customer),
            "points_summary": loyalty_selectors.points_summary(customer),
            "movements": movements,
            "reversible_ids": loyalty_selectors.reversible_ids(movements),
            "purchases": list(purchase_selectors.customer_purchases(customer).select_related("registered_by")[:10]),
            "redemptions": list(reward_selectors.customer_redemptions(customer).defer("code")[:10]),
            "adjust_form": forms.AdjustPointsForm(),
        },
    )


@never_cache
@require_POST
@owner_required
def customer_adjust_points(request, public_id):
    customer = _customer_or_404(request, public_id)
    form = forms.AdjustPointsForm(request.POST)
    if not form.is_valid():
        _form_errors(request, form)
    else:
        try:
            result = ledger.adjust_points(
                actor=request.user,
                customer=customer,
                points=form.cleaned_data["points"],
                reason=form.cleaned_data["reason"],
                idempotency_key=form.cleaned_data["idempotency_key"],
            )
        except ValidationError as exc:
            _error(request, exc)
        else:
            if result.created:
                messages.success(request, f"Ajuste registrado: {result.movement.points:+d} puntos.")
            else:
                messages.info(request, "Este ajuste ya estaba registrado; no se ha duplicado.")
    return redirect("dashboard:customer_detail", public_id=customer.public_id)


@never_cache
@require_POST
@owner_required
def customer_reverse_movement(request, public_id):
    customer = _customer_or_404(request, public_id)
    form = forms.ReverseMovementForm(request.POST)
    if not form.is_valid():
        _form_errors(request, form)
        return redirect("dashboard:customer_detail", public_id=customer.public_id)
    # Solo movimientos de este cliente: otro id responde 404 (sin revelar si existe).
    movement = PointsTransaction.objects.filter(customer=customer, public_id=form.cleaned_data["movement"]).first()
    if movement is None:
        raise Http404
    try:
        result = ledger.reverse_movement(actor=request.user, movement=movement, reason=form.cleaned_data["reason"])
    except ValidationError as exc:
        _error(request, exc)
    else:
        if result.created:
            messages.success(request, f"Movimiento compensado: {result.movement.points:+d} puntos.")
        else:
            messages.info(request, "Ese movimiento ya estaba compensado.")
    return redirect("dashboard:customer_detail", public_id=customer.public_id)


@never_cache
@require_GET
@owner_required
def customer_zones(request):
    actor = request.user
    level = choice(request.GET, "nivel", forms.GEO_LEVEL_CHOICES, "localidad")
    base = choice(request.GET, "base", forms.GEO_BASE_CHOICES, "altas")
    country = choice(request.GET, "pais", COUNTRIES)
    period_form, period = _period(request, default="todo")
    if base == "compras":
        ids = purchase_selectors.customer_ids_with_purchases(actor=actor, start=period.start, end=period.end)
        distribution = accounts_selectors.geographic_distribution(
            actor=actor, level=level, customer_ids=ids, country=country
        )
    else:
        distribution = accounts_selectors.geographic_distribution(
            actor=actor, level=level, start=period.start, end=period.end, country=country
        )
    top = max((row.count for row in distribution.rows), default=0)
    rows = [
        (row, urlencode(row.filters), round(row.count * 100 / top) if top else 0) for row in distribution.rows
    ]
    return _render(
        request,
        "customer_zones.html",
        "clientes",
        {
            "distribution": distribution,
            "rows": rows,
            "others_percent": distribution.percent(distribution.others_count),
            "unknown_percent": distribution.percent(distribution.unknown_count),
            "level": level,
            "base": base,
            "country": country,
            "level_choices": forms.GEO_LEVEL_CHOICES,
            "base_choices": forms.GEO_BASE_CHOICES,
            "countries": COUNTRIES,
            "period_form": period_form,
            "period": period,
        },
    )


# --- Empleados --------------------------------------------------------------------


def _staff_or_404(request, public_id):
    member = accounts_selectors.staff_member(actor=request.user, public_id=public_id)
    if member is None:
        raise Http404
    return member


def _render_employees(request, create_form=None, status=200):
    actor = request.user
    period_form, period = _period(request)
    span = {"actor": actor, "start": period.start, "end": period.end}
    purchases_by = purchase_selectors.purchases_by_staff(**span)
    validations_by = reward_selectors.validations_by_staff(**span)
    rows = [
        (member, purchases_by.get(member.pk, (0, None)), validations_by.get(member.pk, 0))
        for member in accounts_selectors.staff_members(actor=actor)
    ]
    return _render(
        request,
        "employees.html",
        "empleados",
        {
            "rows": rows,
            "period_form": period_form,
            "period": period,
            "create_form": create_form or forms.EmployeeCreateForm(),
            "role_form": forms.RoleChangeForm(),
        },
        status=status,
    )


@never_cache
@require_GET
@owner_required
def employees(request):
    return _render_employees(request)


@never_cache
@require_POST
@owner_required
def employee_create(request):
    form = forms.EmployeeCreateForm(request.POST)
    if form.is_valid():
        data = form.cleaned_data
        try:
            accounts.create_employee(
                actor=request.user,
                email=data["email"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                password=data["password1"],
            )
        except ValidationError as exc:
            if hasattr(exc, "error_dict"):
                _apply_errors(form, exc)
            else:
                # Errores del validador de contraseñas.
                form.add_error("password1", exc.messages)
        else:
            messages.success(request, "Empleado dado de alta. Ya puede entrar con su email y la contraseña inicial.")
            return redirect("dashboard:employees")
    return _render_employees(request, create_form=form, status=400)


@never_cache
@require_POST
@owner_required
def employee_status(request, public_id):
    member = _staff_or_404(request, public_id)
    if member.pk == request.user.pk:
        messages.error(request, "No puedes desactivar tu propia cuenta desde el dashboard.")
        return redirect("dashboard:employees")
    action = request.POST.get("accion")
    if action not in ("activar", "desactivar"):
        messages.error(request, "Acción no válida.")
        return redirect("dashboard:employees")
    try:
        accounts.set_user_active(actor=request.user, user=member, is_active=action == "activar")
    except ValidationError as exc:
        _error(request, exc)
    else:
        messages.success(request, "Cuenta activada." if action == "activar" else "Cuenta desactivada: ya no puede entrar.")
    return redirect("dashboard:employees")


@never_cache
@require_POST
@owner_required
def employee_role(request, public_id):
    member = _staff_or_404(request, public_id)
    if member.pk == request.user.pk:
        messages.error(request, "No puedes cambiar tu propio rol desde el dashboard.")
        return redirect("dashboard:employees")
    form = forms.RoleChangeForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Elige el nuevo rol y marca la casilla de confirmación.")
        return redirect("dashboard:employees")
    try:
        accounts.change_role(actor=request.user, user=member, new_role=form.cleaned_data["role"])
    except ValidationError as exc:
        _error(request, exc)
    else:
        messages.success(request, "Rol actualizado.")
    return redirect("dashboard:employees")


# --- Compras y puntos -------------------------------------------------------------


@never_cache
@require_GET
@owner_required
def purchases(request):
    actor = request.user
    period_form, period = _period(request)
    status = choice(request.GET, "estado", forms.PURCHASE_STATUS_CHOICES)
    staff_options = list(accounts_selectors.staff_members(actor=actor))
    staff_id = request.GET.get("empleado", "")
    selected = next((m for m in staff_options if str(m.public_id) == staff_id), None)
    queryset = purchase_selectors.all_purchases(
        actor=actor, start=period.start, end=period.end, registered_by=selected, status=status
    )
    return _render(
        request,
        "purchases.html",
        "compras",
        {
            "period_form": period_form,
            "period": period,
            "stats": purchase_selectors.registered_purchases_stats(actor=actor, start=period.start, end=period.end),
            "page": _page(request, queryset),
            "status": status,
            "status_choices": forms.PURCHASE_STATUS_CHOICES,
            "staff_options": staff_options,
            "selected_staff": selected,
        },
    )


@never_cache
@require_GET
@owner_required
def points(request):
    actor = request.user
    period_form, period = _period(request)
    kind = choice(request.GET, "tipo", forms.MOVEMENT_KIND_CHOICES)
    queryset = loyalty_selectors.all_movements(actor=actor, start=period.start, end=period.end, kind=kind)
    return _render(
        request,
        "points.html",
        "puntos",
        {
            "period_form": period_form,
            "period": period,
            "stats": loyalty_selectors.points_stats(actor=actor, start=period.start, end=period.end),
            "rate": conversion.current_rate(),
            "page": _page(request, queryset),
            "kind": kind,
            "kind_choices": forms.MOVEMENT_KIND_CHOICES,
        },
    )


# --- Recompensas y promociones ----------------------------------------------------


@never_cache
@require_GET
@owner_required
def rewards_view(request):
    actor = request.user
    period_form, period = _period(request)
    status = choice(request.GET, "estado", forms.REDEMPTION_STATUS_CHOICES)
    queryset = reward_selectors.all_redemptions(actor=actor, start=period.start, end=period.end, status=status)
    return _render(
        request,
        "rewards.html",
        "recompensas",
        {
            "period_form": period_form,
            "period": period,
            "rewards": reward_selectors.rewards_overview(actor=actor),
            "stats": reward_selectors.redemption_stats(actor=actor, start=period.start, end=period.end),
            "page": _page(request, queryset),
            "status": status,
            "status_choices": forms.REDEMPTION_STATUS_CHOICES,
            "manageable": rewards.MANAGEABLE_REWARD_STATUSES,
        },
    )


@never_cache
@require_POST
@owner_required
def reward_status(request, public_id):
    reward = Reward.objects.filter(public_id=public_id).first()
    if reward is None:
        raise Http404
    try:
        rewards.set_reward_status(actor=request.user, reward=reward, status=request.POST.get("estado"))
    except ValidationError as exc:
        _error(request, exc)
    else:
        messages.success(request, f"Estado de «{reward.name}» actualizado.")
    return redirect("dashboard:rewards")


@never_cache
@require_GET
@owner_required
def promotions_view(request):
    return _render(
        request,
        "promotions.html",
        "promociones",
        {
            "promotions": loyalty_selectors.promotions_overview(actor=request.user),
            "manageable": promotions.MANAGEABLE_STATUSES,
        },
    )


@never_cache
@require_POST
@owner_required
def promotion_status(request, public_id):
    promotion = Promotion.objects.filter(public_id=public_id).first()
    if promotion is None:
        raise Http404
    try:
        promotions.set_promotion_status(actor=request.user, promotion=promotion, status=request.POST.get("estado"))
    except ValidationError as exc:
        _error(request, exc)
    else:
        messages.success(request, f"Estado de «{promotion.name}» actualizado.")
    return redirect("dashboard:promotions")


# --- Carta y cervezas -------------------------------------------------------------


def _products(request, *, beers, section):
    status = choice(request.GET, "estado", forms.PRODUCT_STATUS_CHOICES)
    categories = list(Category.objects.order_by("position", "name"))
    category = next((c for c in categories if c.slug == request.GET.get("categoria")), None)
    queryset = catalog_selectors.products_for_management(
        actor=request.user, beers=beers, status=status, category=category
    )
    return _render(
        request,
        "products.html",
        section,
        {
            "page": _page(request, queryset),
            "beers": beers,
            "status": status,
            "status_choices": forms.PRODUCT_STATUS_CHOICES,
            "categories": categories,
            "category": category,
            "tap_menu": catalog_selectors.current_tap_menu(),
            "product_statuses": Product.Status.choices,
        },
    )


@never_cache
@require_GET
@owner_required
def menu(request):
    return _products(request, beers=False, section="carta")


@never_cache
@require_GET
@owner_required
def beers(request):
    return _products(request, beers=True, section="cervezas")


def _product_or_404(public_id):
    product = Product.objects.filter(public_id=public_id).first()
    if product is None:
        raise Http404
    return product


def _back_to_products(request, product):
    target = "dashboard:beers" if product.is_beer else "dashboard:menu"
    return redirect(target)


@never_cache
@require_POST
@owner_required
def product_status(request, public_id):
    product = _product_or_404(public_id)
    try:
        catalog.set_product_status(actor=request.user, product=product, status=request.POST.get("estado"))
    except ValidationError as exc:
        _error(request, exc)
    else:
        messages.success(request, f"Estado de «{product.name}» actualizado.")
    return _back_to_products(request, product)


@never_cache
@require_POST
@owner_required
def product_availability(request, public_id):
    product = _product_or_404(public_id)
    available = request.POST.get("disponible")
    if available not in ("si", "no"):
        messages.error(request, "Acción no válida.")
    else:
        catalog.set_product_availability(actor=request.user, product=product, is_available=available == "si")
        messages.success(
            request, f"«{product.name}» marcado como {'disponible' if available == 'si' else 'agotado'}."
        )
    return _back_to_products(request, product)


# --- Eventos y reservas (Fase 10) -------------------------------------------------


@never_cache
@require_GET
@owner_required
def events(request):
    return _render(request, "pending_phase.html", "eventos", {"title": "Eventos"})


@never_cache
@require_GET
@owner_required
def reservations(request):
    return _render(request, "pending_phase.html", "reservas", {"title": "Reservas"})


# --- Contenido y configuración ----------------------------------------------------


@never_cache
@require_http_methods(["GET", "POST"])
@owner_required
def content(request):
    if request.method == "POST":
        form = forms.BusinessInfoForm(request.POST)
        if form.is_valid():
            try:
                _, changed = web.update_business_info(actor=request.user, data=form.cleaned_data)
            except ValidationError as exc:
                _apply_errors(form, exc)
            else:
                messages.success(request, "Contenido guardado." if changed else "No había cambios que guardar.")
                return redirect("dashboard:content")
        status = 400
    else:
        info = web.editable_business_info()
        form = forms.BusinessInfoForm(initial={name: getattr(info, name) for name in web.EDITABLE_FIELDS})
        status = 200
    return _render(request, "content.html", "contenido", {"form": form}, status=status)


@never_cache
@require_http_methods(["GET", "POST"])
@owner_required
def settings_view(request):
    form = forms.LoyaltyRuleForm(request.POST or None)
    status = 200
    if request.method == "POST":
        if form.is_valid():
            try:
                conversion.create_rule(
                    actor=request.user,
                    points_per_euro=form.cleaned_data["points_per_euro"],
                    note=form.cleaned_data["note"],
                )
            except ValidationError as exc:
                _apply_errors(form, exc)
            else:
                messages.success(request, "Nueva conversión en vigor para las próximas compras.")
                return redirect("dashboard:settings")
        status = 400
    return _render(
        request,
        "settings.html",
        "configuracion",
        {
            "form": form,
            "rate": conversion.current_rate(),
            "rules": conversion.rule_history(),
            "read_only_settings": (
                ("Importe máximo por compra", f"{settings.PURCHASES_MAX_AMOUNT} €"),
                ("Días para recoger una recompensa canjeada", settings.REWARDS_CODE_VALIDITY_DAYS),
                ("Ajuste manual máximo de puntos", settings.LOYALTY_MAX_ADJUSTMENT_POINTS),
                ("Edad mínima para registrarse", settings.ACCOUNTS_MIN_CUSTOMER_AGE),
            ),
            "admin_url": reverse("admin:index"),
        },
        status=status,
    )
