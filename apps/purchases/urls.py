from django.urls import path

from . import views

app_name = "purchases"

urlpatterns = [
    path("", views.scan, name="scan"),
    path("identificar/", views.identify, name="identify"),
    path("registrar/", views.register, name="register"),
    path("<uuid:public_id>/", views.detail, name="detail"),
]
