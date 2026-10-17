"""
Fase 19: filtro «sin gasto», selección de clientes, campañas a seleccionados,
imagen en el email y puntos de regalo con o sin caducidad.
"""
import uuid
from types import SimpleNamespace

from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.dashboard import views as dashboard_views
from apps.loyalty import expiry, ledger
from apps.loyalty.models import PointsTransaction
from apps.notifications import campaigns, services
from apps.notifications.models import Campaign, CampaignRecipient, Channel, Notification
from tests.accounts.factories import registration_data
from tests.catalog.factories import TempMediaMixin, uploaded_image
from tests.loyalty.factories import buy, make_customer_with_qr, make_employee, make_owner
from tests.loyalty.test_expiry import at, mov, pol

Audience = Campaign.Audience
Kind = PointsTransaction.Kind
SELECTION_URL = reverse("dashboard:customer_selection")
CREATE_URL = reverse("dashboard:campaign_create")
CREATE_SELECTED_URL = f"{CREATE_URL}?destinatarios=seleccion"


def customer(email, **data):
    return make_customer_with_qr(email, **data)


def gifts(user):
    return PointsTransaction.objects.filter(customer=user, kind=Kind.CAMPAIGN_GIFT)


class NeverExpiresFifoTests(SimpleTestCase):
    def test_gift_without_expiry_forms_no_lot_and_is_spent_last(self):
        movements = [
            mov(1, 100, at(2027, 1, 10), kind=Kind.CAMPAIGN_GIFT, never_expires=True),
            mov(2, 50, at(2027, 3, 10)),
            mov(3, -30, at(2027, 4, 1)),
        ]
        lots = expiry.remaining_lots(movements, pol(12))
        # Los 30 gastados salen de los que caducan; los 100 regalados no caducan nunca.
        self.assertEqual([(lot.expires_at, lot.points) for lot in lots], [(at(2028, 3, 10), 20)])
        self.assertEqual(expiry.expirable_points(movements, pol(12), at(2040, 1, 1)), 20)

    def test_gift_with_expiry_behaves_like_any_credit(self):
        movements = [SimpleNamespace(pk=1, kind=Kind.CAMPAIGN_GIFT, points=40, created_at=at(2027, 1, 1), reverses_id=None, never_expires=False)]
        self.assertEqual(expiry.expirable_points(movements, pol(12), at(2028, 1, 1)), 40)


class CampaignTestCase(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox.clear()
        self.owner = make_owner()
        self.employee = make_employee()
        self.consenting, self.consenting_token = customer("si@example.com", promo_email_opt_in=True)
        self.silent, _ = customer("no@example.com")
        self.other, _ = customer("otra@example.com", promo_email_opt_in=True)

    def selected_campaign(self, users, **data):
        values = {"name": "Vecinos", "subject": "Hola", "body": "Texto", "channel": Channel.EMAIL, "audience": Audience.SELECTED}
        values.update(data)
        return campaigns.save_campaign(
            actor=self.owner, campaign=Campaign(), data=values, recipients=[u.public_id for u in users]
        )


class LedgerGiftTests(CampaignTestCase):
    def test_grant_is_idempotent_and_marks_never_expires(self):
        campaign_id = uuid.uuid4()
        first = ledger.grant_campaign_gift(customer=self.silent, campaign_public_id=campaign_id, points=25, never_expires=True, reason="x")
        again = ledger.grant_campaign_gift(customer=self.silent, campaign_public_id=campaign_id, points=25, never_expires=True, reason="x")
        self.assertIsNotNone(first)
        self.assertIsNone(again)
        self.assertTrue(first.never_expires)
        self.assertEqual(ledger.balance(self.silent), 25)

    def test_only_active_verified_customers(self):
        from apps.accounts import services as accounts

        unverified = accounts.register_customer(**registration_data(email="pendiente@example.com"))
        for user in (unverified, self.employee):
            self.assertIsNone(
                ledger.grant_campaign_gift(customer=user, campaign_public_id=uuid.uuid4(), points=5, never_expires=False, reason="x")
            )
        self.assertFalse(PointsTransaction.objects.filter(kind=Kind.CAMPAIGN_GIFT).exists())


class SelectedCampaignServiceTests(CampaignTestCase):
    def test_only_consenting_selected_receive_but_all_selected_get_points(self):
        campaign = self.selected_campaign([self.consenting, self.silent], gift_points=30, gift_points_expire=False)
        campaigns.queue_campaign(actor=self.owner, campaign=campaign)
        campaigns.dispatch_queued()
        campaign.refresh_from_db()
        recipients = set(Notification.objects.filter(campaign=campaign).values_list("recipient", flat=True))
        self.assertEqual(recipients, {self.consenting.pk})
        self.assertEqual((campaign.recipients_count, campaign.gifted_count), (1, 2))
        self.assertEqual(gifts(self.consenting).get().points, 30)
        self.assertTrue(gifts(self.silent).get().never_expires)
        self.assertFalse(gifts(self.other).exists())
        # Un segundo reparto no duplica mensajes ni puntos.
        self.assertEqual(campaigns.dispatch_queued(), 0)
        self.assertEqual(PointsTransaction.objects.filter(kind=Kind.CAMPAIGN_GIFT).count(), 2)

    def test_all_audience_gives_points_only_to_recipients(self):
        campaign = campaigns.create_and_queue(
            actor=self.owner,
            campaign=Campaign(),
            data={"name": "Todos", "subject": "Hola", "body": "Texto", "channel": Channel.EMAIL, "audience": Audience.ALL, "gift_points": 10},
        )
        self.assertEqual(campaign.status, Campaign.Status.QUEUED)
        campaigns.dispatch_queued()
        self.assertEqual(set(PointsTransaction.objects.filter(kind=Kind.CAMPAIGN_GIFT).values_list("customer", flat=True)), {self.consenting.pk, self.other.pk})

    def test_selection_ignores_staff_and_unknown_ids(self):
        campaign = campaigns.save_campaign(
            actor=self.owner,
            campaign=Campaign(),
            data={"name": "x", "subject": "y", "body": "z", "channel": Channel.EMAIL, "audience": Audience.SELECTED},
            recipients=[self.silent.public_id, self.employee.public_id, self.owner.public_id, uuid.uuid4()],
        )
        self.assertEqual(list(campaign.selected_recipients.values_list("customer", flat=True)), [self.silent.pk])

    def test_selected_audience_needs_customers_and_required_fields(self):
        with self.assertRaises(ValidationError):
            self.selected_campaign([])
        for field in ("name", "subject", "body"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.selected_campaign([self.silent], **{field: ""})
        with self.assertRaises(ValidationError):
            self.selected_campaign([self.silent], gift_points=Campaign.MAX_GIFT_POINTS + 1)
        self.assertFalse(Campaign.objects.exists())

    def test_create_and_queue_is_all_or_nothing(self):
        # SMS sin proveedor: no se puede programar y tampoco queda el borrador.
        with self.assertRaises(ValidationError):
            campaigns.create_and_queue(
                actor=self.owner,
                campaign=Campaign(),
                data={"name": "x", "subject": "y", "body": "z", "channel": Channel.SMS, "audience": Audience.ALL},
            )
        self.assertFalse(Campaign.objects.exists())


class ImageEmailTests(TempMediaMixin, CampaignTestCase):
    def test_email_carries_inline_image_and_unsubscribe_link(self):
        campaign = campaigns.create_and_queue(
            actor=self.owner,
            campaign=Campaign(),
            data={"name": "Foto", "subject": "Mira", "body": "<b>Hola</b>", "channel": Channel.EMAIL, "audience": Audience.ALL, "gift_points": 5},
            image=uploaded_image(),
        )
        self.assertTrue(campaign.image.name.startswith("campaigns/"))
        campaigns.dispatch_queued()
        services.process_due()
        message = next(m for m in mail.outbox if m.subject == "Mira")
        html, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn('src="cid:imagen"', html)
        self.assertIn("&lt;b&gt;Hola&lt;/b&gt;", html)  # el texto se escapa
        self.assertIn("/comunicaciones/baja/", html)
        self.assertIn("/comunicaciones/baja/", message.body)
        self.assertTrue(any(getattr(part, "get", lambda *_: None)("Content-ID") == "<imagen>" for part in message.attachments))
        self.assertIn("5", message.body)

    def test_sms_drops_the_image(self):
        campaign = campaigns.save_campaign(
            actor=self.owner,
            campaign=Campaign(),
            data={"name": "x", "subject": "y", "body": "z", "channel": Channel.SMS, "audience": Audience.ALL},
            image=uploaded_image(),
        )
        self.assertFalse(campaign.image)


class DashboardFlowTests(TempMediaMixin, CampaignTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)
        buy(self.employee, self.consenting_token, "10.00")

    def test_spent_filter(self):
        url = reverse("dashboard:customers")
        without = {c.pk for c in self.client.get(url, {"gasto": "sin"}).context["page"]}
        with_purchases = {c.pk for c in self.client.get(url, {"gasto": "con"}).context["page"]}
        self.assertEqual(with_purchases, {self.consenting.pk})
        self.assertIn(self.silent.pk, without)
        self.assertNotIn(self.consenting.pk, without)

    def test_customers_page_has_send_column(self):
        response = self.client.get(reverse("dashboard:customers"))
        self.assertContains(response, "data-select-all")
        self.assertContains(response, f'value="{self.silent.public_id}" form="seleccion-envio"')
        self.assertContains(response, "data-selection-bar")

    def test_selection_keeps_only_customers_in_session(self):
        response = self.client.post(
            SELECTION_URL, {"cliente": [self.silent.public_id, self.employee.public_id, "no-es-un-uuid"]}
        )
        self.assertRedirects(response, CREATE_SELECTED_URL)
        self.assertEqual(self.client.session[dashboard_views.SELECTION_SESSION_KEY], [str(self.silent.public_id)])
        form_page = self.client.get(CREATE_SELECTED_URL)
        self.assertEqual(form_page.context["selected_count"], 1)
        self.assertEqual(form_page.context["selected_reach"].email, 0)

    def test_select_all_filtered(self):
        self.client.post(SELECTION_URL, {"todos": "1", "filtros": "gasto=sin"})
        selected = set(self.client.session[dashboard_views.SELECTION_SESSION_KEY])
        self.assertIn(str(self.silent.public_id), selected)
        self.assertNotIn(str(self.consenting.public_id), selected)

    def test_empty_selection_goes_back(self):
        response = self.client.post(SELECTION_URL, {"filtros": "gasto=sin"})
        self.assertRedirects(response, reverse("dashboard:customers") + "?gasto=sin")
        self.assertNotIn(dashboard_views.SELECTION_SESSION_KEY, self.client.session)

    def test_only_owner(self):
        for user in (self.employee, self.silent):
            self.client.force_login(user)
            self.assertEqual(self.client.post(SELECTION_URL, {"cliente": [self.silent.public_id]}).status_code, 403)
            self.assertEqual(self.client.get(CREATE_URL).status_code, 403)

    def test_create_and_send_to_selected(self):
        self.client.post(SELECTION_URL, {"cliente": [self.silent.public_id, self.consenting.public_id]})
        data = {
            "name": "Vecinos",
            "subject": "Hola",
            "audience": "SELECTED",
            "channel": "EMAIL",
            "body": "Texto",
            "gift_points": "15",
            "gift_points_expire": "no",
            "image": uploaded_image(),
            "enviar": "1",
        }
        response = self.client.post(CREATE_SELECTED_URL, data)
        self.assertRedirects(response, reverse("dashboard:communications"))
        campaign = Campaign.objects.get()
        self.assertEqual((campaign.status, campaign.audience, campaign.gift_points, campaign.gift_points_expire), (Campaign.Status.QUEUED, Audience.SELECTED, 15, False))
        self.assertEqual(CampaignRecipient.objects.filter(campaign=campaign).count(), 2)
        self.assertTrue(campaign.image)
        self.assertNotIn(dashboard_views.SELECTION_SESSION_KEY, self.client.session)
        history = self.client.get(reverse("dashboard:communications"))
        self.assertContains(history, "Vecinos")

    def test_draft_button_only_saves(self):
        data = {"name": "Borrador", "subject": "Hola", "audience": "ALL", "channel": "EMAIL", "body": "Texto", "gift_points_expire": "si"}
        self.client.post(CREATE_URL, data)
        self.assertEqual(Campaign.objects.get().status, Campaign.Status.DRAFT)

    def test_invalid_image_is_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        fake = SimpleUploadedFile("foto.png", b"<script>alert(1)</script>", content_type="image/png")
        data = {"name": "x", "subject": "y", "audience": "ALL", "channel": "EMAIL", "body": "z", "image": fake, "enviar": "1"}
        response = self.client.post(CREATE_URL, data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Campaign.objects.exists())

    def test_selected_without_selection_is_rejected(self):
        data = {"name": "x", "subject": "y", "audience": "SELECTED", "channel": "EMAIL", "body": "z", "enviar": "1"}
        self.assertEqual(self.client.post(CREATE_URL, data).status_code, 400)
        self.assertFalse(Campaign.objects.exists())

    def test_form_has_send_button_requiring_fields(self):
        response = self.client.get(CREATE_URL)
        self.assertContains(response, 'data-requires="name subject body"')
        self.assertContains(response, 'enctype="multipart/form-data"')
