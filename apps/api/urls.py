"""Rutas de la API v1, montadas en `/api/v1/`."""
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authentication import SessionAuthentication

from .authentication import JWTAuthentication
from .permissions import CanReadApiDocs
from .views import auth, events, loyalty, me, owner, rewards, staff

app_name = "api"

# Esquema y documentación: GET de solo lectura. Aceptan también la sesión web
# para que el propietario pueda abrirlas en el navegador (sin riesgo CSRF: no
# modifican nada).
_docs = {"permission_classes": [CanReadApiDocs], "authentication_classes": [SessionAuthentication, JWTAuthentication]}

urlpatterns = [
    # Autenticación
    path("auth/register/", auth.RegisterView.as_view(), name="register"),
    path("auth/email/verify/", auth.VerifyEmailView.as_view(), name="verify_email"),
    path("auth/email/resend/", auth.ResendVerificationView.as_view(), name="resend_verification"),
    path("auth/login/", auth.LoginView.as_view(), name="login"),
    path("auth/token/refresh/", auth.TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", auth.LogoutView.as_view(), name="logout"),
    path("auth/logout-all/", auth.LogoutAllView.as_view(), name="logout_all"),
    path("auth/password/change/", auth.PasswordChangeView.as_view(), name="password_change"),
    path("auth/password/reset/", auth.PasswordResetView.as_view(), name="password_reset"),
    path("auth/password/reset/confirm/", auth.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    # Mi cuenta
    path("me/", me.MeView.as_view(), name="me"),
    path("me/profile/", me.ProfileView.as_view(), name="profile"),
    path("me/preferences/", me.PreferencesView.as_view(), name="preferences"),
    path("me/email/change/", me.EmailChangeView.as_view(), name="email_change"),
    path("me/email/resend-verification/", me.ResendMyVerificationView.as_view(), name="resend_my_verification"),
    # Puntos, compras y QR
    path("me/points/", loyalty.PointsSummaryView.as_view(), name="points"),
    path("me/points/movements/", loyalty.MovementListView.as_view(), name="movements"),
    path("me/purchases/", loyalty.PurchaseListView.as_view(), name="purchases"),
    path("me/qr/", loyalty.QRCodeView.as_view(), name="qr"),
    path("me/qr/rotate/", loyalty.QRCodeRotateView.as_view(), name="qr_rotate"),
    # Recompensas y canjes
    path("rewards/", rewards.RewardListView.as_view(), name="rewards"),
    path("rewards/<uuid:public_id>/", rewards.RewardDetailView.as_view(), name="reward"),
    path("rewards/<uuid:public_id>/redeem/", rewards.RedeemView.as_view(), name="redeem"),
    path("me/redemptions/", rewards.MyRedemptionListView.as_view(), name="redemptions"),
    path("me/redemptions/<uuid:public_id>/", rewards.MyRedemptionDetailView.as_view(), name="redemption"),
    path("me/redemptions/<uuid:public_id>/cancel/", rewards.MyRedemptionCancelView.as_view(), name="redemption_cancel"),
    # Eventos y reservas
    path("events/", events.EventListView.as_view(), name="events"),
    path("events/<uuid:public_id>/", events.EventDetailView.as_view(), name="event"),
    path("me/reservations/", events.MyReservationListView.as_view(), name="reservations"),
    path("me/reservations/<uuid:public_id>/", events.MyReservationDetailView.as_view(), name="reservation"),
    path("me/reservations/<uuid:public_id>/cancel/", events.MyReservationCancelView.as_view(), name="reservation_cancel"),
    # Personal
    path("staff/purchases/identify/", staff.IdentifyCustomerView.as_view(), name="staff_identify"),
    path("staff/purchases/", staff.RegisterPurchaseView.as_view(), name="staff_purchases"),
    path("staff/redemptions/lookup/", staff.LookupRedemptionView.as_view(), name="staff_redemption_lookup"),
    path("staff/redemptions/validate/", staff.ValidateRedemptionView.as_view(), name="staff_redemption_validate"),
    # Propietario
    path("owner/stats/", owner.OwnerStatsView.as_view(), name="owner_stats"),
    path("owner/reservations/", owner.OwnerReservationListView.as_view(), name="owner_reservations"),
    path(
        "owner/reservations/<uuid:public_id>/<slug:action>/",
        owner.OwnerReservationTransitionView.as_view(),
        name="owner_reservation_transition",
    ),
    # Esquema OpenAPI y documentación interactiva
    path("schema/", SpectacularAPIView.as_view(**_docs), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema", **_docs), name="docs"),
]
