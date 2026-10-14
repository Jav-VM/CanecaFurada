from django.conf import settings
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Caneca Furada — Administración"
admin.site.site_title = "Caneca Furada"

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("cuenta/", include("apps.accounts.urls")),
]
