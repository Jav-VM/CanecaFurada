from django.urls import path

from . import views

app_name = "notifications"

# Montadas bajo /comunicaciones/.
urlpatterns = [
    path("baja/<str:token>/", views.unsubscribe, name="unsubscribe"),
]
