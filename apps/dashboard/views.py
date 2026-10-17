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
import uuid
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404, QueryDict
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.utils.translation import gettext_lazy as _

from apps.accounts import selectors as accounts_selectors
from apps.accounts import services as accounts
from apps.accounts.countries import COUNTRIES, COUNTRY_NAMES
from apps.accounts.models import CustomerProfile, User
from apps.accounts.permissions import role_required
from apps.catalog import selectors as catalog_selectors
from apps.catalog import services as catalog
from apps.catalog.models import Category, Product
from apps.events import selectors as event_selectors
from apps.events import services as events_services
from apps.events.models import Event, Reservation
from apps.loyalty import birthday_settings, conversion, expiry, ledger, promotions
from apps.loyalty import selectors as loyalty_selectors
from apps.loyalty.models import PointsExpiryPolicy, PointsTransaction, Promotion
from apps.notifications import campaigns
from apps.notifications import selectors as notification_selectors
from apps.notifications import services as notification_services
from apps.notifications.models import Campaign, Channel, Notification
from apps.purchases import selectors as purchase_selectors
from apps.rewards import selectors as reward_selectors
from apps.rewards import services as rewards
from apps.rewards.models import Reward
from apps.web import blocks as web_blocks
from apps.web import layout as web_layout
from apps.web import services as web

from . import forms
from .forms import CustomerFilters, PeriodForm, choice, yes_no
from .sorting import Sort

PAGE_SIZE = 25
CUSTOMER_QUERY_SESSION_KEY = "dashboard_customer_query"
# Fase 19: clientes elegidos para una campaña. En la sesión, no en la URL.
SELECTION_SESSION_KEY = "dashboard_campaign_selection"
MAX_SELECTED_CUSTOMERS = 5000
SELECTED_AUDIENCE_PARAM = "seleccion"

# (clave, etiqueta, nombre de URL).
SECTIONS = (
    ("resumen", _("Resumen"), "dashboard:home"),
    ("clientes", _("Clientes"), "dashboard:customers"),
    ("empleados", _("Empleados"), "dashboard:employees"),
    ("compras", _("Compras"), "dashboard:purchases"),
    ("puntos", _("Puntos"), "dashboard:points"),
    ("recompensas", _("Recompensas"), "dashboard:rewards"),
    ("carta", _("Carta"), "dashboard:menu"),
    ("cervezas", _("Cervezas"), "dashboard:beers"),
    ("eventos", _("Eventos"), "dashboard:events"),
    ("reservas", _("Reservas"), "dashboard:reservations"),
    ("promociones", _("Promociones"), "dashboard:promotions"),
    ("comunicaciones", _("Comunicaciones"), "dashboard:communications"),
    ("contenido", _("Contenido"), "dashboard:content"),
    ("configuracion", _("Configuración"), "dashboard:settings"),
)

owner_required = role_required(User.Role.OWNER)


# --- Ordenación (Fase 18): columnas que se pueden ordenar en cada listado ----------
# Solo estas claves llegan desde la URL; los campos del ORM nunca salen de la petición.

CUSTOMER_COLUMNS = {
    "cliente": ("last_name", "first_name"),
    "email": ("email",),
    "verificacion": ("email_verified_at",),
    "alta": ("date_joined",),
    "estado": ("is_active",),
}
# Empleados y zonas se calculan en memoria: cada columna da el valor de una fila.
EMPLOYEE_COLUMNS = {
    "nombre": lambda row: (row[0].last_name.lower(), row[0].first_name.lower()),
    "email": lambda row: row[0].email.lower(),
    "rol": lambda row: row[0].role,
    "estado": lambda row: row[0].is_active,
    "compras": lambda row: row[1][0],
    "importe": lambda row: row[1][1],
    "canjes": lambda row: row[2],
}
ZONE_COLUMNS = {
    "zona": lambda row: row[0].label.lower(),
    "clientes": lambda row: row[0].count,
}
PURCHASE_COLUMNS = {
    "fecha": ("created_at",),
    "cliente": ("customer__last_name", "customer__first_name"),
    "importe": ("amount",),
    "puntos": ("points",),
    "registrada": ("registered_by__last_name", "registered_by__first_name"),
    "estado": ("status",),
}
MOVEMENT_COLUMNS = {
    "fecha": ("created_at",),
    "cliente": ("customer__last_name", "customer__first_name"),
    "tipo": ("kind",),
    "puntos": ("points",),
}
REWARD_COLUMNS = {
    "recompensa": ("name",),
    "coste": ("points_cost",),
    "estado": ("status",),
    "unidades": ("stock",),
    "utilizadas": ("used_count",),
    "pendientes": ("pending_count",),
}
REDEMPTION_COLUMNS = {
    "solicitado": ("created_at",),
    "cliente": ("customer__last_name", "customer__first_name"),
    "recompensa": ("reward__name",),
    "puntos": ("points_cost",),
    "estado": ("status",),
    "validado": ("validated_at",),
}
PROMOTION_COLUMNS = {
    "promocion": ("name",),
    "tipo": ("kind",),
    "vigencia": ("starts_at",),
    "estado": ("status",),
    "usos": ("uses",),
}
PRODUCT_COLUMNS = {
    "producto": ("name",),
    "categoria": ("category__position", "category__name"),
    "precio": ("price",),
    "publicacion": ("status",),
    "disponibilidad": ("is_available",),
}
EVENT_COLUMNS = {
    "evento": ("title",),
    "empieza": ("starts_at",),
    "estado": ("status",),
    "reservas": ("accepts_reservations",),
    "pendientes": ("pending",),
    "personas": ("confirmed_people",),
}
RESERVATION_COLUMNS = {
    "fecha": ("requested_for",),
    "cliente": ("customer__last_name", "customer__first_name"),
    "personas": ("party_size",),
    "evento": ("event__title",),
    "estado": ("status",),
    "solicitada": ("created_at",),
}
CAMPAIGN_COLUMNS = {
    "campana": ("name",),
    "canal": ("channel",),
    "estado": ("status",),
    "destinatarios": ("recipients_count",),
    "enviadas": ("sent",),
    "no_enviadas": ("skipped",),
    "fallidas": ("failed",),
    "para": ("audience",),
    "puntos": ("gift_points",),
}
NOTIFICATION_COLUMNS = {
    "fecha": ("created_at",),
    "tipo": ("kind",),
    "canal": ("channel",),
    "estado": ("status",),
    "intentos": ("attempts",),
}
# Páginas con dos listados: el segundo usa su propio prefijo en la URL.
CAMPAIGN_SORT_PREFIX = "c_"
REWARD_SORT_PREFIX = "r_"


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
            "reservations": event_selectors.reservation_stats(actor=actor, **span),
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
    filters, period_form, period, queryset = _filtered_customers(request, request.GET)
    sort = Sort(request.GET, CUSTOMER_COLUMNS)
    page = _page(request, sort.apply(queryset))
    return _render(
        request,
        "customers.html",
        "clientes",
        {
            "sort": sort,
            "search_form": forms.CustomerSearchForm(initial={"q": query}),
            "query": query,
            "filters": filters,
            "period_form": period_form,
            "period": period,
            "page": page,
            "yes_no": forms.YES_NO,
            "spent_choices": forms.SPENT_CHOICES,
            "countries": COUNTRIES,
            "filters_query": request.GET.urlencode(),
            "selected_count": len(request.session.get(SELECTION_SESSION_KEY, [])),
        },
    )


def _filtered_customers(request, data):
    """Clientes según los filtros de `data` y la búsqueda guardada en la sesión."""
    filters = CustomerFilters.from_query(data)
    period_form = PeriodForm(data or None, default="todo")
    period = period_form.period()
    queryset = accounts_selectors.search_customers(
        actor=request.user,
        query=request.session.get(CUSTOMER_QUERY_SESSION_KEY, ""),
        verified=yes_no(filters.verified),
        active=yes_no(filters.active),
        promo_email=yes_no(filters.promo),
        start=period.start,
        end=period.end,
        country=filters.country,
        province=filters.province,
        city=filters.city,
        postal_code=filters.postal_code,
        spent=filters.spent_value,
    )
    return filters, period_form, period, queryset


def _valid_uuids(values):
    valid = []
    for value in values:
        try:
            valid.append(uuid.UUID(str(value)))
        except ValueError:
            continue
    return valid


@never_cache
@require_POST
@owner_required
def customer_selection(request):
    """
    Guarda en la sesión los clientes elegidos para una campaña (Fase 19) y
    lleva al formulario de campaña. Los `public_id` se recalculan aquí: solo
    cuentan clientes; cualquier otro identificador se ignora.
    """
    back = reverse("dashboard:customers")
    filters_query = request.POST.get("filtros", "")
    if filters_query:
        back = f"{back}?{QueryDict(filters_query).urlencode()}"
    if request.POST.get("todos") == "1":
        queryset = _filtered_customers(request, QueryDict(filters_query))[-1]
        ids = list(queryset.values_list("public_id", flat=True)[: MAX_SELECTED_CUSTOMERS + 1])
    else:
        candidates = _valid_uuids(request.POST.getlist("cliente")[: MAX_SELECTED_CUSTOMERS + 1])
        ids = list(campaigns.selectable_customers(candidates).values_list("public_id", flat=True))
    if not ids:
        messages.error(request, _("Marca al menos un cliente en la columna «Envío»."))
        return redirect(back)
    if len(ids) > MAX_SELECTED_CUSTOMERS:
        messages.error(
            request,
            _("Puedes seleccionar como máximo %(max)s clientes. Afina los filtros.") % {"max": MAX_SELECTED_CUSTOMERS},
        )
        return redirect(back)
    request.session[SELECTION_SESSION_KEY] = [str(value) for value in ids]
    return redirect(f"{reverse('dashboard:campaign_create')}?destinatarios={SELECTED_AUDIENCE_PARAM}")


@never_cache
@require_POST
@owner_required
def customer_selection_clear(request):
    request.session.pop(SELECTION_SESSION_KEY, None)
    messages.info(request, _("Selección de clientes descartada."))
    return redirect("dashboard:customers")


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
                messages.success(request, _("Ajuste registrado: %(points)s puntos.") % {"points": format(result.movement.points, "+d")})
            else:
                messages.info(request, _("Este ajuste ya estaba registrado; no se ha duplicado."))
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
            messages.success(request, _("Movimiento compensado: %(points)s puntos.") % {"points": format(result.movement.points, "+d")})
        else:
            messages.info(request, _("Ese movimiento ya estaba compensado."))
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
    sort = Sort(request.GET, ZONE_COLUMNS)
    rows = sort.apply_list(
        [(row, urlencode(row.filters), round(row.count * 100 / top) if top else 0) for row in distribution.rows]
    )
    return _render(
        request,
        "customer_zones.html",
        "clientes",
        {
            "sort": sort,
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
    sort = Sort(request.GET, EMPLOYEE_COLUMNS)
    rows = sort.apply_list(
        [
            (member, purchases_by.get(member.pk, (0, None)), validations_by.get(member.pk, 0))
            for member in accounts_selectors.staff_members(actor=actor)
        ]
    )
    return _render(
        request,
        "employees.html",
        "empleados",
        {
            "sort": sort,
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
            messages.success(request, _("Empleado dado de alta. Ya puede entrar con su email y la contraseña inicial."))
            return redirect("dashboard:employees")
    return _render_employees(request, create_form=form, status=400)


@never_cache
@require_POST
@owner_required
def employee_status(request, public_id):
    member = _staff_or_404(request, public_id)
    if member.pk == request.user.pk:
        messages.error(request, _("No puedes desactivar tu propia cuenta desde el dashboard."))
        return redirect("dashboard:employees")
    action = request.POST.get("accion")
    if action not in ("activar", "desactivar"):
        messages.error(request, _("Acción no válida."))
        return redirect("dashboard:employees")
    try:
        accounts.set_user_active(actor=request.user, user=member, is_active=action == "activar")
    except ValidationError as exc:
        _error(request, exc)
    else:
        messages.success(request, _("Cuenta activada.") if action == "activar" else _("Cuenta desactivada: ya no puede entrar."))
    return redirect("dashboard:employees")


@never_cache
@require_POST
@owner_required
def employee_role(request, public_id):
    member = _staff_or_404(request, public_id)
    if member.pk == request.user.pk:
        messages.error(request, _("No puedes cambiar tu propio rol desde el dashboard."))
        return redirect("dashboard:employees")
    form = forms.RoleChangeForm(request.POST)
    if not form.is_valid():
        messages.error(request, _("Elige el nuevo rol y marca la casilla de confirmación."))
        return redirect("dashboard:employees")
    try:
        accounts.change_role(actor=request.user, user=member, new_role=form.cleaned_data["role"])
    except ValidationError as exc:
        _error(request, exc)
    else:
        messages.success(request, _("Rol actualizado."))
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
    sort = Sort(request.GET, PURCHASE_COLUMNS)
    return _render(
        request,
        "purchases.html",
        "compras",
        {
            "sort": sort,
            "period_form": period_form,
            "period": period,
            "stats": purchase_selectors.registered_purchases_stats(actor=actor, start=period.start, end=period.end),
            "page": _page(request, sort.apply(queryset)),
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
    sort = Sort(request.GET, MOVEMENT_COLUMNS)
    return _render(
        request,
        "points.html",
        "puntos",
        {
            "sort": sort,
            "period_form": period_form,
            "period": period,
            "stats": loyalty_selectors.points_stats(actor=actor, start=period.start, end=period.end),
            "rate": conversion.current_rate(),
            "page": _page(request, sort.apply(queryset)),
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
    sort = Sort(request.GET, REDEMPTION_COLUMNS)
    reward_sort = Sort(request.GET, REWARD_COLUMNS, prefix=REWARD_SORT_PREFIX)
    return _render(
        request,
        "rewards.html",
        "recompensas",
        {
            "sort": sort,
            "reward_sort": reward_sort,
            "period_form": period_form,
            "period": period,
            "rewards": reward_sort.apply(reward_selectors.rewards_overview(actor=actor)),
            "stats": reward_selectors.redemption_stats(actor=actor, start=period.start, end=period.end),
            "page": _page(request, sort.apply(queryset)),
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
        messages.success(request, _("Estado de «%(name)s» actualizado.") % {"name": reward.name})
    return redirect("dashboard:rewards")


@never_cache
@require_GET
@owner_required
def promotions_view(request):
    sort = Sort(request.GET, PROMOTION_COLUMNS)
    return _render(
        request,
        "promotions.html",
        "promociones",
        {
            "sort": sort,
            "promotions": sort.apply(loyalty_selectors.promotions_overview(actor=request.user)),
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
        messages.success(request, _("Estado de «%(name)s» actualizado.") % {"name": promotion.name})
    return redirect("dashboard:promotions")


# --- Carta y cervezas -------------------------------------------------------------


def _products(request, *, beers, section):
    status = choice(request.GET, "estado", forms.PRODUCT_STATUS_CHOICES)
    categories = list(Category.objects.order_by("position", "name"))
    category = next((c for c in categories if c.slug == request.GET.get("categoria")), None)
    queryset = catalog_selectors.products_for_management(
        actor=request.user, beers=beers, status=status, category=category
    )
    sort = Sort(request.GET, PRODUCT_COLUMNS)
    return _render(
        request,
        "products.html",
        section,
        {
            "sort": sort,
            "page": _page(request, sort.apply(queryset)),
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
        messages.success(request, _("Estado de «%(name)s» actualizado.") % {"name": product.name})
    return _back_to_products(request, product)


@never_cache
@require_POST
@owner_required
def product_availability(request, public_id):
    product = _product_or_404(public_id)
    available = request.POST.get("disponible")
    if available not in ("si", "no"):
        messages.error(request, _("Acción no válida."))
    else:
        catalog.set_product_availability(actor=request.user, product=product, is_available=available == "si")
        text = _("«%(name)s» marcado como disponible.") if available == "si" else _("«%(name)s» marcado como agotado.")
        messages.success(request, text % {"name": product.name})
    return _back_to_products(request, product)


# --- Eventos (Fase 10) -------------------------------------------------------------


def _event_or_404(request, public_id):
    event = event_selectors.event_for_owner(actor=request.user, public_id=public_id)
    if event is None:
        raise Http404
    return event


@never_cache
@require_GET
@owner_required
def events(request):
    status = choice(request.GET, "estado", forms.EVENT_STATUS_CHOICES)
    queryset = event_selectors.events_for_management(actor=request.user, status=status)
    sort = Sort(request.GET, EVENT_COLUMNS)
    return _render(
        request,
        "events.html",
        "eventos",
        {
            "sort": sort,
            "page": _page(request, sort.apply(queryset)),
            "status": status,
            "status_choices": forms.EVENT_STATUS_CHOICES,
        },
    )


def _event_form_view(request, event):
    form = forms.EventForm(request.POST or None, request.FILES or None, instance=event)
    status = 200
    if request.method == "POST":
        if form.is_valid():
            try:
                saved = events_services.save_event(
                    actor=request.user, event=event if event.pk else Event(), data=form.service_data()
                )
            except ValidationError as exc:
                _apply_errors(form, exc)
            else:
                messages.success(request, _("Evento «%(title)s» guardado.") % {"title": saved.title})
                return redirect("dashboard:events")
        status = 400
    return _render(request, "event_form.html", "eventos", {"form": form, "event": event}, status=status)


@never_cache
@require_http_methods(["GET", "POST"])
@owner_required
def event_create(request):
    return _event_form_view(request, Event())


@never_cache
@require_http_methods(["GET", "POST"])
@owner_required
def event_edit(request, public_id):
    return _event_form_view(request, _event_or_404(request, public_id))


@never_cache
@require_POST
@owner_required
def event_status(request, public_id):
    event = _event_or_404(request, public_id)
    try:
        events_services.set_event_status(actor=request.user, event=event, status=request.POST.get("estado"))
    except ValidationError as exc:
        _error(request, exc)
    else:
        messages.success(request, _("Estado de «%(title)s» actualizado.") % {"title": event.title})
    return redirect("dashboard:events")


# --- Reservas (Fase 10) ------------------------------------------------------------


@never_cache
@require_GET
@owner_required
def reservations(request):
    status = choice(request.GET, "estado", forms.RESERVATION_STATUS_CHOICES)
    when = choice(request.GET, "cuando", forms.RESERVATION_WHEN_CHOICES, default="proximas")
    start, end, newest_first = forms.reservation_period(when)
    queryset = event_selectors.reservations_for_management(actor=request.user, status=status, start=start, end=end)
    if newest_first:
        queryset = queryset.order_by("-requested_for", "-id")
    sort = Sort(request.GET, RESERVATION_COLUMNS)
    return _render(
        request,
        "reservations.html",
        "reservas",
        {
            "sort": sort,
            "page": _page(request, sort.apply(queryset)),
            "status": status,
            "when": when,
            "status_choices": forms.RESERVATION_STATUS_CHOICES,
            "when_choices": forms.RESERVATION_WHEN_CHOICES,
        },
    )


def _reservation_or_404(request, public_id):
    reservation = event_selectors.reservation_for_owner(actor=request.user, public_id=public_id)
    if reservation is None:
        raise Http404
    return reservation


@never_cache
@require_GET
@owner_required
def reservation_detail(request, public_id):
    reservation = _reservation_or_404(request, public_id)
    # El detalle muestra el contacto del cliente: la consulta queda auditada.
    events_services.record_reservation_data_access(actor=request.user, reservation=reservation)
    try:
        phone = reservation.customer.customer_profile.phone_number
    except CustomerProfile.DoesNotExist:
        phone = ""
    allowed = Reservation.TRANSITIONS.get(reservation.status, set())
    return _render(
        request,
        "reservation_detail.html",
        "reservas",
        {
            "reservation": reservation,
            "phone": phone,
            "seats_left": event_selectors.seats_left(reservation.event) if reservation.event_id else None,
            "can_confirm": Reservation.Status.CONFIRMED in allowed,
            "can_reject": Reservation.Status.REJECTED in allowed,
            "can_cancel": Reservation.Status.CANCELLED in allowed,
            "can_complete": Reservation.Status.COMPLETED in allowed,
            "form": forms.ReservationActionForm(),
        },
    )


_RESERVATION_ACTIONS = {
    "confirmar": (events_services.confirm_reservation, _("Reserva confirmada. Se ha avisado al cliente.")),
    "rechazar": (events_services.reject_reservation, _("Reserva rechazada. Se ha avisado al cliente.")),
    "cancelar": (events_services.cancel_reservation, _("Reserva cancelada. Se ha avisado al cliente.")),
}


@never_cache
@require_POST
@owner_required
def reservation_action(request, public_id):
    reservation = _reservation_or_404(request, public_id)
    form = forms.ReservationActionForm(request.POST)
    if not form.is_valid():
        _form_errors(request, form)
        return redirect("dashboard:reservation_detail", public_id=public_id)
    action, message = form.cleaned_data["accion"], form.cleaned_data["mensaje"]
    try:
        if action == "completar":
            result = events_services.complete_reservation(actor=request.user, reservation=reservation)
            success = _("Reserva marcada como completada.")
        else:
            service, success = _RESERVATION_ACTIONS[action]
            result = service(actor=request.user, reservation=reservation, message=message)
    except ValidationError as exc:
        _error(request, exc)
    else:
        if result.created:
            messages.success(request, success)
        else:
            messages.info(request, _("La reserva ya estaba en ese estado."))
    return redirect("dashboard:reservation_detail", public_id=public_id)


# --- Comunicaciones (Fase 10) ------------------------------------------------------


@never_cache
@require_GET
@owner_required
def communications(request):
    actor = request.user
    status = choice(request.GET, "estado", forms.NOTIFICATION_STATUS_CHOICES)
    kind = choice(request.GET, "tipo", forms.NOTIFICATION_KIND_CHOICES)
    counts = notification_selectors.notification_counts(actor=actor)
    sort = Sort(request.GET, NOTIFICATION_COLUMNS)
    campaign_sort = Sort(request.GET, CAMPAIGN_COLUMNS, prefix=CAMPAIGN_SORT_PREFIX)
    return _render(
        request,
        "communications.html",
        "comunicaciones",
        {
            "sort": sort,
            "campaign_sort": campaign_sort,
            "channels": notification_selectors.channel_status(actor=actor),
            "campaigns": campaign_sort.apply(notification_selectors.campaigns_for_owner(actor=actor))[:20],
            "audience": {
                "email": notification_selectors.potential_recipients(actor=actor, channel=Channel.EMAIL),
                "sms": notification_selectors.potential_recipients(actor=actor, channel=Channel.SMS),
            },
            "status_counts": [
                (label, counts.get(value, 0)) for value, label in Notification.Status.choices
            ],
            "page": _page(request, sort.apply(notification_selectors.notification_log(actor=actor, status=status, kind=kind))),
            "status": status,
            "kind": kind,
            "status_choices": forms.NOTIFICATION_STATUS_CHOICES,
            "kind_choices": forms.NOTIFICATION_KIND_CHOICES,
        },
    )


def _campaign_or_404(request, public_id):
    campaign = notification_selectors.campaign_for_owner(actor=request.user, public_id=public_id)
    if campaign is None:
        raise Http404
    return campaign


def _campaign_form_view(request, campaign):
    """
    Formulario único de campaña (Fase 19): todos los clientes con
    consentimiento o los seleccionados en Clientes (lista en la sesión).
    «Crear y enviar» guarda y programa; «Guardar borrador» solo guarda.
    """
    selection = request.session.get(SELECTION_SESSION_KEY, [])
    wants_selection = request.GET.get("destinatarios") == SELECTED_AUDIENCE_PARAM and bool(selection)
    if campaign.pk:
        initial = {name: getattr(campaign, name) for name in campaigns.EDITABLE_FIELDS}
    else:
        initial = {"audience": Campaign.Audience.SELECTED if wants_selection else Campaign.Audience.ALL}
    form = forms.CampaignForm(request.POST or None, request.FILES or None, initial=initial)
    status = 200
    if request.method == "POST":
        if form.is_valid():
            data = form.cleaned_data
            # La selección de la sesión solo se usa si se viene de Clientes; al editar
            # sin venir de allí se conservan los elegidos al crear la campaña.
            recipients = selection if data["audience"] == Campaign.Audience.SELECTED and wants_selection else None
            send_now = "enviar" in request.POST
            service = campaigns.create_and_queue if send_now else campaigns.save_campaign
            try:
                service(
                    actor=request.user,
                    campaign=campaign,
                    data=data,
                    recipients=recipients,
                    image=data.get("image") or None,
                    clear_image=data.get("clear_image", False),
                )
            except ValidationError as exc:
                _apply_errors(form, exc)
            else:
                if recipients is not None:
                    request.session.pop(SELECTION_SESSION_KEY, None)
                if send_now:
                    messages.success(
                        request,
                        _("Campaña creada y programada. Se repartirá en la próxima ejecución de la tarea de envíos, solo a quien lo ha autorizado."),
                    )
                else:
                    messages.success(request, _("Campaña guardada como borrador. Revísala y prográmala cuando quieras."))
                return redirect("dashboard:communications")
        status = 400
    selected_ids = None
    if wants_selection:
        selected_ids = list(campaigns.selectable_customers(selection).values_list("pk", flat=True))
    elif campaign.pk and campaign.audience == Campaign.Audience.SELECTED:
        selected_ids = list(campaign.selected_recipients.values_list("customer_id", flat=True))
    context = {
        "form": form,
        "campaign": campaign,
        "sms_available": notification_services.sms_available(),
        "selected_count": len(selected_ids) if selected_ids is not None else 0,
        "selected_reach": notification_selectors.selected_reach(actor=request.user, customer_ids=selected_ids)
        if selected_ids
        else None,
        "all_reach": {
            "email": notification_selectors.potential_recipients(actor=request.user, channel=Channel.EMAIL),
            "sms": notification_selectors.potential_recipients(actor=request.user, channel=Channel.SMS),
        },
    }
    return _render(request, "campaign_form.html", "comunicaciones", context, status=status)


@never_cache
@require_http_methods(["GET", "POST"])
@owner_required
def campaign_create(request):
    return _campaign_form_view(request, Campaign())


@never_cache
@require_http_methods(["GET", "POST"])
@owner_required
def campaign_edit(request, public_id):
    campaign = _campaign_or_404(request, public_id)
    if campaign.status != Campaign.Status.DRAFT:
        messages.error(request, _("Solo se pueden modificar las campañas en borrador."))
        return redirect("dashboard:communications")
    return _campaign_form_view(request, campaign)


@never_cache
@require_POST
@owner_required
def campaign_queue(request, public_id):
    campaign = _campaign_or_404(request, public_id)
    try:
        campaigns.queue_campaign(actor=request.user, campaign=campaign)
    except ValidationError as exc:
        _error(request, exc)
    else:
        messages.success(
            request,
            _("Campaña programada. Se repartirá en la próxima ejecución de la tarea de envíos, solo a quien lo ha autorizado."),
        )
    return redirect("dashboard:communications")


@never_cache
@require_POST
@owner_required
def campaign_cancel(request, public_id):
    campaign = _campaign_or_404(request, public_id)
    try:
        campaigns.cancel_campaign(actor=request.user, campaign=campaign)
    except ValidationError as exc:
        _error(request, exc)
    else:
        messages.success(request, _("Campaña cancelada."))
    return redirect("dashboard:communications")


# --- Contenido y configuración ----------------------------------------------------


@never_cache
@require_http_methods(["GET", "POST"])
@owner_required
def content(request):
    if request.method == "POST":
        form = forms.BusinessInfoForm(request.POST)
        if form.is_valid():
            try:
                _unused, changed = web.update_business_info(actor=request.user, data=form.cleaned_data)
            except ValidationError as exc:
                _apply_errors(form, exc)
            else:
                messages.success(request, _("Contenido guardado.") if changed else _("No había cambios que guardar."))
                return redirect("dashboard:content")
        status = 400
    else:
        form = _content_form()
        status = 200
    return _render(request, "content.html", "contenido", {"form": form, "layouts": _layouts()}, status=status)


def _content_form():
    info = web.editable_business_info()
    return forms.BusinessInfoForm(initial={name: getattr(info, name) for name in web.EDITABLE_FIELDS})


def _layouts():
    """Bloques de «Orden de las secciones» (Fase 20): (página, título, filas, ¿admite artículos?)."""
    return [
        (page, title, web_layout.rows(web.page_layout(page), web.sections_for(page)), page in web_layout.ARTICLE_PAGES)
        for page, (_field, _sections, title) in web_layout.PAGES.items()
    ]


# --- Contenido de las secciones y artículos (Fase 21) ------------------------------------


def _image_changes(request, block):
    """Imágenes a quitar y descripciones nuevas, solo de este bloque (el servicio lo vuelve a comprobar)."""
    remove = request.POST.getlist("quitar")
    alts = {}
    if block is not None:
        for image in block.images.all():
            name = f"alt-{image.pk}"
            if name in request.POST:
                alts[str(image.pk)] = request.POST[name]
    return remove, alts


def _block_form_view(request, *, page, key, block, article, bound=True, status=200):
    """`bound=False`: formulario vacío aunque la petición sea POST (vuelta desde «Copiar aquí» con error)."""
    allows_images = web_blocks.images_allowed(page, article)
    defaults = web_blocks.defaults(page, key) if key else ("", "", None)
    initial = {"eyebrow": block.eyebrow, "title": block.title, "body": block.body} if block else {}
    form = forms.PageBlockForm(
        (request.POST or None) if bound else None,
        (request.FILES or None) if bound else None,
        initial=initial,
        defaults=defaults,
        images=allows_images,
        article=article,
    )
    if bound and request.method == "POST":
        if form.is_valid():
            data = form.cleaned_data
            remove, alts = _image_changes(request, block)
            new_images = data.get("images") or []
            try:
                if block is None and article:
                    web_blocks.create_article(actor=request.user, page=page, data=data, new_images=new_images, alts=alts)
                else:
                    web_blocks.save_block(
                        actor=request.user, page=page, key=key, data=data, new_images=new_images, remove=remove, alts=alts
                    )
            except ValidationError as exc:
                _apply_errors(form, exc)
            else:
                messages.success(request, _("Contenido de la sección guardado."))
                return redirect(f"{reverse('dashboard:content')}#orden-{page}")
        status = 400
    context = {
        "form": form,
        "page": page,
        "page_label": web_layout.PAGES[page][2],
        "key": key,
        "page_block": block,  # `block` está reservado dentro de {% block %}
        "article": article,
        "section_label": dict(web.sections_for(page)).get(key, "") if key else "",
        "uses_about_text": (page, key) in web_blocks.ABOUT_TEXT_SECTIONS,
        "max_images": web_blocks.PageBlock.MAX_IMAGES,
        # «Nuevo artículo»: artículos de las otras páginas que se pueden copiar aquí (Fase 23).
        # Cada fila lleva su clave de idempotencia (un doble clic no crea dos copias).
        "copy_sources": (
            [(source, uuid.uuid4()) for source in web_blocks.copyable_articles(page)] if article and block is None else None
        ),
    }
    return _render(request, "section_form.html", "contenido", context, status=status)


@never_cache
@require_http_methods(["GET", "POST"])
@owner_required
def section_edit(request, page, key):
    if not web_blocks.is_editable(page, key):
        raise Http404
    block = web_blocks.get_block(page, key)
    return _block_form_view(request, page=page, key=key, block=block, article=bool(block and block.is_article))


@never_cache
@require_http_methods(["GET", "POST"])
@owner_required
def article_create(request, page):
    if page not in web_layout.ARTICLE_PAGES:
        raise Http404
    return _block_form_view(request, page=page, key="", block=None, article=True)


@never_cache
@require_POST
@owner_required
def article_copy(request, page):
    """Copia a `page` un artículo de otra página (Fase 23) y abre la copia para editarla."""
    if page not in web_layout.ARTICLE_PAGES:
        raise Http404
    try:
        source = uuid.UUID(request.POST.get("origen", ""))
        key = uuid.UUID(request.POST.get("idempotency_key", ""))
        block = web_blocks.copy_article(actor=request.user, page=page, source_public_id=source, idempotency_key=key)
    except (ValueError, ValidationError):
        messages.error(request, _("No se ha podido copiar el artículo: elige uno de la lista."))
        return _block_form_view(request, page=page, key="", block=None, article=True, bound=False, status=400)
    messages.success(request, _("Artículo copiado. Revisa los textos y las imágenes y guarda si cambias algo."))
    return redirect("dashboard:section_edit", page, block.key)


@never_cache
@require_http_methods(["GET", "POST"])
@owner_required
def article_delete(request, page, key):
    if page not in web_layout.ARTICLE_PAGES:
        raise Http404
    block = web_blocks.get_block(page, key)
    if block is None or not block.is_article:
        raise Http404
    if request.method == "POST":
        web_blocks.delete_article(actor=request.user, page=page, key=key)
        messages.success(request, _("Artículo eliminado."))
        return redirect(f"{reverse('dashboard:content')}#orden-{page}")
    return _render(request, "article_confirm_delete.html", "contenido", {"page_block": block})


@never_cache
@require_POST
@owner_required
def content_layout(request):
    """Guarda el orden y la visibilidad de las secciones de una página (Fase 20)."""
    page = request.POST.get("pagina", "")
    move = None
    if request.POST.get("mover"):
        key, _sep, direction = request.POST["mover"].partition(":")
        move = (key, direction)
    try:
        changed = web.update_page_layout(
            actor=request.user, page=page, visible=request.POST.getlist("mostrar"), move=move
        )
    except ValidationError as exc:
        _error(request, exc)
        return _render(request, "content.html", "contenido", {"form": _content_form(), "layouts": _layouts()}, status=400)
    messages.success(request, _("Orden de las secciones guardado.") if changed else _("No había cambios que guardar."))
    return redirect(f"{reverse('dashboard:content')}#orden-{page}")


EXPIRY_PREFIX = "caducidad"
BIRTHDAY_PREFIX = "cumple"
RESERVATIONS_PREFIX = "reservas"


def _expiry_initial():
    policy = expiry.current_policy()
    if policy is None:
        return {"enabled": False, "warn_days": PointsExpiryPolicy.DEFAULT_WARN_DAYS}
    return {"enabled": policy.is_active, "months": policy.months, "warn_days": policy.warn_days}


def _birthday_initial():
    state = birthday_settings.current_state()
    return {
        "active": state.active,
        "points": state.points,
        "email_subject": state.message.email_subject,
        "email_body": state.message.email_body,
        "sms_body": state.message.sms_body,
    }


def _settings_page(request, *, form=None, expiry_form=None, birthday_form=None, reservations_form=None, status=200):
    """Configuración: conversión, caducidad, cumpleaños y reservas online (cada uno con su formulario)."""
    reservations_enabled = web.online_reservations_enabled()
    return _render(
        request,
        "settings.html",
        "configuracion",
        {
            "form": form or forms.LoyaltyRuleForm(),
            "rate": conversion.current_rate(),
            "rules": conversion.rule_history(),
            "expiry_form": expiry_form or forms.PointsExpiryForm(prefix=EXPIRY_PREFIX, initial=_expiry_initial()),
            "expiry_policy": expiry.active_policy(),
            "expiry_history": expiry.policy_history(),
            "birthday_form": birthday_form
            or forms.BirthdayGiftForm(prefix=BIRTHDAY_PREFIX, initial=_birthday_initial()),
            "birthday_placeholder": birthday_settings.PLACEHOLDER,
            "reservations_form": reservations_form
            or forms.OnlineReservationsForm(prefix=RESERVATIONS_PREFIX, initial={"enabled": reservations_enabled}),
            "reservations_enabled": reservations_enabled,
            "content_url": reverse("dashboard:content"),
            "read_only_settings": (
                (_("Importe máximo por compra"), f"{settings.PURCHASES_MAX_AMOUNT} €"),
                (_("Días para recoger una recompensa canjeada"), settings.REWARDS_CODE_VALIDITY_DAYS),
                (_("Ajuste manual máximo de puntos"), settings.LOYALTY_MAX_ADJUSTMENT_POINTS),
                (_("Edad mínima para registrarse"), settings.ACCOUNTS_MIN_CUSTOMER_AGE),
            ),
            "admin_url": reverse("admin:index"),
        },
        status=status,
    )


@never_cache
@require_http_methods(["GET", "POST"])
@owner_required
def settings_view(request):
    if request.method != "POST":
        return _settings_page(request)
    form = forms.LoyaltyRuleForm(request.POST)
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
            messages.success(request, _("Nueva conversión en vigor para las próximas compras."))
            return redirect("dashboard:settings")
    return _settings_page(request, form=form, status=400)


@never_cache
@require_POST
@owner_required
def settings_expiry(request):
    form = forms.PointsExpiryForm(request.POST, prefix=EXPIRY_PREFIX)
    if form.is_valid():
        data = form.cleaned_data
        try:
            _unused, created = expiry.set_policy(
                actor=request.user,
                months=data["months"] if data["enabled"] else None,
                warn_days=data["warn_days"],
                note=data["note"],
            )
        except ValidationError as exc:
            _apply_errors(form, exc)
        else:
            if not created:
                messages.info(request, _("No había cambios que guardar."))
            elif data["enabled"]:
                messages.success(request, _("Caducidad de los puntos actualizada."))
            else:
                messages.success(request, _("Los puntos ya no caducan."))
            return redirect("dashboard:settings")
    return _settings_page(request, expiry_form=form, status=400)


@never_cache
@require_POST
@owner_required
def settings_birthday(request):
    form = forms.BirthdayGiftForm(request.POST, prefix=BIRTHDAY_PREFIX)
    if form.is_valid():
        try:
            changed = birthday_settings.update_birthday_gift(actor=request.user, **form.cleaned_data)
        except ValidationError as exc:
            _apply_errors(form, exc)
        else:
            messages.success(request, _("Regalo de cumpleaños guardado.") if changed else _("No había cambios que guardar."))
            return redirect("dashboard:settings")
    return _settings_page(request, birthday_form=form, status=400)


@never_cache
@require_POST
@owner_required
def settings_reservations(request):
    form = forms.OnlineReservationsForm(request.POST, prefix=RESERVATIONS_PREFIX)
    if form.is_valid():
        enabled = form.cleaned_data["enabled"]
        if not web.set_online_reservations(actor=request.user, enabled=enabled):
            messages.info(request, _("No había cambios que guardar."))
        elif enabled:
            messages.success(request, _("Reservas online activadas."))
        else:
            messages.success(request, _("Reservas online desactivadas: los clientes verán que deben reservar por teléfono."))
        return redirect("dashboard:settings")
    return _settings_page(request, reservations_form=form, status=400)
