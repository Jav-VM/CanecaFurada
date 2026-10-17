"""
Contenido estático de la web pública.

Solo datos reales del negocio. Lo que el propietario aún no ha aportado vale
`None` y las plantillas lo muestran como pendiente: nunca se inventan
direcciones, horarios, precios ni textos.

Desde la Fase 9 el propietario edita la dirección, el horario, el contacto, las
redes, la presentación y (Fase 10) los textos del inicio en el dashboard (`models.BusinessInfo`); estos valores
son los de partida y `services.business_info()` los sustituye por lo guardado.
"""

from django.utils.translation import gettext_lazy as _

# Lema oficial, tal como aparece en el logotipo (en gallego en los dos idiomas).
TAGLINE = "A cervexería 100% artesá da Coruña"

BUSINESS = {
    "name": "Caneca Furada",
    "city": "A Coruña",  # figura en el logotipo oficial
    "address": None,
    "maps_url": "https://maps.app.goo.gl/1azgzDRChyNmEtHy8",  # ficha del local en Google Maps
    "opening_hours": None,  # lista de (días, horario) cuando se conozca
    "email": None,
    "phone": None,
    "social_links": (),  # tuplas (nombre, url)
    "about_text": None,  # presentación de la marca
    "hero_text": None,  # frase de bienvenida del inicio (Fase 10)
    "announcement": None,  # aviso destacado del inicio (Fase 10)
}

# Navegación principal: (nombre de URL, etiqueta).
MAIN_NAV = (
    ("web:home", _("Inicio")),
    ("web:about", _("La cervecería")),
    ("web:menu", _("Carta")),
    ("web:rewards", _("Recompensas")),
    ("web:events", _("Eventos")),
    ("web:contact", _("Contacto")),
)
