"""Reservas y eventos (Fase 10): validaciones, estados, aforo, duplicados, permisos y notificaciones."""
import datetime
import uuid

from django.core import mail
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts import services as accounts
from apps.core.models import AuditEvent
from apps.events import services
from apps.events.models import Event, Reservation
from apps.notifications.models import Notification
from tests.accounts.factories import registration_data
from tests.loyalty.factories import make_customer_with_qr, make_employee, make_owner

from .factories import make_event, reserve, table_time

Status = Reservation.Status
NKind = Notification.Kind


class ReservationTestCase(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox.clear()
        self.customer, _ = make_customer_with_qr()
        self.other, _ = make_customer_with_qr("otra@example.com")
        self.owner = make_owner()
        self.employee = make_employee()

    def reserve(self, customer=None, **kwargs):
        with self.captureOnCommitCallbacks(execute=True):
            return reserve(customer or self.customer, **kwargs)

    def act(self, func, reservation, **kwargs):
        with self.captureOnCommitCallbacks(execute=True):
            return func(actor=kwargs.pop("actor", self.owner), reservation=reservation, **kwargs)


class RequestTests(ReservationTestCase):
    def test_table_reservation_is_pending_and_notifies(self):
        result = self.reserve(notes="Cerca de la ventana, por favor")
        reservation = result.reservation
        self.assertTrue(result.created)
        self.assertEqual(reservation.status, Status.PENDING)
        kinds = sorted(Notification.objects.values_list("kind", "status"))
        self.assertEqual(kinds, [(NKind.RESERVATION_OWNER_ALERT, "SENT"), (NKind.RESERVATION_RECEIVED, "SENT")])
        bodies = " ".join(m.body for m in mail.outbox)
        # Los emails no llevan las notas del cliente ni su email en el aviso al propietario.
        self.assertNotIn("ventana", bodies)
        owner_mail = next(m for m in mail.outbox if m.to == [self.owner.email])
        self.assertNotIn(self.customer.email, owner_mail.body)
        self.assertNotIn(self.customer.last_name, owner_mail.body)

    def test_requires_verified_customer(self):
        unverified = accounts.register_customer(**registration_data(email="pendiente@example.com"))
        for user in (unverified, self.employee, self.owner):
            with self.subTest(role=user.role), self.assertRaises(PermissionDenied):
                reserve(user)

    def test_datetime_rules(self):
        now = timezone.now()
        cases = (now + datetime.timedelta(minutes=30), now + datetime.timedelta(days=200), None)
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                services.request_reservation(
                    customer=self.customer, requested_for=value, party_size=2, idempotency_key=uuid.uuid4()
                )
        with self.assertRaises(ValidationError):
            services.request_reservation(
                customer=self.customer,
                requested_for=datetime.datetime(2030, 1, 1, 21),  # sin zona horaria
                party_size=2,
                idempotency_key=uuid.uuid4(),
            )

    def test_party_size_and_notes_limits(self):
        for size in (0, 21, "3; DROP", True, None):
            with self.subTest(size=size), self.assertRaises(ValidationError):
                reserve(self.customer, party_size=size)
        with self.assertRaises(ValidationError):
            reserve(self.customer, notes="x" * 301)
        self.assertEqual(reserve(self.customer, party_size="20").reservation.party_size, 20)

    def test_idempotent_retry_and_conflict(self):
        key = uuid.uuid4()
        first = self.reserve(key=key)
        second = self.reserve(key=key)
        self.assertFalse(second.created)
        self.assertEqual(first.reservation.pk, second.reservation.pk)
        self.assertEqual(Reservation.objects.count(), 1)
        self.assertEqual(Notification.objects.filter(kind=NKind.RESERVATION_RECEIVED).count(), 1)
        with self.assertRaises(ValidationError):
            reserve(self.other, key=key)

    @override_settings(EVENTS_MAX_ACTIVE_RESERVATIONS_PER_CUSTOMER=2)
    def test_max_active_reservations(self):
        reserve(self.customer)
        reserve(self.customer, requested_for=table_time(days=4))
        with self.assertRaises(ValidationError):
            reserve(self.customer, requested_for=table_time(days=5))

    @override_settings(EVENTS_RESERVATION_MAX_REQUESTS_PER_HOUR=2, EVENTS_MAX_ACTIVE_RESERVATIONS_PER_CUSTOMER=10)
    def test_requests_are_rate_limited(self):
        reserve(self.customer)
        reserve(self.customer, requested_for=table_time(days=4))
        with self.assertRaises(ValidationError) as ctx:
            reserve(self.customer, requested_for=table_time(days=5))
        self.assertEqual(ctx.exception.code, "rate_limited")


class EventReservationTests(ReservationTestCase):
    def test_uses_event_time_and_one_active_per_event(self):
        event = make_event()
        reservation = reserve(self.customer, event=event, requested_for=table_time(days=1)).reservation
        self.assertEqual(reservation.requested_for, event.starts_at)
        with self.assertRaises(ValidationError):
            reserve(self.customer, event=event)

    def test_database_allows_one_active_reservation_per_event(self):
        event = make_event()
        reserve(self.customer, event=event)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Reservation.objects.create(
                customer=self.customer, event=event, requested_for=event.starts_at, party_size=1, idempotency_key=uuid.uuid4()
            )

    def test_not_bookable_events(self):
        cases = (
            make_event(title="Borrador", status=Event.Status.DRAFT),
            make_event(title="Sin reservas", accepts_reservations=False),
            make_event(title="Empezado", starts_at=timezone.now() - datetime.timedelta(hours=1)),
            make_event(title="Archivado", status=Event.Status.ARCHIVED),
        )
        for event in cases:
            with self.subTest(event=event.title), self.assertRaises(ValidationError):
                reserve(self.customer, event=event)

    def test_capacity_is_checked_on_request_and_on_confirm(self):
        event = make_event(capacity=4)
        first = reserve(self.customer, event=event, party_size=3).reservation
        second = reserve(self.other, event=event, party_size=2).reservation  # pendientes no ocupan plaza
        services.confirm_reservation(actor=self.owner, reservation=first)
        with self.assertRaises(ValidationError) as ctx:
            services.confirm_reservation(actor=self.owner, reservation=second)
        self.assertEqual(ctx.exception.code, "event_full")
        third_customer, _ = make_customer_with_qr("tercera@example.com")
        with self.assertRaises(ValidationError):
            reserve(third_customer, event=event, party_size=2)

    def test_active_reservations_follow_a_new_event_time(self):
        event = make_event()
        active = reserve(self.customer, event=event).reservation
        cancelled = reserve(self.other, event=event).reservation
        services.cancel_reservation(actor=self.owner, reservation=cancelled)
        new_time = event.starts_at + datetime.timedelta(hours=2)
        services.save_event(actor=self.owner, event=event, data={"starts_at": new_time})
        active.refresh_from_db()
        cancelled.refresh_from_db()
        self.assertEqual(active.requested_for, new_time)
        self.assertNotEqual(cancelled.requested_for, new_time)

    def test_capacity_cannot_go_below_confirmed(self):
        event = make_event(capacity=5)
        services.confirm_reservation(actor=self.owner, reservation=reserve(self.customer, event=event, party_size=4).reservation)
        with self.assertRaises(ValidationError):
            services.save_event(actor=self.owner, event=event, data={"capacity": 3})


class TransitionTests(ReservationTestCase):
    def setUp(self):
        super().setUp()
        self.reservation = self.reserve().reservation
        mail.outbox.clear()

    def test_confirm_notifies_customer_with_message(self):
        result = self.act(services.confirm_reservation, self.reservation, message="Os guardamos la mesa del fondo.")
        self.assertEqual(result.reservation.status, Status.CONFIRMED)
        self.assertEqual(result.reservation.status_changed_by, self.owner)
        self.assertEqual([m.to for m in mail.outbox], [[self.customer.email]])
        self.assertIn("mesa del fondo", mail.outbox[0].body)
        event = AuditEvent.objects.get(action=AuditEvent.Action.RESERVATION_STATUS_CHANGED)
        self.assertEqual(event.metadata, {"from": "PENDING", "to": "CONFIRMED", "by": "owner"})

    def test_repeating_a_transition_does_nothing(self):
        self.act(services.confirm_reservation, self.reservation)
        again = self.act(services.confirm_reservation, self.reservation)
        self.assertFalse(again.created)
        self.assertEqual(Notification.objects.filter(kind=NKind.RESERVATION_CONFIRMED).count(), 1)

    def test_invalid_transitions(self):
        self.act(services.reject_reservation, self.reservation)
        for func in (services.confirm_reservation, services.cancel_reservation):
            with self.subTest(func=func.__name__), self.assertRaises(ValidationError):
                func(actor=self.owner, reservation=self.reservation)
        pending = reserve(self.customer, requested_for=table_time(days=6)).reservation
        with self.assertRaises(ValidationError):
            services.complete_reservation(actor=self.owner, reservation=pending)  # no está confirmada

    def test_complete_only_from_its_day(self):
        self.act(services.confirm_reservation, self.reservation)
        with self.assertRaises(ValidationError) as ctx:
            services.complete_reservation(actor=self.owner, reservation=self.reservation)
        self.assertEqual(ctx.exception.code, "too_early")
        Reservation.objects.filter(pk=self.reservation.pk).update(requested_for=timezone.now() - datetime.timedelta(hours=1))
        result = services.complete_reservation(actor=self.owner, reservation=self.reservation)
        self.assertEqual(result.reservation.status, Status.COMPLETED)
        with self.assertRaises(ValidationError):
            services.cancel_reservation(actor=self.owner, reservation=self.reservation)

    def test_cannot_confirm_past_reservation(self):
        Reservation.objects.filter(pk=self.reservation.pk).update(requested_for=timezone.now() - datetime.timedelta(hours=1))
        with self.assertRaises(ValidationError):
            services.confirm_reservation(actor=self.owner, reservation=self.reservation)

    def test_only_owner_changes_status(self):
        for actor in (self.employee, self.customer, self.other):
            for func in (services.confirm_reservation, services.reject_reservation, services.cancel_reservation):
                with self.subTest(actor=actor.email, func=func.__name__), self.assertRaises(PermissionDenied):
                    func(actor=actor, reservation=self.reservation)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Status.PENDING)

    def test_customer_cancels_own_reservation_and_owner_is_told(self):
        with self.captureOnCommitCallbacks(execute=True):
            result = services.cancel_own_reservation(customer=self.customer, reservation=self.reservation)
        self.assertEqual(result.reservation.status, Status.CANCELLED)
        recipients = sorted(m.to[0] for m in mail.outbox)
        self.assertEqual(recipients, sorted([self.customer.email, self.owner.email]))
        self.assertIn("Has cancelado", next(m.body for m in mail.outbox if m.to == [self.customer.email]))

    def test_customer_cannot_cancel_others_or_after_the_time(self):
        with self.assertRaises(PermissionDenied):
            services.cancel_own_reservation(customer=self.other, reservation=self.reservation)
        Reservation.objects.filter(pk=self.reservation.pk).update(requested_for=timezone.now() - datetime.timedelta(minutes=5))
        with self.assertRaises(ValidationError):
            services.cancel_own_reservation(customer=self.customer, reservation=self.reservation)

    def test_audit_never_contains_notes_or_messages(self):
        self.act(services.reject_reservation, self.reservation, message="Completo ese día")
        self.assertNotIn("Completo", str(list(AuditEvent.objects.values_list("metadata", flat=True))))


class EventServiceTests(ReservationTestCase):
    def test_owner_creates_publishes_and_archives(self):
        event = services.save_event(
            actor=self.owner,
            event=Event(),
            data={"title": "  Concierto   acústico ", "starts_at": timezone.now() + datetime.timedelta(days=3)},
        )
        self.assertEqual((event.title, event.status), ("Concierto acústico", Event.Status.DRAFT))
        event = services.set_event_status(actor=self.owner, event=event, status=Event.Status.PUBLISHED)
        self.assertIsNotNone(event.published_at)
        event = services.set_event_status(actor=self.owner, event=event, status=Event.Status.ARCHIVED)
        self.assertEqual(event.status, Event.Status.ARCHIVED)
        self.assertEqual(AuditEvent.objects.filter(action=AuditEvent.Action.EVENT_SAVED).count(), 3)
        with self.assertRaises(ValidationError):
            services.set_event_status(actor=self.owner, event=event, status=Event.Status.PUBLISHED)

    def test_cannot_publish_started_event_and_validates_dates(self):
        event = make_event(status=Event.Status.DRAFT, starts_at=timezone.now() - datetime.timedelta(hours=1))
        with self.assertRaises(ValidationError):
            services.set_event_status(actor=self.owner, event=event, status=Event.Status.PUBLISHED)
        with self.assertRaises(ValidationError):
            services.save_event(actor=self.owner, event=event, data={"ends_at": event.starts_at - datetime.timedelta(hours=1)})

    def test_only_owner_and_whitelisted_fields(self):
        with self.assertRaises(PermissionDenied):
            services.save_event(actor=self.employee, event=Event(), data={"title": "x"})
        with self.assertRaises(ValidationError):
            services.save_event(actor=self.owner, event=make_event(), data={"status": "PUBLISHED"})
        with self.assertRaises(ValidationError):
            services.set_event_status(actor=self.owner, event=make_event(), status="BORRADO")
