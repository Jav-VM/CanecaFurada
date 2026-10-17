"""
Construcción de los datos de demostración (Fase 13).

Cada escenario de `data.py` se traduce en pasos fechados que llaman a los
**servicios reales** (registro, verificación por enlace, QR, compras, ledger,
canjes, eventos, reservas, campañas). Los pasos se ordenan por fecha y se
ejecutan con el reloj simulado (`clock.py`), de modo que cada regla de negocio
se aplica en su momento y el ledger se escribe en orden cronológico.

No hay transacción global: cada servicio confirma la suya, y así los
`on_commit` (emails al backend en memoria, avisos de reservas) ocurren en su
fecha. Si un paso falla, el comando deshace la carga con `cleanup.clean()`.

Ningún secreto sale de aquí: el token de verificación se lee del email en
memoria y se usa al momento; contraseñas, tokens QR y códigos de canje nunca
se imprimen.
"""
import datetime
import random
import re
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from django.core import mail
from django.db.models import Max
from django.utils import timezone

from apps.accounts import services as accounts
from apps.accounts.models import CommunicationPreferenceChange, CustomerProfile, User
from apps.catalog import services as catalog
from apps.catalog.models import BeerStyle, Category, Product, TapMenu
from apps.events import services as events
from apps.events.models import Event, Reservation
from apps.loyalty import birthdays, conversion, ledger, promotions
from apps.loyalty import services as loyalty
from apps.loyalty.models import CustomerQRCode, PointsTransaction, Promotion
from apps.notifications import campaigns
from apps.notifications import services as notifications
from apps.notifications.models import Campaign
from apps.purchases import services as purchases
from apps.rewards import services as rewards
from apps.rewards.models import Redemption, Reward

from . import data, images
from .clock import SimulatedClock

_TOKEN_RE = re.compile(r"/verificar-email/([A-Za-z0-9_-]+)/")
DEMO_SEXES = tuple(CustomerProfile.Sex.values)


class DemoBuildError(Exception):
    """Un paso de la carga falló. El mensaje no incluye datos personales ni secretos."""


@dataclass(order=True)
class _Step:
    when: datetime.datetime
    seq: int
    label: str = field(compare=False)
    action: object = field(compare=False)


class DemoBuilder:
    def __init__(self, *, reference_date, password):
        self.reference_date = reference_date
        self.password = password
        self._steps = []
        # Hora real al empezar (antes de simular el reloj).
        self._started_at = timezone.now()

    # --- Utilidades ---------------------------------------------------------------

    def at(self, days, hour=12, minute=0):
        day = self.reference_date + datetime.timedelta(days=days)
        return timezone.make_aware(datetime.datetime.combine(day, datetime.time(hour, minute)))

    def _schedule(self, when, label, action):
        self._steps.append(_Step(when, len(self._steps), label, action))

    @staticmethod
    def user(key):
        return User.objects.get(email=data.demo_email(key))

    def owner(self):
        return self.user(data.OWNER.key)

    @staticmethod
    def _now():
        return timezone.now()

    # --- Ejecución ----------------------------------------------------------------

    def build(self):
        self._plan()
        steps = sorted(self._steps)
        previous_outbox = getattr(mail, "outbox", None)
        mail.outbox = []
        try:
            with SimulatedClock(steps[0].when) as clock:
                for step in steps:
                    clock.set(step.when)
                    try:
                        step.action()
                    except Exception as exc:
                        raise DemoBuildError(f"Falló el paso «{step.label}»: {exc}") from exc
                    mail.outbox.clear()  # nada de lo enviado se conserva
            # Avisos que quedaran en cola: se entregan ya, con la hora real.
            notifications.process_due()
        finally:
            if previous_outbox is None:
                del mail.outbox
            else:
                mail.outbox = previous_outbox
        return len(steps)

    def _plan(self):
        self._plan_staff()
        self._plan_rules_and_promotions()
        self._plan_catalog()
        self._plan_rewards()
        self._plan_customers()
        self._plan_points()
        self._plan_purchases()
        self._plan_redemptions()
        self._plan_events_and_reservations()
        self._plan_campaigns()
        self._plan_birthday()

    # --- Personas -----------------------------------------------------------------

    def _stamp_joined(self, user):
        # `date_joined` toma su valor por defecto al importar el modelo (no del
        # reloj simulado): se fija a la fecha simulada del alta.
        User.objects.filter(pk=user.pk).update(date_joined=self._now())

    def _stamp_preferences(self, user, after_id):
        # Igual con el historial de consentimientos que se acaba de crear.
        CommunicationPreferenceChange.objects.filter(user=user, pk__gt=after_id or 0).update(created_at=self._now())

    @staticmethod
    def _last_preference_id():
        return CommunicationPreferenceChange.objects.aggregate(last=Max("pk"))["last"]

    def _confirm_from_email(self, user):
        """Verifica el email con el enlace real que el servicio acaba de enviar (en memoria)."""
        messages = [m for m in mail.outbox if user.email in m.to]
        match = _TOKEN_RE.search(messages[-1].body) if messages else None
        if match is None:
            raise DemoBuildError("No se encontró el enlace de verificación en el email en memoria.")
        accounts.confirm_email_token(match.group(1))

    def _verify_staff(self, key):
        user = self.user(key)
        accounts.resend_verification_email(user)
        self._confirm_from_email(user)

    def _plan_staff(self):
        owner = data.OWNER

        def create_owner():
            user = accounts.create_owner(
                email=data.demo_email(owner.key),
                first_name=owner.first_name,
                last_name=owner.last_name,
                password=self.password,
            )
            self._stamp_joined(user)
            self._verify_staff(owner.key)

        self._schedule(self.at(owner.joined, 9), "alta de la propietaria", create_owner)

        for employee in data.EMPLOYEES:

            def create_employee(employee=employee):
                user = accounts.create_employee(
                    actor=self.owner(),
                    email=data.demo_email(employee.key),
                    first_name=employee.first_name,
                    last_name=employee.last_name,
                    password=self.password,
                )
                self._stamp_joined(user)
                self._verify_staff(employee.key)

            self._schedule(self.at(employee.joined, 10), f"alta de {employee.key}", create_employee)
            if employee.deactivated is not None:
                self._schedule(
                    self.at(employee.deactivated, 10),
                    f"baja de {employee.key}",
                    lambda key=employee.key: accounts.set_user_active(
                        actor=self.owner(), user=self.user(key), is_active=False
                    ),
                )

    def birthday_date(self):
        day = self.reference_date - datetime.timedelta(days=data.BIRTHDAY_DAYS_AGO)
        if (day.month, day.day) == (2, 29):
            day -= datetime.timedelta(days=1)
        return day

    def _plan_customers(self):
        for customer in data.CUSTOMERS:
            self._schedule(self._joined_at(customer), f"registro de {customer.key}", lambda c=customer: self._register(c))
            if customer.deactivated is not None:
                self._schedule(
                    self.at(customer.deactivated, 10),
                    f"baja de {customer.key}",
                    lambda key=customer.key: accounts.set_user_active(
                        actor=self.owner(), user=self.user(key), is_active=False
                    ),
                )
        key, day = data.RESEND_VERIFICATION
        self._schedule(
            self.at(day, 18),
            f"reenvío de verificación de {key}",
            lambda key=key: accounts.resend_verification_email(self.user(key)),
        )
        for key, day, email_opt_in, sms_opt_in in data.PREFERENCE_CHANGES:

            def change(key=key, email_opt_in=email_opt_in, sms_opt_in=sms_opt_in):
                user = self.user(key)
                after = self._last_preference_id()
                accounts.set_communication_preferences(
                    user=user, promo_email_opt_in=email_opt_in, promo_sms_opt_in=sms_opt_in
                )
                self._stamp_preferences(user, after)

            self._schedule(self.at(day, 13), f"preferencias de {key}", change)

    def _joined_at(self, customer):
        if customer.joined == 0:
            # «Recién registrado»: una hora antes de la carga, para que su enlace
            # de verificación siga vigente (24 h). Nunca después de la hora real.
            return min(self._started_at - datetime.timedelta(hours=1), self.at(0, 11, 30))
        return self.at(customer.joined, 11, 30)

    def _register(self, customer):
        date_of_birth = customer.date_of_birth
        if date_of_birth is None:
            birthday = self.birthday_date()
            date_of_birth = datetime.date(1991, birthday.month, birthday.day)
        after = self._last_preference_id()
        user = accounts.register_customer(
            email=data.demo_email(customer.key),
            password=self.password,
            first_name=customer.first_name,
            last_name=customer.last_name,
            address_line_1=f"Rúa Ficticia {customer.street_number}",
            address_line_2=customer.address_line_2,
            postal_code=customer.postal_code,
            city=customer.city,
            province=customer.province,
            country=customer.country,
            date_of_birth=date_of_birth,
            # Reparto fijo de las tres opciones (no se deduce del nombre).
            sex=DEMO_SEXES[data.CUSTOMERS.index(customer) % len(DEMO_SEXES)],
            phone_number=customer.phone,
            promo_email_opt_in=customer.promo_email,
            promo_sms_opt_in=customer.promo_sms,
            accept_terms=True,  # Fase 25: los clientes de demostración aceptan los textos (ficticio).
        )
        self._stamp_joined(user)
        self._stamp_preferences(user, after)
        if customer.verify:
            self._confirm_from_email(user)
            loyalty.get_customer_qr(self.user(customer.key))

    # --- Puntos: reglas, promociones y ajustes -------------------------------------

    def _plan_rules_and_promotions(self):
        for day, rate, note in data.LOYALTY_RULES:
            self._schedule(
                self.at(day, 9, 30),
                f"regla de conversión {rate}",
                lambda rate=rate, note=note: conversion.create_rule(
                    actor=self.owner(), points_per_euro=Decimal(rate), note=f"{data.TEXT_PREFIX} {note}"
                ),
            )
        for promo in data.PROMOTIONS:
            self._schedule(self.at(promo.created, 9, 45), f"promoción {promo.key}", lambda p=promo: self._create_promotion(p))
            for day, status in promo.status_changes:
                self._schedule(
                    self.at(day, 9, 45),
                    f"estado de la promoción {promo.key}",
                    lambda key=promo.key, status=status: promotions.set_promotion_status(
                        actor=self.owner(), promotion=self._promotion(key), status=status
                    ),
                )

    @staticmethod
    def _promotion(key):
        return Promotion.objects.get(public_id=data.demo_uuid(f"promotion:{key}"))

    def _create_promotion(self, promo):
        promotion = Promotion(
            public_id=data.demo_uuid(f"promotion:{promo.key}"),
            name=promo.name,
            description=promo.description,
            kind=promo.kind,
            bonus_type=promo.bonus_type,
            fixed_points=promo.fixed_points,
            multiplier=data.decimal(promo.multiplier),
            min_purchase_amount=data.decimal(promo.min_purchase_amount),
            starts_at=self.at(promo.starts, 0, 0),
            ends_at=self.at(promo.ends, 0, 0) if promo.ends is not None else None,
            max_uses_per_customer=promo.max_uses_per_customer,
            max_total_uses=promo.max_total_uses,
            status=promo.status,
        )
        promotions.save_promotion(actor=self.owner(), promotion=promotion, changed_fields=())

    def _plan_points(self):
        for key, customer, day, points, reason in data.ADJUSTMENTS:
            self._schedule(
                self.at(day, 12),
                f"ajuste {key}",
                lambda key=key, customer=customer, points=points, reason=reason: ledger.adjust_points(
                    actor=self.owner(),
                    customer=self.user(customer),
                    points=points,
                    reason=reason,
                    idempotency_key=data.demo_uuid(f"adjustment:{key}"),
                ),
            )
        for key, day, reason in data.REVERSALS:

            def reverse(key=key, reason=reason):
                movement = PointsTransaction.objects.get(idempotency_key=data.demo_uuid(f"adjustment:{key}"))
                ledger.reverse_movement(actor=self.owner(), movement=movement, reason=reason)

            self._schedule(self.at(day, 12), f"compensación {key}", reverse)
        for key, day in data.QR_ROTATIONS:
            self._schedule(self.at(day, 17), f"QR renovado de {key}", lambda key=key: loyalty.rotate_customer_qr(self.user(key)))

    # --- Compras ------------------------------------------------------------------

    def _staff_on(self, day):
        """Personal en activo ese día (ordenado: el resultado es determinista)."""
        people = [data.OWNER, *data.EMPLOYEES]
        return [
            person.key
            for person in people
            if person.joined < day and (person.deactivated is None or day < person.deactivated)
        ]

    def _plan_purchases(self):
        for customer in data.CUSTOMERS:
            if not customer.verify or not customer.visits:
                continue
            rng = random.Random(f"caneca-demo:{customer.key}")
            start = customer.joined + 3
            end = (customer.deactivated if customer.deactivated is not None else 0) - 2
            span = end - start
            for index in range(customer.visits):
                day = start + round((index + 0.5) * span / customer.visits)
                staff = rng.choice(self._staff_on(day))
                amount = rng.choice(data.VISIT_AMOUNTS)
                hour, minute = rng.choice((19, 20, 21, 22)), rng.choice((5, 20, 35, 50))
                self._schedule_purchase(customer.key, staff, self.at(day, hour, minute), amount)
        for customer, staff, day, hour, amount in data.SPECIAL_PURCHASES:
            self._schedule_purchase(customer, staff, self.at(day, hour, 10), amount)

    def _schedule_purchase(self, customer_key, staff_key, when, amount):
        def register():
            token = CustomerQRCode.objects.get(user=self.user(customer_key)).token
            purchases.register_purchase(
                staff=self.user(staff_key), qr_code=token, amount=amount, idempotency_key=uuid.uuid4()
            )

        self._schedule(when, f"compra de {customer_key}", register)

    # --- Carta --------------------------------------------------------------------

    def _plan_catalog(self):
        self._schedule(self.at(-410, 10), "carta", self._create_catalog)
        self._schedule(self.at(data.TAP_MENU["day"], 10), "carta de grifos", self._create_tap_menu)

    def _create_catalog(self):
        owner = self.owner()
        categories = {}
        for slug, name, description, position, published in data.CATEGORIES:
            category = Category(
                name=name,
                slug=f"{data.CATEGORY_SLUG_PREFIX}{slug}",
                description=description,
                position=position,
                is_published=published,
            )
            category.full_clean()
            category.save()
            categories[slug] = category
        styles = {name: BeerStyle.objects.get_or_create(name=name)[0] for name in data.STYLE_NAMES}
        for position, item in enumerate(data.PRODUCTS, start=1):
            product = Product(
                public_id=data.demo_uuid(f"product:{item.key}"),
                category=categories[item.category],
                kind=item.kind,
                name=item.name,
                description=item.description,
                style=styles[item.style] if item.style else None,
                abv=data.decimal(item.abv),
                brewery=item.brewery,
                price=Decimal(item.price),
                serving=item.serving,
                position=position,
                is_featured=item.featured,
            )
            if item.image:
                product.image = images.placeholder(item.image)
            product.full_clean()
            product.save()
            if item.status in (Product.Status.PUBLISHED, Product.Status.ARCHIVED):
                product = catalog.set_product_status(actor=owner, product=product, status=Product.Status.PUBLISHED)
            if item.status == Product.Status.ARCHIVED:
                catalog.set_product_status(actor=owner, product=product, status=Product.Status.ARCHIVED)
            if not item.available:
                catalog.set_product_availability(actor=owner, product=product, is_available=False)

    def _create_tap_menu(self):
        menu = TapMenu(
            title=data.TAP_MENU["title"],
            text_alternative=data.TAP_MENU["text_alternative"],
            image=images.placeholder("#2a2a2a", size=(900, 1200)),
            is_published=True,
        )
        menu.full_clean()
        menu.save()

    # --- Recompensas y canjes -------------------------------------------------------

    @staticmethod
    def _reward(key):
        return Reward.objects.get(public_id=data.demo_uuid(f"reward:{key}"))

    def _plan_rewards(self):
        for item in data.REWARDS:

            def create(item=item):
                reward = Reward(
                    public_id=data.demo_uuid(f"reward:{item.key}"),
                    name=item.name,
                    description=item.description,
                    points_cost=item.points_cost,
                    status=item.status,
                    valid_from=self._now(),
                    stock=item.stock,
                    position=item.position,
                )
                if item.image:
                    reward.image = images.placeholder(item.image)
                rewards.save_reward(actor=self.owner(), reward=reward, changed_fields=())

            self._schedule(self.at(item.created, 9, 50), f"recompensa {item.key}", create)
            for day, status in item.status_changes:
                self._schedule(
                    self.at(day, 9, 50),
                    f"estado de la recompensa {item.key}",
                    lambda key=item.key, status=status: rewards.set_reward_status(
                        actor=self.owner(), reward=self._reward(key), status=status
                    ),
                )

    def _plan_redemptions(self):
        for item in data.REDEMPTIONS:
            key = data.demo_uuid(f"redemption:{item.key}")
            self._schedule(
                self.at(item.requested, 20, 40),
                f"canje {item.key}",
                lambda item=item, key=key: rewards.request_redemption(
                    customer=self.user(item.customer), reward=self._reward(item.reward), idempotency_key=key
                ),
            )
            if item.validated:
                day, staff = item.validated

                def validate(key=key, staff=staff):
                    code = Redemption.objects.get(idempotency_key=key).code
                    rewards.validate_redemption(staff=self.user(staff), code=code)

                self._schedule(self.at(day, 21, 10), f"validación del canje {item.key}", validate)
            if item.cancelled is not None:
                self._schedule(
                    self.at(item.cancelled, 13),
                    f"cancelación del canje {item.key}",
                    lambda item=item, key=key: rewards.cancel_redemption(
                        customer=self.user(item.customer), redemption=Redemption.objects.get(idempotency_key=key)
                    ),
                )
            if item.expired is not None:
                # Lo que hace el comando programado `expire_redemptions` ese día.
                self._schedule(self.at(item.expired, 3), f"caducidad del canje {item.key}", rewards.expire_pending_redemptions)

    # --- Eventos y reservas -----------------------------------------------------------

    @staticmethod
    def _event(key):
        return Event.objects.get(public_id=data.demo_uuid(f"event:{key}"))

    def _plan_events_and_reservations(self):
        for item in data.EVENTS:
            self._schedule(self.at(item.created, 10, 15), f"evento {item.key}", lambda item=item: self._create_event(item))
            if item.archived is not None:
                self._schedule(
                    self.at(item.archived, 10, 15),
                    f"archivo del evento {item.key}",
                    lambda key=item.key: events.set_event_status(
                        actor=self.owner(), event=self._event(key), status=Event.Status.ARCHIVED
                    ),
                )
        for index, item in enumerate(data.RESERVATIONS):
            key = data.demo_uuid(f"reservation:{index}")
            self._schedule(
                self.at(item.requested, 16, 30), f"reserva {index}", lambda item=item, key=key: self._reserve(item, key)
            )
            for day, action, message in item.steps:
                self._schedule(
                    self.at(day, 12, 30),
                    f"reserva {index}: {action}",
                    lambda item=item, key=key, action=action, message=message: self._transition(item, key, action, message),
                )

    def _create_event(self, item):
        starts_at = self.at(item.starts, item.hour)
        payload = {
            "title": item.title,
            "summary": item.summary,
            "description": f"Evento de demostración. {item.summary}",
            "starts_at": starts_at,
            "ends_at": starts_at + datetime.timedelta(hours=item.duration_hours) if item.duration_hours else None,
            "is_featured": item.featured,
            "accepts_reservations": item.accepts_reservations,
            "capacity": item.capacity,
        }
        if item.image:
            payload["image"] = images.placeholder(item.image)
        event = events.save_event(actor=self.owner(), event=Event(public_id=data.demo_uuid(f"event:{item.key}")), data=payload)
        if item.publish:
            events.set_event_status(actor=self.owner(), event=event, status=Event.Status.PUBLISHED)

    def _reserve(self, item, key):
        events.request_reservation(
            customer=self.user(item.customer),
            event=self._event(item.event) if item.event else None,
            requested_for=self.at(item.table_day, item.table_hour) if item.event is None else None,
            party_size=item.party_size,
            notes=item.notes,
            idempotency_key=key,
        )

    def _transition(self, item, key, action, message):
        reservation = Reservation.objects.get(idempotency_key=key)
        owner = self.owner()
        if action == "confirm":
            events.confirm_reservation(actor=owner, reservation=reservation, message=message)
        elif action == "reject":
            events.reject_reservation(actor=owner, reservation=reservation, message=message)
        elif action == "cancel":
            events.cancel_reservation(actor=owner, reservation=reservation, message=message)
        elif action == "complete":
            events.complete_reservation(actor=owner, reservation=reservation)
        elif action == "cancel_own":
            events.cancel_own_reservation(customer=self.user(item.customer), reservation=reservation)
        else:
            raise DemoBuildError(f"Acción de reserva desconocida: {action}")

    # --- Campañas y cumpleaños ----------------------------------------------------------

    @staticmethod
    def _campaign(key):
        return Campaign.objects.get(public_id=data.demo_uuid(f"campaign:{key}"))

    def _plan_campaigns(self):
        for item in data.CAMPAIGNS:
            self._schedule(
                self.at(item.created, 11),
                f"campaña {item.key}",
                lambda item=item: campaigns.save_campaign(
                    actor=self.owner(),
                    campaign=Campaign(public_id=data.demo_uuid(f"campaign:{item.key}")),
                    data={"name": item.name, "channel": "EMAIL", "subject": item.subject, "body": item.body},
                ),
            )
            if item.queued is not None:
                self._schedule(
                    self.at(item.queued, 11, 30),
                    f"campaña {item.key} programada",
                    lambda key=item.key: campaigns.queue_campaign(actor=self.owner(), campaign=self._campaign(key)),
                )
            if item.cancelled is not None:
                self._schedule(
                    self.at(item.cancelled, 9),
                    f"campaña {item.key} cancelada",
                    lambda key=item.key: campaigns.cancel_campaign(actor=self.owner(), campaign=self._campaign(key)),
                )
            elif item.queued is not None:
                # Lo que hace `process_notifications` en su siguiente ejecución.
                self._schedule(self.at(item.queued, 12), f"reparto de la campaña {item.key}", self._process_notifications)

    def _process_notifications(self):
        campaigns.dispatch_queued()
        notifications.process_due()

    def _plan_birthday(self):
        day = self.birthday_date()
        days = (day - self.reference_date).days
        # Lo que hace el comando diario `run_birthday_promotions` y, después, `process_notifications`.
        self._schedule(self.at(days, 8), "promociones de cumpleaños", lambda day=day: birthdays.run_birthday_promotions(day=day))
        self._schedule(self.at(days, 8, 5), "avisos de cumpleaños", notifications.process_due)
