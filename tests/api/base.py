"""Utilidades comunes de los tests de la API v1 (datos ficticios)."""
import base64
import json
import uuid

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.api import tokens


def api_url(name, *args):
    return reverse(f"api:{name}", args=args)


def jwt_payload(raw_token):
    """Contenido (sin verificar) de un JWT: lo que puede leer cualquiera que tenga el token."""
    segment = raw_token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))


class ApiTestCase(TestCase):
    client_class = APIClient

    def setUp(self):
        super().setUp()
        cache.clear()  # límites de intentos y throttling de DRF

    def authenticate(self, user, client=None):
        """Inicia sesión como en la app: con un token emitido por el servidor."""
        pair = tokens.issue_tokens(user)
        (client or self.client).credentials(HTTP_AUTHORIZATION=f"Bearer {pair['access']}")
        return pair

    def anonymous(self):
        self.client.credentials()

    def post(self, name, data=None, *args, key=None):
        headers = {"HTTP_IDEMPOTENCY_KEY": str(key)} if key is not None else {}
        return self.client.post(api_url(name, *args), data or {}, format="json", **headers)

    @staticmethod
    def new_key():
        return uuid.uuid4()
