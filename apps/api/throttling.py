"""
Límites de peticiones de la API (DRF), además de los límites propios de los
servicios (login por email e IP, reenvíos, QR, códigos...).

Como en `apps.core.throttling`, la IP o el identificador del usuario se
guardan en la caché como hash, nunca en claro. La IP se calcula con
`NUM_PROXIES` (= `TRUSTED_PROXY_COUNT`), igual que `apps.core.http.client_ip`.
"""
import hashlib

from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle


class _HashedIdentMixin:
    def get_ident(self, request):
        ident = super().get_ident(request)
        return hashlib.sha256(f"{self.scope}:{ident}".encode("utf-8")).hexdigest()

    def get_cache_key(self, request, view):
        key = super().get_cache_key(request, view)
        if key is None or not request.user or not request.user.is_authenticated:
            return key
        # UserRateThrottle usa la PK; también se convierte en hash.
        digest = hashlib.sha256(f"{self.scope}:user:{request.user.pk}".encode("utf-8")).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": digest}


class AnonThrottle(_HashedIdentMixin, AnonRateThrottle):
    pass


class UserThrottle(_HashedIdentMixin, UserRateThrottle):
    pass


class AuthThrottle(_HashedIdentMixin, SimpleRateThrottle):
    """Login, registro, recuperación y verificación: por IP, haya o no sesión."""

    scope = "auth"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
