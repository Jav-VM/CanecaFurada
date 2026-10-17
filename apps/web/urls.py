from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("la-cerveceria/", views.AboutView.as_view(), name="about"),
    path("carta/", views.MenuView.as_view(), name="menu"),
    path("recompensas/", views.RewardsView.as_view(), name="rewards"),
    path("eventos/", views.EventsView.as_view(), name="events"),
    path("contacto/", views.ContactView.as_view(), name="contact"),
    path("legal/<slug:kind>/", views.LegalView.as_view(), name="legal"),
]
