from django.urls import path

from . import views

app_name = "dashboard"

# Montadas bajo /dashboard/. Solo propietarios. Los objetos se identifican por su
# `public_id`; la búsqueda de clientes nunca viaja en la URL.
urlpatterns = [
    path("", views.home, name="home"),
    path("clientes/", views.customers, name="customers"),
    path("clientes/zonas/", views.customer_zones, name="customer_zones"),
    path("clientes/<uuid:public_id>/", views.customer_detail, name="customer_detail"),
    path("clientes/<uuid:public_id>/ajustar-puntos/", views.customer_adjust_points, name="customer_adjust_points"),
    path("clientes/<uuid:public_id>/compensar/", views.customer_reverse_movement, name="customer_reverse_movement"),
    path("empleados/", views.employees, name="employees"),
    path("empleados/nuevo/", views.employee_create, name="employee_create"),
    path("empleados/<uuid:public_id>/estado/", views.employee_status, name="employee_status"),
    path("empleados/<uuid:public_id>/rol/", views.employee_role, name="employee_role"),
    path("compras/", views.purchases, name="purchases"),
    path("puntos/", views.points, name="points"),
    path("recompensas/", views.rewards_view, name="rewards"),
    path("recompensas/<uuid:public_id>/estado/", views.reward_status, name="reward_status"),
    path("carta/", views.menu, name="menu"),
    path("cervezas/", views.beers, name="beers"),
    path("productos/<uuid:public_id>/estado/", views.product_status, name="product_status"),
    path("productos/<uuid:public_id>/disponibilidad/", views.product_availability, name="product_availability"),
    path("eventos/", views.events, name="events"),
    path("eventos/nuevo/", views.event_create, name="event_create"),
    path("eventos/<uuid:public_id>/editar/", views.event_edit, name="event_edit"),
    path("eventos/<uuid:public_id>/estado/", views.event_status, name="event_status"),
    path("reservas/", views.reservations, name="reservations"),
    path("reservas/<uuid:public_id>/", views.reservation_detail, name="reservation_detail"),
    path("reservas/<uuid:public_id>/estado/", views.reservation_action, name="reservation_action"),
    path("comunicaciones/", views.communications, name="communications"),
    path("comunicaciones/nueva/", views.campaign_create, name="campaign_create"),
    path("comunicaciones/<uuid:public_id>/editar/", views.campaign_edit, name="campaign_edit"),
    path("comunicaciones/<uuid:public_id>/programar/", views.campaign_queue, name="campaign_queue"),
    path("comunicaciones/<uuid:public_id>/cancelar/", views.campaign_cancel, name="campaign_cancel"),
    path("promociones/", views.promotions_view, name="promotions"),
    path("promociones/<uuid:public_id>/estado/", views.promotion_status, name="promotion_status"),
    path("contenido/", views.content, name="content"),
    path("configuracion/", views.settings_view, name="settings"),
    path("configuracion/caducidad/", views.settings_expiry, name="settings_expiry"),
    path("configuracion/cumpleanos/", views.settings_birthday, name="settings_birthday"),
]
