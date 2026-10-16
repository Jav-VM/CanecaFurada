from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.utils.translation import gettext_lazy as _

from apps.accounts.forms import ThrottledAdminAuthenticationForm

admin.site.site_header = _("Caneca Furada — Administración")
admin.site.site_title = "Caneca Furada"
# Mismo límite de intentos fallidos que el login web y la API.
admin.site.login_form = ThrottledAdminAuthenticationForm

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/v1/", include("apps.api.urls")),
    # Cambio de idioma con las banderas: POST con CSRF (django.views.i18n.set_language).
    path("i18n/", include("django.conf.urls.i18n")),
    path("cuenta/", include("apps.loyalty.urls")),
    path("cuenta/", include("apps.rewards.urls")),
    path("cuenta/", include("apps.accounts.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("panel/", include("apps.staff.urls")),
    path("panel/compras/", include("apps.purchases.urls")),
    path("panel/canjes/", include("apps.rewards.panel_urls")),
    path("comunicaciones/", include("apps.notifications.urls")),
    path("", include("apps.events.urls")),
    path("", include("apps.web.urls")),
]

# Solo en desarrollo: Django sirve las imágenes subidas. En producción las
# servirá el almacenamiento que se defina en la fase de despliegue (`static()` no hace
# nada con DEBUG=False).
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
