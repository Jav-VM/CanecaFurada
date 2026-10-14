"""Piezas del esquema OpenAPI (drf-spectacular) propias de la API."""
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, inline_serializer
from rest_framework import serializers


class JWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.api.authentication.JWTAuthentication"
    name = "jwtAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Token de acceso de `POST /api/v1/auth/login/` en la cabecera "
                "`Authorization: Bearer <access>`. Caduca a los 15 minutos; se renueva con "
                "`POST /api/v1/auth/token/refresh/`."
            ),
        }


IDEMPOTENCY_KEY = OpenApiParameter(
    name="Idempotency-Key",
    type=OpenApiTypes.UUID,
    location=OpenApiParameter.HEADER,
    required=True,
    description=(
        "UUID v4 generado por la app para esta operación. Si la respuesta se pierde, "
        "reintenta con el mismo valor: no se duplica (200 en lugar de 201)."
    ),
)

ERROR = inline_serializer(
    name="Error",
    fields={
        "code": serializers.CharField(help_text="Identificador estable del error."),
        "detail": serializers.CharField(help_text="Mensaje legible en español."),
        "fields": serializers.DictField(
            child=serializers.ListField(child=serializers.CharField()),
            required=False,
            help_text="Errores por campo (solo en validaciones).",
        ),
    },
)

DETAIL = inline_serializer(name="Detail", fields={"detail": serializers.CharField()})
