"""Gestión de la carta desde el admin: permisos, validación, servicios y conservación del historial."""
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.catalog.models import BeerStyle, Category, Product, TapMenu
from apps.core.models import AuditEvent
from tests.accounts.factories import make_user

from .factories import TempMediaMixin, make_category, make_product, make_style, uploaded_image

CATALOG_ADMIN_URLS = (
    "admin:catalog_product_changelist",
    "admin:catalog_product_add",
    "admin:catalog_category_changelist",
    "admin:catalog_beerstyle_changelist",
    "admin:catalog_tapmenu_changelist",
    "admin:catalog_tapmenu_add",
)


class CatalogAdminPermissionTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com", role=User.Role.OWNER)
        self.product = make_product()

    def test_owner_can_open_catalog_admin(self):
        self.client.force_login(self.owner)
        for url_name in CATALOG_ADMIN_URLS:
            with self.subTest(url_name):
                self.assertEqual(self.client.get(reverse(url_name)).status_code, 200)

    def test_other_roles_and_anonymous_cannot_access(self):
        users = (
            None,
            make_user("empleado@example.com", role=User.Role.EMPLOYEE),
            make_user("cliente@example.com"),
        )
        for user in users:
            self.client.logout()
            if user:
                self.client.force_login(user)
            for url_name in CATALOG_ADMIN_URLS:
                with self.subTest(user=user, url=url_name):
                    response = self.client.get(reverse(url_name))
                    self.assertEqual(response.status_code, 302)
                    self.assertIn("login", response["Location"])

    def test_non_owner_cannot_run_actions(self):
        self.client.force_login(make_user("empleado@example.com", role=User.Role.EMPLOYEE))
        self.client.post(
            reverse("admin:catalog_product_changelist"),
            {"action": "publish_products", "_selected_action": [self.product.pk]},
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.DRAFT)

    def test_nothing_can_be_deleted_from_admin(self):
        self.client.force_login(self.owner)
        objects = (
            ("admin:catalog_product_delete", self.product.pk),
            ("admin:catalog_category_delete", self.product.category.pk),
            ("admin:catalog_beerstyle_delete", self.product.style.pk),
        )
        for url_name, pk in objects:
            with self.subTest(url_name):
                self.assertEqual(self.client.post(reverse(url_name, args=[pk]), {"post": "yes"}).status_code, 403)
        response = self.client.get(reverse("admin:catalog_product_changelist"))
        self.assertNotContains(response, "delete_selected")
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())


class ProductAdminTests(TempMediaMixin, TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com", role=User.Role.OWNER)
        self.client.force_login(self.owner)
        self.category = make_category()
        self.style = make_style()

    def form_data(self, **overrides):
        data = {
            "category": self.category.pk,
            "kind": Product.Kind.GUEST_BEER,
            "name": "Invitada Ficticia",
            "description": "Notas de prueba.",
            "style": self.style.pk,
            "abv": "6.5",
            "brewery": "Cervecera Ficticia",
            "price": "4.20",
            "serving": "33 cl",
            "position": "0",
            "status": Product.Status.PUBLISHED,
            "is_available": "on",
        }
        data.update(overrides)
        return {key: value for key, value in data.items() if value is not None}

    def test_owner_creates_published_product_through_service(self):
        data = self.form_data(image=uploaded_image("Mi foto.png"))
        response = self.client.post(reverse("admin:catalog_product_add"), data)
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(name="Invitada Ficticia")
        self.assertEqual(product.status, Product.Status.PUBLISHED)
        self.assertEqual(str(product.price), "4.20")
        self.assertIsNotNone(product.published_at)
        self.assertTrue(product.image.name.startswith("catalog/products/"))
        self.assertNotIn("Mi foto", product.image.name)
        self.assertEqual((product.image_width, product.image_height), (8, 8))
        event = AuditEvent.objects.get(action=AuditEvent.Action.PRODUCT_STATUS_CHANGED)
        self.assertEqual(event.actor, self.owner)

    def test_invalid_prices_are_rejected(self):
        for price in ("0", "-2", "3.555", "abc", "10000"):
            with self.subTest(price=price):
                response = self.client.post(reverse("admin:catalog_product_add"), self.form_data(price=price))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["adminform"].form.errors.get("price"))
        self.assertFalse(Product.objects.exists())

    def test_invalid_image_is_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        fake = SimpleUploadedFile("foto.png", b"<script>alert(1)</script>", content_type="image/png")
        response = self.client.post(reverse("admin:catalog_product_add"), self.form_data(image=fake))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["adminform"].form.errors.get("image"))
        self.assertFalse(Product.objects.exists())

    def test_beer_without_style_or_abv_is_rejected(self):
        response = self.client.post(reverse("admin:catalog_product_add"), self.form_data(style="", abv=""))
        self.assertEqual(response.status_code, 200)
        errors = response.context["adminform"].form.errors
        self.assertIn("style", errors)
        self.assertIn("abv", errors)

    def test_editing_availability_in_form_goes_through_service(self):
        product = make_product(category=self.category, status=Product.Status.PUBLISHED)
        data = self.form_data(name=product.name, kind=product.kind, is_available=None, brewery="")
        response = self.client.post(reverse("admin:catalog_product_change", args=[product.pk]), data)
        self.assertEqual(response.status_code, 302)
        product.refresh_from_db()
        self.assertFalse(product.is_available)
        self.assertEqual(product.status, Product.Status.PUBLISHED)
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.Action.PRODUCT_AVAILABILITY_CHANGED).exists())
        self.assertFalse(AuditEvent.objects.filter(action=AuditEvent.Action.PRODUCT_STATUS_CHANGED).exists())

    def test_archiving_from_form_sets_archived_at(self):
        product = make_product(category=self.category, status=Product.Status.PUBLISHED)
        data = self.form_data(name=product.name, kind=product.kind, status=Product.Status.ARCHIVED)
        self.client.post(reverse("admin:catalog_product_change", args=[product.pk]), data)
        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.ARCHIVED)
        self.assertIsNotNone(product.archived_at)

    def test_list_actions_use_services(self):
        products = [make_product(category=self.category, name=f"Cerveza {i}") for i in range(2)]
        changelist = reverse("admin:catalog_product_changelist")
        ids = [p.pk for p in products]
        self.client.post(changelist, {"action": "publish_products", "_selected_action": ids})
        self.client.post(changelist, {"action": "mark_sold_out", "_selected_action": ids})
        self.client.post(changelist, {"action": "archive_products", "_selected_action": ids[:1]})
        statuses = dict(Product.objects.values_list("name", "status"))
        self.assertEqual(statuses, {"Cerveza 0": "ARCHIVED", "Cerveza 1": "PUBLISHED"})
        self.assertFalse(Product.objects.filter(is_available=True).exists())
        self.assertEqual(AuditEvent.objects.count(), 2 + 2 + 1)

    def test_archived_products_remain_listed_as_history(self):
        make_product(category=self.category, name="Histórica", status=Product.Status.ARCHIVED, archived_at="2026-01-01T00:00:00Z")
        response = self.client.get(reverse("admin:catalog_product_changelist") + "?status__exact=ARCHIVED")
        self.assertContains(response, "Histórica")


class CatalogSupportAdminTests(TempMediaMixin, TestCase):
    def setUp(self):
        self.client.force_login(make_user("owner@example.com", role=User.Role.OWNER))

    def test_owner_manages_categories_and_styles(self):
        response = self.client.post(
            reverse("admin:catalog_category_add"),
            {"name": "Para picar", "slug": "para-picar", "description": "", "position": "2", "is_published": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Category.objects.filter(slug="para-picar").exists())
        self.client.post(reverse("admin:catalog_beerstyle_add"), {"name": "Stout"})
        self.assertTrue(BeerStyle.objects.filter(name="Stout").exists())

    def test_owner_uploads_tap_menu_image(self):
        response = self.client.post(
            reverse("admin:catalog_tapmenu_add"),
            {"title": "Carta de grifos", "image": uploaded_image("grifos.jpg", fmt="JPEG"), "text_alternative": "", "is_published": "on"},
        )
        self.assertEqual(response.status_code, 302)
        tap_menu = TapMenu.objects.get()
        self.assertTrue(tap_menu.image.name.startswith("catalog/taps/"))
        self.assertTrue(tap_menu.is_published)

    def test_tap_menu_rejects_invalid_image(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        svg = SimpleUploadedFile("grifos.svg", b"<svg></svg>", content_type="image/svg+xml")
        response = self.client.post(reverse("admin:catalog_tapmenu_add"), {"title": "Grifos", "image": svg})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TapMenu.objects.exists())
