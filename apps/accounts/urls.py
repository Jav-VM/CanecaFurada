from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("", views.home, name="home"),
    path("registro/", views.register, name="register"),
    path("registro/enviado/", views.register_done, name="register_done"),
    path("localidades/", views.localities, name="localities"),
    path("verificar-email/reenviar/", views.resend_verification, name="resend_verification"),
    path("verificar-email/reenviar-mio/", views.resend_verification_self, name="resend_verification_self"),
    path("verificar-email/<str:token>/", views.verify_email, name="verify_email"),
    path("perfil/", views.profile, name="profile"),
    path("perfil/preferencias/", views.preferences, name="preferences"),
    path("perfil/email/", views.email_change, name="email_change"),
    path("perfil/contrasena/", views.PasswordChangeView.as_view(), name="password_change"),
    path("entrar/", views.LoginView.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("contrasena/recuperar/", views.PasswordResetView.as_view(), name="password_reset"),
    path(
        "contrasena/recuperar/enviado/",
        auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "contrasena/restablecer/<uidb64>/<token>/",
        views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "contrasena/restablecida/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]
