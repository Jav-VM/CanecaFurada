"""
Limpieza de los datos de demostración (Fase 13).

Solo borra lo identificable como demo (`selectors.py`), en una transacción y
en el orden que imponen las relaciones `PROTECT`. Si algún dato **ajeno** a la
demo depende de un dato de demo (p. ej. una compra registrada a mano a un
cliente real por un empleado de demo), no borra nada y lo explica.

Es la única excepción a "los historiales no se borran": aquí no se corrige
ningún historial real, se retira un conjunto de datos ficticios completo. Los
eventos de auditoría agregados sin actor ni objetivo (p. ej. las ejecuciones
de cumpleaños) se conservan: no contienen datos personales.
"""
from django.db import transaction
from django.db.models import Q

from apps.accounts.models import User
from apps.catalog.models import BeerStyle, Product
from apps.core.models import AuditEvent
from apps.events.models import Event, Reservation
from apps.loyalty.models import LoyaltyRule, PointsTransaction
from apps.notifications.models import Campaign, Notification
from apps.purchases.models import Purchase
from apps.rewards.models import Redemption

from . import data, selectors


class DemoCleanupBlocked(Exception):
    pass


def _blockers(users, events, rewards, promotions, campaigns, rules, products, categories):
    """Datos que no son de demo y referencian datos de demo."""
    checks = {
        "compras": Purchase.objects.filter(Q(customer__in=users) | Q(registered_by__in=users)).exclude(
            customer__in=users, registered_by__in=users
        ),
        "movimientos de puntos": PointsTransaction.objects.exclude(customer__in=users).filter(
            Q(created_by__in=users) | Q(promotion__in=promotions) | Q(rule__in=rules)
        ),
        "canjes": Redemption.objects.exclude(customer__in=users).filter(
            Q(validated_by__in=users) | Q(reward__in=rewards)
        ),
        "reservas": Reservation.objects.exclude(customer__in=users).filter(
            Q(event__in=events) | Q(status_changed_by__in=users)
        ),
        "campañas": Campaign.objects.exclude(pk__in=campaigns).filter(created_by__in=users),
        "notificaciones": Notification.objects.exclude(recipient__in=users).filter(campaign__in=campaigns),
        "reglas de conversión": LoyaltyRule.objects.exclude(pk__in=rules).filter(created_by__in=users),
        "productos": Product.objects.exclude(pk__in=products).filter(category__in=categories),
    }
    counts = {label: queryset.count() for label, queryset in checks.items()}
    return {label: count for label, count in counts.items() if count}


def clean():
    """Borra los datos de demostración. Devuelve los recuentos borrados por entidad."""
    deleted = {}
    files = []
    with transaction.atomic():
        users = list(selectors.demo_users().values_list("pk", flat=True))
        events = list(selectors.demo_events().values_list("pk", flat=True))
        rewards = list(selectors.demo_rewards().values_list("pk", flat=True))
        promotions = list(selectors.demo_promotions().values_list("pk", flat=True))
        campaigns = list(selectors.demo_campaigns().values_list("pk", flat=True))
        rules = list(selectors.demo_rules().values_list("pk", flat=True))
        products = list(selectors.demo_products().values_list("pk", flat=True))
        categories = list(selectors.demo_categories().values_list("pk", flat=True))

        blockers = _blockers(users, events, rewards, promotions, campaigns, rules, products, categories)
        if blockers:
            detail = ", ".join(f"{label}: {count}" for label, count in blockers.items())
            raise DemoCleanupBlocked(
                f"Hay datos que no son de demostración ligados a datos de demostración ({detail}). "
                "No se ha borrado nada."
            )

        # Identificadores públicos para retirar también su auditoría.
        public_ids = [
            *User.objects.filter(pk__in=users).values_list("public_id", flat=True),
            *Purchase.objects.filter(customer__in=users).values_list("public_id", flat=True),
            *Redemption.objects.filter(customer__in=users).values_list("public_id", flat=True),
            *Reservation.objects.filter(customer__in=users).values_list("public_id", flat=True),
            *PointsTransaction.objects.filter(customer__in=users).values_list("public_id", flat=True),
            *selectors.demo_rules().values_list("public_id", flat=True),
            *Product.objects.filter(pk__in=products).values_list("public_id", flat=True),
            *data.event_ids(),
            *data.reward_ids(),
            *data.promotion_ids(),
            *data.campaign_ids(),
        ]
        files = [
            (field.storage, field.name)
            for queryset, attr in (
                (Product.objects.filter(pk__in=products), "image"),
                (Event.objects.filter(pk__in=events), "image"),
                (selectors.demo_rewards(), "image"),
                (selectors.demo_tap_menus(), "image"),
            )
            for field in (getattr(obj, attr) for obj in queryset)
            if field
        ]

        steps = (
            ("notificaciones", Notification.objects.filter(Q(recipient__in=users) | Q(campaign__in=campaigns))),
            ("campañas", Campaign.objects.filter(pk__in=campaigns)),
            ("canjes", Redemption.objects.filter(customer__in=users)),
            # Primero las compensaciones: protegen al movimiento que compensan.
            ("movimientos de puntos", PointsTransaction.objects.filter(customer__in=users, reverses__isnull=False)),
            ("movimientos de puntos", PointsTransaction.objects.filter(customer__in=users)),
            ("compras", Purchase.objects.filter(customer__in=users)),
            ("reservas", Reservation.objects.filter(customer__in=users)),
            ("eventos", Event.objects.filter(pk__in=events)),
            ("recompensas", selectors.demo_rewards()),
            ("promociones", selectors.demo_promotions()),
            ("reglas de conversión", LoyaltyRule.objects.filter(pk__in=rules)),
            ("productos", Product.objects.filter(pk__in=products)),
            ("categorías", selectors.demo_categories()),
            ("estilos de cerveza", BeerStyle.objects.filter(name__in=data.STYLE_NAMES, products__isnull=True)),
            ("cartas de grifos", selectors.demo_tap_menus()),
            ("auditoría", AuditEvent.objects.filter(Q(actor__in=users) | Q(target_public_id__in=public_ids))),
            # En cascada: perfiles, QR, tokens de email e historial de preferencias.
            ("usuarios", User.objects.filter(pk__in=users)),
        )
        for label, queryset in steps:
            # Se cuenta la entidad principal; `delete()` sumaría también las cascadas.
            count = queryset.count()
            queryset.delete()
            deleted[label] = deleted.get(label, 0) + count
        # Los ficheros, solo cuando la transacción se haya confirmado.
        transaction.on_commit(lambda: _delete_files(files))
    return {label: count for label, count in deleted.items() if count}


def _delete_files(files):
    for storage, name in files:
        storage.delete(name)
