"""API v1 del cliente: puntos, compras, QR, recompensas, canjes, eventos y reservas."""
import datetime

from django.test import override_settings
from django.utils import timezone

from apps.events.models import Event, Reservation
from apps.loyalty import ledger
from apps.loyalty import services as loyalty
from apps.notifications.models import Notification
from apps.rewards.models import Redemption, Reward
from tests.events.factories import make_event, reserve, table_time
from tests.loyalty.factories import buy, make_customer_with_qr, make_employee, make_verified_customer
from tests.rewards.factories import give_points, make_reward, redeem

from .base import ApiTestCase, api_url


class PointsAndPurchasesTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.customer, token = make_customer_with_qr()
        self.other, other_token = make_customer_with_qr("otra@example.com")
        staff = make_employee()
        self.purchase = buy(staff, token, "12.50")
        buy(staff, other_token, "40.00")
        self.authenticate(self.customer)

    def test_summary_movements_and_purchases_are_only_mine(self):
        self.assertEqual(self.client.get(api_url("points")).json(), {"balance": 12, "earned": 12, "used": 0, "corrected": 0, "expired": 0})
        movements = self.client.get(api_url("movements")).json()
        self.assertEqual(movements["count"], 1)
        movement = movements["results"][0]
        self.assertEqual(movement["purchase"], str(self.purchase.public_id))
        self.assertFalse({"id", "reason", "created_by", "idempotency_key", "rule"} & set(movement))
        purchases = self.client.get(api_url("purchases")).json()
        self.assertEqual(purchases["count"], 1)
        self.assertEqual(purchases["results"][0]["amount"], "12.50")
        self.assertEqual(purchases["results"][0]["points"], 12)
        self.assertNotIn("registered_by", purchases["results"][0])

    def test_other_roles_and_anonymous(self):
        self.authenticate(make_employee("e2@example.com"))
        self.assertEqual(self.client.get(api_url("points")).status_code, 403)
        self.anonymous()
        self.assertEqual(self.client.get(api_url("points")).status_code, 401)


class QRCodeTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_verified_customer()
        self.authenticate(self.customer)

    def test_get_and_rotate(self):
        first = self.client.get(api_url("qr")).json()
        self.assertTrue(first["payload"].startswith("CF1:"))
        rotated = self.post("qr_rotate").json()
        self.assertNotEqual(rotated["payload"], first["payload"])
        self.assertIsNotNone(rotated["rotated_at"])

    @override_settings(LOYALTY_QR_MAX_ROTATIONS_PER_DAY=2)
    def test_rotation_limit(self):
        self.post("qr_rotate")
        self.post("qr_rotate")
        response = self.post("qr_rotate")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["code"], "rate_limited")


class RewardsAndRedemptionsTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_verified_customer()
        self.reward = make_reward()
        give_points(self.customer, 120)
        self.authenticate(self.customer)

    def test_public_list_hides_management_data(self):
        make_reward(name="Borrador", status=Reward.Status.DRAFT)
        self.anonymous()
        body = self.client.get(api_url("rewards")).json()
        self.assertEqual(body["count"], 1)
        self.assertFalse({"id", "status", "stock", "position"} & set(body["results"][0]))
        self.assertEqual(self.client.get(api_url("reward", self.reward.public_id)).status_code, 200)
        draft = Reward.objects.get(name="Borrador")
        self.assertEqual(self.client.get(api_url("reward", draft.public_id)).status_code, 404)

    def test_redeem_is_idempotent(self):
        key = self.new_key()
        created = self.post("redeem", None, self.reward.public_id, key=key)
        self.assertEqual(created.status_code, 201, created.json())
        self.assertIsNotNone(created.json()["code"])
        retry = self.post("redeem", None, self.reward.public_id, key=key)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json()["public_id"], created.json()["public_id"])
        self.assertEqual(ledger.balance(self.customer), 70)

    def test_redeem_errors(self):
        missing_key = self.post("redeem", None, self.reward.public_id)
        self.assertEqual((missing_key.status_code, missing_key.json()["code"]), (400, "idempotency_invalid"))
        self.post("redeem", None, self.reward.public_id, key=self.new_key())
        duplicate = self.post("redeem", None, self.reward.public_id, key=self.new_key())
        self.assertEqual((duplicate.status_code, duplicate.json()["code"]), (409, "duplicate_pending"))
        expensive = make_reward(name="Barril", points_cost=1000)
        poor = self.post("redeem", None, expensive.public_id, key=self.new_key())
        self.assertEqual((poor.status_code, poor.json()["code"]), (400, "insufficient_points"))

    def test_points_cost_cannot_be_sent_by_the_client(self):
        response = self.client.post(
            api_url("redeem", self.reward.public_id), {"points_cost": 1, "status": "USED"}, format="json",
            HTTP_IDEMPOTENCY_KEY=str(self.new_key()),
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["points_cost"], 50)
        self.assertEqual(response.json()["status"], Redemption.Status.PENDING)

    def test_list_without_codes_detail_and_cancel_only_mine(self):
        mine = redeem(self.customer, self.reward).redemption
        other = make_verified_customer("otra@example.com")
        give_points(other, 100)
        theirs = redeem(other, self.reward).redemption

        listing = self.client.get(api_url("redemptions")).json()
        self.assertEqual(listing["count"], 1)
        self.assertNotIn("code", listing["results"][0])
        self.assertIsNotNone(self.client.get(api_url("redemption", mine.public_id)).json()["code"])
        self.assertEqual(self.client.get(api_url("redemption", theirs.public_id)).status_code, 404)
        self.assertEqual(self.post("redemption_cancel", None, theirs.public_id).status_code, 404)

        cancelled = self.post("redemption_cancel", None, mine.public_id)
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.json()["status"], Redemption.Status.CANCELLED)
        self.assertIsNone(cancelled.json()["code"])
        self.assertEqual(ledger.balance(self.customer), 120)
        self.assertEqual(self.post("redemption_cancel", None, mine.public_id).status_code, 200)  # idempotente


class EventsAndReservationsTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_verified_customer()
        self.event = make_event()
        self.authenticate(self.customer)

    def test_public_events(self):
        make_event(title="Borrador", status=Event.Status.DRAFT)
        self.anonymous()
        body = self.client.get(api_url("events")).json()
        self.assertEqual(body["count"], 1)
        self.assertTrue(body["results"][0]["bookable"])
        self.assertNotIn("status", body["results"][0])
        detail = self.client.get(api_url("event", self.event.public_id)).json()
        self.assertEqual(detail["seats_left"], 10)
        draft = Event.objects.get(title="Borrador")
        self.assertEqual(self.client.get(api_url("event", draft.public_id)).status_code, 404)

    def test_event_reservation_is_idempotent_and_ignores_status(self):
        key = self.new_key()
        payload = {"event": str(self.event.public_id), "party_size": 2, "status": "CONFIRMED", "notes": "Sin gluten"}
        created = self.post("reservations", payload, key=key)
        self.assertEqual(created.status_code, 201, created.json())
        self.assertEqual(created.json()["status"], Reservation.Status.PENDING)
        # Mismo servicio que la web: aviso al cliente (sin las notas) en la cola de notificaciones.
        notice = Notification.objects.get(kind=Notification.Kind.RESERVATION_RECEIVED)
        self.assertEqual(notice.recipient, self.customer)
        self.assertNotIn("Sin gluten", str(notice.context))
        retry = self.post("reservations", payload, key=key)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(Reservation.objects.count(), 1)
        again = self.post("reservations", payload, key=self.new_key())
        self.assertEqual((again.status_code, again.json()["code"]), (409, "already_reserved"))

    def test_table_reservation_and_validation(self):
        when = table_time().isoformat()
        self.assertEqual(self.post("reservations", {"requested_for": when, "party_size": 4}, key=self.new_key()).status_code, 201)
        missing = self.post("reservations", {"party_size": 2}, key=self.new_key())
        self.assertIn("requested_for", missing.json()["fields"])
        past = (timezone.now() - datetime.timedelta(hours=1)).isoformat()
        self.assertEqual(self.post("reservations", {"requested_for": past, "party_size": 2}, key=self.new_key()).status_code, 400)
        too_many = self.post("reservations", {"requested_for": when, "party_size": 45}, key=self.new_key())
        self.assertIn("party_size", too_many.json()["fields"])
        unknown = self.post("reservations", {"event": str(self.new_key()), "party_size": 2}, key=self.new_key())
        self.assertEqual(unknown.json()["code"], "event_not_found")

    def test_detail_and_cancel_only_mine(self):
        mine = reserve(self.customer).reservation
        other = make_verified_customer("otra@example.com")
        theirs = reserve(other).reservation
        self.assertEqual(self.client.get(api_url("reservations")).json()["count"], 1)
        self.assertEqual(self.client.get(api_url("reservation", theirs.public_id)).status_code, 404)
        self.assertEqual(self.post("reservation_cancel", None, theirs.public_id).status_code, 404)
        response = self.post("reservation_cancel", None, mine.public_id)
        self.assertEqual(response.json()["status"], Reservation.Status.CANCELLED)
        theirs.refresh_from_db()
        self.assertEqual(theirs.status, Reservation.Status.PENDING)

    def test_staff_cannot_reserve(self):
        self.authenticate(make_employee())
        response = self.post("reservations", {"event": str(self.event.public_id), "party_size": 2}, key=self.new_key())
        self.assertEqual(response.status_code, 403)


class LoyaltyQRIdentityTests(ApiTestCase):
    def test_qr_belongs_to_the_authenticated_customer(self):
        customer = make_verified_customer()
        self.authenticate(customer)
        payload = self.client.get(api_url("qr")).json()["payload"]
        self.assertEqual(loyalty.identify_customer(payload), customer)
