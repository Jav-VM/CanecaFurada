"""
Qué es dato de demostración y qué no.

- Usuarios: email en `data.DEMO_EMAIL_DOMAIN` (todo lo que cuelga de ellos
  —perfil, QR, compras, puntos, canjes, reservas, notificaciones— también).
- Productos, eventos, recompensas, promociones y campañas: `public_id`
  determinista (`data.demo_uuid`). Categorías: slug `demo-`. Reglas de
  conversión y cartas de grifos: prefijo `[DEMO]`. Estilos: lista de `data`.
"""
from django.db.models import Q

from apps.accounts.models import User
from apps.catalog.models import BeerStyle, Category, Product, TapMenu
from apps.events.models import Event, Reservation
from apps.loyalty.models import LoyaltyRule, PointsTransaction, Promotion
from apps.notifications.models import Campaign, Notification
from apps.purchases.models import Purchase
from apps.rewards.models import Redemption, Reward

from . import data


def demo_users():
    return User.objects.filter(email__iendswith=f"@{data.DEMO_EMAIL_DOMAIN}")


def demo_categories():
    return Category.objects.filter(slug__startswith=data.CATEGORY_SLUG_PREFIX)


def demo_products():
    return Product.objects.filter(Q(public_id__in=data.product_ids()) | Q(category__in=demo_categories()))


def demo_events():
    return Event.objects.filter(public_id__in=data.event_ids())


def demo_rewards():
    return Reward.objects.filter(public_id__in=data.reward_ids())


def demo_promotions():
    return Promotion.objects.filter(public_id__in=data.promotion_ids())


def demo_campaigns():
    return Campaign.objects.filter(public_id__in=data.campaign_ids())


def demo_rules():
    return LoyaltyRule.objects.filter(note__startswith=data.TEXT_PREFIX)


def demo_tap_menus():
    return TapMenu.objects.filter(title__startswith=data.TEXT_PREFIX)


def demo_data_present():
    return any(
        queryset.exists()
        for queryset in (
            demo_users(),
            demo_categories(),
            demo_products(),
            demo_events(),
            demo_rewards(),
            demo_promotions(),
            demo_campaigns(),
            demo_rules(),
            demo_tap_menus(),
        )
    )


def foreign_data_counts():
    """
    Filas que no son de demostración. La carga exige que no haya ninguna: así
    nunca se mezclan datos de demo con datos del usuario (ver la Fase 13).
    """
    checks = {
        "usuarios": User.objects.exclude(pk__in=demo_users()),
        "categorías": Category.objects.exclude(pk__in=demo_categories()),
        "estilos de cerveza": BeerStyle.objects.exclude(name__in=data.STYLE_NAMES),
        "productos": Product.objects.exclude(pk__in=demo_products()),
        "cartas de grifos": TapMenu.objects.exclude(pk__in=demo_tap_menus()),
        "eventos": Event.objects.exclude(pk__in=demo_events()),
        "recompensas": Reward.objects.exclude(pk__in=demo_rewards()),
        "promociones": Promotion.objects.exclude(pk__in=demo_promotions()),
        "reglas de conversión": LoyaltyRule.objects.exclude(pk__in=demo_rules()),
        "campañas": Campaign.objects.exclude(pk__in=demo_campaigns()),
    }
    counts = {label: queryset.count() for label, queryset in checks.items()}
    return {label: count for label, count in counts.items() if count}


def demo_counts():
    """Resumen de lo cargado, por entidad."""
    users = demo_users()
    return {
        "propietarios": users.filter(role=User.Role.OWNER).count(),
        "empleados": users.filter(role=User.Role.EMPLOYEE).count(),
        "clientes": users.filter(role=User.Role.CUSTOMER).count(),
        "categorías": demo_categories().count(),
        "productos": demo_products().count(),
        "cartas de grifos": demo_tap_menus().count(),
        "reglas de conversión": demo_rules().count(),
        "promociones": demo_promotions().count(),
        "compras": Purchase.objects.filter(customer__in=users).count(),
        "movimientos de puntos": PointsTransaction.objects.filter(customer__in=users).count(),
        "recompensas": demo_rewards().count(),
        "canjes": Redemption.objects.filter(customer__in=users).count(),
        "eventos": demo_events().count(),
        "reservas": Reservation.objects.filter(customer__in=users).count(),
        "campañas": demo_campaigns().count(),
        "notificaciones": Notification.objects.filter(recipient__in=users).count(),
    }
