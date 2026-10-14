"""API v1 del personal (compras y canjes en barra) y del propietario (estadísticas y reservas)."""
from apps.events.models import Reservation
from apps.purchases.models import Purchase
from apps.rewards.models import Redemption
from tests.events.factories import reserve
from tests.loyalty.factories import make_customer_with_qr, make_employee, make_owner, make_verified_customer
from tests.rewards.factories import give_points, make_reward, redeem

from .base import ApiTestCase, api_url


class StaffPermissionTests(ApiTestCase):
    def test_customers_and_anonymous_are_rejected(self):
        customer, token = make_customer_with_qr()
        for user in (None, customer):
            if user:
                self.authenticate(user)
            for name in ("staff_identify", "staff_purchases", "staff_redemption_lookup", "staff_redemption_validate"):
                with self.subTest(name=name, user=user):
                    response = self.post(name, {"qr_code": token, "amount": "5", "code": "x"}, key=self.new_key())
                    self.assertEqual(response.status_code, 401 if user is None else 403)
        self.assertFalse(Purchase.objects.exists())


class StaffPurchaseTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.customer, self.token = make_customer_with_qr()
        self.employee = make_employee()
        self.authenticate(self.employee)

    def test_identify_returns_only_the_short_name(self):
        body = self.post("staff_identify", {"qr_code": self.token}).json()
        self.assertEqual(body, {"display_name": "Lúa F."})
        invalid = self.post("staff_identify", {"qr_code": "CF1:NOEXISTE"})
        self.assertEqual((invalid.status_code, invalid.json()["code"]), (400, "invalid_qr"))

    def test_register_purchase_is_idempotent_and_points_are_server_side(self):
        key = self.new_key()
        payload = {"qr_code": self.token, "amount": "12.50", "points": 9999, "customer": "otro"}
        created = self.post("staff_purchases", payload, key=key)
        self.assertEqual(created.status_code, 201, created.json())
        body = created.json()
        self.assertEqual((body["amount"], body["points"], body["customer_name"]), ("12.50", 12, "Lúa F."))
        self.assertNotIn("email", str(body))
        self.assertEqual(self.post("staff_purchases", payload, key=key).status_code, 200)
        conflict = self.post("staff_purchases", {**payload, "amount": "20.00"}, key=key)
        self.assertEqual((conflict.status_code, conflict.json()["code"]), (409, "idempotency_conflict"))
        self.assertEqual(Purchase.objects.count(), 1)

    def test_invalid_amount_and_missing_key(self):
        bad = self.post("staff_purchases", {"qr_code": self.token, "amount": "-3"}, key=self.new_key())
        self.assertEqual((bad.status_code, bad.json()["code"]), (400, "amount_min"))
        no_key = self.post("staff_purchases", {"qr_code": self.token, "amount": "3"})
        self.assertEqual(no_key.json()["code"], "idempotency_invalid")


class StaffRedemptionTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        customer = make_verified_customer()
        give_points(customer, 100)
        self.redemption = redeem(customer, make_reward()).redemption
        self.authenticate(make_employee())

    def test_lookup_and_validate_once(self):
        code = self.redemption.code
        preview = self.post("staff_redemption_lookup", {"code": code}).json()
        self.assertTrue(preview["can_validate"])
        self.assertEqual(preview["customer_name"], "Lúa F.")
        self.assertNotIn("email", preview)
        validated = self.post("staff_redemption_validate", {"code": code})
        self.assertEqual(validated.status_code, 200)
        self.assertEqual(validated.json()["status"], Redemption.Status.USED)
        again = self.post("staff_redemption_validate", {"code": code})
        self.assertEqual((again.status_code, again.json()["code"]), (409, "code_used"))
        unknown = self.post("staff_redemption_lookup", {"code": "AAAA-BBBB-CCCC"})
        self.assertEqual((unknown.status_code, unknown.json()["code"]), (400, "invalid_code"))


class OwnerTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.owner = make_owner()
        self.customer = make_verified_customer()
        self.reservation = reserve(self.customer).reservation

    def test_only_owner(self):
        for user in (self.customer, make_employee()):
            self.authenticate(user)
            with self.subTest(role=user.role):
                self.assertEqual(self.client.get(api_url("owner_stats")).status_code, 403)
                self.assertEqual(self.client.get(api_url("owner_reservations")).status_code, 403)
                response = self.post("owner_reservation_transition", None, self.reservation.public_id, "confirm")
                self.assertEqual(response.status_code, 403)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.PENDING)

    def test_stats_are_aggregated(self):
        self.authenticate(self.owner)
        body = self.client.get(api_url("owner_stats"), {"date_from": "2026-01-01", "date_to": "2026-12-31"}).json()
        self.assertEqual(body["customers"]["total"], 1)
        self.assertIsNone(body["purchases"]["business_revenue"])
        self.assertEqual(body["reservations"]["pending_now"], 1)
        self.assertNotIn("cliente@example.com", str(body))
        invalid = self.client.get(api_url("owner_stats"), {"date_from": "2026-12-31", "date_to": "2026-01-01"})
        self.assertEqual(invalid.status_code, 400)

    def test_reservations_without_contact_and_transitions(self):
        self.authenticate(self.owner)
        listing = self.client.get(api_url("owner_reservations"), {"status": "PENDING"}).json()
        self.assertEqual(listing["count"], 1)
        row = listing["results"][0]
        self.assertEqual(row["customer_name"], "Lúa F.")
        self.assertFalse({"email", "phone_number", "notes", "address_line_1"} & set(row))
        self.assertEqual(self.client.get(api_url("owner_reservations"), {"status": "XX"}).status_code, 400)

        confirm = self.post("owner_reservation_transition", {"message": "¡Os esperamos!"}, self.reservation.public_id, "confirm")
        self.assertEqual(confirm.status_code, 200, confirm.json())
        self.assertEqual(confirm.json()["status"], Reservation.Status.CONFIRMED)
        invalid = self.post("owner_reservation_transition", None, self.reservation.public_id, "reject")
        self.assertEqual((invalid.status_code, invalid.json()["code"]), (409, "invalid_transition"))
        self.assertEqual(self.post("owner_reservation_transition", None, self.reservation.public_id, "borrar").status_code, 404)
