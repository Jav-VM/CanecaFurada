"""
Contenido de las secciones de las páginas, y artículos (Fases 21 y 23).

- Las secciones fijas (lista blanca de `layout.py`) guardan sus textos en
  `PageBlock`; un campo vacío deja el texto por defecto (`layout.DEFAULT_TEXTS`),
  traducido. Lo escrito por el propietario se muestra tal cual (Fase 15).
- Admiten imágenes las secciones fijas de La cervecería y todos los artículos:
  una se muestra junto al texto; dos o más, en un carrusel en su lugar.
- Los artículos (Inicio, La cervecería y Eventos: `layout.ARTICLE_PAGES`) son
  secciones más de su página: entran en su lista blanca (`services.sections_for`)
  y se ordenan y ocultan como las demás.

Todo cambio es del propietario, en una transacción y auditado sin textos.
"""
import os
import uuid
from dataclasses import dataclass, field

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files import File
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.utils.translation import gettext as _

from apps.accounts.permissions import is_owner
from apps.accounts.validators import normalize_text
from apps.core.models import AuditEvent
from apps.core.services import record_audit_event

from . import layout, services
from .models import PageBlock, PageBlockImage

ARTICLE_PREFIX = "articulo-"
# Secciones cuyo texto por defecto es la presentación de Contenido (`about_text`).
ABOUT_TEXT_SECTIONS = {(layout.HOME, "marca"), (layout.ABOUT, "historia")}


def _require_owner(actor):
    if not is_owner(actor):
        raise PermissionDenied(_("Solo el propietario puede editar el contenido de las páginas."))


def fixed_keys(page):
    _field, sections, _label = layout.PAGES[page]
    return [key for key, _unused in sections]


def allows_images(page):
    """¿Las secciones fijas de `page` llevan imágenes?"""
    return page in layout.IMAGE_PAGES


def images_allowed(page, is_article):
    """Imágenes de una sección fija (según su página) o de un artículo (siempre)."""
    return is_article or allows_images(page)


def defaults(page, key):
    """(antetítulo, título, texto) por defecto de la sección; artículos: vacío."""
    return layout.DEFAULT_TEXTS.get(page, {}).get(key, ("", "", None))


def get_block(page, key):
    """Bloque guardado de una sección fija o de un artículo, o `None`."""
    return PageBlock.objects.filter(page=page, key=key).prefetch_related("images").first()


def is_editable(page, key):
    if page not in layout.PAGES:
        return False
    if key in fixed_keys(page):
        return True
    return page in layout.ARTICLE_PAGES and PageBlock.objects.filter(page=page, key=key, is_article=True).exists()


# --- Escritura --------------------------------------------------------------------------


def _audit(actor, page, key, event):
    record_audit_event(
        action=AuditEvent.Action.SITE_CONTENT_UPDATED,
        actor=actor,
        metadata={"page": page, "section": key, "event": event},
    )


def _delete_files_on_commit(names):
    names = [name for name in names if name]
    if names:
        transaction.on_commit(lambda: [default_storage.delete(name) for name in names])


def _apply(block, *, data, new_images, remove, alts):
    block.eyebrow = normalize_text(data.get("eyebrow", block.eyebrow))
    block.title = normalize_text(data.get("title", block.title))
    block.body = "\n".join(line.rstrip() for line in str(data.get("body", block.body) or "").strip().splitlines())
    errors = {}
    if block.is_article and not block.title:
        errors["title"] = _("El artículo necesita un título.")
    new_images = list(new_images or [])
    remove = {str(value) for value in remove or []}
    if not images_allowed(block.page, block.is_article) and (new_images or remove):
        errors["images"] = _("Las secciones del inicio no llevan imágenes.")
    existing = list(block.images.all()) if block.pk else []
    unknown = remove - {str(image.pk) for image in existing}
    if unknown:
        errors["images"] = _("Imagen desconocida.")
    kept = [image for image in existing if str(image.pk) not in remove]
    if len(kept) + len(new_images) > PageBlock.MAX_IMAGES:
        errors["images"] = _("Como máximo %(max)s imágenes por sección.") % {"max": PageBlock.MAX_IMAGES}
    if errors:
        raise ValidationError(errors)
    block.full_clean(exclude=["created_by"])
    block.save()
    removed = [image for image in existing if str(image.pk) in remove]
    _delete_files_on_commit([image.image.name for image in removed])
    PageBlockImage.objects.filter(pk__in=[image.pk for image in removed]).delete()
    alts = alts or {}
    for image in kept:
        alt = normalize_text(alts.get(str(image.pk), image.alt))[:200]
        if alt != image.alt:
            image.alt = alt
            image.save(update_fields=["alt"])
    position = max((image.position for image in kept), default=-1)
    for upload in new_images:
        position += 1
        image = PageBlockImage(block=block, image=upload, position=position)
        image.full_clean(exclude=["block"])
        image.save()
    transaction.on_commit(services.invalidate_cache)
    return block


@transaction.atomic
def save_block(*, actor, page, key, data, new_images=(), remove=(), alts=None):
    """Guarda los textos (y, si los admite, las imágenes) de una sección o artículo."""
    _require_owner(actor)
    if not is_editable(page, key):
        raise ValidationError(_("Sección desconocida."), code="unknown_section")
    block = PageBlock.objects.select_for_update().filter(page=page, key=key).first()
    if block is None:
        block = PageBlock(page=page, key=key, created_by=actor)
    block = _apply(block, data=data, new_images=new_images, remove=remove, alts=alts)
    _audit(actor, page, key, "edited")
    return block


@transaction.atomic
def create_article(*, actor, page, data, new_images=(), alts=None):
    """Artículo nuevo de `page` (`layout.ARTICLE_PAGES`); aparece al final de la página, visible."""
    _require_owner(actor)
    if page not in layout.ARTICLE_PAGES:
        raise ValidationError(_("Sección desconocida."), code="unknown_section")
    block = PageBlock(page=page, key=f"{ARTICLE_PREFIX}{uuid.uuid4().hex[:12]}", is_article=True, created_by=actor)
    block = _apply(block, data=data, new_images=new_images, remove=(), alts=alts)
    _audit(actor, block.page, block.key, "article_created")
    return block


def copyable_articles(page):
    """Artículos de las otras páginas con artículos, que se pueden copiar a `page` (Fase 23)."""
    others = [other for other in layout.ARTICLE_PAGES if other != page]
    return list(
        PageBlock.objects.filter(page__in=others, is_article=True).order_by("page", "created_at", "id").prefetch_related("images")
    )


@transaction.atomic
def copy_article(*, actor, page, source_public_id, idempotency_key):
    """
    Copia en `page` un artículo de otra página: textos e imágenes, con ficheros nuevos,
    así que cada copia se edita y se elimina por separado. Aparece al final, visible.

    `idempotency_key` (UUID que pone el formulario) hace que un doble envío devuelva la
    copia ya hecha en vez de crear otra; la restricción única resuelve los envíos simultáneos.
    """
    _require_owner(actor)
    if page not in layout.ARTICLE_PAGES:
        raise ValidationError(_("Sección desconocida."), code="unknown_section")
    existing = PageBlock.objects.filter(copy_key=idempotency_key, page=page, is_article=True).first()
    if existing is not None:
        return existing
    source = (
        PageBlock.objects.select_for_update()
        .filter(public_id=source_public_id, is_article=True, page__in=layout.ARTICLE_PAGES)
        .exclude(page=page)
        .first()
    )
    if source is None:
        raise ValidationError(_("Artículo desconocido."), code="unknown_article")
    block = PageBlock(
        page=page,
        key=f"{ARTICLE_PREFIX}{uuid.uuid4().hex[:12]}",
        is_article=True,
        eyebrow=source.eyebrow,
        title=source.title,
        body=source.body,
        copy_key=idempotency_key,
        created_by=actor,
    )
    block.full_clean(exclude=["created_by", "copy_key"])
    try:
        with transaction.atomic():
            block.save()
    except IntegrityError:
        # Otro envío con la misma clave se ha adelantado: se devuelve su copia.
        existing = PageBlock.objects.filter(copy_key=idempotency_key, page=page, is_article=True).first()
        if existing is None:
            raise
        return existing
    written = []
    try:
        for original in source.images.all():
            image = PageBlockImage(block=block, alt=original.alt, position=original.position)
            with original.image.open("rb") as content:
                image.image.save(os.path.basename(original.image.name), File(content), save=False)
            written.append(image.image.name)
            image.save()
    except Exception:
        # La transacción deshace las filas; los ficheros ya escritos se borran aquí.
        for name in written:
            default_storage.delete(name)
        raise
    transaction.on_commit(services.invalidate_cache)
    record_audit_event(
        action=AuditEvent.Action.SITE_CONTENT_UPDATED,
        actor=actor,
        metadata={"page": page, "section": block.key, "event": "article_copied", "source_page": source.page, "source_section": source.key},
    )
    return block


@transaction.atomic
def delete_article(*, actor, page, key):
    """Elimina un artículo de `page` y sus imágenes (también los ficheros, al confirmar)."""
    _require_owner(actor)
    # Por página y clave: desde la URL de una página no se borra un artículo de otra.
    block = PageBlock.objects.select_for_update().filter(page=page, key=key, is_article=True).first()
    if block is None:
        raise ValidationError(_("Artículo desconocido."), code="unknown_article")
    _delete_files_on_commit([image.image.name for image in block.images.all()])
    block.delete()
    transaction.on_commit(services.invalidate_cache)
    _audit(actor, page, key, "article_deleted")


# --- Lectura para las páginas públicas ---------------------------------------------------


@dataclass
class Section:
    key: str
    page: str
    template: str
    eyebrow: str
    title: str
    body: str | None
    custom_body: bool
    is_article: bool = False
    images: list = field(default_factory=list)

    @property
    def single_image(self):
        return self.images[0] if len(self.images) == 1 else None

    @property
    def gallery(self):
        return self.images if len(self.images) > 1 else []


def _template(page, key, is_article):
    if is_article:
        return "web/about/_article.html"
    return f"web/{layout.TEMPLATE_FOLDERS[page]}/_{key}.html"


def page_sections(page, business):
    """Secciones visibles de `page`, en orden, con sus textos ya resueltos."""
    keys = business["page_sections_visible"][page]
    blocks = {block.key: block for block in PageBlock.objects.filter(page=page).prefetch_related("images")}
    fixed = set(fixed_keys(page))
    sections = []
    for key in keys:
        block = blocks.get(key)
        if key not in fixed and (block is None or not block.is_article):
            continue
        eyebrow, title, body = defaults(page, key)
        custom_body = bool(block and block.body)
        if custom_body:
            body = block.body
        elif (page, key) in ABOUT_TEXT_SECTIONS and business.get("about_text"):
            body, custom_body = business["about_text"], True
        sections.append(
            Section(
                key=key,
                page=page,
                template=_template(page, key, bool(block and block.is_article)),
                eyebrow=(block.eyebrow if block and block.eyebrow else eyebrow),
                title=(block.title if block and block.title else title),
                body=body,
                custom_body=custom_body,
                is_article=bool(block and block.is_article),
                images=list(block.images.all()) if block and images_allowed(page, block.is_article) else [],
            )
        )
    return sections
