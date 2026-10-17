"""
Orden y visibilidad de las secciones de «Inicio» y «La cervecería» (Fase 20).

Cada página tiene una **lista blanca** de secciones movibles, en su orden por
defecto. El aviso y la portada del inicio, y la cabecera de La cervecería, no
están aquí: van siempre arriba.

Lo guardado es una lista `[{"key": …, "visible": …}]` en `BusinessInfo`.
`normalize` la limpia antes de usarla: quita claves desconocidas o repetidas y
añade al final, visibles, las que falten. Así la página nunca se rompe aunque
cambien las secciones del código, y en las plantillas solo se incluyen
parciales de la lista blanca.
"""
from django.utils.translation import gettext_lazy as _

HOME = "inicio"
ABOUT = "cerveceria"

HOME_SECTIONS = (
    ("marca", _("Somos Caneca Furada")),
    ("carta", _("La carta de la casa")),
    ("cervezas", _("Nuestras cervezas")),
    ("puntos", _("Programa de puntos")),
    ("eventos", _("Eventos destacados")),
    ("local", _("El local")),
)
ABOUT_SECTIONS = (
    ("historia", _("Nuestra historia")),
    ("como", _("Cómo trabajamos")),
)
PAGES = {
    HOME: ("home_layout", HOME_SECTIONS, _("Inicio")),
    ABOUT: ("about_layout", ABOUT_SECTIONS, _("La cervecería")),
}
UP = "arriba"
DOWN = "abajo"


def normalize(stored, sections):
    """Lista limpia `[{"key", "visible"}]` con todas las secciones de la lista blanca."""
    known = [key for key, _label in sections]
    layout, seen = [], set()
    for item in stored if isinstance(stored, list) else []:
        key = item.get("key") if isinstance(item, dict) else None
        if key in known and key not in seen:
            seen.add(key)
            layout.append({"key": key, "visible": bool(item.get("visible", True))})
    layout.extend({"key": key, "visible": True} for key in known if key not in seen)
    return layout


def visible_keys(layout):
    return [item["key"] for item in layout if item["visible"]]


def with_visibility(layout, visible):
    visible = set(visible)
    return [{"key": item["key"], "visible": item["key"] in visible} for item in layout]


def move(layout, key, direction):
    """Sube o baja una sección un puesto. En los extremos no cambia nada."""
    keys = [item["key"] for item in layout]
    index = keys.index(key)
    target = index - 1 if direction == UP else index + 1
    if not 0 <= target < len(layout):
        return list(layout)
    moved = list(layout)
    moved[index], moved[target] = moved[target], moved[index]
    return moved


def rows(layout, sections):
    """Filas para el dashboard: (clave, etiqueta, visible)."""
    labels = dict(sections)
    return [(item["key"], labels[item["key"]], item["visible"]) for item in layout]
