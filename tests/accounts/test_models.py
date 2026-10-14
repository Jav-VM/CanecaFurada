from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User

from .factories import PASSWORD, make_user


class EmailPolicyTests(TestCase):
    def test_email_is_stripped_and_lowercased(self):
        user = make_user(email="  Ana.Perez@Example.COM ")
        self.assertEqual(user.email, "ana.perez@example.com")

    def test_email_is_unique_case_insensitive_via_manager(self):
        make_user(email="ana@example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_user(email="ANA@example.com")

    def test_db_constraint_blocks_case_variant_written_with_update(self):
        make_user(email="ana@example.com")
        other = make_user(email="otra@example.com")
        # update() salta save(): la restricción funcional de BD sigue protegiendo.
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=other.pk).update(email="ANA@example.com")

    def test_full_clean_reports_duplicate_email(self):
        make_user(email="ana@example.com")
        user = User(email="Ana@Example.com", first_name="X", last_name="Y")
        with self.assertRaises(ValidationError):
            user.full_clean(exclude=["password"])

    def test_login_is_case_insensitive(self):
        make_user(email="ana@example.com")
        self.assertIsNotNone(authenticate(username="ANA@Example.com", password=PASSWORD))

    def test_invalid_email_rejected(self):
        user = User(email="no-es-un-email", first_name="X", last_name="Y")
        with self.assertRaises(ValidationError) as ctx:
            user.full_clean(exclude=["password"])
        self.assertIn("email", ctx.exception.message_dict)


class RoleDefaultsTests(TestCase):
    def test_create_user_defaults_to_customer_without_admin_access(self):
        user = make_user()
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser_is_always_owner(self):
        user = User.objects.create_superuser(
            email="dueno@example.com", password=PASSWORD, first_name="D", last_name="F",
            role=User.Role.CUSTOMER,
        )
        self.assertEqual(user.role, User.Role.OWNER)
        self.assertTrue(user.is_staff and user.is_superuser)

    def test_public_id_generated_unique_and_not_editable(self):
        a = make_user(email="a@example.com")
        b = make_user(email="b@example.com")
        self.assertIsNotNone(a.public_id)
        self.assertNotEqual(a.public_id, b.public_id)
        self.assertFalse(User._meta.get_field("public_id").editable)


class RoleConstraintTests(TestCase):
    def test_non_owner_cannot_be_staff(self):
        for role in (User.Role.CUSTOMER, User.Role.EMPLOYEE):
            with self.subTest(role=role), self.assertRaises(IntegrityError), transaction.atomic():
                make_user(email=f"{role.lower()}@example.com", role=role, is_staff=True)

    def test_non_owner_cannot_be_superuser(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_user(role=User.Role.EMPLOYEE, is_superuser=True)

    def test_unknown_role_rejected_by_database(self):
        user = make_user()
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=user.pk).update(role="ADMIN")
