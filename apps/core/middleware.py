"""Middleware transversal de la plataforma."""
from django.db import DatabaseError, connection
from django.http import HttpResponse

HEALTH_PATH = "/healthz"


class HealthCheckMiddleware:
    """
    Responde a `GET /healthz` para los healthchecks de Docker y Nginx.

    Va el primero de `MIDDLEWARE`: contesta antes de la validación de
    `ALLOWED_HOSTS` y de la redirección a HTTPS, que harían fallar la comprobación
    interna (`http://localhost:8000`). Solo comprueba que la BD responde; no
    devuelve versiones, nombres de servicios ni ningún otro dato. Nginx no
    publica esta ruta.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path != HEALTH_PATH:
            return self.get_response(request)
        if request.method not in ("GET", "HEAD"):
            return _plain(405, "")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except DatabaseError:
            return _plain(503, "error")
        return _plain(200, "ok")


def _plain(status, body):
    response = HttpResponse(body, status=status, content_type="text/plain; charset=utf-8")
    response["Cache-Control"] = "no-store"
    return response
