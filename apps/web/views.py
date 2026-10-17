"""
Páginas públicas. Solo presentación: no contienen reglas de negocio.

La carta se obtiene de `apps.catalog.selectors`, que decide qué es público y
qué está disponible; las recompensas, de `apps.rewards.selectors`; los
eventos, de `apps.events.selectors` (solo publicados y no terminados).
"""
from django.http import Http404
from django.views.generic import TemplateView

from apps.catalog import selectors as catalog
from apps.events import selectors as events
from apps.rewards import selectors as rewards

from . import blocks, layout, legal
from . import services as web


class HomeView(TemplateView):
    template_name = "web/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["featured_beers"] = catalog.featured_beers()
        context["featured_events"] = events.featured_events()
        context["sections"] = blocks.page_sections(layout.HOME, web.business_info())
        return context


class AboutView(TemplateView):
    template_name = "web/about.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sections"] = blocks.page_sections(layout.ABOUT, web.business_info())
        return context


class MenuView(TemplateView):
    template_name = "web/menu.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = catalog.public_menu()
        context["tap_menu"] = catalog.current_tap_menu()
        context["sections"] = blocks.page_sections(layout.MENU, web.business_info())
        return context


class RewardsView(TemplateView):
    template_name = "web/rewards.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["rewards"] = rewards.public_rewards()
        context["sections"] = blocks.page_sections(layout.REWARDS, web.business_info())
        return context


class EventsView(TemplateView):
    template_name = "web/events.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["events"] = events.public_events()
        context["sections"] = blocks.page_sections(layout.EVENTS, web.business_info())
        return context


class ContactView(TemplateView):
    template_name = "web/contact.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sections"] = blocks.page_sections(layout.CONTACT, web.business_info())
        return context


class LegalView(TemplateView):
    """Textos legales (Fase 25): el publicado por el propietario o, si no hay, el borrador base."""

    template_name = "web/legal.html"

    def get_context_data(self, **kwargs):
        kind = kwargs["kind"]
        if kind not in legal.KINDS:
            raise Http404
        context = super().get_context_data(**kwargs)
        context["document"] = legal.get_document(kind, web.business_info())
        context["legal_documents"] = [(value, label) for value, label in legal.Kind.choices]
        return context

