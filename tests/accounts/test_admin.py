from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts import services
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

    def test_owner_deactivates_and_reactivates_employee_with_audit(self):
        self.client.force_login(self.owner)
        self.client.post(
            self.changelist, {"action": "deactivate_users", "_selected_action": [self.employee.pk]}
        )
        self.employee.refresh_from_db()
        self.assertFalse(self.employee.is_active)
        self.client.post(
            self.changelist, {"action": "activate_users", "_selected_action": [self.employee.pk]}
        )
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.is_active)
        actions = list(
            AuditEvent.objects.filter(target_public_id=self.employee.public_id)
            .order_by("id")
            .values_list("action", flat=True)
        )
        self.assertEqual(actions, ["ACCOUNT_DEACTIVATED", "ACCOUNT_ACTIVATED"])

    def test_change_form_deactivation_is_audited(self):
        self.client.force_login(self.owner)
        url = reverse("admin:accounts_user_change", args=[self.employee.pk])
        self.client.post(url, {"email": self.employee.email, "first_name": "E", "last_name": "F"})
        self.employee.refresh_from_db()
        self.assertFalse(self.employee.is_active)
        self.assertTrue(AuditEvent.objects.filter(action="ACCOUNT_DEACTIVATED").exists())

    def test_deactivated_employee_loses_access(self):
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(reverse("accounts:home")).status_code, 200)
        services.set_user_active(actor=self.owner, user=self.employee, is_active=False)
        response = self.client.get(reverse("accounts:home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_non_owner_cannot_change_active_state(self):
        with self.assertRaises(PermissionDenied):
            services.set_user_active(actor=self.employee, user=self.customer, is_active=False)

    def test_last_owner_cannot_be_deactivated_by_action(self):
        self.client.force_login(self.owner)
        self.client.post(self.changelist, {"action": "deactivate_users", "_selected_action": [self.owner.pk]})
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)

    def test_admin_email_edit_resets_verification(self):
        User.objects.filter(pk=self.customer.pk).update(email_verified_at=timezone.now())
        self.client.force_login(self.owner)
        url = reverse("admin:accounts_user_change", args=[self.customer.pk])
        self.client.post(
            url,
            {"email": "corregido@example.com", "first_name": "Ana", "last_name": "F", "is_active": "on",
             "email_verified_at": "2020-01-01 00:00"},
        )
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.email, "corregido@example.com")
        self.assertFalse(self.customer.is_email_verified)

    def test_preference_history_is_read_only(self):
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(reverse("admin:accounts_communicationpreferencechange_add")).status_code, 403
        )

    def test_users_cannot_be_deleted_from_admin(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("admin:accounts_user_delete", args=[self.customer.pk]))
        self.assertEqual(response.status_code, 403)
