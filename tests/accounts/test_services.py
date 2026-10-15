from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.accounts import services
from apps.accounts.models import User
from apps.core.models import AuditEvent

from .factories import PASSWORD, make_user

NEW = {"first_name": "Nuevo", "last_name": "Ficticio", "password": PASSWORD}


class CreateCustomerTests(TestCase):
    def test_creates_customer_with_audit(self):
        user = services.create_customer(email="Nuevo@Example.com", **NEW)
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertEqual(user.email, "nuevo@example.com")
        self.assertTrue(user.check_password(PASSWORD))
        event = AuditEvent.objects.get(action=AuditEvent.Action.CUSTOMER_CREATED)
        self.assertEqual(event.target_public_id, user.public_id)
        self.assertIsNone(event.actor)

    def test_public_signup_cannot_choose_role(self):
        with self.assertRaises(TypeError):
            services.create_customer(email="x@example.com", role=User.Role.OWNER, **NEW)

    def test_weak_password_rejected(self):
        with self.assertRaises(ValidationError):
            services.create_customer(email="x@example.com", **{**NEW, "password": "1234"})
        self.assertFalse(User.objects.exists())

    def test_duplicate_email_rejected(self):
        make_user(email="x@example.com")
        with self.assertRaises(ValidationError):
            services.create_customer(email="X@example.com", **NEW)

    def test_required_names(self):
        with self.assertRaises(ValidationError):
            services.create_customer(email="x@example.com", **{**NEW, "first_name": ""})

    def test_audit_metadata_contains_no_personal_data(self):
        services.create_customer(email="x@example.com", **NEW)
        event = AuditEvent.objects.get()
        self.assertEqual(event.metadata, {"role": "CUSTOMER"})


class CreateEmployeeTests(TestCase):
    def setUp(self):
        self.owner = make_user(email="dueno@example.com", role=User.Role.OWNER)

    def test_owner_creates_employee(self):
        employee = services.create_employee(actor=self.owner, email="e@example.com", **NEW)
        self.assertEqual(employee.role, User.Role.EMPLOYEE)
        self.assertFalse(employee.is_staff)
        event = AuditEvent.objects.get(action=AuditEvent.Action.EMPLOYEE_CREATED)
        self.assertEqual(event.actor, self.owner)

    def test_non_owners_cannot_create_employees(self):
        actors = [
            make_user(email="c@example.com"),
            make_user(email="e@example.com", role=User.Role.EMPLOYEE),
            AnonymousUser(),
            None,
        ]
        for actor in actors:
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                services.create_employee(actor=actor, email="nuevo@example.com", **NEW)
        self.assertFalse(User.objects.filter(email="nuevo@example.com").exists())

    def test_inactive_owner_cannot_create_employees(self):
        User.objects.filter(pk=self.owner.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            services.create_employee(actor=self.owner, email="n@example.com", **NEW)

    def test_stale_in_memory_role_is_not_trusted(self):
        employee = make_user(email="e@example.com", role=User.Role.EMPLOYEE)
        employee.role = User.Role.OWNER  # manipulación en memoria, no en BD
        with self.assertRaises(PermissionDenied):
            services.create_employee(actor=employee, email="n@example.com", **NEW)


class CreateOwnerTests(TestCase):
    def test_first_owner_without_actor(self):
        owner = services.create_owner(email="dueno@example.com", **NEW)
        self.assertEqual(owner.role, User.Role.OWNER)
        self.assertTrue(owner.is_staff and owner.is_superuser)
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.Action.OWNER_CREATED).exists())

    def test_second_owner_without_actor_is_denied(self):
        services.create_owner(email="dueno@example.com", **NEW)
        with self.assertRaises(PermissionDenied):
            services.create_owner(email="otro@example.com", **NEW)

    def test_owner_can_create_another_owner(self):
        first = services.create_owner(email="dueno@example.com", **NEW)
        second = services.create_owner(actor=first, email="otro@example.com", **NEW)
        self.assertEqual(second.role, User.Role.OWNER)

    def test_employee_cannot_create_owner(self):
        services.create_owner(email="dueno@example.com", **NEW)
        employee = make_user(email="e@example.com", role=User.Role.EMPLOYEE)
        with self.assertRaises(PermissionDenied):
            services.create_owner(actor=employee, email="otro@example.com", **NEW)


class ChangeRoleTests(TestCase):
    def setUp(self):
        self.owner = make_user(email="dueno@example.com", role=User.Role.OWNER)
        self.customer = make_user(email="c@example.com")

    def test_owner_promotes_customer_to_employee(self):
        services.change_role(actor=self.owner, user=self.customer, new_role=User.Role.EMPLOYEE)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.role, User.Role.EMPLOYEE)
        self.assertFalse(self.customer.is_staff)
        event = AuditEvent.objects.get(action=AuditEvent.Action.ROLE_CHANGED)
        self.assertEqual(event.metadata, {"from": "CUSTOMER", "to": "EMPLOYEE"})
        self.assertEqual(event.actor, self.owner)

    def test_promotion_to_owner_grants_admin_flags(self):
        services.change_role(actor=self.owner, user=self.customer, new_role=User.Role.OWNER)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_staff and self.customer.is_superuser)

    def test_demoted_owner_loses_admin_flags(self):
        other = make_user(email="otro@example.com", role=User.Role.OWNER)
        services.change_role(actor=self.owner, user=other, new_role=User.Role.EMPLOYEE)
        other.refresh_from_db()
        self.assertFalse(other.is_staff or other.is_superuser)

    def test_privilege_escalation_denied(self):
        employee = make_user(email="e@example.com", role=User.Role.EMPLOYEE)
        attempts = [
            (self.customer, self.customer, User.Role.OWNER),
            (self.customer, self.customer, User.Role.EMPLOYEE),
            (employee, employee, User.Role.OWNER),
            (employee, self.customer, User.Role.EMPLOYEE),
        ]
        for actor, target, role in attempts:
            with self.subTest(actor=actor.role, role=role), self.assertRaises(PermissionDenied):
                services.change_role(actor=actor, user=target, new_role=role)
        self.customer.refresh_from_db()
        employee.refresh_from_db()
        self.assertEqual(self.customer.role, User.Role.CUSTOMER)
        self.assertEqual(employee.role, User.Role.EMPLOYEE)
        self.assertFalse(AuditEvent.objects.exists())

    def test_last_active_owner_cannot_be_demoted(self):
        with self.assertRaises(ValidationError):
            services.change_role(actor=self.owner, user=self.owner, new_role=User.Role.CUSTOMER)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.role, User.Role.OWNER)

    def test_owner_can_step_down_if_another_active_owner_exists(self):
        make_user(email="otro@example.com", role=User.Role.OWNER)
        services.change_role(actor=self.owner, user=self.owner, new_role=User.Role.EMPLOYEE)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.role, User.Role.EMPLOYEE)

    def test_invalid_role_rejected(self):
        with self.assertRaises(ValidationError):
            services.change_role(actor=self.owner, user=self.customer, new_role="ADMIN")

    def test_same_role_is_noop_without_audit(self):
        services.change_role(actor=self.owner, user=self.customer, new_role=User.Role.CUSTOMER)
        self.assertFalse(AuditEvent.objects.exists())

    def test_inactive_owner_can_be_demoted_with_a_single_active_owner(self):
        inactive = make_user(email="inactivo@example.com", role=User.Role.OWNER, is_active=False)
        services.change_role(actor=self.owner, user=inactive, new_role=User.Role.EMPLOYEE)
        inactive.refresh_from_db()
        self.assertEqual(inactive.role, User.Role.EMPLOYEE)

    def test_last_owner_message_is_kept(self):
        with self.assertRaisesMessage(ValidationError, "No se puede retirar el rol al último propietario activo."):
            services.change_role(actor=self.owner, user=self.owner, new_role=User.Role.EMPLOYEE)


class SetUserActiveTests(TestCase):
    """La regla del último propietario se comprueba en el servicio, no solo en el admin."""

    def setUp(self):
        self.owner = make_user(email="dueno@example.com", role=User.Role.OWNER)

    def test_last_active_owner_cannot_be_deactivated(self):
        with self.assertRaisesMessage(ValidationError, "No se puede desactivar al último propietario activo."):
            services.set_user_active(actor=self.owner, user=self.owner, is_active=False)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)
        self.assertFalse(AuditEvent.objects.exists())

    def test_owner_can_be_deactivated_if_another_active_owner_exists(self):
        other = make_user(email="otro@example.com", role=User.Role.OWNER)
        services.set_user_active(actor=self.owner, user=other, is_active=False)
        other.refresh_from_db()
        self.assertFalse(other.is_active)
        event = AuditEvent.objects.get()
        self.assertEqual(event.action, AuditEvent.Action.ACCOUNT_DEACTIVATED)
        self.assertEqual(event.metadata, {"role": "OWNER"})

    def test_inactive_owner_can_be_reactivated(self):
        other = make_user(email="otro@example.com", role=User.Role.OWNER, is_active=False)
        services.set_user_active(actor=self.owner, user=other, is_active=True)
        other.refresh_from_db()
        self.assertTrue(other.is_active)
        self.assertEqual(AuditEvent.objects.get().action, AuditEvent.Action.ACCOUNT_ACTIVATED)

    def test_same_state_is_noop_without_audit(self):
        employee = make_user(email="e@example.com", role=User.Role.EMPLOYEE)
        services.set_user_active(actor=self.owner, user=employee, is_active=True)
        self.assertFalse(AuditEvent.objects.exists())
