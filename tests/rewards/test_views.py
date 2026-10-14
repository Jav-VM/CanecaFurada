"""Vistas de recompensas y canjes: catálogo público, cliente, panel del personal y admin (acceso, IDOR, privacidad)."""
import datetime
import re
import uuid

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts import services as accounts
from apps.core.models import AuditEvent
from apps.loyalty import ledger
from apps.rewards import codes, services
from apps.rewards.models import Redemption, Reward
from tests.accounts.factories import registration_data

from .factories import give_points, make_customer_with_qr, make_employee, make_owner, make_reward, redeem

Status = Redemption.Status


class RewardsViewTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_owner()
        self.employee = make_employee()
        self.customer, _ = make_customer_with_qr()
        give_points(self.customer, 120, owner=self.owner)
        self.reward = make_reward(name="Caña de la casa", points_cost=50)

    def key_from(self, response):
        return re.search(r'name="idempotency_key" value="([0-9a-f-]{36})"', response.content.decode()).group(1)


class PublicCatalogTests(RewardsViewTestCase):
    def test_lists_only_active_rewards_in_period(self):
        now = timezone.now()
        make_reward(name="Borrador oculto", status=Reward.Status.DRAFT)
        make_reward(name="Pausada oculta", status=Reward.Status.PAUSED)
        make_reward(name="Futura oculta", valid_from=now + datetime.timedelta(days=1))
        make_reward(name="Terminada oculta", valid_from=now - datetime.timedelta(days=3), valid_until=now)
        make_reward(name="Agotada visible", stock=0)
        response = self.client.get(reverse("web:rewards"))
        self.assertContains(response, "Caña de la casa")
        self.assertContains(response, "50 puntos")
        self.assertContains(response, "Agotada visible")
        self.assertContains(response, "Agotada</span>")
        for hidden in ("Borrador oculto", "Pausada oculta", "Futura oculta", "Terminada oculta"):
            self.assertNotContains(response, hidden)
        self.assertContains(response, reverse("rewards:reward_detail", args=[self.reward.public_id]))

    def test_empty_state_without_rewards(self):
        Reward.objects.all().update(status=Reward.Status.ARCHIVED)
        self.assertContains(self.client.get(reverse("web:rewards")), "El catálogo de recompensas aún no está publicado")


class CustomerRedeemViewTests(RewardsViewTestCase):
    def detail_url(self, reward=None):
        return reverse("rewards:reward_detail", args=[(reward or self.reward).public_id])

    def redeem_url(self, reward=None):
        return reverse("rewards:redeem", args=[(reward or self.reward).public_id])

    def test_requires_login(self):
        for url in (self.detail_url(), reverse("rewards:my_redemptions")):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertEqual(self.client.post(self.redeem_url(), {"idempotency_key": str(uuid.uuid4())}).status_code, 302)
        self.assertFalse(Redemption.objects.exists())

    def test_only_verified_customers(self):
        unverified = accounts.register_customer(**registration_data(email="pendiente@example.com"))
        for user in (unverified, self.employee, self.owner):
            with self.subTest(user=user.email):
                self.client.force_login(user)
                self.assertEqual(self.client.get(self.detail_url()).status_code, 403)
                self.assertEqual(
                    self.client.post(self.redeem_url(), {"idempotency_key": str(uuid.uuid4())}).status_code, 403
                )
                self.assertEqual(self.client.get(reverse("rewards:my_redemptions")).status_code, 403)
        self.assertFalse(Redemption.objects.exists())

    def test_hidden_rewards_are_404(self):
        self.client.force_login(self.customer)
        draft = make_reward(name="Borrador", status=Reward.Status.DRAFT)
        self.assertEqual(self.client.get(self.detail_url(draft)).status_code, 404)
        self.assertEqual(self.client.get(reverse("rewards:reward_detail", args=[uuid.uuid4()])).status_code, 404)

    def test_full_flow_redeem_shows_code_and_qr(self):
        self.client.force_login(self.customer)
        page = self.client.get(self.detail_url())
        self.assertContains(page, 'data-balance>120 puntos<')
        self.assertIn("no-store", page["Cache-Control"])
        response = self.client.post(self.redeem_url(), {"idempotency_key": self.key_from(page)}, follow=True)
        redemption = Redemption.objects.get()
        self.assertRedirects(response, reverse("rewards:redemption_detail", args=[redemption.public_id]))
        self.assertContains(response, codes.format_code(redemption.code))
        self.assertContains(response, "data-redemption-qr")
        self.assertContains(response, "Pendiente de recoger")
        self.assertEqual(ledger.balance(self.customer), 70)
        # El código no aparece en ninguna URL.
        self.assertNotIn(redemption.code, response.redirect_chain[0][0])

    def test_double_submit_does_not_charge_twice(self):
        self.client.force_login(self.customer)
        key = self.key_from(self.client.get(self.detail_url()))
        self.client.post(self.redeem_url(), {"idempotency_key": key})
        second = self.client.post(self.redeem_url(), {"idempotency_key": key}, follow=True)
        self.assertContains(second, "No se han descontado más puntos")
        self.assertEqual(Redemption.objects.count(), 1)
        self.assertEqual(ledger.balance(self.customer), 70)

    def test_insufficient_balance(self):
        expensive = make_reward(name="Camiseta", points_cost=500)
        self.client.force_login(self.customer)
        page = self.client.get(self.detail_url(expensive))
        self.assertContains(page, "Te faltan 380 puntos")
        self.assertNotContains(page, 'name="idempotency_key"')
        # Aunque se fuerce el POST, el servidor lo rechaza.
        response = self.client.post(self.redeem_url(expensive), {"idempotency_key": str(uuid.uuid4())})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "no tiene puntos suficientes", status_code=400)
        self.assertFalse(Redemption.objects.exists())

    def test_client_cannot_set_cost_points_or_customer(self):
        other, _ = make_customer_with_qr("otra@example.com")
        self.client.force_login(self.customer)
        self.client.post(
            self.redeem_url(),
            {
                "idempotency_key": str(uuid.uuid4()),
                "points_cost": "1",
                "points": "1",
                "customer": str(other.public_id),
                "status": "USED",
                "code": "ABCDEFGHJKMN",
            },
        )
        redemption = Redemption.objects.get()
        self.assertEqual((redemption.customer, redemption.points_cost, redemption.status), (self.customer, 50, Status.PENDING))
        self.assertNotEqual(redemption.code, "ABCDEFGHJKMN")

    def test_redeem_requires_post_and_valid_key(self):
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(self.redeem_url()).status_code, 405)
        self.assertEqual(self.client.post(self.redeem_url(), {"idempotency_key": "x"}).status_code, 400)
        self.assertFalse(Redemption.objects.exists())

    def test_reward_withdrawn_before_confirming(self):
        self.client.force_login(self.customer)
        key = self.key_from(self.client.get(self.detail_url()))
        Reward.objects.filter(pk=self.reward.pk).update(status=Reward.Status.PAUSED)
        response = self.client.post(self.redeem_url(), {"idempotency_key": key}, follow=True)
        self.assertContains(response, "no está disponible")
        self.assertFalse(Redemption.objects.exists())

    def test_pending_code_is_offered_instead_of_a_new_one(self):
        redemption = redeem(self.customer, self.reward).redemption
        self.client.force_login(self.customer)
        page = self.client.get(self.detail_url())
        self.assertContains(page, "Ya tienes un código pendiente")
        self.assertContains(page, reverse("rewards:redemption_detail", args=[redemption.public_id]))


class CustomerHistoryViewTests(RewardsViewTestCase):
    def test_history_and_status_only_own(self):
        own = redeem(self.customer, self.reward).redemption
        other, _ = make_customer_with_qr("otra@example.com")
        give_points(other, 100, owner=self.owner)
        foreign = redeem(other, make_reward(name="Recompensa ajena", points_cost=10)).redemption
        self.client.force_login(self.customer)
        response = self.client.get(reverse("rewards:my_redemptions"))
        self.assertContains(response, "Caña de la casa")
        self.assertContains(response, "Pendiente de recoger")
        self.assertNotContains(response, "Recompensa ajena")
        # IDOR: el canje de otro cliente no existe para mí.
        self.assertEqual(self.client.get(reverse("rewards:redemption_detail", args=[foreign.public_id])).status_code, 404)
        self.assertEqual(self.client.post(reverse("rewards:cancel", args=[foreign.public_id])).status_code, 404)
        foreign.refresh_from_db()
        self.assertEqual(foreign.status, Status.PENDING)
        self.assertEqual(self.client.get(reverse("rewards:redemption_detail", args=[own.public_id])).status_code, 200)

    def test_used_redemption_hides_code(self):
        redemption = redeem(self.customer, self.reward).redemption
        services.validate_redemption(staff=self.employee, code=redemption.code)
        self.client.force_login(self.customer)
        response = self.client.get(reverse("rewards:redemption_detail", args=[redemption.public_id]))
        self.assertContains(response, "Canjeado")
        self.assertNotContains(response, codes.format_code(redemption.code))
        self.assertNotContains(response, "data-redemption-qr")

    def test_cancel_returns_points(self):
        redemption = redeem(self.customer, self.reward).redemption
        self.client.force_login(self.customer)
        url = reverse("rewards:cancel", args=[redemption.public_id])
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url, follow=True)
        self.assertContains(response, "Te hemos devuelto 50 puntos")
        self.assertContains(response, "Cancelado")
        self.assertEqual(ledger.balance(self.customer), 120)
        points = self.client.get(reverse("loyalty:my_points"))
        self.assertContains(points, "Devolución de canje")
        self.assertContains(points, "data-points-used>0<")

    def test_expired_pending_code_is_not_shown(self):
        redemption = redeem(self.customer, self.reward).redemption
        past = timezone.now() - datetime.timedelta(days=31)
        Redemption.objects.filter(pk=redemption.pk).update(created_at=past, expires_at=past + datetime.timedelta(days=30))
        self.client.force_login(self.customer)
        response = self.client.get(reverse("rewards:redemption_detail", args=[redemption.public_id]))
        self.assertContains(response, "Caducado")
        self.assertNotContains(response, codes.format_code(redemption.code))

    def test_profile_and_points_link_to_redemptions(self):
        self.client.force_login(self.customer)
        self.assertContains(self.client.get(reverse("accounts:profile")), reverse("rewards:my_redemptions"))
        self.assertContains(self.client.get(reverse("loyalty:my_points")), reverse("rewards:my_redemptions"))


class StaffPanelViewTests(RewardsViewTestCase):
    def setUp(self):
        super().setUp()
        self.redemption = redeem(self.customer, self.reward).redemption

    def test_only_staff(self):
        urls = [
            ("get", reverse("rewards_panel:scan"), {}),
            ("post", reverse("rewards_panel:lookup"), {"code": self.redemption.code}),
            ("post", reverse("rewards_panel:validate"), {"code": self.redemption.code}),
        ]
        for method, url, data in urls:
            with self.subTest(url=url):
                self.client.logout()
                self.assertEqual(getattr(self.client, method)(url, data).status_code, 302)
                self.client.force_login(self.customer)
                self.assertEqual(getattr(self.client, method)(url, data).status_code, 403)
        self.redemption.refresh_from_db()
        self.assertEqual(self.redemption.status, Status.PENDING)

    def test_lookup_shows_minimum_data(self):
        self.client.force_login(self.employee)
        response = self.client.post(reverse("rewards_panel:lookup"), {"code": codes.qr_payload(self.redemption.code)})
        self.assertContains(response, 'data-reward-name>Caña de la casa<')
        self.assertContains(response, 'data-customer-name>Lúa F.<')
        self.assertContains(response, "Validar y entregar")
        for private in (self.customer.email, self.customer.last_name, str(self.customer.public_id), "120"):
            self.assertNotContains(response, private)
        self.assertIn("no-store", response["Cache-Control"])
        self.redemption.refresh_from_db()
        self.assertEqual(self.redemption.status, Status.PENDING)

    def test_validate_flow_and_single_use(self):
        self.client.force_login(self.employee)
        response = self.client.post(reverse("rewards_panel:validate"), {"code": self.redemption.code}, follow=True)
        self.assertRedirects(response, reverse("rewards_panel:detail", args=[self.redemption.public_id]))
        self.assertContains(response, "Canje validado")
        self.assertNotIn(self.redemption.code, response.redirect_chain[0][0])
        self.redemption.refresh_from_db()
        self.assertEqual((self.redemption.status, self.redemption.validated_by), (Status.USED, self.employee))
        again = self.client.post(reverse("rewards_panel:validate"), {"code": self.redemption.code})
        self.assertEqual(again.status_code, 400)
        self.assertContains(again, "ya se utilizó", status_code=400)
        lookup = self.client.post(reverse("rewards_panel:lookup"), {"code": self.redemption.code})
        self.assertContains(lookup, "no entregues la recompensa")
        self.assertNotContains(lookup, "Validar y entregar")
        self.assertEqual(AuditEvent.objects.filter(action=AuditEvent.Action.REDEMPTION_VALIDATED).count(), 1)

    def test_invalid_code_message_is_generic(self):
        self.client.force_login(self.employee)
        response = self.client.post(reverse("rewards_panel:lookup"), {"code": "ABCD-EFGH-JKMN"})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "El código no es válido.", status_code=400)

    def test_validated_detail_visibility(self):
        services.validate_redemption(staff=self.employee, code=self.redemption.code)
        url = reverse("rewards_panel:detail", args=[self.redemption.public_id])
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(make_employee("otro@example.com"))
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_staff_home_links_to_panel(self):
        self.client.force_login(self.employee)
        self.assertContains(self.client.get(reverse("accounts:home")), reverse("rewards_panel:scan"))


class RewardsAdminTests(RewardsViewTestCase):
    def test_owner_creates_reward_with_audit_and_cannot_delete(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("admin:rewards_reward_add"),
            {
                "name": "Vaso serigrafiado",
                "description": "",
                "status": "ACTIVE",
                "position": "0",
                "points_cost": "200",
                "stock": "10",
                "valid_from_0": "01/01/2026",
                "valid_from_1": "00:00:00",
                "valid_until_0": "",
                "valid_until_1": "",
            },
        )
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context["adminform"].errors)
        reward = Reward.objects.get(name="Vaso serigrafiado")
        self.assertEqual(AuditEvent.objects.filter(action=AuditEvent.Action.REWARD_SAVED, target_public_id=reward.public_id).count(), 1)
        delete = self.client.post(reverse("admin:rewards_reward_delete", args=[reward.pk]), {"post": "yes"})
        self.assertEqual(delete.status_code, 403)

    def test_redemptions_are_read_only_and_hide_code(self):
        redemption = redeem(self.customer, self.reward).redemption
        self.client.force_login(self.owner)
        changelist = self.client.get(reverse("admin:rewards_redemption_changelist"))
        change = self.client.get(reverse("admin:rewards_redemption_change", args=[redemption.pk]))
        for response in (changelist, change):
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, redemption.code)
        self.assertEqual(self.client.get(reverse("admin:rewards_redemption_add")).status_code, 403)
        self.client.post(reverse("admin:rewards_redemption_change", args=[redemption.pk]), {"status": "USED"})
        redemption.refresh_from_db()
        self.assertEqual(redemption.status, Status.PENDING)

    def test_employee_has_no_access(self):
        self.client.force_login(self.employee)
        response = self.client.get(reverse("admin:rewards_reward_changelist"))
        self.assertIn(response.status_code, (302, 403))
