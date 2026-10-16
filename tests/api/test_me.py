"""API v1: datos de la cuenta, perfil personal y preferencias del usuario autenticado."""
from apps.accounts.models import CommunicationPreferenceChange, CustomerProfile, User
from tests.accounts.factories import VALID_MOBILE, make_user
from tests.loyalty.factories import make_employee, make_verified_customer

from .base import ApiTestCase, api_url

PERSONAL_FIELDS = {
    "address_line_1", "address_line_2", "postal_code", "date_of_birth", "sex", "phone_number", "promo_email_opt_in",
}


class MeTests(ApiTestCase):
    def test_general_profile_has_no_personal_data(self):
        customer = make_verified_customer(phone_number=VALID_MOBILE)
        self.authenticate(customer)
        body = self.client.get(api_url("me")).json()
        self.assertEqual(body["public_id"], str(customer.public_id))
        self.assertTrue(body["email_verified"])
        self.assertTrue(body["profile_complete"])
        self.assertFalse(PERSONAL_FIELDS & set(body))
        self.assertNotIn("id", body)
        self.assertNotIn("password", body)

    def test_staff_profile_complete_is_null(self):
        self.authenticate(make_employee())
        body = self.client.get(api_url("me")).json()
        self.assertEqual(body["role"], User.Role.EMPLOYEE)
        self.assertIsNone(body["profile_complete"])


class ProfileTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_verified_customer()
        self.authenticate(self.customer)

    def test_get_own_profile(self):
        body = self.client.get(api_url("profile")).json()
        self.assertEqual(body["city"], "A Coruña")
        self.assertEqual(body["missing_fields"], [])
        self.assertNotIn("promo_email_opt_in", body)

    def test_patch_changes_only_sent_fields(self):
        response = self.client.patch(api_url("profile"), {"sex": "FEMALE"}, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["sex"], "FEMALE")
        self.assertEqual(response.json()["first_name"], "Lúa")
        self.assertEqual(CustomerProfile.objects.get(user=self.customer).postal_code, "15001")

    def test_locality_must_belong_to_the_postal_code(self):
        response = self.client.patch(api_url("profile"), {"city": "Santiago de Compostela"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("city", response.json()["fields"])
        response = self.client.patch(
            api_url("profile"), {"postal_code": "15701", "city": "santiago de compostela"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual((response.json()["city"], response.json()["province"]), ("Santiago de Compostela", "A Coruña"))

    def test_invalid_sex(self):
        response = self.client.patch(api_url("profile"), {"sex": "OTRO"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("sex", response.json()["fields"])

    def test_patch_ignores_fields_that_cannot_be_changed_here(self):
        payload = {
            "first_name": "Iria", "email": "otro@example.com", "role": "OWNER",
            "email_verified": False, "public_id": "00000000-0000-0000-0000-000000000000",
        }
        self.assertEqual(self.client.patch(api_url("profile"), payload, format="json").status_code, 200)
        user = User.objects.get(pk=self.customer.pk)
        self.assertEqual(user.first_name, "Iria")
        self.assertEqual((user.email, user.role, user.public_id), ("cliente@example.com", "CUSTOMER", self.customer.public_id))
        self.assertTrue(user.is_email_verified)

    def test_invalid_data(self):
        response = self.client.patch(api_url("profile"), {"postal_code": "ABC"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("postal_code", response.json()["fields"])
        response = self.client.patch(api_url("profile"), {"city": ""}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_date_of_birth_can_change_once_a_year(self):
        first = self.client.patch(api_url("profile"), {"date_of_birth": "1990-03-01"}, format="json")
        self.assertEqual(first.status_code, 200)
        second = self.client.patch(api_url("profile"), {"date_of_birth": "1991-03-01"}, format="json")
        self.assertEqual(second.status_code, 400)
        self.assertIn("date_of_birth", second.json()["fields"])

    def test_staff_has_no_customer_profile(self):
        self.authenticate(make_employee())
        self.assertEqual(self.client.get(api_url("profile")).status_code, 403)
        self.assertEqual(self.client.get(api_url("preferences")).status_code, 403)

    def test_unverified_customer_can_edit_profile_but_not_use_points(self):
        unverified = make_user("pendiente@example.com")
        self.authenticate(unverified)
        self.assertEqual(self.client.get(api_url("profile")).status_code, 200)
        response = self.client.get(api_url("points"))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "email_not_verified")


class PreferencesTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.customer = make_verified_customer()
        self.authenticate(self.customer)

    def test_preferences_default_off_and_change_is_recorded(self):
        self.assertEqual(
            self.client.get(api_url("preferences")).json(), {"promo_email_opt_in": False, "promo_sms_opt_in": False}
        )
        response = self.client.patch(api_url("preferences"), {"promo_email_opt_in": True}, format="json")
        self.assertEqual(response.json(), {"promo_email_opt_in": True, "promo_sms_opt_in": False})
        self.assertTrue(
            CommunicationPreferenceChange.objects.filter(
                user=self.customer, channel="EMAIL", opted_in=True, source="PROFILE"
            ).exists()
        )

    def test_sms_requires_phone(self):
        response = self.client.patch(api_url("preferences"), {"promo_sms_opt_in": True}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("promo_sms_opt_in", response.json()["fields"])

    def test_removing_phone_withdraws_sms_consent(self):
        self.client.patch(api_url("profile"), {"phone_number": VALID_MOBILE}, format="json")
        self.client.patch(api_url("preferences"), {"promo_sms_opt_in": True}, format="json")
        self.client.patch(api_url("profile"), {"phone_number": ""}, format="json")
        self.assertFalse(self.client.get(api_url("preferences")).json()["promo_sms_opt_in"])
