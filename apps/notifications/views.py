"""
Baja de las comunicaciones promocionales desde el enlace de un mensaje.

GET muestra un botón; POST retira el consentimiento con
`accounts.services.withdraw_promotional_consent` (queda en el historial de
preferencias con origen «Enlace de baja»). Un enlace no válido o caducado
muestra la misma página genérica, sin revelar si la cuenta existe.
"""
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.accounts import services as accounts

from . import unsubscribe as tokens
from .models import Channel


@never_cache
@require_http_methods(["GET", "POST"])
def unsubscribe(request, token):
    found = tokens.read_token(token)
    if found is None:
        return render(request, "notifications/unsubscribe.html", {"invalid": True}, status=400)
    user, channel = found
    context = {"channel_label": Channel(channel).label.lower(), "done": False}
    if request.method == "POST":
        accounts.withdraw_promotional_consent(user=user, channel=channel)
        context["done"] = True
    return render(request, "notifications/unsubscribe.html", context)
