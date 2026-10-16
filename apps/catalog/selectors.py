"""
Consultas de lectura de la carta pública.

Concentran las reglas de visibilidad para que la web y la futura API muestren
exactamente lo mismo:

- Un producto es público si está **publicado** y su categoría también.
  Borradores y archivados nunca salen.
- Dentro de cada categoría, los agotados van al final y se marcan como tales
  (`is_available=False`); nunca se presentan como disponibles.
- La selección del inicio solo incluye cervezas destacadas, públicas y
  disponibles.
- Las categorías sin productos públicos no se muestran.
"""
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.utils.translation import gettext as _

from apps.accounts.permissions import is_owner

from .models import Category, Product, TapMenu

FEATURED_BEERS_LIMIT = 6


def public_products():
    return Product.objects.filter(
        status=Product.Status.PUBLISHED, category__is_published=True
    ).select_related("category", "style")


def public_menu():
    """Categorías publicadas con sus productos públicos en `public_products`."""
    products = public_products().order_by("-is_available", "position", "name")
    categories = (
        Category.objects.filter(is_published=True)
        .prefetch_related(Prefetch("products", queryset=products, to_attr="public_products"))
        .order_by("position", "name")
    )
    return [category for category in categories if category.public_products]


def featured_beers(limit=FEATURED_BEERS_LIMIT):
    return list(
        public_products()
        .filter(kind__in=Product.BEER_KINDS, is_featured=True, is_available=True)
        .order_by("category__position", "position", "name")[:limit]
    )


def current_tap_menu():
    """Carta de grifos publicada más reciente, o `None`."""
    return TapMenu.objects.filter(is_published=True).order_by("-updated_at", "-id").first()


def products_for_management(*, actor, beers=None, status=None, category=None):
    """
    Todos los productos, también borradores y archivados (solo propietario,
    dashboard de la Fase 9). `beers=True` solo cervezas; `False`, el resto.
    """
    if not is_owner(actor):
        raise PermissionDenied(_("Solo el propietario puede gestionar la carta."))
    queryset = Product.objects.select_related("category", "style")
    if beers is True:
        queryset = queryset.filter(kind__in=Product.BEER_KINDS)
    elif beers is False:
        queryset = queryset.exclude(kind__in=Product.BEER_KINDS)
    if status:
        queryset = queryset.filter(status=status)
    if category is not None:
        queryset = queryset.filter(category=category)
    return queryset.order_by("category__position", "category__name", "position", "name")
