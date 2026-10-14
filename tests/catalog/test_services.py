"""Publicación, archivo y disponibilidad: permisos, idempotencia y auditoría."""
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.catalog import services
from apps.catalog.models import Product
from apps.core.models import AuditEvent
from tests.accounts.factories import make_user

from .factories import make_product


class CatalogServicePermissionTests(TestCase):
    def setUp(self):
        self.product = make_product()
        self.owner = make_user("owner@example.com", role=User.Role.OWNER)

    def test_only_active_owner_can_manage(self):
        inactive_owner = make_user("owner2@example.com", role=User.Role.OWNER, is_active=False)
        denied = (
            AnonymousUser(),
            None,
            make_user("empleado@example.com", role=User.Role.EMPLOYEE),
            make_user("cliente@example.com"),
            inactive_owner,
        )
        for actor in denied:
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionDenied):
                    services.set_product_status(actor=actor, product=self.product, status=Product.Status.PUBLISHED)
                with self.assertRaises(PermissionDenied):
                    services.set_product_availability(actor=actor, product=self.product, is_available=False)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.DRAFT)
        self.assertTrue(self.product.is_available)
        self.assertFalse(AuditEvent.objects.exists())

    def test_rejects_unknown_status(self):
        with self.assertRaises(ValidationError):
            services.set_product_status(actor=self.owner, product=self.product, status="DELETED")


class ProductStatusTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com", role=User.Role.OWNER)
        self.product = make_product()

    def set_status(self, status):
        return services.set_product_status(actor=self.owner, product=self.product, status=status)

    def test_publish_records_date_and_audit(self):
        product = self.set_status(Product.Status.PUBLISHED)
        self.assertEqual(product.status, Product.Status.PUBLISHED)
        self.assertIsNotNone(product.published_at)
        event = AuditEvent.objects.get(action=AuditEvent.Action.PRODUCT_STATUS_CHANGED)
        self.assertEqual(event.actor, self.owner)
        self.assertEqual(event.target_public_id, self.product.public_id)
        self.assertEqual(event.metadata, {"from": "DRAFT", "to": "PUBLISHED"})

    def test_repeating_an_operation_is_idempotent(self):
        self.set_status(Product.Status.PUBLISHED)
        self.set_status(Product.Status.PUBLISHED)
        self.assertEqual(AuditEvent.objects.filter(action=AuditEvent.Action.PRODUCT_STATUS_CHANGED).count(), 1)

    def test_archive_keeps_the_product_and_can_be_restored(self):
        self.set_status(Product.Status.PUBLISHED)
        archived = self.set_status(Product.Status.ARCHIVED)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.assertIsNotNone(archived.archived_at)
        restored = self.set_status(Product.Status.DRAFT)
        self.assertIsNone(restored.archived_at)
        self.assertEqual(AuditEvent.objects.filter(action=AuditEvent.Action.PRODUCT_STATUS_CHANGED).count(), 3)

    def test_archived_product_can_be_published_again(self):
        self.set_status(Product.Status.ARCHIVED)
        product = self.set_status(Product.Status.PUBLISHED)
        self.assertEqual(product.status, Product.Status.PUBLISHED)
        self.assertIsNone(product.archived_at)

    def test_status_change_uses_database_state_not_stale_instance(self):
        stale = Product.objects.get(pk=self.product.pk)
        self.set_status(Product.Status.PUBLISHED)
        services.set_product_status(actor=self.owner, product=stale, status=Product.Status.PUBLISHED)
        self.assertEqual(AuditEvent.objects.count(), 1)


class ProductAvailabilityTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com", role=User.Role.OWNER)
        self.product = make_product(status=Product.Status.PUBLISHED)

    def test_sold_out_product_stays_published_but_is_not_available(self):
        product = services.set_product_availability(actor=self.owner, product=self.product, is_available=False)
        self.assertEqual(product.status, Product.Status.PUBLISHED)
        self.assertFalse(product.is_available)
        self.assertFalse(product.is_currently_available)
        self.assertIsNotNone(product.availability_changed_at)
        event = AuditEvent.objects.get(action=AuditEvent.Action.PRODUCT_AVAILABILITY_CHANGED)
        self.assertEqual(event.metadata, {"is_available": False})

    def test_availability_is_idempotent(self):
        for _ in range(2):
            services.set_product_availability(actor=self.owner, product=self.product, is_available=False)
        services.set_product_availability(actor=self.owner, product=self.product, is_available=True)
        self.assertEqual(AuditEvent.objects.count(), 2)

    def test_availability_does_not_touch_permanent_information(self):
        before = Product.objects.values("name", "price", "status", "published_at").get(pk=self.product.pk)
        services.set_product_availability(actor=self.owner, product=self.product, is_available=False)
        after = Product.objects.values("name", "price", "status", "published_at").get(pk=self.product.pk)
        self.assertEqual(before, after)
