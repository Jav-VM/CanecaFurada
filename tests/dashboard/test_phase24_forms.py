"""
Fase 24: crear y editar productos, categorías, estilos, cartas de grifos,
recompensas y promociones desde el dashboard, sin pasar por el admin.
"""
import datetime
import re
import uuid
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import BeerStyle, Category, Product, TapMenu
from apps.core.models import AuditEvent
from apps.loyalty.models import Promotion
from apps.rewards.models import Reward
from tests.catalog.factories import TempMediaMixin, make_category, make_product, make_style, uploaded_image
from tests.loyalty.factories import make_promotion
from tests.rewards.factories import make_customer_with_qr, make_employee, make_owner, make_reward


def local(dt):
    return timezone.localtime(dt).strftime("%Y-%m-%dT%H:%M")


class FormsTestCase(TempMediaMixin, TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_owner()
        self.employee = make_employee()
        self.customer, _token = make_customer_with_qr()
        self.client.force_login(self.owner)
        self.category = make_category("Cervezas da casa", slug="cervezas-da-casa")
        self.style = make_style("IPA")

    def post(self, url, data):
        return self.client.post(url, data)

    def audited(self, model, created):
        return AuditEvent.objects.filter(
            action=AuditEvent.Action.CATALOG_SAVED, metadata__model=model, metadata__created=created
        ).exists()


class ProductFormTests(FormsTestCase):
    def beer_data(self, **extra):
        data = {
            "category": self.category.pk,
            "kind": Product.Kind.HOUSE_BEER,
            "name": "Rubia Ficticia",
            "description": "Lixeira e fresca.",
            "style": self.style.pk,
            "abv": "5.2",
            "brewery": "",
            "price": "3.50",
            "serving": "33 cl",
            "position": "1",
        }
        data.update(extra)
        return data

    def test_create_beer_starts_as_draft_and_available(self):
        self.assertContains(self.client.get(reverse("dashboard:product_create") + "?tipo=HOUSE_BEER"), 'value="HOUSE_BEER" selected')
        response = self.post(reverse("dashboard:product_create"), self.beer_data(image=uploaded_image()))
        self.assertRedirects(response, reverse("dashboard:beers"), fetch_redirect_response=False)
        product = Product.objects.get(name="Rubia Ficticia")
        self.assertEqual(product.status, Product.Status.DRAFT)
        self.assertTrue(product.is_available)
        self.assertTrue(product.image)
        self.assertEqual((product.image_width, product.image_height), (8, 8))
        self.assertTrue(self.audited("product", True))

    def test_fixed_product_goes_back_to_the_menu(self):
        response = self.post(
            reverse("dashboard:product_create"),
            self.beer_data(kind=Product.Kind.FIXED, style="", abv="", name="Patacas"),
        )
        self.assertRedirects(response, reverse("dashboard:menu"), fetch_redirect_response=False)
        self.assertEqual(Product.objects.get(name="Patacas").kind, Product.Kind.FIXED)

    def test_edit_keeps_status_and_availability(self):
        product = make_product(category=self.category, status=Product.Status.PUBLISHED, published_at=timezone.now(), is_available=False)
        url = reverse("dashboard:product_edit", args=[product.public_id])
        self.assertContains(self.client.get(url), product.name)
        data = self.beer_data(name="Nome novo", style=product.style_id)
        response = self.post(url, data)
        self.assertEqual(response.status_code, 302)
        product.refresh_from_db()
        self.assertEqual(product.name, "Nome novo")
        self.assertEqual(product.status, Product.Status.PUBLISHED)
        self.assertFalse(product.is_available)
        event = AuditEvent.objects.get(action=AuditEvent.Action.CATALOG_SAVED, metadata__model="product")
        self.assertIn("name", event.metadata["fields"])
        self.assertNotIn("Nome novo", str(event.metadata))

    def test_rejects_beer_without_style_featured_fixed_and_negative_price(self):
        cases = (
            self.beer_data(style="", abv=""),
            self.beer_data(kind=Product.Kind.FIXED, style="", abv="", is_featured="on"),
            self.beer_data(price="-1"),
        )
        for data in cases:
            with self.subTest(data=data):
                self.assertEqual(self.post(reverse("dashboard:product_create"), data).status_code, 400)
        self.assertFalse(Product.objects.exists())

    def test_rejects_fake_image(self):
        fake = SimpleUploadedFile("foto.png", b"<script>alert(1)</script>", content_type="image/png")
        self.assertEqual(self.post(reverse("dashboard:product_create"), self.beer_data(image=fake)).status_code, 400)
        self.assertFalse(Product.objects.exists())

    def test_status_cannot_be_set_from_the_form(self):
        self.post(reverse("dashboard:product_create"), self.beer_data(status="PUBLISHED", is_available=""))
        product = Product.objects.get()
        self.assertEqual(product.status, Product.Status.DRAFT)
        self.assertTrue(product.is_available)

    def test_unknown_product_is_404(self):
        self.assertEqual(self.client.get(reverse("dashboard:product_edit", args=[uuid.uuid4()])).status_code, 404)


class CategoryAndStyleTests(FormsTestCase):
    def test_create_category_generates_a_unique_slug(self):
        for _n in range(2):
            self.post(reverse("dashboard:category_create"), {"name": "Para picar", "slug": "", "position": "2", "is_published": "on"})
        # El segundo nombre igual se rechaza (único sin distinguir mayúsculas).
        self.assertEqual(Category.objects.filter(name="Para picar").count(), 1)
        self.assertEqual(Category.objects.get(name="Para picar").slug, "para-picar")
        self.post(reverse("dashboard:category_create"), {"name": "Para Picar!", "slug": "", "position": "3"})
        self.assertEqual(Category.objects.filter(name__iexact="para picar!").get().slug, "para-picar-2")
        self.assertTrue(self.audited("category", True))
        self.assertContains(self.client.get(reverse("dashboard:categories")), "Para picar")

    def test_duplicate_category_name_is_an_error(self):
        response = self.post(reverse("dashboard:category_create"), {"name": "cervezas da casa", "slug": "", "position": "0"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Category.objects.count(), 1)

    def test_edit_category_hides_it(self):
        url = reverse("dashboard:category_edit", args=[self.category.slug])
        response = self.post(url, {"name": self.category.name, "slug": self.category.slug, "position": "5"})
        self.assertRedirects(response, reverse("dashboard:categories"), fetch_redirect_response=False)
        self.category.refresh_from_db()
        self.assertFalse(self.category.is_published)
        self.assertEqual(self.category.position, 5)
        self.assertEqual(self.client.get(reverse("dashboard:category_edit", args=["non-existe"])).status_code, 404)

    def test_styles_create_edit_and_duplicates(self):
        self.post(reverse("dashboard:beer_style_create"), {"name": "Stout"})
        stout = BeerStyle.objects.get(name="Stout")
        self.assertEqual(self.post(reverse("dashboard:beer_style_create"), {"name": "ipa"}).status_code, 400)
        self.post(reverse("dashboard:beer_style_edit", args=[stout.pk]), {"name": "Imperial Stout"})
        stout.refresh_from_db()
        self.assertEqual(stout.name, "Imperial Stout")
        self.assertTrue(self.audited("beer_style", False))
        self.assertContains(self.client.get(reverse("dashboard:beer_styles")), "Imperial Stout")
        self.assertEqual(self.client.get(reverse("dashboard:beer_style_edit", args=[99999])).status_code, 404)


class TapMenuTests(FormsTestCase):
    def test_create_requires_an_image_and_publishes(self):
        self.assertEqual(self.post(reverse("dashboard:tap_menu_create"), {"title": "Billas"}).status_code, 400)
        self.post(reverse("dashboard:tap_menu_create"), {"title": "Billas", "image": uploaded_image(), "text_alternative": "Grifo 1", "is_published": "on"})
        tap_menu = TapMenu.objects.get()
        self.assertTrue(tap_menu.is_published)
        page = self.client.get(reverse("dashboard:tap_menus"))
        self.assertContains(page, "Billas")
        self.assertContains(page, "En la web")
        self.assertContains(self.client.get(reverse("web:menu")), "Grifo 1")

    def test_edit_keeps_the_image_if_none_is_uploaded(self):
        tap_menu = TapMenu.objects.create(title="Vella", image=uploaded_image(), is_published=True)
        name = tap_menu.image.name
        self.post(reverse("dashboard:tap_menu_edit", args=[tap_menu.pk]), {"title": "Nova", "text_alternative": ""})
        tap_menu.refresh_from_db()
        self.assertEqual((tap_menu.title, tap_menu.image.name, tap_menu.is_published), ("Nova", name, False))


class RewardAndPromotionTests(FormsTestCase):
    def test_create_and_edit_reward(self):
        start = timezone.now()
        data = {"name": "Camiseta", "description": "Da casa.", "points_cost": "300", "stock": "10", "valid_from": local(start), "position": "1"}
        response = self.post(reverse("dashboard:reward_create"), data)
        self.assertRedirects(response, reverse("dashboard:rewards"), fetch_redirect_response=False)
        reward = Reward.objects.get(name="Camiseta")
        self.assertEqual(reward.status, Reward.Status.DRAFT)
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.Action.REWARD_SAVED, metadata__created=True).exists())
        data.update(points_cost="250", valid_until=local(start - datetime.timedelta(days=1)))
        self.assertEqual(self.post(reverse("dashboard:reward_edit", args=[reward.public_id]), data).status_code, 400)
        data.update(valid_until="")
        self.post(reverse("dashboard:reward_edit", args=[reward.public_id]), data)
        reward.refresh_from_db()
        self.assertEqual(reward.points_cost, 250)

    def test_edit_reward_keeps_status(self):
        reward = make_reward(status=Reward.Status.ACTIVE)
        data = {"name": "Outra", "points_cost": "40", "valid_from": local(reward.valid_from), "position": "0", "status": "ARCHIVED"}
        self.post(reverse("dashboard:reward_edit", args=[reward.public_id]), data)
        reward.refresh_from_db()
        self.assertEqual((reward.name, reward.status), ("Outra", Reward.Status.ACTIVE))

    def test_create_and_validate_promotion(self):
        base = {
            "name": "Dobre",
            "kind": Promotion.Kind.PURCHASE,
            "bonus_type": Promotion.BonusType.MULTIPLIER,
            "multiplier": "2.0",
            "starts_at": local(timezone.now()),
        }
        response = self.post(reverse("dashboard:promotion_create"), base)
        self.assertRedirects(response, reverse("dashboard:promotions"), fetch_redirect_response=False)
        promotion = Promotion.objects.get(name="Dobre")
        self.assertEqual(promotion.status, Promotion.Status.DRAFT)
        # Cumpleaños con multiplicador: no.
        bad = dict(base, name="Aniversario", kind=Promotion.Kind.BIRTHDAY)
        self.assertEqual(self.post(reverse("dashboard:promotion_create"), bad).status_code, 400)
        self.assertFalse(Promotion.objects.filter(name="Aniversario").exists())

    def test_edit_promotion(self):
        promotion = make_promotion()
        url = reverse("dashboard:promotion_edit", args=[promotion.public_id])
        data = {
            "name": "Promo editada",
            "kind": promotion.kind,
            "bonus_type": promotion.bonus_type,
            "fixed_points": "25",
            "starts_at": local(promotion.starts_at),
        }
        self.post(url, data)
        promotion.refresh_from_db()
        self.assertEqual((promotion.name, promotion.fixed_points, promotion.status), ("Promo editada", 25, Promotion.Status.ACTIVE))
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.Action.PROMOTION_SAVED, metadata__created=False).exists())
        self.assertEqual(self.client.get(reverse("dashboard:promotion_edit", args=[uuid.uuid4()])).status_code, 404)


class AccessAndLinksTests(FormsTestCase):
    def post_urls(self):
        product = make_product(category=self.category)
        return [
            reverse("dashboard:product_create"),
            reverse("dashboard:product_edit", args=[product.public_id]),
            reverse("dashboard:category_create"),
            reverse("dashboard:category_edit", args=[self.category.slug]),
            reverse("dashboard:beer_style_create"),
            reverse("dashboard:beer_style_edit", args=[self.style.pk]),
            reverse("dashboard:tap_menu_create"),
            reverse("dashboard:reward_create"),
            reverse("dashboard:reward_edit", args=[make_reward().public_id]),
            reverse("dashboard:promotion_create"),
            reverse("dashboard:promotion_edit", args=[make_promotion().public_id]),
        ]

    def test_only_the_owner_can_save(self):
        urls = self.post_urls()
        before = (Product.objects.count(), Category.objects.count(), BeerStyle.objects.count(), Reward.objects.count(), Promotion.objects.count())
        for user in (self.employee, self.customer):
            self.client.force_login(user)
            for url in urls:
                with self.subTest(user=user.role, url=url):
                    self.assertEqual(self.client.post(url, {"name": "x"}).status_code, 403)
        self.client.logout()
        self.assertIn(reverse("accounts:login"), self.client.post(urls[0], {"name": "x"})["Location"])
        after = (Product.objects.count(), Category.objects.count(), BeerStyle.objects.count(), Reward.objects.count(), Promotion.objects.count())
        self.assertEqual(before, after)
        self.assertFalse(AuditEvent.objects.filter(action=AuditEvent.Action.CATALOG_SAVED).exists())

    def test_lists_link_to_the_dashboard_not_the_admin(self):
        product = make_product(category=self.category)
        reward = make_reward()
        promotion = make_promotion()
        pages = {
            "dashboard:beers": [reverse("dashboard:product_edit", args=[product.public_id]), reverse("dashboard:beer_styles"), reverse("dashboard:tap_menus")],
            "dashboard:menu": [reverse("dashboard:product_create"), reverse("dashboard:categories")],
            "dashboard:rewards": [reverse("dashboard:reward_create"), reverse("dashboard:reward_edit", args=[reward.public_id])],
            "dashboard:promotions": [reverse("dashboard:promotion_create"), reverse("dashboard:promotion_edit", args=[promotion.public_id])],
        }
        for name, links in pages.items():
            html = self.client.get(reverse(name)).content.decode()
            with self.subTest(page=name):
                self.assertNotIn(reverse("admin:index"), html)
                for link in links:
                    self.assertIn(link, html)

    def test_settings_keeps_a_link_to_the_admin(self):
        response = self.client.get(reverse("dashboard:settings"))
        self.assertContains(response, "data-admin-link")
        self.assertContains(response, f'href="{reverse("admin:index")}"')

    def test_no_dashboard_template_links_to_the_admin_except_settings(self):
        folder = Path(settings.BASE_DIR) / "templates" / "dashboard"
        offenders = [
            path.name
            for path in folder.glob("*.html")
            if path.name != "settings.html" and re.search(r"\{%\s*url\s+['\"]admin:", path.read_text(encoding="utf-8"))
        ]
        self.assertEqual(offenders, [])

    def test_prices_are_stored_as_decimals(self):
        # Formato del formulario: punto decimal, como en el admin.
        self.post(reverse("dashboard:product_create"), {
            "category": self.category.pk, "kind": Product.Kind.FIXED, "name": "Auga", "price": "1.20", "position": "0",
        })
        self.assertEqual(Product.objects.get(name="Auga").price, Decimal("1.20"))


class FitTablesTests(FormsTestCase):
    """Empleados y Promociones caben sin scroll lateral: tarjetas por debajo de xl (.data-table-fit)."""

    def test_employees_and_promotions_use_fit_tables_with_labels(self):
        make_promotion()
        for name, marker in (("dashboard:employees", "data-staff-list"), ("dashboard:promotions", "data-promotion-list")):
            html = self.client.get(reverse(name)).content.decode()
            with self.subTest(page=name):
                self.assertIn(f'class="data-table data-table-fit" {marker}', html)
                table = html[html.index(marker):html.index("</table>", html.index(marker))]
                body = table[table.index("<tbody>"):]
                cells = re.findall(r"<td\b[^>]*>", body)
                self.assertTrue(cells)
                # Cada celda lleva su etiqueta para la vista en tarjetas (salvo el título, que no la muestra).
                self.assertTrue(all("data-label=" in cell or "cell-title" in cell for cell in cells), cells)
