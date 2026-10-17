"""
Tests de los datos de demostración (Fase 13): guardas de entorno, carga por
los servicios reales, coherencia, idempotencia, limpieza y escenarios
negativos sobre los datos cargados.

La carga necesita `TransactionTestCase`: verifica los emails con el enlace que
se envía al confirmar cada transacción (`on_commit`).
"""
import uuid
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import CommandError, call_command
from django.db.models import Sum
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.accounts.models import EmailVerificationToken, User
from apps.catalog.models import Category, Product
from apps.demo import data, guard, selectors
from apps.events import services as events
from apps.events.models import Event, Reservation
from apps.loyalty import ledger
from apps.loyalty import services as loyalty
from apps.loyalty.models import CustomerQRCode, PointsTransaction
from apps.purchases import services as purchases
from apps.purchases.models import Purchase
from apps.rewards import services as rewards
from apps.rewards.models import Redemption, Reward
from tests.accounts.factories import make_user
from tests.catalog.factories import TempMediaMixin

BASE_DIR = Path(settings.BASE_DIR)


def run(*args):
    out = StringIO()
    call_command("seed_demo_data", "--noinput", *args, stdout=out)
    return out.getvalue()


def demo_user(key):
    return User.objects.get(email=data.demo_email(key))


def event(key):
    return Event.objects.get(public_id=data.demo_uuid(f"event:{key}"))


def reward(key):
    return Reward.objects.get(public_id=data.demo_uuid(f"reward:{key}"))


class EnvironmentGuardTests(SimpleTestCase):
    def test_rejects_production_settings(self):
        with override_settings(SETTINGS_MODULE="config.settings.prod"):
            with self.assertRaisesMessage(CommandError, "solo se cargan en desarrollo"):
                run()

    def test_rejects_development_without_debug(self):
        with override_settings(SETTINGS_MODULE="config.settings.dev", DEBUG=False):
            with self.assertRaisesMessage(CommandError, "DEBUG=False"):
                run()

    def test_rejects_unknown_settings(self):
        with override_settings(SETTINGS_MODULE="otro.modulo"):
            with self.assertRaises(guard.DemoEnvironmentError):
                guard.check_environment()

    def test_accepts_development_with_debug(self):
        with override_settings(SETTINGS_MODULE="config.settings.dev", DEBUG=True):
            guard.check_environment()

    def test_future_reference_date_rejected(self):
        with self.assertRaisesMessage(CommandError, "no puede ser futura"):
            run("--reference-date", "2999-01-01")

    def test_demo_app_only_in_dev_and_test_settings(self):
        from config.settings import base

        self.assertNotIn("apps.demo", base.INSTALLED_APPS)
        self.assertNotIn("apps.demo", (BASE_DIR / "config/settings/prod.py").read_text(encoding="utf-8"))
        self.assertIn("apps.demo", settings.INSTALLED_APPS)

    def test_not_wired_into_deployment(self):
        files = [BASE_DIR / "Dockerfile", *BASE_DIR.glob("compose*.yaml"), *(BASE_DIR / "deploy").rglob("*")]
        for path in files:
            if path.is_file():
                self.assertNotIn("seed_demo_data", path.read_text(encoding="utf-8", errors="ignore"), path)


class PreconditionTests(TestCase):
    def test_refuses_database_with_foreign_data(self):
        make_user("persona@example.com")
        with self.assertRaisesMessage(CommandError, "no son de demostración"):
            run()
        self.assertFalse(selectors.demo_users().exists())
        self.assertFalse(selectors.demo_data_present())


class SeedDemoDataTests(TempMediaMixin, TransactionTestCase):
    def setUp(self):
        # Los límites anti-abuso viven en la caché, que sobrevive entre tests.
        cache.clear()
        self.output = run()

    def test_loads_every_area(self):
        counts = selectors.demo_counts()
        expected_minimums = {
            "propietarios": 1,
            "empleados": 4,
            "clientes": 20,
            "categorías": 5,
            "productos": 15,
            "promociones": 5,
            "compras": 30,
            "recompensas": 6,
            "canjes": 8,
            "eventos": 8,
            "reservas": 20,
            "campañas": 3,
        }
        for label, minimum in expected_minimums.items():
            self.assertGreaterEqual(counts[label], minimum, label)
        self.assertEqual(counts["propietarios"], 1)
        self.assertIn("Datos de demostración cargados", self.output)

    def test_roles_and_accounts(self):
        self.assertEqual(User.objects.count(), selectors.demo_users().count())
        self.assertTrue(all(u.email.endswith("@demo.example.com") for u in User.objects.all()))
        self.assertEqual(list(User.objects.filter(is_staff=True)), list(User.objects.filter(role=User.Role.OWNER)))
        self.assertEqual(list(User.objects.filter(is_superuser=True)), list(User.objects.filter(role=User.Role.OWNER)))
        customers = User.objects.filter(role=User.Role.CUSTOMER)
        self.assertFalse(customers.filter(customer_profile__isnull=True).exists())
        self.assertTrue(customers.filter(email_verified_at__isnull=True).exists())
        self.assertTrue(User.objects.filter(is_active=False, role=User.Role.CUSTOMER).exists())
        self.assertTrue(User.objects.filter(is_active=False, role=User.Role.EMPLOYEE).exists())
        self.assertTrue(demo_user("lua.proba").check_password(data.DEFAULT_PASSWORD))
        # Solo los verificados tienen QR, y con el formato del modelo.
        self.assertFalse(CustomerQRCode.objects.filter(user__email_verified_at__isnull=True).exists())
        self.assertTrue(all(len(qr.token) == 32 for qr in CustomerQRCode.objects.all()))

    def test_email_tokens_are_hashed_and_not_reusable(self):
        tokens = EmailVerificationToken.objects.all()
        self.assertTrue(all(len(t.token_hash) == 64 for t in tokens))
        # Ningún verificado conserva un enlace vigente sin usar.
        self.assertFalse(
            tokens.filter(user__email_verified_at__isnull=False, used_at__isnull=True, revoked_at__isnull=True).exists()
        )
        # El reenvío revocó el primer enlace.
        lois = tokens.filter(user=demo_user("lois.pendente"))
        self.assertEqual(lois.filter(revoked_at__isnull=False).count(), 1)
        # La recién registrada conserva un enlace vigente (solo su hash); el resto caducó.
        self.assertTrue(tokens.filter(user=demo_user("xiana.pendente"), expires_at__gt=timezone.now()).exists())
        self.assertFalse(tokens.filter(user=demo_user("uxio.pendente"), expires_at__gt=timezone.now()).exists())

    def test_output_does_not_leak_secrets(self):
        self.assertNotIn(data.DEFAULT_PASSWORD, self.output)
        for token in CustomerQRCode.objects.values_list("token", flat=True):
            self.assertNotIn(token, self.output)
        for code in Redemption.objects.values_list("code", flat=True):
            self.assertNotIn(code, self.output)

    def test_points_match_the_ledger(self):
        for customer in User.objects.filter(role=User.Role.CUSTOMER):
            running = 0
            for movement in PointsTransaction.objects.filter(customer=customer).order_by("created_at", "id"):
                running += movement.points
                self.assertEqual(movement.balance_after, running, customer.email)
                self.assertGreaterEqual(running, 0)
            self.assertEqual(ledger.balance(customer), running)
        self.assertEqual(ledger.balance(demo_user("hugo.proba")), 0)
        # Una acumulación como máximo por compra; la compra de 0,99 € no da puntos base.
        for purchase in Purchase.objects.all():
            self.assertLessEqual(purchase.points_transactions.filter(kind="EARN_PURCHASE").count(), 1)
        tiny = Purchase.objects.get(amount="0.99")
        self.assertFalse(tiny.points_transactions.filter(kind="EARN_PURCHASE").exists())
        kinds = set(PointsTransaction.objects.values_list("kind", flat=True))
        # La demo no configura caducidad (Fase 14): sus puntos no caducan. Tampoco
        # reparte campañas con puntos de regalo (Fase 19).
        excluded = {PointsTransaction.Kind.EXPIRATION, PointsTransaction.Kind.CAMPAIGN_GIFT}
        self.assertEqual(kinds, set(PointsTransaction.Kind.values) - excluded)

    def test_operations_cover_every_state(self):
        self.assertEqual(set(Reservation.objects.values_list("status", flat=True)), set(Reservation.Status.values))
        self.assertEqual(set(Redemption.objects.values_list("status", flat=True)), set(Redemption.Status.values))
        self.assertEqual(set(Event.objects.values_list("status", flat=True)), set(Event.Status.values))
        self.assertEqual(set(Product.objects.values_list("status", flat=True)), set(Product.Status.values))
        for closed in Redemption.objects.filter(status__in=Redemption.CLOSED_STATUSES):
            self.assertIsNotNone(closed.refund_movement_id)
        for item in Event.objects.exclude(capacity=None):
            self.assertLessEqual(events.confirmed_seats(item), item.capacity)
        self.assertEqual(events.confirmed_seats(event("cata-guiada")), 9)
        self.assertEqual(reward("camiseta").stock, 0)

    def test_rerun_is_idempotent_and_reset_reloads(self):
        before = selectors.demo_counts()
        self.assertIn("ya están cargados", run())
        self.assertEqual(selectors.demo_counts(), before)
        old_owner = demo_user("propietaria").pk
        run("--reset")
        self.assertEqual(selectors.demo_counts(), before)
        self.assertNotEqual(demo_user("propietaria").pk, old_owner)

    def test_clean_removes_only_demo_data_and_files(self):
        foreign_user = make_user("persona@example.com")
        foreign_category = Category.objects.create(name="Carta real", slug="carta-real")
        foreign_product = Product.objects.create(category=foreign_category, name="Producto real", price="2.00")
        image_paths = [Path(p.image.path) for p in Product.objects.exclude(image="")]
        self.assertTrue(image_paths and all(path.exists() for path in image_paths))

        run("--clean")

        self.assertFalse(selectors.demo_data_present())
        self.assertEqual(list(User.objects.all()), [foreign_user])
        self.assertEqual(list(Product.objects.all()), [foreign_product])
        self.assertFalse(any(path.exists() for path in image_paths))

    def test_clean_refuses_when_foreign_data_depends_on_demo(self):
        customer = make_user("persona@example.com", email_verified_at=demo_user("hugo.proba").email_verified_at)
        token = loyalty.get_customer_qr(customer).token
        purchases.register_purchase(
            staff=demo_user("brais.empregado"), qr_code=token, amount="5.00", idempotency_key=uuid.uuid4()
        )
        before = selectors.demo_counts()
        with self.assertRaisesMessage(CommandError, "No se ha borrado nada"):
            run("--clean")
        self.assertEqual(selectors.demo_counts(), before)

    def test_negative_scenarios_are_rejected(self):
        used = Redemption.objects.get(idempotency_key=data.demo_uuid("redemption:martin-camiseta"))
        with self.assertRaises(rewards.RedemptionAlreadyUsed):
            rewards.validate_redemption(staff=demo_user("uxia.empregada"), code=used.code)

        with self.assertRaises(ledger.InsufficientPoints):
            rewards.request_redemption(
                customer=demo_user("tiago.exemplo"), reward=reward("cana"), idempotency_key=uuid.uuid4()
            )

        pending = Reservation.objects.get(customer=demo_user("xoan.proba"), event=event("cata-guiada"))
        with self.assertRaisesMessage(ValidationError, "aforo"):
            events.confirm_reservation(actor=demo_user("propietaria"), reservation=pending)

        others = Redemption.objects.get(idempotency_key=data.demo_uuid("redemption:lua-pinta"))
        with self.assertRaises(PermissionDenied):
            rewards.cancel_redemption(customer=demo_user("hugo.proba"), redemption=others)

        with self.assertRaisesMessage(ValidationError, "Ya tienes una reserva activa"):
            events.request_reservation(
                customer=demo_user("lua.proba"), event=event("cata-guiada"), party_size=1, idempotency_key=uuid.uuid4()
            )

        inactive_qr = CustomerQRCode.objects.get(user=demo_user("noelia.exemplo")).token
        with self.assertRaises(loyalty.InvalidQRCode):
            purchases.register_purchase(
                staff=demo_user("brais.empregado"), qr_code=inactive_qr, amount="5.00", idempotency_key=uuid.uuid4()
            )

        with self.assertRaises(PermissionDenied):
            loyalty.get_customer_qr(demo_user("xiana.pendente"))

        with self.assertRaises(PermissionDenied):
            ledger.adjust_points(
                actor=demo_user("brais.empregado"),
                customer=demo_user("hugo.proba"),
                points=10,
                reason="Intento sin permiso",
                idempotency_key=uuid.uuid4(),
            )
        self.assertEqual(
            PointsTransaction.objects.filter(customer=demo_user("hugo.proba")).aggregate(s=Sum("points"))["s"], None
        )
