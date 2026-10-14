from rest_framework import generics
from rest_framework.views import APIView

from ..throttling import AnonThrottle, AuthThrottle, UserThrottle


class _NoStoreMixin:
    """Las respuestas llevan datos de la cuenta, saldos o códigos: ni el navegador ni los proxies las guardan."""

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response.headers.setdefault("Cache-Control", "no-store, private")
        return response


class ApiView(_NoStoreMixin, APIView):
    pass


class ListApiView(_NoStoreMixin, generics.ListAPIView):
    pass


class PublicAuthView(ApiView):
    """Login, registro, verificación y recuperación: sin sesión y con límite por IP."""

    authentication_classes = []
    permission_classes = []
    throttle_classes = [AuthThrottle, AnonThrottle, UserThrottle]


def idempotency_key(request):
    """La app envía un UUID por operación en la cabecera `Idempotency-Key`; el servicio lo valida."""
    return request.headers.get("Idempotency-Key", "")
