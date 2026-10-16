from apps.core.middleware import fixed_language_path

from . import content, services


def site(request):
    """Datos comunes a todas las páginas (cabecera, navegación y pie)."""
    return {
        "site_nav": content.MAIN_NAV,
        "business": services.business_info(),
        "tagline": content.TAGLINE,
        # Banderas de idioma: no en panel, dashboard ni admin (siempre en gallego).
        "language_switch_enabled": not fixed_language_path(request.path),
    }
