"""
Consultas de clientes para el propietario (Fase 9). Solo lectura.

Todas exigen un propietario (`PermissionDenied` en otro caso): los empleados no
acceden a la dirección postal ni a la fecha de nacimiento de los clientes.

- `search_customers`: listado con los campos mínimos (sin dirección, teléfono
  ni fecha de nacimiento) y filtros.
- `customer_for_owner`: ficha completa de un cliente por su `public_id`.
- `customer_counts`: recuentos reales de clientes.
- `geographic_distribution`: clientes agrupados por país, provincia, localidad
  o código postal. Procede **solo de las direcciones postales declaradas por
  los propios clientes** en su perfil: no se usa geolocalización por IP ni se
  infiere ningún domicilio, y nunca se devuelven direcciones completas.
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max, Q
from django.db.models.functions import Upper

from .countries import COUNTRY_NAMES
from .models import CustomerProfile, User
from .permissions import is_owner

GEO_SOURCE_NOTE = (
    "Datos procedentes de las direcciones postales declaradas por los propios clientes en su perfil. "
    "No se usa geolocalización por IP ni se deducen domicilios."
)

# Nivel → campos que identifican la zona. El país acompaña siempre para no
# mezclar provincias, localidades o códigos postales homónimos de otro país.
GEO_LEVELS = {
    "pais": ("country",),
    "provincia": ("country", "province"),
    "localidad": ("country", "province", "city"),
    "cp": ("country", "postal_code"),
}
GEO_LEVEL_LABELS = {"pais": "País", "provincia": "Provincia", "localidad": "Localidad", "cp": "Código postal"}

# Campos del listado: lo necesario para identificar y contactar, nada más.
LIST_FIELDS = ("public_id", "first_name", "last_name", "email", "email_verified_at", "date_joined", "is_active")


def _require_owner(actor):
    if not is_owner(actor):
        raise PermissionDenied("Solo el propietario puede consultar los datos de los clientes.")


def customers():
    return User.objects.filter(role=User.Role.CUSTOMER)


def search_customers(
    *,
    actor,
    query="",
    verified=None,
    active=None,
    start=None,
    end=None,
    country="",
    province="",
    city="",
    postal_code="",
    promo_email=None,
):
    """Clientes que cumplen los filtros, del alta más reciente a la más antigua."""
    _require_owner(actor)
    queryset = customers()
    for term in (query or "").split()[:5]:
        queryset = queryset.filter(
            Q(first_name__icontains=term) | Q(last_name__icontains=term) | Q(email__icontains=term)
        )
    if verified is not None:
        queryset = queryset.filter(email_verified_at__isnull=not verified)
    if active is not None:
        queryset = queryset.filter(is_active=active)
    if start is not None:
        queryset = queryset.filter(date_joined__gte=start)
    if end is not None:
        queryset = queryset.filter(date_joined__lt=end)
    if country:
        queryset = queryset.filter(customer_profile__country=country)
    if province:
        queryset = queryset.filter(customer_profile__province__iexact=province)
    if city:
        queryset = queryset.filter(customer_profile__city__iexact=city)
    if postal_code:
        queryset = queryset.filter(customer_profile__postal_code__iexact=postal_code)
    if promo_email is not None:
        queryset = queryset.filter(customer_profile__promo_email_opt_in=promo_email)
    return queryset.only(*LIST_FIELDS).order_by("-date_joined", "-id")


def customer_for_owner(*, actor, public_id):
    """Cliente con su perfil, o `None` si no existe o no es cliente."""
    _require_owner(actor)
    return customers().select_related("customer_profile").filter(public_id=public_id).first()


def preference_history(*, actor, customer, limit=10):
    _require_owner(actor)
    return list(customer.communication_preference_changes.all()[:limit])


@dataclass(frozen=True)
class CustomerCounts:
    total: int
    active: int
    verified: int
    promo_email: int
    new_in_period: int


def customer_counts(*, actor, start=None, end=None):
    """Clientes registrados (cuentas activas) y altas del periodo `[start, end)`."""
    _require_owner(actor)
    period = Q()
    if start is not None:
        period &= Q(date_joined__gte=start)
    if end is not None:
        period &= Q(date_joined__lt=end)
    active = Q(is_active=True)
    totals = customers().aggregate(
        total=Count("id"),
        active=Count("id", filter=active),
        verified=Count("id", filter=active & Q(email_verified_at__isnull=False)),
        promo_email=Count("id", filter=active & Q(customer_profile__promo_email_opt_in=True)),
        new=Count("id", filter=active & period),
    )
    return CustomerCounts(
        total=totals["total"],
        active=totals["active"],
        verified=totals["verified"],
        promo_email=totals["promo_email"],
        new_in_period=totals["new"],
    )


@dataclass(frozen=True)
class GeoRow:
    label: str
    context: str
    count: int
    percent: Decimal
    filters: dict


@dataclass(frozen=True)
class GeoDistribution:
    level: str
    total: int
    rows: list
    others_count: int
    unknown_count: int
    note: str = GEO_SOURCE_NOTE

    @property
    def level_label(self):
        return GEO_LEVEL_LABELS[self.level]

    def percent(self, count):
        return _percent(count, self.total)


def _percent(count, total):
    if not total:
        return Decimal("0.0")
    return (Decimal(count) * 100 / total).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _country_name(code):
    return COUNTRY_NAMES.get(code, code)


def _row(level, values, count, total):
    country = values["country"]
    if level == "pais":
        label, context, filters = _country_name(country), "", {"pais": country}
    elif level == "provincia":
        label, context = values["province_label"], _country_name(country)
        filters = {"pais": country, "provincia": values["province_label"]}
    elif level == "localidad":
        label = values["city_label"]
        context = f"{values['province_label']} · {_country_name(country)}" if values["province_label"] else _country_name(country)
        filters = {"pais": country, "localidad": values["city_label"]}
    else:
        label, context = values["postal_code_label"], _country_name(country)
        filters = {"pais": country, "cp": values["postal_code_label"]}
    return GeoRow(label=label, context=context, count=count, percent=_percent(count, total), filters=filters)


def geographic_distribution(*, actor, level, start=None, end=None, customer_ids=None, country="", limit=25):
    """
    Clientes activos agrupados por `level` (ver `GEO_LEVELS`).

    `start`/`end` limitan a las altas de ese periodo. `customer_ids` (consulta
    de ids) restringe además la base, p. ej. a los clientes con compras en un
    periodo, calculados por el módulo que conoce esos datos. `country` limita
    a un país. Las zonas se agrupan sin distinguir mayúsculas. Devuelve las `limit` zonas con más clientes; el resto suma en
    `others_count` y quienes no tienen el dato en `unknown_count`. Los
    porcentajes son sobre el total de clientes de la base.
    """
    _require_owner(actor)
    if level not in GEO_LEVELS:
        raise ValueError(f"Nivel geográfico desconocido: {level}")
    base = customers().filter(is_active=True)
    if start is not None:
        base = base.filter(date_joined__gte=start)
    if end is not None:
        base = base.filter(date_joined__lt=end)
    if customer_ids is not None:
        base = base.filter(pk__in=customer_ids)
    if country:
        base = base.filter(customer_profile__country=country)
    total = base.count()

    fields = GEO_LEVELS[level]
    profiles = CustomerProfile.objects.filter(user__in=base)
    keys, labels, has_data = {"country": "country"}, {}, Q()
    for name in fields:
        has_data &= ~Q(**{name: ""})
        if name != "country":
            keys[f"{name}_key"] = Upper(name)
            labels[f"{name}_label"] = Max(name)
    grouped = (
        profiles.filter(has_data)
        .annotate(**{k: v for k, v in keys.items() if k != "country"})
        .values(*keys.keys())
        .annotate(count=Count("id"), **labels)
        .order_by("-count", *keys.keys())
    )
    grouped = list(grouped)
    known = sum(item["count"] for item in grouped)
    rows = [_row(level, item, item["count"], total) for item in grouped[:limit]]
    return GeoDistribution(
        level=level,
        total=total,
        rows=rows,
        others_count=sum(item["count"] for item in grouped[limit:]),
        unknown_count=total - known,
    )


def staff_members(*, actor):
    """Empleados y propietarios, activos primero."""
    _require_owner(actor)
    return (
        User.objects.filter(role__in=[User.Role.EMPLOYEE, User.Role.OWNER])
        .only("public_id", "first_name", "last_name", "email", "role", "is_active", "date_joined", "last_login")
        .order_by("-is_active", "role", "first_name", "last_name")
    )


def staff_member(*, actor, public_id):
    _require_owner(actor)
    return User.objects.filter(role__in=[User.Role.EMPLOYEE, User.Role.OWNER], public_id=public_id).first()
