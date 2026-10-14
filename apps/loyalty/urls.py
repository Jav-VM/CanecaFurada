from django.urls import path

from . import views

app_name = "loyalty"

# Montadas bajo /cuenta/ (antes que las de accounts).
urlpatterns = [
    path("mi-qr/", views.my_qr, name="my_qr"),
    path("mi-qr/renovar/", views.rotate, name="rotate"),
    path("puntos/", views.my_points, name="my_points"),
]
