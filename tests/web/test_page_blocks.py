"""
Contenido editable de las secciones y artículos de La cervecería (Fase 21):
textos con valor por defecto, imágenes (figura y galería), artículos y accesos.
"""
import os

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.core.models import AuditEvent
from apps.web import blocks, layout
from apps.web import services as web
from apps.web.models import PageBlock, PageBlockImage
from tests.catalog.factories import TempMediaMixin, uploaded_image
from tests.loyalty.factories import make_customer_with_qr, make_employee, make_owner


def edit_url(page, key):
    return reverse("dashboard:section_edit", args=[page, key])


class BlocksTestCase(TempMediaMixin, TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_owner()
        self.employee = make_employee()
        self.customer, _ = make_customer_with_qr()
        self.client.force_login(self.owner)

    def post(self, url, data):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(url, data)

    def home(self):
        return self.client.get(reverse("web:home")).content.decode()

    def about(self):
        return self.client.get(reverse("web:about")).content.decode()


class HomeTextsTests(BlocksTestCase):
    def test_defaults_are_the_original_texts(self):
        html = self.home()
        self.assertIn("Nuestras cervezas", html)
        self.assertIn("Ven a vernos", html)

    def test_owner_overrides_texts_and_empty_restores_default(self):
        response = self.post(edit_url("inicio", "cervezas"), {"eyebrow": "Na billa", "title": "As da casa", "body": "Feitas aquí."})
        self.assertRedirects(response, reverse("dashboard:content") + "#orden-inicio", fetch_redirect_response=False)
        html = self.home()
        self.assertIn("As da casa", html)
        self.assertIn("Feitas aquí.", html)
        self.assertNotIn("Nuestras cervezas", html)
        self.post(edit_url("inicio", "cervezas"), {"eyebrow": "", "title": "", "body": ""})
        self.assertIn("Nuestras cervezas", self.home())

    def test_texts_are_escaped(self):
        self.post(edit_url("inicio", "local"), {"title": "<script>alert(1)</script>", "body": "<b>x</b>"})
        html = self.home()
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_home_sections_take_no_images(self):
        form = self.client.get(edit_url("inicio", "marca"))
        self.assertNotContains(form, 'name="images"')
        with self.assertRaises(ValidationError):
            blocks.save_block(actor=self.owner, page="inicio", key="marca", data={}, new_images=[uploaded_image()])

    def test_marca_falls_back_to_presentation_text(self):
        web.update_business_info(actor=self.owner, data={"about_text": "Presentación de proba"})
        cache.clear()
        self.assertIn("Presentación de proba", self.home())
        self.post(edit_url("inicio", "marca"), {"body": "Texto propio da marca"})
        html = self.home()
        self.assertIn("Texto propio da marca", html)
        self.assertNotIn("Presentación de proba", html)


class AboutImagesTests(BlocksTestCase):
    def test_one_image_is_a_figure_and_more_make_a_gallery(self):
        self.post(edit_url("cerveceria", "historia"), {"title": "A nosa historia", "images": [uploaded_image()]})
        html = self.about()
        self.assertIn("A nosa historia", html)
        self.assertNotIn("data-gallery", html)
        self.assertIn("/media/pages/", html)
        self.post(edit_url("cerveceria", "historia"), {"title": "A nosa historia", "images": [uploaded_image("b.png"), uploaded_image("c.png")]})
        self.assertIn("data-gallery", self.about())
        self.assertEqual(PageBlockImage.objects.count(), 3)

    def test_alt_and_remove_only_own_images(self):
        self.post(edit_url("cerveceria", "como"), {"images": [uploaded_image(), uploaded_image("b.png")]})
        first, second = PageBlockImage.objects.order_by("position")
        path = first.image.path
        self.post(edit_url("cerveceria", "como"), {f"alt-{second.pk}": "Os tanques", "quitar": [first.pk]})
        self.assertEqual(list(PageBlockImage.objects.values_list("alt", flat=True)), ["Os tanques"])
        self.assertFalse(os.path.exists(path))
        # Una imagen de otra sección no se puede quitar desde esta.
        self.post(edit_url("cerveceria", "historia"), {"images": [uploaded_image()]})
        other = PageBlockImage.objects.get(block__key="historia")
        self.assertEqual(self.post(edit_url("cerveceria", "como"), {"quitar": [other.pk]}).status_code, 400)
        self.assertTrue(PageBlockImage.objects.filter(pk=other.pk).exists())

    def test_fake_image_and_limit(self):
        fake = SimpleUploadedFile("foto.png", b"<script>alert(1)</script>", content_type="image/png")
        self.assertEqual(self.post(edit_url("cerveceria", "como"), {"images": [fake]}).status_code, 400)
        too_many = [uploaded_image(f"{n}.png") for n in range(PageBlock.MAX_IMAGES + 1)]
        self.assertEqual(self.post(edit_url("cerveceria", "como"), {"images": too_many}).status_code, 400)
        self.assertFalse(PageBlockImage.objects.exists())


class ArticleTests(BlocksTestCase):
    def create(self, **data):
        values = {"title": "Novo artigo", "body": "Primeiro parágrafo.\n\nSegundo.", "images": [uploaded_image(), uploaded_image("b.png")]}
        values.update(data)
        return self.post(reverse("dashboard:article_create"), values)

    def test_create_shows_at_the_end_with_gallery(self):
        self.create()
        article = PageBlock.objects.get(is_article=True)
        html = self.about()
        self.assertIn("Novo artigo", html)
        self.assertIn("data-article", html)
        self.assertIn("data-gallery", html)
        self.assertLess(html.index("como-titulo"), html.index("Novo artigo"))
        self.assertIn(article.key, [key for key, _label in web.sections_for(layout.ABOUT)])
        self.assertTrue(AuditEvent.objects.filter(metadata__event="article_created").exists())

    def test_article_needs_a_title(self):
        self.assertEqual(self.create(title="").status_code, 400)
        self.assertFalse(PageBlock.objects.exists())

    def test_order_hide_edit_and_delete(self):
        self.create()
        key = PageBlock.objects.get(is_article=True).key
        keys = ["historia", "como", key]
        self.post(reverse("dashboard:content_layout"), {"pagina": "cerveceria", "mostrar": keys, "mover": f"{key}:arriba"})
        html = self.about()
        self.assertLess(html.index("Novo artigo"), html.index("como-titulo"))
        self.post(reverse("dashboard:content_layout"), {"pagina": "cerveceria", "mostrar": ["historia", "como"]})
        self.assertNotIn("Novo artigo", self.about())
        self.post(edit_url("cerveceria", key), {"title": "Artigo editado"})
        self.assertEqual(PageBlock.objects.get(key=key).title, "Artigo editado")
        paths = [image.image.path for image in PageBlockImage.objects.all()]
        confirm = self.client.get(reverse("dashboard:article_delete", args=[key]))
        self.assertContains(confirm, "data-article-delete")
        self.post(reverse("dashboard:article_delete", args=[key]), {})
        self.assertFalse(PageBlock.objects.filter(key=key).exists())
        self.assertFalse(any(os.path.exists(path) for path in paths))
        self.assertNotIn(key, [k for k, _label in web.sections_for(layout.ABOUT)])
        self.assertEqual(self.client.get(edit_url("cerveceria", key)).status_code, 404)

    def test_fixed_sections_cannot_be_deleted(self):
        self.assertEqual(self.client.get(reverse("dashboard:article_delete", args=["historia"])).status_code, 404)


class AccessTests(BlocksTestCase):
    def test_unknown_page_or_section_is_404(self):
        for page, key in (("admin", "marca"), ("inicio", "historia"), ("cerveceria", "articulo-noexiste")):
            self.assertEqual(self.client.get(edit_url(page, key)).status_code, 404)

    def test_only_owner(self):
        urls = [edit_url("inicio", "marca"), reverse("dashboard:article_create")]
        for user in (self.employee, self.customer):
            self.client.force_login(user)
            for url in urls:
                self.assertEqual(self.client.post(url, {"title": "x"}).status_code, 403)
        self.client.logout()
        response = self.client.get(urls[0])
        self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertFalse(PageBlock.objects.exists())

    def test_content_page_has_separator_edit_links_and_new_article(self):
        response = self.client.get(reverse("dashboard:content"))
        self.assertContains(response, "border-t border-line pt-10")
        self.assertContains(response, edit_url("inicio", "eventos"))
        self.assertContains(response, "data-new-article")
