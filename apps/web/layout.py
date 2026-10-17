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
# Fase 22.
MENU = "carta"
REWARDS = "agasallos"
EVENTS = "eventos"
CONTACT = "contacto"

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
MENU_SECTIONS = (
    ("grifos", _("Carta de grifos")),
    ("listado", _("Carta por categorías")),
)
REWARDS_SECTIONS = (
    ("como", _("Cómo funciona")),
    ("catalogo", _("Recompensas disponibles")),
    ("unete", _("Únete al club")),
)
EVENTS_SECTIONS = (
    ("listado", _("Próximos eventos")),
    ("reservar", _("¿Quieres reservar mesa?")),
)
CONTACT_SECTIONS = (
    ("local", _("El local")),
    ("cuenta", _("¿Tienes cuenta?")),
)
# Página: (campo de `BusinessInfo`, secciones, nombre, carpeta de plantillas).
PAGES = {
    HOME: ("home_layout", HOME_SECTIONS, _("Inicio")),
    ABOUT: ("about_layout", ABOUT_SECTIONS, _("La cervecería")),
    MENU: ("menu_layout", MENU_SECTIONS, _("Carta")),
    REWARDS: ("rewards_layout", REWARDS_SECTIONS, _("Recompensas")),
    EVENTS: ("events_layout", EVENTS_SECTIONS, _("Eventos")),
    CONTACT: ("contact_layout", CONTACT_SECTIONS, _("Contacto")),
}
TEMPLATE_FOLDERS = {HOME: "home", ABOUT: "about", MENU: "menu", REWARDS: "rewards", EVENTS: "events", CONTACT: "contact"}
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


# --- Fase 21: textos por defecto de cada sección ----------------------------------------
# (antetítulo, título, texto). Se usan cuando el propietario deja un campo vacío y como
# ayuda en el formulario. `None` en el texto: la sección no tiene frase por defecto.
# «Somos Caneca Furada» y «Nuestra historia» usan antes la presentación de Contenido.
DEFAULT_TEXTS = {
    HOME: {
        "marca": (_("La casa"), _("Somos Caneca Furada"), _("Una cervecería 100% artesana en A Coruña.")),
        "carta": (_("Carta"), _("La carta de la casa"), _("Consulta las cervezas y todo lo que servimos.")),
        "cervezas": (_("Selección"), _("Nuestras cervezas"), None),
        "puntos": (
            _("Programa de puntos"),
            _("Cada visita suma"),
            _("Así funciona el club de Caneca Furada. Crea tu cuenta, verifica tu email y enseña tu QR en la barra para sumar puntos."),
        ),
        "eventos": (_("Agenda"), _("Eventos destacados"), None),
        "local": (_("El local"), _("Ven a vernos"), _("Te esperamos en A Coruña.")),
    },
    ABOUT: {
        "historia": (_("Nuestra historia"), _("Cerveza 100% artesana"), _("Caneca Furada es una cervecería artesana de A Coruña.")),
        "como": (_("La casa"), _("Cómo trabajamos"), None),
    },
    # Fase 22. "" = el texto depende del estado (sesión, pizarra, reservas online) y lo
    # pone la plantilla; o la sección no tiene encabezado salvo que lo escriba el propietario.
    MENU: {
        "grifos": (_("En grifo"), "", None),
        "listado": ("", "", None),
    },
    REWARDS: {
        "como": ("", _("Cómo funciona"), _("Para sumar y canjear puntos necesitas una cuenta con el email verificado. Al canjear recibes un código de un solo uso que enseñas en la barra; si no lo usas a tiempo o lo cancelas, recuperas los puntos.")),
        "catalogo": (_("Catálogo"), _("Recompensas disponibles"), None),
        "unete": ("", "", None),
    },
    EVENTS: {
        "listado": ("", "", None),
        "reservar": ("", _("¿Quieres reservar mesa?"), None),
    },
    CONTACT: {
        "local": ("", _("El local"), None),
        "cuenta": ("", _("¿Tienes cuenta?"), _("Gestiona tus datos, tu email y tus preferencias de comunicación desde tu perfil.")),
    },
}
# Secciones fijas con imágenes propias (solo La cervecería).
IMAGE_PAGES = (ABOUT,)
# Páginas que admiten artículos del propietario (Fase 21: La cervecería; Fase 23: también
# Inicio y Eventos). Los artículos llevan imágenes en cualquiera de ellas.
ARTICLE_PAGES = (HOME, ABOUT, EVENTS)
