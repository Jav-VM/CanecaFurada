"""
Comprobaciones de entorno de los datos de demostración.

Primera barrera: la app `apps.demo` solo está instalada en
`config.settings.dev` y `config.settings.test`. Segunda (esta): aunque alguien
la instalara en otro sitio, solo se acepta la configuración de tests, o la de
desarrollo con `DEBUG=True`. No se confía en una variable suelta: se mira el
módulo de configuración realmente cargado.
"""
from pathlib import Path

from django.conf import UserSettingsHolder, settings
from django.db import connection

TEST_SETTINGS = "config.settings.test"
DEV_SETTINGS = "config.settings.dev"


class DemoEnvironmentError(Exception):
    pass


def loaded_settings_module():
    """
    Módulo de configuración realmente cargado. Con `override_settings` activo,
    `settings.SETTINGS_MODULE` vale `None` (`UserSettingsHolder` lo define en la
    clase), así que se recorren las capas hasta la configuración original; un
    valor sobrescrito explícitamente en una capa (tests) tiene prioridad.
    """
    holder = settings._wrapped if settings.configured else None
    while isinstance(holder, UserSettingsHolder):
        if "SETTINGS_MODULE" in holder.__dict__:
            return holder.SETTINGS_MODULE
        holder = holder.default_settings
    return getattr(holder, "SETTINGS_MODULE", None)


def check_environment():
    module = loaded_settings_module()
    if module == TEST_SETTINGS:
        return
    if module == DEV_SETTINGS and settings.DEBUG is True:
        return
    raise DemoEnvironmentError(
        "Los datos de demostración solo se cargan en desarrollo: usa "
        f"DJANGO_SETTINGS_MODULE={DEV_SETTINGS} con DJANGO_DEBUG=True (o la configuración de tests). "
        f"Configuración actual: {module or 'desconocida'}"
        + (" con DEBUG=False." if module == DEV_SETTINGS else ".")
    )


def database_label():
    """Motor y nombre de la base de datos, sin host, usuario ni contraseña."""
    engine = connection.settings_dict["ENGINE"].rsplit(".", 1)[-1]
    name = str(connection.settings_dict.get("NAME") or "")
    if engine == "sqlite3":
        name = Path(name).name
    return f"{engine} «{name}»"
