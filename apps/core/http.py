"""
Utilidades HTTP compartidas por la web y la API.

`client_ip(request)` devuelve la IP que se usa para limitar intentos. Sin
proxy (`TRUSTED_PROXY_COUNT = 0`, valor por defecto) es `REMOTE_ADDR`. Detrás
de N proxies inversos de confianza que añaden su entrada a `X-Forwarded-For`,
la IP del cliente es la N-ésima empezando por la derecha: las entradas de la
izquierda las puede inventar el propio cliente y nunca se usan.

La IP solo se usa para contar intentos (se guarda como hash en la caché); no
se registra en logs ni en la base de datos.
"""
from django.conf import settings

from . import throttling


def client_ip(request):
    remote_addr = request.META.get("REMOTE_ADDR") or "-"
    proxies = getattr(settings, "TRUSTED_PROXY_COUNT", 0)
    if proxies <= 0:
        return remote_addr
    forwarded = [part.strip() for part in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if part.strip()]
    if len(forwarded) < proxies:
        # Cabecera ausente o incompleta: la petición no pasó por todos los proxies.
        return remote_addr
    return forwarded[-proxies]


def ip_limited(request, scope, limit, window_seconds=60 * 60):
    """Cuenta un intento de `request` en `scope` y devuelve True si se supera `limit` en la ventana."""
    ip = client_ip(request)
    if throttling.is_limited(scope, ip, limit):
        return True
    throttling.register_attempt(scope, ip, window_seconds)
    return False
