"""
Carta de Caneca Furada.

Se separan dos tipos de información del producto:

- **Permanente** (qué es): categoría, tipo, nombre, descripción, estilo,
  graduación, precio, imagen y estado de publicación (borrador, publicado,
  archivado).
- **Disponibilidad actual** (si hoy se puede servir): `is_available`. Una
  cerveza agotada sigue publicada, pero nunca se presenta como disponible.

Los productos no se borran: se archivan, y las relaciones usan `PROTECT` para
conservar el historial. Las reglas de visibilidad pública están en
`selectors.py` y los cambios de estado y disponibilidad en `services.py`; las
plantillas y la futura API solo los consumen.
"""
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.core.models import TimeStampedModel

from .validators import (
    product_image_path,
    tap_menu_image_path,
    validate_image_extension,
    validate_image_file,
)

MIN_PRICE = Decimal("0.01")
MIN_ABV = Decimal("0.0")
MAX_ABV = Decimal("100.0")


class Category(TimeStampedModel):
    """Categoría dentro de la sección Carta (p. ej. Cervezas de la casa, Para picar)."""

    name = models.CharField("nombre", max_length=80)
    slug = models.SlugField(
        "identificador en la URL",
        max_length=80,
        unique=True,
        help_text="Se usa como ancla en la página de la carta (/carta/#identificador).",
    )
    description = models.TextField("descripción", blank=True, max_length=500)
    position = models.PositiveSmallIntegerField(
        "orden", default=0, help_text="Las categorías se muestran de menor a mayor."
    )
    is_published = models.BooleanField(
        "publicada",
        default=True,
        help_text="Si se desmarca, la categoría y todos sus productos dejan de verse en la web.",
    )

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["position", "name"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="catalog_category_name_ci_unique"),
        ]

    def __str__(self):
        return self.name


class BeerStyle(TimeStampedModel):
    """Estilo de cerveza (IPA, Stout, Lager...). Lista gestionada por el propietario."""

    name = models.CharField("nombre", max_length=60)

    class Meta:
        verbose_name = "estilo de cerveza"
        verbose_name_plural = "estilos de cerveza"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="catalog_beerstyle_name_ci_unique"),
        ]

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    class Kind(models.TextChoices):
        FIXED = "FIXED", "Producto fijo"
        HOUSE_BEER = "HOUSE_BEER", "Cerveza propia"
        GUEST_BEER = "GUEST_BEER", "Cerveza invitada"
        ROTATING_BEER = "ROTATING_BEER", "Cerveza rotativa"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        PUBLISHED = "PUBLISHED", "Publicado"
        ARCHIVED = "ARCHIVED", "Archivado"

    BEER_KINDS = (Kind.HOUSE_BEER, Kind.GUEST_BEER, Kind.ROTATING_BEER)

    public_id = models.UUIDField(
        "identificador público", default=uuid.uuid4, unique=True, editable=False
    )
    category = models.ForeignKey(
        Category, verbose_name="categoría", on_delete=models.PROTECT, related_name="products"
    )
    kind = models.CharField("tipo", max_length=16, choices=Kind.choices, default=Kind.FIXED)
    name = models.CharField("nombre", max_length=120)
    description = models.TextField("descripción", blank=True, max_length=1000)
    style = models.ForeignKey(
        BeerStyle,
        verbose_name="estilo",
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
        help_text="Obligatorio en las cervezas; vacío en los productos fijos.",
    )
    abv = models.DecimalField(
        "graduación (% vol.)",
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(MIN_ABV), MaxValueValidator(MAX_ABV)],
        help_text="Obligatoria en las cervezas. Opcional en otros productos con alcohol.",
    )
    brewery = models.CharField(
        "cervecera",
        max_length=120,
        blank=True,
        help_text="Elaborador de las cervezas invitadas.",
    )
    price = models.DecimalField(
        "precio (€)",
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(MIN_PRICE)],
        help_text="IVA incluido, con dos decimales (p. ej. 3.50). Máximo 9999.99.",
    )
    serving = models.CharField(
        "formato", max_length=40, blank=True, help_text="Opcional, p. ej. «33 cl» o «Ración»."
    )
    image = models.ImageField(
        "imagen",
        upload_to=product_image_path,
        blank=True,
        width_field="image_width",
        height_field="image_height",
        validators=[validate_image_extension, validate_image_file],
        help_text="JPEG, PNG o WebP. Opcional.",
    )
    image_width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    image_height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    position = models.PositiveSmallIntegerField(
        "orden", default=0, help_text="Orden dentro de la categoría, de menor a mayor."
    )
    is_featured = models.BooleanField(
        "destacada en el inicio",
        default=False,
        help_text="Solo las cervezas publicadas y disponibles aparecen en la selección del inicio.",
    )

    # Publicación. Se cambia mediante `services.set_product_status`.
    status = models.CharField(
        "estado", max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    published_at = models.DateTimeField("publicado el", null=True, blank=True, editable=False)
    archived_at = models.DateTimeField("archivado el", null=True, blank=True, editable=False)

    # Disponibilidad actual. Se cambia mediante `services.set_product_availability`.
    is_available = models.BooleanField(
        "disponible ahora",
        default=True,
        help_text="Desmárcalo cuando se agote. Seguirá en la carta como «Agotada».",
    )
    availability_changed_at = models.DateTimeField(
        "disponibilidad cambiada el", null=True, blank=True, editable=False
    )

    class Meta:
        verbose_name = "producto"
        verbose_name_plural = "productos"
        ordering = ["category__position", "position", "name"]
        indexes = [models.Index(fields=["status", "category"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=MIN_PRICE), name="catalog_product_price_positive"
            ),
            models.CheckConstraint(
                condition=Q(abv__isnull=True) | (Q(abv__gte=MIN_ABV) & Q(abv__lte=MAX_ABV)),
                name="catalog_product_abv_range",
            ),
            models.CheckConstraint(
                condition=Q(kind__in=["FIXED", "HOUSE_BEER", "GUEST_BEER", "ROTATING_BEER"]),
                name="catalog_product_kind_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["DRAFT", "PUBLISHED", "ARCHIVED"]),
                name="catalog_product_status_valid",
            ),
            # Las cervezas siempre tienen estilo y graduación; los productos fijos no tienen estilo.
            models.CheckConstraint(
                condition=Q(kind="FIXED", style__isnull=True)
                | (~Q(kind="FIXED") & Q(style__isnull=False) & Q(abv__isnull=False)),
                name="catalog_product_beer_fields",
            ),
            models.CheckConstraint(
                condition=Q(status="ARCHIVED", archived_at__isnull=False)
                | (~Q(status="ARCHIVED") & Q(archived_at__isnull=True)),
                name="catalog_product_archived_at_consistent",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        errors = {}
        if self.is_beer:
            if self.style_id is None:
                errors["style"] = "Indica el estilo de la cerveza."
            if self.abv is None:
                errors["abv"] = "Indica la graduación de la cerveza."
        else:
            if self.style_id is not None:
                errors["style"] = "Los productos fijos no tienen estilo de cerveza."
            if self.is_featured:
                errors["is_featured"] = "Solo se pueden destacar cervezas."
        if errors:
            raise ValidationError(errors)

    @property
    def is_beer(self):
        return self.kind in self.BEER_KINDS

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED

    @property
    def is_archived(self):
        return self.status == self.Status.ARCHIVED

    @property
    def is_publicly_visible(self):
        """Se ve en la web: publicado y en una categoría publicada."""
        return self.is_published and self.category.is_published

    @property
    def is_currently_available(self):
        """Se puede pedir ahora: visible y no agotado."""
        return self.is_publicly_visible and self.is_available


class TapMenu(TimeStampedModel):
    """
    Imagen de la carta de grifos que sube el propietario.

    En la web se muestra la más reciente que esté publicada; si no hay
    ninguna, la Carta muestra un hueco reservado. Las anteriores se conservan
    como historial (despublicadas) en lugar de borrarse.
    """

    title = models.CharField("título", max_length=80, default="Carta de grifos")
    image = models.ImageField(
        "imagen",
        upload_to=tap_menu_image_path,
        width_field="image_width",
        height_field="image_height",
        validators=[validate_image_extension, validate_image_file],
        help_text="JPEG, PNG o WebP.",
    )
    image_width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    image_height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    text_alternative = models.TextField(
        "versión en texto",
        blank=True,
        max_length=2000,
        help_text=(
            "Recomendado: las cervezas de la imagen en texto, para quien usa lector de "
            "pantalla o no puede ver bien la imagen."
        ),
    )
    is_published = models.BooleanField("publicada", default=False)

    class Meta:
        verbose_name = "carta de grifos"
        verbose_name_plural = "cartas de grifos"
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return f"{self.title} · {self.created_at:%Y-%m-%d}" if self.created_at else self.title
