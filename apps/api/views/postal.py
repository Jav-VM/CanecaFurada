"""Localidades por código postal, para el formulario de registro y perfil de la app."""
from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import exceptions, serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts import postal, validators

from ..schema import ERROR
from .base import ApiView

TAG = "Autenticación"


class LocalitiesView(ApiView):
    """Público (el registro es anónimo) con el límite general de la API; solo datos públicos (GeoNames)."""

    permission_classes = [AllowAny]

    @extend_schema(
        tags=[TAG],
        summary="Localidades de un código postal español",
        description=(
            "Lista vacía si el CP no tiene datos: entonces la localidad es texto libre opcional. "
            "Con una sola, la app puede marcarla directamente. Fuente: GeoNames (CC BY 4.0)."
        ),
        responses={
            200: inline_serializer("Localities", {"localities": serializers.ListField(child=serializers.CharField())}),
            400: ERROR,
        },
    )
    def get(self, request, postal_code):
        postal_code = validators.normalize_postal_code(postal_code)
        try:
            validators.validate_postal_code(postal_code, "ES")
        except ValidationError as exc:
            raise exceptions.ValidationError({"postal_code": exc.messages}) from None
        return Response({"localities": postal.localities_for("ES", postal_code)})
