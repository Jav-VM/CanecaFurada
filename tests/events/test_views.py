"""Vistas de eventos y reservas (Fase 10): web pública, cliente y dashboard, con IDOR y escalada de privilegios."""
import datetime
import uuid

from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts import services as accounts
from apps.core.models import AuditEvent
from apps.events.models import Event, Reservation
from apps.web import services as web
from tests.accounts.factories import VALID_MOBILE, registration_data
from tests.loyalty.factories import make_customer_with_qr, make_employee, make_owner

from .factories import make_event, reserve, table_time

Status = Reservation.Status


class ViewTestCase(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox.clear()
        self.customer, _ = make_customer_with_qr(phone_number=VALID_MOBILE)
        self.other, _ = make_customer_with_qr("otra@example.com")
        self.owner = make_owner()
        self.employee = make_employee()


class PublicPagesTests(ViewTestCase):
    def test_only_published_upcoming_events_are_public(self):
        public = make_event(title="Cata pública")
        draft = make_event(title="Evento en borrador", status=Event.Status.DRAFT)
        make_event(title="Evento pasado", starts_at=timezone.now() - datetime.timedelta(days=2))
        response = self.client.get(reverse("web:events"))
        self.assertContains(response, "Cata pública")
        self.assertNotContains(response, "Evento en borrador")
        self.assertNotContains(response, "Evento pasado")
        self.assertEqual(self.client.get(reverse("events:event_detail", args=[public.public_id])).status_code, 200)
        self.assertEqual(self.client.get(reverse("events:event_detail", args=[draft.public_id])).status_code, 404)

    def test_home_shows_featured_events_and_editable_texts(self):
        make_event(title="Concierto destacado", is_featured=True)
        web.update_business_info(
            actor=self.owner, data={"hero_text": "Bienvenida de prueba", "announcement": "Cerrado el lunes festivo"}
        )
        response = self.client.get(reverse("web:home"))
        self.assertContains(response, "Concierto destacado")
        self.assertContains(response, "Bienvenida de prueba")
        self.assertContains(response, "Cerrado el lunes festivo")

    def test_home_texts_are_escaped(self):
        web.update_business_info(actor=self.owner, data={"announcement": "<script>alert(1)</script>"})
        response = self.client.get(reverse("web:home"))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")

    def test_event_detail_shows_seats_and_reserve_button(self):
        event = make_event(capacity=6)
        response = self.client.get(reverse("events:event_detail", args=[event.public_id]))
        self.assertContains(response, 'data-seats-left>6<', html=False)
        self.assertContains(response, "data-reserve-event")


class CustomerViewsTests(ViewTestCase):
    def login(self, user=None):
        self.client.force_login(user or self.customer)

    def test_anonymous_unverified_and_staff_are_refused(self):
        url = reverse("events:reservation_new")
        self.assertEqual(self.client.get(url).status_code, 302)
        unverified = accounts.register_customer(**registration_data(email="pendiente@example.com"))
        for user in (unverified, self.employee, self.owner):
            self.client.force_login(user)
            with self.subTest(role=user.role):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_table_reservation_form(self):
        self.login()
        response = self.client.get(reverse("events:reservation_new"))
        key = response.context["form"]["idempotency_key"].value()
        when = table_time()
        data = {"date": when.date().isoformat(), "time": "21:00", "party_size": "4", "notes": "", "idempotency_key": key}
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("events:reservation_new"), data)
        reservation = Reservation.objects.get()
        self.assertRedirects(response, reverse("events:reservation_detail", args=[reservation.public_id]))
        self.assertEqual((reservation.customer, reservation.party_size, reservation.status), (self.customer, 4, Status.PENDING))
        # Doble envío del mismo formulario: no crea otra reserva.
        self.client.post(reverse("events:reservation_new"), data)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_form_errors_are_shown(self):
        self.login()
        data = {"date": timezone.localdate().isoformat(), "time": "00:00", "party_size": "2", "idempotency_key": str(uuid.uuid4())}
        response = self.client.post(reverse("events:reservation_new"), data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Reservation.objects.exists())

    def test_event_reservation_form(self):
        event = make_event()
        self.login()
        url = reverse("events:event_reservation_new", args=[event.public_id])
        data = {"party_size": "2", "idempotency_key": str(uuid.uuid4())}
        self.client.post(url, data)
        reservation = Reservation.objects.get()
        self.assertEqual(reservation.event, event)
        # Con una activa, el formulario redirige a ella.
        response = self.client.get(url)
        self.assertRedirects(response, reverse("events:reservation_detail", args=[reservation.public_id]))

    def test_cannot_see_or_cancel_others_reservations(self):
        own = reserve(self.customer).reservation
        others = reserve(self.other).reservation
        self.login()
        self.assertEqual(self.client.get(reverse("events:reservation_detail", args=[own.public_id])).status_code, 200)
        self.assertEqual(self.client.get(reverse("events:reservation_detail", args=[others.public_id])).status_code, 404)
        self.assertEqual(self.client.post(reverse("events:reservation_cancel", args=[others.public_id])).status_code, 404)
        others.refresh_from_db()
        self.assertEqual(others.status, Status.PENDING)
        response = self.client.get(reverse("events:my_reservations"))
        self.assertEqual(list(response.context["reservations"].object_list), [own])

    def test_cancel_requires_post(self):
        own = reserve(self.customer).reservation
        self.login()
        url = reverse("events:reservation_cancel", args=[own.public_id])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        own.refresh_from_db()
        self.assertEqual(own.status, Status.CANCELLED)


class DashboardTests(ViewTestCase):
    def setUp(self):
        super().setUp()
        self.reservation = reserve(self.customer, notes="Somos celíacos").reservation
        self.client.force_login(self.owner)

    def test_staff_and_customers_cannot_manage(self):
        urls = [
            ("get", reverse("dashboard:reservation_detail", args=[self.reservation.public_id])),
            ("post", reverse("dashboard:reservation_action", args=[self.reservation.public_id])),
            ("post", reverse("dashboard:event_create")),
        ]
        for user in (self.employee, self.customer):
            self.client.force_login(user)
            for method, url in urls:
                with self.subTest(role=user.role, url=url):
                    response = getattr(self.client, method)(url, {"accion": "confirmar"})
                    self.assertEqual(response.status_code, 403)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Status.PENDING)

    def test_list_has_no_contact_data_and_detail_is_audited(self):
        response = self.client.get(reverse("dashboard:reservations"))
        self.assertContains(response, "Lúa F.")
        self.assertNotContains(response, self.customer.email)
        self.assertNotContains(response, "600 000 001")
        detail = self.client.get(reverse("dashboard:reservation_detail", args=[self.reservation.public_id]))
        self.assertContains(detail, self.customer.email)
        self.assertContains(detail, "+34600000001")
        self.assertContains(detail, "Somos celíacos")
        event = AuditEvent.objects.get(action=AuditEvent.Action.RESERVATION_DATA_VIEWED)
        self.assertEqual(event.target_public_id, self.reservation.public_id)

    def test_owner_confirms_from_the_dashboard(self):
        url = reverse("dashboard:reservation_action", args=[self.reservation.public_id])
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, {"accion": "confirmar", "mensaje": "¡Os esperamos!"})
        self.reservation.refresh_from_db()
        self.assertEqual((self.reservation.status, self.reservation.owner_message), (Status.CONFIRMED, "¡Os esperamos!"))
        response = self.client.post(url, {"accion": "rechazar"}, follow=True)
        self.assertContains(response, "no puede pasar a")
        response = self.client.post(url, {"accion": "borrar"}, follow=True)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Status.CONFIRMED)

    def test_owner_creates_edits_and_publishes_events(self):
        starts = (timezone.localtime() + datetime.timedelta(days=5)).strftime("%Y-%m-%dT%H:%M")
        response = self.client.post(
            reverse("dashboard:event_create"),
            {"title": "Noche de IPA", "summary": "", "description": "", "starts_at": starts, "capacity": "30", "accepts_reservations": "on"},
        )
        self.assertRedirects(response, reverse("dashboard:events"))
        event = Event.objects.get(title="Noche de IPA")
        self.assertEqual(event.status, Event.Status.DRAFT)
        self.client.post(reverse("dashboard:event_status", args=[event.public_id]), {"estado": "PUBLISHED"})
        event.refresh_from_db()
        self.assertEqual(event.status, Event.Status.PUBLISHED)
        self.client.post(
            reverse("dashboard:event_edit", args=[event.public_id]),
            {"title": "Noche de IPA y APA", "starts_at": starts, "capacity": "30", "accepts_reservations": "on"},
        )
        event.refresh_from_db()
        self.assertEqual(event.title, "Noche de IPA y APA")
        response = self.client.get(reverse("dashboard:events"))
        self.assertContains(response, "Noche de IPA y APA")
        # La tabla se ajusta al ancho (tarjetas en pantallas estrechas): cada celda lleva su etiqueta
        self.assertContains(response, 'class="data-table data-table-fit"')
        self.assertContains(response, "data-label=", count=7)  # un evento × 7 columnas

    def test_home_shows_reservation_figures(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, 'data-stat="reservations">1<', html=False)

    def test_campaign_flow_from_dashboard(self):
        response = self.client.post(
            reverse("dashboard:campaign_create"),
            {"name": "Otoño", "channel": "EMAIL", "subject": "Nueva cerveza", "body": "Ya está aquí."},
        )
        self.assertRedirects(response, reverse("dashboard:communications"))
        from apps.notifications.models import Campaign

        campaign = Campaign.objects.get()
        self.client.post(reverse("dashboard:campaign_queue", args=[campaign.public_id]))
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.QUEUED)
        self.assertEqual(mail.outbox, [])  # la petición web no envía
