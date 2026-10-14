"""
Páginas públicas. Solo presentación: no contienen reglas de negocio.

La carta se obtiene de `apps.catalog.selectors`, que decide qué es público y
qué está disponible; las recompensas, de `apps.rewards.selectors`; los
eventos, de `apps.events.selectors` (solo publicados y no terminados).
"""
from django.views.generic import TemplateView

from apps.catalog import selectors as catalog
from apps.events import selectors as events
from apps.rewards import selectors as rewards


class HomeView(TemplateView):
    template_name = "web/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["featured_beers"] = catalog.featured_beers()
        context["featured_events"] = events.featured_events()
        return context


class AboutView(TemplateView):
    template_name = "web/about.html"


class MenuView(TemplateView):
    template_name = "web/menu.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = catalog.public_menu()
        context["tap_menu"] = catalog.current_tap_menu()
        return context


class RewardsView(TemplateView):
    template_name = "web/rewards.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["rewards"] = rewards.public_rewards()
        return context


class EventsView(TemplateView):
    template_name = "web/events.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["events"] = events.public_events()
        return context


class ContactView(TemplateView):
    template_name = "web/contact.html"
