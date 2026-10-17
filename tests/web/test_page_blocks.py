"""
Contenido editable de las secciones y artículos (Fases 21 y 23): textos con
valor por defecto, imágenes (figura y carrusel), artículos de Inicio, La
cervecería y Eventos, y accesos.
"""
import os
import uuid

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
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

    def events(self):
        return self.client.get(reverse("web:events")).content.decode()


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

    def test_gallery_is_a_carousel_one_image_at_a_time(self):
        images = [uploaded_image(f"{n}.png") for n in range(3)]
        self.post(edit_url("cerveceria", "historia"), {"title": "A nosa historia", "images": images})
        html = self.about()
        gallery = html[html.index("data-carousel"):]
        gallery = gallery[:gallery.index("</div>")]
        # Una imagen por «pantalla», a todo el ancho; ya no es una cuadrícula de miniaturas.
        self.assertEqual(gallery.count('<li class="flex w-full shrink-0 snap-center'), 3)
        self.assertIn('aria-label="Imagen 1 de 3"', gallery)
        self.assertIn('aria-label="Imagen 3 de 3"', gallery)
        self.assertNotIn("grid-cols", gallery)
        # Mismo tamaño y proporción que una imagen sola (`_figure.html`).
        self.assertIn('<div class="relative mx-auto w-full max-w-md" role="region"', html)
        self.assertEqual(gallery.count('class="h-auto w-full rounded-xl object-cover"'), 3)
        self.assertNotIn("max-h-[80vh]", gallery)
        # Al pulsar una imagen se abre en otra pestaña.
        self.assertEqual(gallery.count('target="_blank" rel="noopener noreferrer"'), 3)
        # Flechas: ocultas hasta que el JS las activa, solo con su etiqueta accesible.
        self.assertRegex(gallery, r'<button type="button" class="carousel-arrow left-2" aria-label="Imagen anterior" hidden data-carousel-prev>')
        self.assertRegex(gallery, r'<button type="button" class="carousel-arrow right-2" aria-label="Imagen siguiente" hidden data-carousel-next>')

    def test_gallery_alt_text_is_escaped(self):
        self.post(edit_url("cerveceria", "como"), {"images": [uploaded_image(), uploaded_image("b.png")]})
        first = PageBlockImage.objects.order_by("position").first()
        self.post(edit_url("cerveceria", "como"), {f"alt-{first.pk}": '"><script>x</script>'})
        html = self.about()
        self.assertNotIn("<script>x</script>", html)
        self.assertIn("&quot;&gt;&lt;script&gt;x&lt;/script&gt;", html)

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
    def create(self, page="cerveceria", **data):
        values = {"title": "Novo artigo", "body": "Primeiro parágrafo.\n\nSegundo.", "images": [uploaded_image(), uploaded_image("b.png")]}
        values.update(data)
        return self.post(reverse("dashboard:article_create", args=[page]), values)

    def test_article_carousel_sits_next_to_the_text_like_a_single_image(self):
        self.create()
        html = self.about()
        article = html[html.index("data-article"):]
        article = article[:article.index("</section>")]
        # Dos columnas en pantallas grandes: texto y, a su lado, el carrusel.
        self.assertIn("lg:grid-cols-2 lg:items-center", article)
        self.assertLess(article.index("Segundo."), article.index("data-carousel"))
        # El carrusel va dentro de la rejilla, no debajo: tras él se cierran el carrusel y la rejilla, y nada más.
        tail = article[article.index("data-carousel-next"):]
        tail = tail[tail.index("</button>") + len("</button>"):]
        self.assertEqual(tail.split(), ["</div>", "</div>"])

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
        confirm = self.client.get(reverse("dashboard:article_delete", args=["cerveceria", key]))
        self.assertContains(confirm, "data-article-delete")
        self.post(reverse("dashboard:article_delete", args=["cerveceria", key]), {})
        self.assertFalse(PageBlock.objects.filter(key=key).exists())
        self.assertFalse(any(os.path.exists(path) for path in paths))
        self.assertNotIn(key, [k for k, _label in web.sections_for(layout.ABOUT)])
        self.assertEqual(self.client.get(edit_url("cerveceria", key)).status_code, 404)

    def test_fixed_sections_cannot_be_deleted(self):
        self.assertEqual(self.client.get(reverse("dashboard:article_delete", args=["cerveceria", "historia"])).status_code, 404)


class AccessTests(BlocksTestCase):
    def test_unknown_page_or_section_is_404(self):
        for page, key in (("admin", "marca"), ("inicio", "historia"), ("cerveceria", "articulo-noexiste")):
            self.assertEqual(self.client.get(edit_url(page, key)).status_code, 404)

    def test_only_owner(self):
        urls = [edit_url("inicio", "marca")] + [reverse("dashboard:article_create", args=[page]) for page in layout.ARTICLE_PAGES]
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


class ArticlesOnMorePagesTests(BlocksTestCase):
    """Fase 23: artículos también en Inicio y Eventos, con las mismas características."""

    create = ArticleTests.create

    def test_home_and_events_accept_articles_with_carousel(self):
        for page, read in (("inicio", self.home), ("eventos", self.events)):
            with self.subTest(page=page):
                response = self.create(page=page, title=f"Artigo de {page}")
                self.assertRedirects(response, reverse("dashboard:content") + f"#orden-{page}", fetch_redirect_response=False)
                article = PageBlock.objects.get(page=page, is_article=True)
                html = read()
                self.assertIn(f"Artigo de {page}", html)
                section = html[html.index(f'aria-labelledby="{article.key}-titulo"'):]
                section = section[:section.index("</section>")]
                self.assertIn("data-carousel", section)
                self.assertEqual(section.count("snap-center"), 2)
                # Al final de su página, y en su lista de Contenido (orden y visibilidad).
                self.assertEqual(web.sections_for(page)[-1], (article.key, f"Artigo de {page}"))
                self.assertNotIn(article.key, [key for key, _label in web.sections_for(layout.ABOUT)])
        self.assertTrue(AuditEvent.objects.filter(metadata__event="article_created", metadata__page="eventos").exists())

    def test_events_article_does_not_nest_containers(self):
        self.create(page="eventos")
        html = self.events()
        self.assertIn('class="border-t border-line pt-10" data-article', html)
        self.assertNotIn('class="container-page border-t border-line py-20" data-article', html)

    def test_single_image_article_on_home_is_a_figure(self):
        self.create(page="inicio", images=[uploaded_image()])
        html = self.home()
        self.assertIn("data-article", html)
        self.assertNotIn("data-carousel", html)
        self.assertIn("/media/pages/", html)

    def test_edit_and_delete_home_and_events_articles(self):
        for page in ("inicio", "eventos"):
            with self.subTest(page=page):
                self.create(page=page)
                key = PageBlock.objects.get(page=page, is_article=True).key
                self.post(edit_url(page, key), {"title": "Artigo editado"})
                self.assertEqual(PageBlock.objects.get(key=key).title, "Artigo editado")
                paths = [image.image.path for image in PageBlockImage.objects.filter(block__key=key)]
                self.post(reverse("dashboard:article_delete", args=[page, key]), {})
                self.assertFalse(PageBlock.objects.filter(key=key).exists())
                self.assertFalse(any(os.path.exists(path) for path in paths))

    def test_pages_without_articles_are_404(self):
        for page in ("carta", "agasallos", "contacto", "admin"):
            with self.subTest(page=page):
                self.assertEqual(self.client.get(reverse("dashboard:article_create", args=[page])).status_code, 404)
                self.assertEqual(self.post(reverse("dashboard:article_create", args=[page]), {"title": "x"}).status_code, 404)
        self.assertFalse(PageBlock.objects.exists())
        with self.assertRaises(ValidationError):
            blocks.create_article(actor=self.owner, page="carta", data={"title": "x"})

    def test_article_cannot_be_deleted_from_another_page_url(self):
        self.create(page="inicio")
        key = PageBlock.objects.get(page="inicio", is_article=True).key
        self.assertEqual(self.client.get(reverse("dashboard:article_delete", args=["eventos", key])).status_code, 404)
        self.assertEqual(self.post(reverse("dashboard:article_delete", args=["eventos", key]), {}).status_code, 404)
        self.assertTrue(PageBlock.objects.filter(key=key).exists())
        with self.assertRaises(ValidationError):
            blocks.delete_article(actor=self.owner, page="eventos", key=key)

    def test_only_owner_can_delete(self):
        self.create(page="eventos")
        key = PageBlock.objects.get(page="eventos", is_article=True).key
        for user in (self.employee, self.customer):
            self.client.force_login(user)
            self.assertEqual(self.post(reverse("dashboard:article_delete", args=["eventos", key]), {}).status_code, 403)
        self.assertTrue(PageBlock.objects.filter(key=key).exists())

    def test_fixed_home_and_events_sections_still_have_no_images(self):
        for page, key in (("inicio", "marca"), ("eventos", "reservar")):
            with self.subTest(page=page):
                self.assertNotContains(self.client.get(edit_url(page, key)), 'name="images"')
                self.post(edit_url(page, key), {"images": [uploaded_image()]})
                self.assertFalse(PageBlockImage.objects.exists())
                with self.assertRaises(ValidationError):
                    blocks.save_block(actor=self.owner, page=page, key=key, data={}, new_images=[uploaded_image()])

    def test_content_page_offers_new_article_on_home_about_and_events(self):
        response = self.client.get(reverse("dashboard:content"))
        for page in ("inicio", "cerveceria", "eventos"):
            self.assertContains(response, reverse("dashboard:article_create", args=[page]))
        for page in ("carta", "agasallos", "contacto"):
            self.assertNotContains(response, f"/contenido/{page}/articulos/nuevo/")

    def test_database_rejects_articles_on_other_pages(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PageBlock.objects.create(page="carta", key="articulo-x", is_article=True, title="x")


class CopyArticleTests(BlocksTestCase):
    """Fase 23: en «Nuevo artículo», copiar un artículo de otra página."""

    create = ArticleTests.create

    def copy(self, page, source_public_id):
        return self.post(reverse("dashboard:article_copy", args=[page]), {"origen": str(source_public_id)})

    def test_new_article_lists_only_articles_of_other_pages(self):
        self.create(page="cerveceria", title="Da cervexaría")
        self.create(page="inicio", title="Do inicio")
        self.create(page="eventos", title="Dos eventos")
        response = self.client.get(reverse("dashboard:article_create", args=["eventos"]))
        self.assertContains(response, "data-copy-articles")
        self.assertContains(response, "data-copy-source", count=2)
        self.assertContains(response, "Da cervexaría")
        self.assertContains(response, "Do inicio")
        self.assertNotContains(response, "Dos eventos")
        self.assertContains(response, reverse("dashboard:article_copy", args=["eventos"]))
        # Editar un artículo no muestra la lista.
        key = PageBlock.objects.get(page="eventos").key
        self.assertNotContains(self.client.get(edit_url("eventos", key)), "data-copy-articles")

    def test_empty_list_message(self):
        response = self.client.get(reverse("dashboard:article_create", args=["inicio"]))
        self.assertContains(response, "data-copy-empty")
        self.assertNotContains(response, "data-copy-source")

    def test_copy_creates_an_independent_article_with_its_own_image_files(self):
        self.create(page="cerveceria", title="Festa", eyebrow="Novidade", body="Texto da festa.")
        source = PageBlock.objects.get(page="cerveceria", is_article=True)
        first = source.images.order_by("position").first()
        self.post(edit_url("cerveceria", source.key), {f"alt-{first.pk}": "A billa"})
        response = self.copy("eventos", source.public_id)
        copy = PageBlock.objects.get(page="eventos", is_article=True)
        self.assertRedirects(response, edit_url("eventos", copy.key), fetch_redirect_response=False)
        self.assertNotEqual(copy.key, source.key)
        self.assertEqual((copy.eyebrow, copy.title, copy.body), ("Novidade", "Festa", "Texto da festa."))
        originals = list(source.images.order_by("position"))
        copies = list(copy.images.order_by("position"))
        self.assertEqual(len(copies), 2)
        self.assertEqual([image.alt for image in copies], [image.alt for image in originals])
        for original, image in zip(originals, copies):
            self.assertNotEqual(original.image.name, image.image.name)
            self.assertTrue(os.path.exists(image.image.path))
            self.assertEqual((image.width, image.height), (original.width, original.height))
        html = self.events()
        self.assertIn("Festa", html)
        self.assertIn("data-carousel", html)
        self.assertEqual(web.sections_for("eventos")[-1], (copy.key, "Festa"))
        event = AuditEvent.objects.get(metadata__event="article_copied")
        self.assertEqual(event.metadata["source_page"], "cerveceria")
        self.assertNotIn("Festa", str(event.metadata))
        # Independientes: eliminar la copia no toca el original ni sus ficheros.
        self.post(edit_url("eventos", copy.key), {"title": "Festa en Eventos"})
        self.post(reverse("dashboard:article_delete", args=["eventos", copy.key]), {})
        source.refresh_from_db()
        self.assertEqual(source.title, "Festa")
        self.assertTrue(all(os.path.exists(image.image.path) for image in originals))

    def test_copy_rejects_invalid_sources(self):
        self.create(page="eventos", title="Dos eventos")
        same_page = PageBlock.objects.get(page="eventos")
        fixed = PageBlock.objects.create(page="cerveceria", key="historia", title="Historia")
        for value in (same_page.public_id, fixed.public_id, uuid.uuid4(), "non-e-un-uuid", ""):
            with self.subTest(value=value):
                response = self.copy("eventos", value)
                self.assertEqual(response.status_code, 400)
                self.assertContains(response, "No se ha podido copiar el artículo", status_code=400)
        self.assertEqual(PageBlock.objects.filter(is_article=True).count(), 1)
        with self.assertRaises(ValidationError):
            blocks.copy_article(actor=self.owner, page="eventos", source_public_id=same_page.public_id)

    def test_copy_to_a_page_without_articles_is_404(self):
        self.create(page="eventos")
        source = PageBlock.objects.get(page="eventos")
        for page in ("carta", "contacto"):
            self.assertEqual(self.copy(page, source.public_id).status_code, 404)
        self.assertEqual(PageBlock.objects.filter(is_article=True).count(), 1)

    def test_only_owner_and_only_post(self):
        self.create(page="inicio")
        source = PageBlock.objects.get(page="inicio")
        self.assertEqual(self.client.get(reverse("dashboard:article_copy", args=["eventos"])).status_code, 405)
        for user in (self.employee, self.customer):
            self.client.force_login(user)
            self.assertEqual(self.copy("eventos", source.public_id).status_code, 403)
        self.client.logout()
        self.assertIn(reverse("accounts:login"), self.copy("eventos", source.public_id)["Location"])
        self.assertEqual(PageBlock.objects.filter(is_article=True).count(), 1)
