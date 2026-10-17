"""
Contenido del local editable por el propietario (Fase 9; textos del inicio, Fase 10).

Una sola fila (`BusinessInfo`, id = 1, también restringido en la BD). Los
campos vacíos significan "pendiente de aportar": la web pública sigue
mostrándolos como pendientes y nunca se inventan valores. El nombre y la
ciudad son de la marca y no se editan aquí (`content.BUSINESS`).

Las reglas (permisos, auditoría, caché) están en `services.py`.
"""
import re
import uuid
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.accounts.validators import normalize_text
from apps.catalog.validators import validate_image_extension, validate_image_file

SINGLETON_ID = 1
LINE_SEPARATOR = "|"
MAX_LINES = 10
_PHONE_RE = re.compile(r"^\+?[0-9 ]{6,20}$")


def parse_pairs(value):
    """Convierte líneas `izquierda | derecha` en tuplas, ignorando las vacías."""
    pairs = []
    for line in (value or "").splitlines():
        line = line.strip()
        if not line:
            continue
        left, _unused, right = line.partition(LINE_SEPARATOR)
        pairs.append((normalize_text(left), normalize_text(right)))
    return pairs


def _is_safe_url(url):
    parts = urlsplit(url)
    return parts.scheme == "https" and bool(parts.netloc) and " " not in url


class BusinessInfo(models.Model):
    address = models.CharField(_("dirección pública del local"), max_length=200, blank=True)
    opening_hours = models.TextField(
        _("horario"),
        blank=True,
        max_length=1000,
        help_text=_("Una línea por franja: «Días | horario», por ejemplo «Lunes a jueves | 18:00–00:00»."),
    )
    email = models.EmailField(_("email de contacto"), blank=True)
    phone = models.CharField(_("teléfono de contacto"), max_length=20, blank=True)
    social_links = models.TextField(
        _("redes sociales"),
        blank=True,
        max_length=1000,
        help_text=_("Una línea por red: «Nombre | https://…». Solo enlaces https."),
    )
    about_text = models.TextField(_("presentación de la cervecería"), blank=True, max_length=2000)
    # Fase 10: textos principales del inicio.
    hero_text = models.CharField(_("texto de bienvenida del inicio"), max_length=300, blank=True)
    announcement = models.CharField(_("aviso destacado"), max_length=200, blank=True)
    # Fase 17: si está desactivado, los enlaces de reserva llevan a Contacto (reserva por teléfono).
    online_reservations_enabled = models.BooleanField(_("reservas online activadas"), default=True)
    # Fase 20: orden y visibilidad de las secciones (ver `layout.py`). Vacío = orden por defecto.
    home_layout = models.JSONField(_("orden de las secciones del inicio"), default=list, blank=True)
    about_layout = models.JSONField(_("orden de las secciones de La cervecería"), default=list, blank=True)
    # Fase 22.
    menu_layout = models.JSONField(_("orden de las secciones de la Carta"), default=list, blank=True)
    rewards_layout = models.JSONField(_("orden de las secciones de Recompensas"), default=list, blank=True)
    events_layout = models.JSONField(_("orden de las secciones de Eventos"), default=list, blank=True)
    contact_layout = models.JSONField(_("orden de las secciones de Contacto"), default=list, blank=True)
    updated_at = models.DateTimeField(_("actualizado"), auto_now=True)

    class Meta:
        verbose_name = _("contenido del local")
        verbose_name_plural = _("contenido del local")
        constraints = [models.CheckConstraint(condition=Q(id=SINGLETON_ID), name="web_businessinfo_singleton")]

    def __str__(self):
        return _("Contenido del local")

    def save(self, *args, **kwargs):
        self.pk = SINGLETON_ID
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        self.address = normalize_text(self.address)
        self.phone = normalize_text(self.phone)
        self.email = (self.email or "").strip().lower()
        self.about_text = (self.about_text or "").strip()
        self.hero_text = normalize_text(self.hero_text)
        self.announcement = normalize_text(self.announcement)
        errors = {}
        if self.phone and not _PHONE_RE.match(self.phone):
            errors["phone"] = _("Teléfono no válido: solo números, espacios y un + inicial.")
        hours = parse_pairs(self.opening_hours)
        if len(hours) > MAX_LINES or any(not days or not time for days, time in hours):
            errors["opening_hours"] = _("Escribe hasta %(MAX_LINES)s líneas con el formato «Días | horario».") % {"MAX_LINES": MAX_LINES}
        links = parse_pairs(self.social_links)
        if len(links) > MAX_LINES or any(not name or not _is_safe_url(url) for name, url in links):
            errors["social_links"] = _("Escribe hasta %(MAX_LINES)s líneas con el formato «Nombre | https://…».") % {"MAX_LINES": MAX_LINES}
        if errors:
            raise ValidationError(errors)
        self.opening_hours = "\n".join(f"{a} {LINE_SEPARATOR} {b}" for a, b in hours)
        self.social_links = "\n".join(f"{a} {LINE_SEPARATOR} {b}" for a, b in links)


# --- Fase 21: contenido de las secciones y artículos ----------------------------------


def page_image_path(instance, filename):
    # Nombre aleatorio: no se publica el nombre original del fichero.
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    ext = "jpg" if ext == "jpeg" else ext
    return f"pages/{uuid.uuid4().hex}.{ext}"


class PageBlock(models.Model):
    """
    Textos propios de una sección de una página, o un artículo de Inicio, La
    cervecería o Eventos (`layout.ARTICLE_PAGES`). Un campo vacío deja el texto
    por defecto (traducido) de la sección. Lo que escribe el propietario no se
    traduce (Fase 15).
    """

    class Page(models.TextChoices):
        HOME = "inicio", _("Inicio")
        ABOUT = "cerveceria", _("La cervecería")
        MENU = "carta", _("Carta")
        REWARDS = "agasallos", _("Recompensas")
        EVENTS = "eventos", _("Eventos")
        CONTACT = "contacto", _("Contacto")

    MAX_IMAGES = 12

    public_id = models.UUIDField(_("identificador"), default=uuid.uuid4, unique=True, editable=False)
    page = models.CharField(_("página"), max_length=12, choices=Page.choices)
    key = models.CharField(_("sección"), max_length=40)
    is_article = models.BooleanField(_("artículo"), default=False)
    eyebrow = models.CharField(_("antetítulo"), max_length=80, blank=True)
    title = models.CharField(_("título"), max_length=120, blank=True)
    body = models.TextField(_("texto"), max_length=5000, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("creado por"), null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(_("creado"), auto_now_add=True)
    updated_at = models.DateTimeField(_("actualizado"), auto_now=True)

    class Meta:
        verbose_name = _("sección de página")
        verbose_name_plural = _("secciones de página")
        constraints = [
            models.UniqueConstraint(fields=["page", "key"], name="web_pageblock_page_key_unique"),
            models.CheckConstraint(
                condition=Q(page__in=["inicio", "cerveceria", "carta", "agasallos", "eventos", "contacto"]),
                name="web_pageblock_page_valid",
            ),
            models.CheckConstraint(
                # Artículos: solo en `layout.ARTICLE_PAGES` y siempre con título (Fase 23).
                condition=Q(is_article=False) | (Q(page__in=["inicio", "cerveceria", "eventos"]) & ~Q(title="")),
                name="web_pageblock_article_shape",
            ),
        ]

    def __str__(self):
        return f"{self.page}:{self.key}"


class PageBlockImage(models.Model):
    """Imagen de una sección o artículo de La cervecería. Con más de una, galería."""

    block = models.ForeignKey(PageBlock, verbose_name=_("sección"), on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(
        _("imagen"),
        upload_to=page_image_path,
        width_field="width",
        height_field="height",
        validators=[validate_image_extension, validate_image_file],
    )
    width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    alt = models.CharField(_("descripción"), max_length=200, blank=True)
    position = models.PositiveSmallIntegerField(_("posición"), default=0)

    class Meta:
        verbose_name = _("imagen de sección")
        verbose_name_plural = _("imágenes de sección")
        ordering = ["position", "id"]
