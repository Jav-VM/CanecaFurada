"""
Imágenes de relleno para la demostración.

Se generan en memoria con Pillow (dependencia del proyecto): un fondo de color
con un marco más oscuro. Sin descargas, sin recursos con derechos de autor y
sin texto (no depende de fuentes instaladas). Pasan los mismos validadores que
una imagen subida desde el admin.
"""
import io

from django.core.files.base import ContentFile
from PIL import Image, ImageColor, ImageDraw


def placeholder(color, size=(640, 480)):
    rgb = ImageColor.getrgb(color)
    darker = tuple(max(0, int(channel * 0.6)) for channel in rgb)
    image = Image.new("RGB", size, rgb)
    border = max(8, min(size) // 20)
    ImageDraw.Draw(image).rectangle(
        (border, border, size[0] - border - 1, size[1] - border - 1), outline=darker, width=border // 2
    )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    # El nombre lo sustituye `upload_to` por uno aleatorio.
    return ContentFile(buffer.getvalue(), name="demo.png")
