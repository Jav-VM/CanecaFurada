"""
Validación de las imágenes de la carta.

Se aplica como validador de los `ImageField` del modelo, de modo que el admin,
la futura API y cualquier otro formulario comprueban lo mismo:

- tamaño máximo del fichero (`CATALOG_IMAGE_MAX_BYTES`);
- contenido real JPEG, PNG o WebP verificado con Pillow (no basta la
  extensión; se rechazan SVG, HTML disfrazado y ficheros corruptos);
- dimensiones máximas (`CATALOG_IMAGE_MAX_DIMENSION`), que además limitan las
  "bombas de descompresión".

Los mensajes de error no repiten el nombre del fichero recibido.
"""
import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext as _
from PIL import Image, UnidentifiedImageError

ALLOWED_IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "webp")
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}

validate_image_extension = FileExtensionValidator(ALLOWED_IMAGE_EXTENSIONS)


def validate_image_file(file):
    # Los ficheros ya guardados se validaron al subirlos; no se vuelven a leer
    # del almacenamiento en cada edición.
    if getattr(file, "_committed", False):
        return

    max_bytes = settings.CATALOG_IMAGE_MAX_BYTES
    if file.size is not None and file.size > max_bytes:
        raise ValidationError(
            _("La imagen ocupa demasiado. Máximo: %(max)s MB."),
            code="image_too_large",
            params={"max": max_bytes // (1024 * 1024)},
        )

    max_dimension = settings.CATALOG_IMAGE_MAX_DIMENSION
    try:
        file.seek(0)
        with Image.open(file) as image:
            image_format = image.format
            width, height = image.size
            if image_format not in ALLOWED_IMAGE_FORMATS:
                raise ValidationError(
                    _("Formato no admitido. Usa JPEG, PNG o WebP."), code="image_format"
                )
            if width > max_dimension or height > max_dimension:
                raise ValidationError(
                    _("La imagen es demasiado grande. Máximo: %(max)s px por lado."),
                    code="image_dimensions",
                    params={"max": max_dimension},
                )
            image.verify()
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise ValidationError(_("El fichero no es una imagen válida."), code="image_invalid")
    finally:
        file.seek(0)


def _random_image_path(folder, filename):
    # Nombre aleatorio: no se publica el nombre original del fichero (puede
    # contener datos personales) y no hay colisiones.
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".jpeg":
        ext = ".jpg"
    return f"catalog/{folder}/{uuid.uuid4().hex}{ext}"


def product_image_path(instance, filename):
    return _random_image_path("products", filename)


def tap_menu_image_path(instance, filename):
    return _random_image_path("taps", filename)
