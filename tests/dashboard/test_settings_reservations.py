"""
Dashboard → Configuración → Reservas online (Fase 17): interruptor del
propietario, enlaces públicos, bloqueo en servidor (web, servicio y API) y
reservas existentes intactas.
"""
import uuid

from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.core.models import AuditEvent
from apps.events.models import Reservation
from apps.web import services as web
from tests.api.base import ApiTestCase, api_url
from tests.events.factories import make_event, reserve, table_time
from tests.loyalty.factories import make_verified_customer
from tests.rewards.factories import make_customer_with_qr, make_employee, make_owner

SETTINGS_URL = reverse("dashboard:settings")
TOGGLE_URL = reverse("dashboard:settings_reservations")
CONTACT_RESERVATIONS = reverse("web:contact") + "#reservas"


def audit_count():
    return AuditEvent.objects.filter(
        action=AuditEvent.Action.SITE_CONTENT_UPDATED, metadata__fields=["online_reservations_enabled"]
    ).count()


class ReservationsToggleTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.customer, _ = make_customer_with_qr()
        self.employee = make_employee()
        self.owner = make_owner()

    def set_enabled(self, enabled):
        with self.captureOnCommitCallbacks(execute=True):
            return web.set_online_reservations(actor=self.owner, enabled=enabled)


class SettingsViewTests(ReservationsToggleTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)

    def post(self, data):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(TOGGLE_URL, data)

    def test_enabled_by_default_and_shown_in_settings(self):
        self.assertTrue(web.online_reservations_enabled())
        response = self.client.get(SETTINGS_URL)
        self.assertContains(response, "data-reservations-settings")
        self.assertContains(response, 'name="reservas-enabled"')
        self.assertContains(response, 'data-reservations-status="on"')

    def test_owner_disables_and_enables(self):
        response = self.post({})
        self.assertRedirects(response, SETTINGS_URL)
        self.assertFalse(web.online_reservations_enabled())
        self.assertContains(self.client.get(SETTINGS_URL), 'data-reservations-status="off"')
        self.post({"reservas-enabled": "on"})
        self.assertTrue(web.online_reservations_enabled())
        self.assertEqual(audit_count(), 2)
        event = AuditEvent.objects.filter(action=AuditEvent.Action.SITE_CONTENT_UPDATED).first()
        self.assertEqual((event.actor, event.metadata["enabled"]), (self.owner, True))

    def test_repeating_the_same_value_changes_nothing(self):
        response = self.client.post(TOGGLE_URL, {"reservas-enabled": "on"})
        self.assertRedirects(response, SETTINGS_URL)
        self.assertTrue(web.online_reservations_enabled())
        self.assertEqual(audit_count(), 0)

    def test_warns_when_there_is_no_phone(self):
        self.assertContains(self.client.get(SETTINGS_URL), "data-reservations-no-phone")
        web.update_business_info(actor=self.owner, data={"phone": "+34 600 000 000"})
        cache.clear()
        self.assertNotContains(self.client.get(SETTINGS_URL), "data-reservations-no-phone")

    def test_only_post_is_allowed(self):
        self.assertEqual(self.client.get(TOGGLE_URL).status_code, 405)

    def test_employee_and_customer_are_forbidden(self):
        for user in (self.employee, self.customer):
            self.client.force_login(user)
            self.assertEqual(self.client.post(TOGGLE_URL, {}).status_code, 403)
        self.assertTrue(web.online_reservations_enabled())

    def test_anonymous_is_sent_to_login(self):
        self.client.logout()
        response = self.client.post(TOGGLE_URL, {})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertTrue(web.online_reservations_enabled())


class ServiceTests(ReservationsToggleTestCase):
    def test_only_the_owner_can_toggle(self):
        for user in (self.employee, self.customer):
            with self.assertRaises(PermissionDenied):
                web.set_online_reservations(actor=user, enabled=False)
        self.assertTrue(web.online_reservations_enabled())

    def test_content_form_cannot_change_the_flag(self):
        # Lista blanca de `update_business_info`: el campo no es editable desde Contenido.
        web.update_business_info(actor=self.owner, data={"address": "Rúa Ficticia 1", "online_reservations_enabled": False})
        cache.clear()
        self.assertTrue(web.online_reservations_enabled())

    def test_disabled_rejects_new_reservations(self):
        customer = make_verified_customer("reservas@example.com")
        self.set_enabled(False)
        with self.assertRaises(ValidationError) as ctx:
            reserve(customer)
        self.assertEqual(ctx.exception.code, "reservations_disabled")
        with self.assertRaises(ValidationError):
            reserve(customer, event=make_event())
        self.assertFalse(Reservation.objects.exists())


class PublicPagesTests(ReservationsToggleTestCase):
    def setUp(self):
        super().setUp()
        self.event = make_event()

    def test_enabled_links_go_to_the_reservation_system(self):
        self.assertContains(self.client.get(reverse("web:events")), reverse("events:reservation_new"))
        detail = self.client.get(reverse("events:event_detail", args=[self.event.public_id]))
        self.assertContains(detail, reverse("events:event_reservation_new", args=[self.event.public_id]))
        self.assertNotContains(self.client.get(reverse("web:contact")), "data-phone-reservations")

    def test_disabled_links_go_to_contact(self):
        self.set_enabled(False)
        events = self.client.get(reverse("web:events"))
        self.assertNotContains(events, reverse("events:reservation_new"))
        self.assertContains(events, CONTACT_RESERVATIONS)
        detail = self.client.get(reverse("events:event_detail", args=[self.event.public_id]))
        self.assertNotContains(detail, reverse("events:event_reservation_new", args=[self.event.public_id]))
        self.assertContains(detail, CONTACT_RESERVATIONS)
        self.client.force_login(self.customer)
        mine = self.client.get(reverse("events:my_reservations"))
        self.assertNotContains(mine, reverse("events:reservation_new"))
        self.assertContains(mine, CONTACT_RESERVATIONS)

    def test_contact_shows_phone_notice(self):
        self.set_enabled(False)
        contact = self.client.get(reverse("web:contact"))
        self.assertContains(contact, 'id="reservas"')
        self.assertContains(contact, "data-phone-reservations")
        web.update_business_info(actor=self.owner, data={"phone": "+34 600 000 000"})
        cache.clear()
        self.assertContains(self.client.get(reverse("web:contact")), 'href="tel:+34 600 000 000"')


class ReservationViewsTests(ReservationsToggleTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.customer)
        self.event = make_event()

    def test_disabled_forms_redirect_to_contact_and_create_nothing(self):
        existing = reserve(self.customer).reservation
        self.set_enabled(False)
        table = reverse("events:reservation_new")
        event = reverse("events:event_reservation_new", args=[self.event.public_id])
        when = table_time(days=4)
        table_data = {"date": when.date().isoformat(), "time": "21:00", "party_size": "2", "idempotency_key": str(uuid.uuid4())}
        event_data = {"party_size": "2", "idempotency_key": str(uuid.uuid4())}
        for url, data in ((table, table_data), (event, event_data)):
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), CONTACT_RESERVATIONS, fetch_redirect_response=False)
                self.assertRedirects(self.client.post(url, data), CONTACT_RESERVATIONS, fetch_redirect_response=False)
        self.assertEqual(list(Reservation.objects.all()), [existing])

    def test_existing_reservations_stay_visible_and_cancellable(self):
        own = reserve(self.customer).reservation
        self.set_enabled(False)
        detail = reverse("events:reservation_detail", args=[own.public_id])
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.client.post(reverse("events:reservation_cancel", args=[own.public_id]))
        own.refresh_from_db()
        self.assertEqual(own.status, Reservation.Status.CANCELLED)


class ApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.owner = make_owner()
        self.customer = make_verified_customer()
        self.event = make_event()
        with self.captureOnCommitCallbacks(execute=True):
            web.set_online_reservations(actor=self.owner, enabled=False)
        self.authenticate(self.customer)

    def test_events_are_not_bookable_and_post_is_rejected(self):
        body = self.client.get(api_url("events")).json()
        self.assertFalse(body["results"][0]["bookable"])
        payload = {"event": str(self.event.public_id), "party_size": 2}
        response = self.post("reservations", payload, key=self.new_key())
        self.assertEqual((response.status_code, response.json()["code"]), (409, "reservations_disabled"))
        table = self.post("reservations", {"requested_for": table_time().isoformat(), "party_size": 2}, key=self.new_key())
        self.assertEqual(table.status_code, 409)
        self.assertFalse(Reservation.objects.exists())
