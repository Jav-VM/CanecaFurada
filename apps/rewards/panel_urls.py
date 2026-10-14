from django.urls import path

from . import views

app_name = "rewards_panel"

# Montadas bajo /panel/canjes/ (empleados y propietarios).
urlpatterns = [
    path("", views.staff_scan, name="scan"),
    path("consultar/", views.staff_lookup, name="lookup"),
    path("validar/", views.staff_validate, name="validate"),
    path("<uuid:public_id>/", views.staff_detail, name="detail"),
]
