"""Dashboard (Fase 9): clientes (búsqueda, filtros, ficha, privacidad) y acciones del propietario."""
import uuid

from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.models import AuditEvent
from apps.loyalty import conversion, ledger
from apps.loyalty.models import PointsTransaction, Promotion
from apps.rewards.models import Reward
from apps.web import services as web
from apps.web.models import BusinessInfo
from tests.accounts.factories import PASSWORD, VALID_MOBILE, adult_birth_date
from tests.catalog.factories import make_product
from tests.dashboard.test_access import DashboardTestCase
from tests.loyalty.factories import buy, make_promotion, make_verified_customer
from tests.rewards.factories import give_points, make_reward, redeem

ADDRESS = "Rúa Ficticia 1, 2º"
BIRTH_YEAR = str(adult_birth_date().year)


class CustomerListTests(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.porto = make_verified_customer(
            "porto@example.com", first_name="Xoana", country="PT", city="Porto", province="Porto", postal_code="4000-123",
            promo_email_opt_in=True,
        )
        User.objects.filter(pk=self.porto.pk).update(email_verified_at=None)
        self.url = reverse("dashboard:customers")

    def emails(self, response):
        return {c.email for c in response.context["page"]}

    def test_list_shows_only_minimal_fields(self):
        User.objects.filter(pk=self.customer.pk).update(email_verified_at=None)
        make_verified_customer("tel@example.com", phone_number=VALID_MOBILE)
        response = self.client.get(self.url)
        self.assertContains(response, "cliente@example.com")
        for private in (ADDRESS, "15001", "+34600000001", "600 000 001", BIRTH_YEAR):
            with self.subTest(private=private):
                self.assertNotContains(response, private)

    def test_search_is_posted_and_kept_out_of_the_url(self):
        response = self.client.post(self.url, {"q": "porto@example"})
        self.assertRedirects(response, self.url)
        self.assertNotIn("porto", response["Location"])
        self.assertEqual(self.emails(self.client.get(self.url)), {"porto@example.com"})
        self.assertEqual(self.emails(self.client.get(self.url, {"pais": "PT"})), {"porto@example.com"})
        self.client.post(self.url, {"q": "", "limpiar": "1"})
        self.assertEqual(self.emails(self.client.get(self.url)), {"cliente@example.com", "porto@example.com"})

    def test_search_by_name_terms(self):
        self.client.post(self.url, {"q": "xoana ficticia"})
        self.assertEqual(self.emails(self.client.get(self.url)), {"porto@example.com"})

    def test_filters(self):
        cases = [
            ({"verificado": "si"}, {"cliente@example.com"}),
            ({"verificado": "no"}, {"porto@example.com"}),
            ({"localidad": "a coruña"}, {"cliente@example.com"}),
            ({"provincia": "PORTO"}, {"porto@example.com"}),
            ({"cp": "15001"}, {"cliente@example.com"}),
            ({"promo": "si"}, {"porto@example.com"}),
            ({"pais": "XX"}, {"cliente@example.com", "porto@example.com"}),  # país desconocido: se ignora
        ]
        for params, expected in cases:
            with self.subTest(params):
                self.assertEqual(self.emails(self.client.get(self.url, params)), expected)

    def test_staff_are_not_listed_as_customers(self):
        self.assertNotIn("empleado@example.com", self.emails(self.client.get(self.url)))


class CustomerDetailTests(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("dashboard:customer_detail", args=[self.customer.public_id])

    def test_detail_shows_authorized_data_and_activity(self):
        buy(self.employee, self.token, "12.50")
        response = self.client.get(self.url)
        for value in ("Lúa", "Ficticia Exemplo", "cliente@example.com", "Verificado", ADDRESS, "15001", BIRTH_YEAR, "No acepta"):
            with self.subTest(value=value):
                self.assertContains(response, value)
        self.assertEqual(response.context["points_summary"].balance, 12)
        self.assertContains(response, "12,50 €")

    def test_detail_access_is_audited_without_personal_data(self):
        self.client.get(self.url)
        event = AuditEvent.objects.get(action=AuditEvent.Action.CUSTOMER_DATA_VIEWED)
        self.assertEqual((event.actor, event.target_public_id, event.metadata), (self.owner, self.customer.public_id, {}))

    def test_staff_and_unknown_ids_return_404(self):
        for public_id in (self.employee.public_id, self.owner.public_id, uuid.uuid4()):
            with self.subTest(public_id=public_id):
                self.assertEqual(
                    self.client.get(reverse("dashboard:customer_detail", args=[public_id])).status_code, 404
                )

    def test_customer_without_profile_does_not_crash(self):
        legacy = User.objects.create_user(email="legacy@example.com", password=PASSWORD, first_name="A", last_name="B")
        response = self.client.get(reverse("dashboard:customer_detail", args=[legacy.public_id]))
        self.assertContains(response, "Sin dirección en el perfil")


class PointsActionTests(DashboardTestCase):
    def adjust(self, points, key=None, reason="Corrección de prueba"):
        return self.client.post(
            reverse("dashboard:customer_adjust_points", args=[self.customer.public_id]),
            {"points": points, "reason": reason, "idempotency_key": str(key or uuid.uuid4())},
            follow=True,
        )

    def test_adjustment_is_idempotent(self):
        key = uuid.uuid4()
        self.assertContains(self.adjust(30, key), "Ajuste registrado: +30 puntos.")
        self.assertContains(self.adjust(30, key), "ya estaba registrado")
        self.assertEqual(ledger.balance(self.customer), 30)
        self.assertEqual(AuditEvent.objects.filter(action=AuditEvent.Action.POINTS_ADJUSTED).count(), 1)

    def test_adjustment_cannot_leave_negative_balance_or_lack_reason(self):
        self.assertContains(self.adjust(-5), "no tiene puntos suficientes")
        self.adjust(5, reason="")
        self.assertFalse(PointsTransaction.objects.exists())

    def test_reverse_purchase_movement_once(self):
        buy(self.employee, self.token, "12.50")
        movement = PointsTransaction.objects.get()
        url = reverse("dashboard:customer_reverse_movement", args=[self.customer.public_id])
        response = self.client.post(url, {"movement": movement.public_id, "reason": "Compra errónea"}, follow=True)
        self.assertContains(response, "Movimiento compensado: -12 puntos.")
        self.client.post(url, {"movement": movement.public_id, "reason": "Otra vez"})
        self.assertEqual(PointsTransaction.objects.filter(kind=PointsTransaction.Kind.REVERSAL).count(), 1)
        self.assertEqual(ledger.balance(self.customer), 0)

    def test_cannot_reverse_other_customers_movement_through_url(self):
        other = make_verified_customer("otra@example.com")
        give_points(other, 10, owner=self.owner)
        movement = PointsTransaction.objects.get(customer=other)
        url = reverse("dashboard:customer_reverse_movement", args=[self.customer.public_id])
        self.assertEqual(self.client.post(url, {"movement": movement.public_id, "reason": "X"}).status_code, 404)
        self.assertEqual(ledger.balance(other), 10)

    def test_redemption_movements_cannot_be_reversed(self):
        give_points(self.customer, 50, owner=self.owner)
        redemption = redeem(self.customer, make_reward()).redemption
        with self.assertRaises(ValidationError):
            ledger.reverse_movement(actor=self.owner, movement=redemption.spend_movement, reason="X")
        response = self.client.get(reverse("dashboard:customer_detail", args=[self.customer.public_id]))
        self.assertNotIn(redemption.spend_movement.pk, response.context["reversible_ids"])
        self.assertEqual(ledger.balance(self.customer), 0)


class EmployeeActionTests(DashboardTestCase):
    def create(self, **overrides):
        data = {
            "first_name": "Brais", "last_name": "Ficticio", "email": "nuevo@example.com",
            "password1": PASSWORD, "password2": PASSWORD,
        }
        data.update(overrides)
        return self.client.post(reverse("dashboard:employee_create"), data)

    def test_create_employee(self):
        self.assertRedirects(self.create(), reverse("dashboard:employees"))
        user = User.objects.get(email="nuevo@example.com")
        self.assertEqual(user.role, User.Role.EMPLOYEE)
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.Action.EMPLOYEE_CREATED, actor=self.owner).exists())

    def test_create_employee_errors(self):
        self.assertContains(self.create(email="empleado@example.com"), "Ya existe", status_code=400)
        self.assertContains(self.create(password2="otra-cosa-distinta"), "no coinciden", status_code=400)
        self.assertEqual(self.create(password1="1234", password2="1234").status_code, 400)
        self.assertFalse(User.objects.filter(email="nuevo@example.com").exists())

    def test_deactivate_and_reactivate_employee(self):
        url = reverse("dashboard:employee_status", args=[self.employee.public_id])
        self.client.post(url, {"accion": "desactivar"})
        self.employee.refresh_from_db()
        self.assertFalse(self.employee.is_active)
        self.client.post(url, {"accion": "activar"})
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.is_active)

    def test_owner_cannot_deactivate_or_demote_self(self):
        self.client.post(reverse("dashboard:employee_status", args=[self.owner.public_id]), {"accion": "desactivar"})
        self.client.post(reverse("dashboard:employee_role", args=[self.owner.public_id]), {"role": "EMPLOYEE", "confirm": "on"})
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)
        self.assertEqual(self.owner.role, User.Role.OWNER)

    def test_role_change_requires_confirmation_and_never_targets_customers(self):
        url = reverse("dashboard:employee_role", args=[self.employee.public_id])
        self.client.post(url, {"role": "OWNER"})
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role, User.Role.EMPLOYEE)
        self.client.post(url, {"role": "CUSTOMER", "confirm": "on"})
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role, User.Role.EMPLOYEE)
        self.client.post(url, {"role": "OWNER", "confirm": "on"})
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role, User.Role.OWNER)
        customer_url = reverse("dashboard:employee_role", args=[self.customer.public_id])
        self.assertEqual(self.client.post(customer_url, {"role": "OWNER", "confirm": "on"}).status_code, 404)


class CatalogActionTests(DashboardTestCase):
    def test_reward_and_promotion_status(self):
        reward, promo = make_reward(), make_promotion()
        self.client.post(reverse("dashboard:reward_status", args=[reward.public_id]), {"estado": "PAUSED"})
        self.client.post(reverse("dashboard:promotion_status", args=[promo.public_id]), {"estado": "ENDED"})
        reward.refresh_from_db()
        promo.refresh_from_db()
        self.assertEqual((reward.status, promo.status), (Reward.Status.PAUSED, Promotion.Status.ENDED))
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.Action.REWARD_SAVED).exists())
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.Action.PROMOTION_SAVED).exists())
        response = self.client.post(
            reverse("dashboard:reward_status", args=[reward.public_id]), {"estado": "DRAFT"}, follow=True
        )
        self.assertContains(response, "Estado de recompensa no válido.")

    def test_product_status_and_availability(self):
        beer = make_product()
        fixed = make_product(kind=Product.Kind.FIXED, name="Tosta ficticia")
        response = self.client.post(reverse("dashboard:product_status", args=[beer.public_id]), {"estado": "PUBLISHED"})
        self.assertRedirects(response, reverse("dashboard:beers"))
        response = self.client.post(reverse("dashboard:product_availability", args=[fixed.public_id]), {"disponible": "no"})
        self.assertRedirects(response, reverse("dashboard:menu"))
        beer.refresh_from_db()
        fixed.refresh_from_db()
        self.assertEqual(beer.status, Product.Status.PUBLISHED)
        self.assertFalse(fixed.is_available)

    def test_beers_and_menu_sections_split_products(self):
        make_product(name="IPA ficticia")
        make_product(kind=Product.Kind.FIXED, name="Tosta ficticia")
        beers = self.client.get(reverse("dashboard:beers"))
        menu = self.client.get(reverse("dashboard:menu"))
        self.assertContains(beers, "IPA ficticia")
        self.assertNotContains(beers, "Tosta ficticia")
        self.assertContains(menu, "Tosta ficticia")
        self.assertNotContains(menu, "IPA ficticia")
        # Las dos listas se ajustan al ancho (tarjetas en pantallas estrechas): cada celda lleva su etiqueta.
        # Cervezas: 7 columnas (tipo, estilo y graduación juntos); carta: 6.
        for response, columns in ((beers, 7), (menu, 6)):
            self.assertContains(response, 'class="data-table data-table-fit"')
            self.assertContains(response, "data-label=", count=columns)


class ContentAndSettingsTests(DashboardTestCase):
    def post_content(self, **data):
        return self.client.post(reverse("dashboard:content"), data)

    def test_content_is_published_on_the_public_site(self):
        response = self.post_content(
            address="Rúa Ficticia 0, A Coruña",
            opening_hours="Lunes a jueves | 18:00–00:00",
            social_links="Red ficticia | https://example.com/caneca",
            email="info@example.com",
        )
        self.assertRedirects(response, reverse("dashboard:content"))
        contact = self.client.get(reverse("web:contact"))
        self.assertContains(contact, "Rúa Ficticia 0, A Coruña")
        # Contacto: una línea por franja, la hora a la derecha del día.
        self.assertRegex(contact.content.decode(), r"<span[^>]*>Lunes a jueves</span><span[^>]*>18:00–00:00</span>")
        self.assertContains(contact, 'href="https://example.com/caneca"')
        event = AuditEvent.objects.get(action=AuditEvent.Action.SITE_CONTENT_UPDATED)
        self.assertEqual(event.metadata["fields"], ["address", "email", "opening_hours", "social_links"])

    def test_empty_content_stays_pending(self):
        self.post_content(address="")
        self.assertContains(self.client.get(reverse("web:contact")), "dirección pendiente de publicar")

    def test_unsafe_links_and_bad_lines_are_rejected(self):
        for data in (
            {"social_links": "Malo | javascript:alert(1)"},
            {"social_links": "Sin enlace"},
            {"opening_hours": "Lunes sin separador"},
            {"phone": "<script>"},
        ):
            with self.subTest(data):
                self.assertEqual(self.post_content(**data).status_code, 400)
        self.assertFalse(BusinessInfo.objects.exists())
        self.assertNotContains(self.client.get(reverse("web:contact")), "javascript:")

    def test_content_is_escaped(self):
        web.update_business_info(actor=self.owner, data={"about_text": "<script>alert(1)</script>"})
        response = self.client.get(reverse("web:about"))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")

    def test_new_conversion_rule(self):
        response = self.client.post(reverse("dashboard:settings"), {"points_per_euro": "2,50", "note": "Prueba"})
        self.assertRedirects(response, reverse("dashboard:settings"))
        self.assertEqual(str(conversion.current_rate().points_per_euro), "2.50")
        self.assertEqual(self.client.post(reverse("dashboard:settings"), {"points_per_euro": "abc"}).status_code, 400)
        self.assertEqual(self.client.post(reverse("dashboard:settings"), {"points_per_euro": "500"}).status_code, 400)
