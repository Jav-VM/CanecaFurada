from . import content


def site(request):
    """Datos comunes a todas las páginas (cabecera, navegación y pie)."""
    return {
        "site_nav": content.MAIN_NAV,
        "business": content.BUSINESS,
        "tagline": content.TAGLINE,
    }
