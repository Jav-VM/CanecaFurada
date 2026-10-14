from django.urls import path

from . import views

app_name = "loyalty"

urlpatterns = [
    path("", views.my_qr, name="my_qr"),
    path("renovar/", views.rotate, name="rotate"),
]
