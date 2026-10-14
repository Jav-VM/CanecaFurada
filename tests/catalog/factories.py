"""Datos ficticios de la carta para tests."""
import io
import shutil
import tempfile
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image

from apps.catalog.models import BeerStyle, Category, Product


def image_bytes(fmt="PNG", size=(8, 8)):
    buffer = io.BytesIO()
    Image.new("RGB", size, (255, 184, 0)).save(buffer, format=fmt)
    return buffer.getvalue()


def uploaded_image(name="foto.png", fmt="PNG", size=(8, 8), content_type="image/png"):
    return SimpleUploadedFile(name, image_bytes(fmt, size), content_type=content_type)


def make_category(name="Cervezas de la casa", slug=None, **extra):
    return Category.objects.create(name=name, slug=slug or name.lower().replace(" ", "-"), **extra)


def make_style(name="IPA"):
    return BeerStyle.objects.get_or_create(name=name)[0]


def make_product(category=None, kind=Product.Kind.HOUSE_BEER, name="Cerveza Ficticia", **extra):
    category = category or Category.objects.first() or make_category()
    if kind != Product.Kind.FIXED:
        extra.setdefault("style", make_style())
        extra.setdefault("abv", Decimal("5.5"))
    extra.setdefault("price", Decimal("3.50"))
    return Product.objects.create(category=category, kind=kind, name=name, **extra)


def make_published(**kwargs):
    kwargs.setdefault("status", Product.Status.PUBLISHED)
    kwargs.setdefault("published_at", timezone.now())
    return make_product(**kwargs)


class TempMediaMixin:
    """Guarda los ficheros subidos en un directorio temporal, nunca en media/."""

    @classmethod
    def setUpClass(cls):
        cls._media_root = tempfile.mkdtemp(prefix="caneca-test-media-")
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)
