"""
Canal SMS opcional.

**No hay ningún proveedor de SMS integrado.** El canal solo se activa si la
variable de entorno `SMS_BACKEND` apunta a una clase con el método
`send(*, to, body)` que hable con un proveedor real (hay que escribirla al
contratarlo, con sus credenciales en variables de entorno). Mientras esté
vacía, `is_configured()` es `False`: no se crean SMS, las campañas por SMS no
se pueden programar y las notificaciones SMS que existieran se marcan como no
enviadas (`sms_sin_proveedor`). Nunca se da un SMS por enviado sin proveedor.

`LocmemSmsBackend` solo existe para los tests y producción lo rechaza.
"""
from django.conf import settings
from django.utils.module_loading import import_string

SIMULATED_BACKENDS = {"apps.notifications.sms.LocmemSmsBackend"}


class BaseSmsBackend:
    def send(self, *, to, body):
        """Envía `body` al número E.164 `to`. Debe lanzar una excepción si el proveedor no lo acepta."""
        raise NotImplementedError


class LocmemSmsBackend(BaseSmsBackend):
    """Guarda los mensajes en memoria. Solo para tests."""

    outbox = []

    def send(self, *, to, body):
        LocmemSmsBackend.outbox.append({"to": to, "body": body})


def is_configured():
    return bool(settings.SMS_BACKEND)


def get_backend():
    return import_string(settings.SMS_BACKEND)()
