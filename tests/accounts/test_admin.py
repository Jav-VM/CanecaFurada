from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import AuditEvent

from .factories import PASSWORD, make_user


class UserAdminTests(TestCase):
    def setUp(self):
        self.owner = make_user(email="o@example.com", role=User.Role.OWNER)
        self.employee = make_user(email="e@example.com", role=User.Role.EMPLOYEE)
        self.customer = make_user(email="c@example.com")
        self.changelist = reverse("admin:accounts_user_changelist")

    def test_admin_url_is_configurable(self):
        self.assertTrue(self.changelist.startswith("/" + settings.ADMIN_URL))

    def test_non_owners_cannot_access_admin(self):
        for user in (self.employee, self.customer):
            self.client.force_login(user)
            with self.subTest(role=user.role):
                response = self.client.get(self.changelist)
                self.assertEqual(response.status_code, 302)
                self.assertIn("login", response["Location"])

    def test_owner_creates_employee_through_service(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("admin:accounts_user_add"),
            {
                "email": "Nuevo@Example.com",
                "first_name": "Nuevo",
                "last_name": "Ficticio",
                "role": User.Role.EMPLOYEE,
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="nuevo@example.com")
        self.assertEqual(user.role, User.Role.EMPLOYEE)
        self.assertFalse(user.is_staff)
        event = AuditEvent.objects.get(action=AuditEvent.Action.EMPLOYEE_CREATED)
        self.assertEqual(event.actor, self.owner)

    def test_change_form_cannot_alter_role_or_staff_flags(self):
        self.client.force_login(self.owner)
        url = reverse("admin:accounts_user_change", args=[self.customer.pk])
        self.client.post(
            url,
            {
                "email": self.customer.email,
                "first_name": "Ana",
                "last_name": "Cambiada",
                "is_active": "on",
                "role": User.Role.OWNER,
                "is_staff": "on",
                "is_superuser": "on",
            },
        )
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.last_name, "Cambiada")
        self.assertEqual(self.customer.role, User.Role.CUSTOMER)
        self.assertFalse(self.customer.is_staff or self.customer.is_superuser)

    def test_role_action_uses_service_and_audits(self):
        self.client.force_login(self.owner)
        self.client.post(
            self.changelist,
            {"action": "make_employee", "_selected_action": [self.customer.pk]},
        )
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.role, User.Role.EMPLOYEE)
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.Action.ROLE_CHANGED).exists())

    def test_role_action_protects_last_owner(self):
        self.client.force_login(self.owner)
        self.client.post(
            self.changelist,
            {"action": "make_customer", "_selected_action": [self.owner.pk]},
        )
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.role, User.Role.OWNER)

    def test_last_owner_cannot_be_deactivated(self):
        self.client.force_login(self.owner)
        url = reverse("admin:accounts_user_change", args=[self.owner.pk])
        response = self.client.post(
            url,
            {"email": self.owner.email, "first_name": "D", "last_name": "F"},  # is_active ausente = False
        )
        self.assertEqual(response.status_code, 200)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)

    def test_users_cannot_be_deleted_from_admin(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("admin:accounts_user_delete", args=[self.customer.pk]))
        self.assertEqual(response.status_code, 403)
