from . import content, services


def site(request):
    """Datos comunes a todas las páginas (cabecera, navegación y pie)."""
    return {
        "site_nav": content.MAIN_NAV,
        "business": services.business_info(),
        "tagline": content.TAGLINE,
    }
