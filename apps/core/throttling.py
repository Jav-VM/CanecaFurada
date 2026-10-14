"""
Contadores de intentos con ventana fija sobre la caché de Django.

Las claves se derivan con SHA-256 para no guardar emails ni IPs en claro en la
caché. Con la caché en memoria por defecto el límite es por proceso; en
producción con varios procesos debe configurarse una caché compartida
(`CACHE_URL`).
"""
import hashlib

from django.core.cache import cache


def _key(scope, identifier):
    digest = hashlib.sha256(f"{scope}:{identifier}".encode("utf-8")).hexdigest()
    return f"throttle:{scope}:{digest}"


def is_limited(scope, identifier, limit):
    return cache.get(_key(scope, identifier), 0) >= limit


def register_attempt(scope, identifier, window_seconds):
    key = _key(scope, identifier)
    if cache.add(key, 1, timeout=window_seconds):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        # La clave caducó entre `add` e `incr`.
        cache.set(key, 1, timeout=window_seconds)
        return 1


def reset_attempts(scope, identifier):
    cache.delete(_key(scope, identifier))
