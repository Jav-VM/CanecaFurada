from django.urls import path

from . import views

app_name = "rewards"

# Montadas bajo /cuenta/ (cliente).
urlpatterns = [
    path("recompensas/<uuid:public_id>/", views.reward_detail, name="reward_detail"),
    path("recompensas/<uuid:public_id>/canjear/", views.redeem, name="redeem"),
    path("canjes/", views.my_redemptions, name="my_redemptions"),
    path("canjes/<uuid:public_id>/", views.redemption_detail, name="redemption_detail"),
    path("canjes/<uuid:public_id>/cancelar/", views.cancel, name="cancel"),
]
