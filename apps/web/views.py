"""
Páginas públicas. Solo presentación: no contienen reglas de negocio.

Carta, recompensas y eventos aún no tienen modelos (Fases 4, 7 y 8). Las vistas
pasan listas vacías con los nombres que usarán esas fases, de modo que las
plantillas ya muestran su estado vacío y solo habrá que rellenar el contexto.
"""
from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = "web/home.html"
    extra_context = {"featured_beers": [], "featured_events": []}


class AboutView(TemplateView):
    template_name = "web/about.html"


class MenuView(TemplateView):
    template_name = "web/menu.html"
    extra_context = {"categories": []}


class RewardsView(TemplateView):
    template_name = "web/rewards.html"
    extra_context = {"rewards": []}


class EventsView(TemplateView):
    template_name = "web/events.html"
    extra_context = {"events": []}


class ContactView(TemplateView):
    template_name = "web/contact.html"
