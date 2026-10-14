from django.urls import path

from . import views

app_name = "staff"

# Montadas bajo /panel/ (empleados y propietarios). Las operaciones viven en
# /panel/compras/ (apps.purchases) y /panel/canjes/ (apps.rewards).
urlpatterns = [
    path("", views.home, name="home"),
    path("perfil/", views.profile, name="profile"),
    path("resultados/", views.results, name="results"),
]
