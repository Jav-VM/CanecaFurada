from django.urls import path

from . import views

app_name = "events"

# Montadas en la raíz (ver `config/urls.py`): detalle público bajo /eventos/ y
# reservas del cliente bajo /cuenta/. Los objetos se identifican por su `public_id`.
urlpatterns = [
    path("eventos/<uuid:public_id>/", views.event_detail, name="event_detail"),
    path("cuenta/reservas/", views.my_reservations, name="my_reservations"),
    path("cuenta/reservas/nueva/", views.reservation_new, name="reservation_new"),
    path("cuenta/reservas/evento/<uuid:public_id>/", views.event_reservation_new, name="event_reservation_new"),
    path("cuenta/reservas/<uuid:public_id>/", views.reservation_detail, name="reservation_detail"),
    path("cuenta/reservas/<uuid:public_id>/cancelar/", views.reservation_cancel, name="reservation_cancel"),
]
