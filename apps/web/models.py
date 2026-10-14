"""
Contenido del local editable por el propietario (Fase 9; textos del inicio, Fase 10).

Una sola fila (`BusinessInfo`, id = 1, también restringido en la BD). Los
campos vacíos significan "pendiente de aportar": la web pública sigue
mostrándolos como pendientes y nunca se inventan valores. El nombre y la
ciudad son de la marca y no se editan aquí (`content.BUSINESS`).

Las reglas (permisos, auditoría, caché) están en `services.py`.
"""
import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.accounts.validators import normalize_text

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
        left, _, right = line.partition(LINE_SEPARATOR)
        pairs.append((normalize_text(left), normalize_text(right)))
    return pairs


def _is_safe_url(url):
    parts = urlsplit(url)
    return parts.scheme == "https" and bool(parts.netloc) and " " not in url


class BusinessInfo(models.Model):
    address = models.CharField("dirección pública del local", max_length=200, blank=True)
    opening_hours = models.TextField(
        "horario",
        blank=True,
        max_length=1000,
        help_text="Una línea por franja: «Días | horario», por ejemplo «Lunes a jueves | 18:00–00:00».",
    )
    email = models.EmailField("email de contacto", blank=True)
    phone = models.CharField("teléfono de contacto", max_length=20, blank=True)
    social_links = models.TextField(
        "redes sociales",
        blank=True,
        max_length=1000,
        help_text="Una línea por red: «Nombre | https://…». Solo enlaces https.",
    )
    about_text = models.TextField("presentación de la cervecería", blank=True, max_length=2000)
    # Fase 10: textos principales del inicio.
    hero_text = models.CharField("texto de bienvenida del inicio", max_length=300, blank=True)
    announcement = models.CharField("aviso destacado", max_length=200, blank=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)

    class Meta:
        verbose_name = "contenido del local"
        verbose_name_plural = "contenido del local"
        constraints = [models.CheckConstraint(condition=Q(id=SINGLETON_ID), name="web_businessinfo_singleton")]

    def __str__(self):
        return "Contenido del local"

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
            errors["phone"] = "Teléfono no válido: solo números, espacios y un + inicial."
        hours = parse_pairs(self.opening_hours)
        if len(hours) > MAX_LINES or any(not days or not time for days, time in hours):
            errors["opening_hours"] = f"Escribe hasta {MAX_LINES} líneas con el formato «Días | horario»."
        links = parse_pairs(self.social_links)
        if len(links) > MAX_LINES or any(not name or not _is_safe_url(url) for name, url in links):
            errors["social_links"] = f"Escribe hasta {MAX_LINES} líneas con el formato «Nombre | https://…»."
        if errors:
            raise ValidationError(errors)
        self.opening_hours = "\n".join(f"{a} {LINE_SEPARATOR} {b}" for a, b in hours)
        self.social_links = "\n".join(f"{a} {LINE_SEPARATOR} {b}" for a, b in links)
