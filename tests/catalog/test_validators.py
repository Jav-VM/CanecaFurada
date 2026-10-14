"""Validación de imágenes de la carta."""
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from apps.catalog.validators import product_image_path, validate_image_extension, validate_image_file

from .factories import image_bytes, uploaded_image

SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


class ImageValidatorTests(SimpleTestCase):
    def test_accepts_jpeg_png_and_webp(self):
        for fmt, name in (("JPEG", "a.jpg"), ("PNG", "a.png"), ("WEBP", "a.webp")):
            with self.subTest(fmt):
                file = uploaded_image(name=name, fmt=fmt)
                validate_image_extension(file)
                validate_image_file(file)
                self.assertEqual(file.tell(), 0)

    def test_rejects_non_image_with_image_extension(self):
        file = SimpleUploadedFile("falsa.png", b"<html><script>alert(1)</script></html>", content_type="image/png")
        with self.assertRaisesMessage(ValidationError, "no es una imagen válida"):
            validate_image_file(file)

    def test_rejects_svg(self):
        svg = SimpleUploadedFile("logo.svg", SVG)
        with self.assertRaises(ValidationError):
            validate_image_extension(svg)
        with self.assertRaises(ValidationError):
            validate_image_file(svg)

    def test_rejects_disallowed_real_format(self):
        gif = SimpleUploadedFile("animada.png", image_bytes("GIF"), content_type="image/png")
        with self.assertRaisesMessage(ValidationError, "Formato no admitido"):
            validate_image_file(gif)

    def test_rejects_truncated_image(self):
        data = image_bytes("PNG", size=(64, 64))
        with self.assertRaises(ValidationError):
            validate_image_file(SimpleUploadedFile("rota.png", data[: len(data) // 2]))

    @override_settings(CATALOG_IMAGE_MAX_BYTES=100)
    def test_rejects_large_files(self):
        file = SimpleUploadedFile("grande.png", image_bytes("PNG") + b"\0" * 200)
        with self.assertRaisesMessage(ValidationError, "ocupa demasiado"):
            validate_image_file(file)

    @override_settings(CATALOG_IMAGE_MAX_DIMENSION=16)
    def test_rejects_large_dimensions(self):
        with self.assertRaisesMessage(ValidationError, "demasiado grande"):
            validate_image_file(uploaded_image(size=(17, 8)))

    def test_error_message_does_not_echo_filename(self):
        file = SimpleUploadedFile("nombre-privado.png", b"no-imagen")
        with self.assertRaises(ValidationError) as ctx:
            validate_image_file(file)
        self.assertNotIn("nombre-privado", " ".join(ctx.exception.messages))

    def test_stored_name_is_random_and_hides_original_name(self):
        path = product_image_path(None, "Foto de Ana Pérez.JPEG")
        self.assertTrue(path.startswith("catalog/products/"))
        self.assertTrue(path.endswith(".jpg"))
        self.assertNotIn("Ana", path)
        self.assertNotEqual(path, product_image_path(None, "Foto de Ana Pérez.JPEG"))
