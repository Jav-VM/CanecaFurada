"""
Fase 24: «Eliminar» del dashboard las campañas canceladas o repartidas (se conservan
en la BD y en el admin, solo lectura) y Comunicaciones sin scroll lateral.
"""
import re
import uuid

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.core.models import AuditEvent
from apps.notifications import campaigns
from apps.notifications.models import Campaign, CampaignRecipient, Channel, Notification
from tests.loyalty.factories import make_customer_with_qr, make_employee, make_owner

Status = Campaign.Status
COMMUNICATIONS = reverse("dashboard:communications")


class HideCampaignTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_owner()
        self.employee = make_employee()
        self.customer, _token = make_customer_with_qr("si@example.com", promo_email_opt_in=True)
        self.client.force_login(self.owner)

    def campaign(self, name, status=Status.DRAFT):
        data = {"name": name, "subject": "Ola", "body": "Texto", "channel": Channel.EMAIL, "audience": Campaign.Audience.ALL}
        campaign = campaigns.save_campaign(actor=self.owner, campaign=Campaign(), data=data)
        if status == Status.DISPATCHED:
            campaigns.queue_campaign(actor=self.owner, campaign=campaign)
            campaigns.dispatch_queued()
        elif status == Status.CANCELLED:
            campaigns.cancel_campaign(actor=self.owner, campaign=campaign)
        elif status == Status.QUEUED:
            campaigns.queue_campaign(actor=self.owner, campaign=campaign)
        campaign.refresh_from_db()
        return campaign

    def hide_url(self, campaign):
        return reverse("dashboard:campaign_hide", args=[campaign.public_id])

    def test_button_is_active_only_for_cancelled_or_dispatched(self):
        # La repartida primero: `dispatch_queued` reparte todas las programadas que haya.
        dispatched = self.campaign("Repartida", Status.DISPATCHED)
        draft = self.campaign("Borrador")
        queued = self.campaign("Programada", Status.QUEUED)
        cancelled = self.campaign("Cancelada", Status.CANCELLED)
        html = self.client.get(COMMUNICATIONS).content.decode()
        for campaign in (cancelled, dispatched):
            self.assertIn(f'href="{self.hide_url(campaign)}" data-hide-campaign', html)
        for campaign in (draft, queued):
            self.assertNotIn(self.hide_url(campaign), html)
        self.assertEqual(html.count("data-hide-campaign-disabled"), 2)

    def test_hide_removes_it_from_the_dashboard_but_keeps_everything(self):
        name = "Campaña Ficticia Verán"
        dispatched = self.campaign(name, Status.DISPATCHED)
        notifications = Notification.objects.filter(campaign=dispatched).count()
        self.assertEqual(notifications, 1)
        self.assertContains(self.client.get(self.hide_url(dispatched)), "data-campaign-hide")
        response = self.client.post(self.hide_url(dispatched))
        self.assertRedirects(response, COMMUNICATIONS, fetch_redirect_response=False)
        dispatched.refresh_from_db()
        self.assertIsNotNone(dispatched.hidden_at)
        self.assertEqual(dispatched.status, Status.DISPATCHED)
        self.assertEqual(Notification.objects.filter(campaign=dispatched).count(), notifications)
        self.client.get(COMMUNICATIONS)  # consume el mensaje de confirmación, que lleva el nombre
        self.assertNotIn(name, self.client.get(COMMUNICATIONS).content.decode())
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.Action.CAMPAIGN_UPDATED, metadata__event="hidden").exists())
        # Tampoco aparece en «Enviar una campaña ya creada».
        self.client.post(reverse("dashboard:customer_selection"), {"cliente": [self.customer.public_id]})
        self.assertNotContains(self.client.get(reverse("dashboard:campaign_create") + "?destinatarios=seleccion"), name)
        # Ya quitada: 404 en su página de eliminar; el servicio no cambia nada.
        self.assertEqual(self.client.get(self.hide_url(dispatched)).status_code, 404)
        hidden_at = dispatched.hidden_at
        campaigns.hide_campaign(actor=self.owner, campaign=dispatched)
        dispatched.refresh_from_db()
        self.assertEqual(dispatched.hidden_at, hidden_at)

    def test_selected_campaign_keeps_its_recipients(self):
        campaign = campaigns.save_campaign(
            actor=self.owner,
            campaign=Campaign(),
            data={"name": "Só eles", "subject": "x", "body": "y", "channel": Channel.EMAIL, "audience": Campaign.Audience.SELECTED},
            recipients=[self.customer.public_id],
        )
        campaigns.cancel_campaign(actor=self.owner, campaign=campaign)
        self.client.post(self.hide_url(campaign))
        self.assertTrue(CampaignRecipient.objects.filter(campaign=campaign).exists())
        self.assertTrue(Campaign.objects.filter(pk=campaign.pk, hidden_at__isnull=False).exists())

    def test_draft_and_queued_cannot_be_hidden(self):
        for status in (Status.DRAFT, Status.QUEUED):
            campaign = self.campaign(f"Non {status}", status)
            with self.subTest(status=status):
                self.assertRedirects(self.client.get(self.hide_url(campaign)), COMMUNICATIONS, fetch_redirect_response=False)
                self.client.post(self.hide_url(campaign))
                campaign.refresh_from_db()
                self.assertIsNone(campaign.hidden_at)
                with self.assertRaises(ValidationError):
                    campaigns.hide_campaign(actor=self.owner, campaign=campaign)
        self.assertEqual(self.client.get(reverse("dashboard:campaign_hide", args=[uuid.uuid4()])).status_code, 404)

    def test_only_owner(self):
        cancelled = self.campaign("Cancelada", Status.CANCELLED)
        for user in (self.employee, self.customer):
            self.client.force_login(user)
            self.assertEqual(self.client.post(self.hide_url(cancelled)).status_code, 403)
        self.client.logout()
        self.assertIn(reverse("accounts:login"), self.client.post(self.hide_url(cancelled))["Location"])
        cancelled.refresh_from_db()
        self.assertIsNone(cancelled.hidden_at)

    def test_communications_fit_without_side_scroll(self):
        self.campaign("Repartida", Status.DISPATCHED)
        html = self.client.get(COMMUNICATIONS).content.decode()
        # Las campañas, siempre en tarjetas; el registro, compacto desde xl y en tarjetas por debajo.
        self.assertIn('class="data-table data-table-fit data-table-cards" data-campaign-list', html)
        self.assertIn('class="data-table data-table-fit" data-notification-log', html)
        for marker in ("data-campaign-list", "data-notification-log"):
            with self.subTest(table=marker):
                start = html.index(marker)
                body = html[html.index("<tbody>", start):html.index("</table>", start)]
                cells = re.findall(r"<td\b[^>]*>", body)
                self.assertTrue(cells)
                self.assertTrue(all("data-label=" in cell for cell in cells), cells)


class CampaignAdminTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_owner()
        self.employee = make_employee()
        data = {"name": "Oculta", "subject": "x", "body": "y", "channel": Channel.EMAIL, "audience": Campaign.Audience.ALL}
        self.campaign = campaigns.save_campaign(actor=self.owner, campaign=Campaign(), data=data)
        campaigns.cancel_campaign(actor=self.owner, campaign=self.campaign)
        campaigns.hide_campaign(actor=self.owner, campaign=self.campaign)

    def test_owner_sees_hidden_campaigns_read_only(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("admin:notifications_campaign_changelist")), "Oculta")
        self.assertEqual(self.client.get(reverse("admin:notifications_campaign_add")).status_code, 403)
        change_url = reverse("admin:notifications_campaign_change", args=[self.campaign.pk])
        page = self.client.get(change_url)
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'name="_save"')
        self.client.post(change_url, {"name": "Cambiada"})
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.name, "Oculta")
        self.assertEqual(self.client.get(reverse("admin:notifications_campaign_delete", args=[self.campaign.pk])).status_code, 403)

    def test_employee_cannot_see_campaigns_in_admin(self):
        self.client.force_login(self.employee)
        self.assertNotEqual(self.client.get(reverse("admin:notifications_campaign_changelist")).status_code, 200)


class ReactivateCampaignTests(TestCase):
    """Una campaña cancelada vuelve a borrador para editarla y programarla otra vez."""

    campaign = HideCampaignTests.campaign

    def setUp(self):
        cache.clear()
        self.owner = make_owner()
        self.employee = make_employee()
        self.customer, _token = make_customer_with_qr("si@example.com", promo_email_opt_in=True)
        self.client.force_login(self.owner)

    def url(self, campaign):
        return reverse("dashboard:campaign_reactivate", args=[campaign.public_id])

    def test_cancelled_campaign_goes_back_to_draft_and_can_be_sent(self):
        cancelled = self.campaign("Recuperable", Status.CANCELLED)
        html = self.client.get(COMMUNICATIONS).content.decode()
        self.assertIn(f'action="{self.url(cancelled)}"', html)
        response = self.client.post(self.url(cancelled))
        self.assertRedirects(response, COMMUNICATIONS, fetch_redirect_response=False)
        cancelled.refresh_from_db()
        self.assertEqual((cancelled.status, cancelled.queued_at), (Status.DRAFT, None))
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.Action.CAMPAIGN_UPDATED, metadata__event="reactivated").exists())
        # Ya en borrador: se edita y se programa como cualquier otra.
        self.assertEqual(self.client.get(reverse("dashboard:campaign_edit", args=[cancelled.public_id])).status_code, 200)
        campaigns.queue_campaign(actor=self.owner, campaign=cancelled)
        campaigns.dispatch_queued()
        self.assertEqual(Notification.objects.filter(campaign=cancelled).count(), 1)

    def test_only_cancelled_and_not_hidden(self):
        dispatched = self.campaign("Repartida", Status.DISPATCHED)
        draft = self.campaign("Borrador")
        queued = self.campaign("Programada", Status.QUEUED)
        for campaign in (draft, queued, dispatched):
            with self.subTest(status=campaign.status):
                before = campaign.status
                self.client.post(self.url(campaign))
                campaign.refresh_from_db()
                self.assertEqual(campaign.status, before)
                with self.assertRaises(ValidationError):
                    campaigns.reactivate_campaign(actor=self.owner, campaign=campaign)
        hidden = self.campaign("Oculta", Status.CANCELLED)
        campaigns.hide_campaign(actor=self.owner, campaign=hidden)
        self.assertEqual(self.client.post(self.url(hidden)).status_code, 404)
        self.assertEqual(self.client.post(reverse("dashboard:campaign_reactivate", args=[uuid.uuid4()])).status_code, 404)

    def test_only_owner_and_only_post(self):
        cancelled = self.campaign("Cancelada", Status.CANCELLED)
        self.assertEqual(self.client.get(self.url(cancelled)).status_code, 405)
        for user in (self.employee, self.customer):
            self.client.force_login(user)
            self.assertEqual(self.client.post(self.url(cancelled)).status_code, 403)
        cancelled.refresh_from_db()
        self.assertEqual(cancelled.status, Status.CANCELLED)

    def test_date_is_on_the_right_of_the_name(self):
        self.campaign("Con fecha")
        html = self.client.get(COMMUNICATIONS).content.decode()
        self.assertRegex(html, r'<span class="min-w-0 flex-1 break-words">Con fecha</span><span class="ml-auto[^"]*" data-campaign-date>')


class TemplateCommentsTests(TestCase):
    """Django solo trata `{# … #}` como comentario en una línea: en varias, se pinta en la página."""

    def test_no_multiline_hash_comments_in_templates(self):
        from pathlib import Path

        from django.conf import settings

        offenders = []
        for path in (Path(settings.BASE_DIR) / "templates").rglob("*.*"):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "{#" in line and "#}" not in line[line.index("{#"):]:
                    offenders.append(f"{path.name}:{number}")
        self.assertEqual(offenders, [])
