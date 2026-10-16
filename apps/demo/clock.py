"""
Reloj simulado para construir un historial coherente por los servicios reales.

Los servicios toman la hora de `django.utils.timezone.now()` (también
`auto_now_add` y `timezone.localdate()`). Mientras el reloj está activo esa
función devuelve la hora simulada, de modo que cada operación se ejecuta "en su
fecha" con todas sus reglas (antelación de reservas, caducidad de canjes,
regla de conversión vigente...). Solo existe dentro del comando de demo y se
restaura siempre al salir.

No afecta a los `default=timezone.now` de los modelos (se resolvieron al
importar): el constructor corrige esas fechas explícitamente.
"""
from unittest import mock


class SimulatedClock:
    def __init__(self, start):
        self._now = start
        self._patcher = None

    def now(self):
        return self._now

    def set(self, value):
        # Nunca hacia atrás: el ledger y los historiales se escriben en orden.
        if value < self._now:
            raise ValueError("El reloj simulado no puede retroceder.")
        self._now = value

    def __enter__(self):
        self._patcher = mock.patch("django.utils.timezone.now", new=self.now)
        self._patcher.start()
        return self

    def __exit__(self, *exc_info):
        self._patcher.stop()
        self._patcher = None
        return False
