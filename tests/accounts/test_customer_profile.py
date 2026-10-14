from importlib import import_module
from unittest import mock

from django.apps import apps as global_apps
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts import services
from apps.accounts.models import CustomerProfile, User

from .factories import PASSWORD, make_user

NEW = {"first_name": "Nuevo", "last_name": "Ficticio", "password": PASSWORD}


class CustomerProfileCreationTests(TestCase):
    def setUp(self):
        self.owner = make_user(email="dueno@example.com", role=User.Role.OWNER)

    def test_create_customer_creates_profile(self):
        user = services.create_customer(email="c@example.com", **NEW)
        self.assertTrue(CustomerProfile.objects.filter(user=user).exists())

    def test_owner_created_customer_gets_profile(self):
        user = services.create_user_by_owner(
            actor=self.owner, role=User.Role.CUSTOMER, email="c@example.com", **NEW
        )
        self.assertTrue(CustomerProfile.objects.filter(user=user).exists())

    def test_staff_roles_get_no_profile(self):
        employee = services.create_employee(actor=self.owner, email="e@example.com", **NEW)
        self.assertFalse(CustomerProfile.objects.filter(user=employee).exists())
        self.assertFalse(CustomerProfile.objects.filter(user=self.owner).exists())

    def test_change_role_to_customer_creates_profile(self):
        employee = services.create_employee(actor=self.owner, email="e@example.com", **NEW)
        services.change_role(actor=self.owner, user=employee, new_role=User.Role.CUSTOMER)
        self.assertTrue(CustomerProfile.objects.filter(user=employee).exists())

    def test_role_round_trip_keeps_single_profile(self):
        user = services.create_customer(email="c@example.com", **NEW)
        services.change_role(actor=self.owner, user=user, new_role=User.Role.EMPLOYEE)
        services.change_role(actor=self.owner, user=user, new_role=User.Role.CUSTOMER)
        self.assertEqual(CustomerProfile.objects.filter(user=user).count(), 1)

    def test_ensure_is_idempotent(self):
        user = services.create_customer(email="c@example.com", **NEW)
        first = services.ensure_customer_profile(user)
        second = services.ensure_customer_profile(user)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(CustomerProfile.objects.count(), 1)

    def test_signup_rolls_back_if_profile_fails(self):
        with mock.patch.object(
            services, "ensure_customer_profile", side_effect=IntegrityError("fallo simulado")
        ):
            with self.assertRaises(IntegrityError):
                services.create_customer(email="c@example.com", **NEW)
        self.assertFalse(User.objects.filter(email="c@example.com").exists())

    def test_failed_signup_creates_no_profile(self):
        with self.assertRaises(Exception):
            services.create_customer(email="c@example.com", **{**NEW, "password": "1234"})
        self.assertFalse(CustomerProfile.objects.exists())

    def test_database_prevents_duplicate_profiles(self):
        user = services.create_customer(email="c@example.com", **NEW)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CustomerProfile.objects.create(user=user)


class BackfillMigrationTests(TestCase):
    def test_backfill_creates_missing_profiles_only_for_customers(self):
        migration = import_module("apps.accounts.migrations.0003_backfill_customer_profiles")
        customer = make_user(email="c@example.com")  # el manager no crea el perfil
        employee = make_user(email="e@example.com", role=User.Role.EMPLOYEE)
        with_profile = services.create_customer(email="p@example.com", **NEW)

        migration.create_missing_customer_profiles(global_apps, None)
        migration.create_missing_customer_profiles(global_apps, None)  # repetible

        self.assertTrue(CustomerProfile.objects.filter(user=customer).exists())
        self.assertFalse(CustomerProfile.objects.filter(user=employee).exists())
        self.assertEqual(CustomerProfile.objects.filter(user=with_profile).count(), 1)
