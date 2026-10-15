"""
Configuración de Gunicorn para el contenedor `web` (Fase 12).

Los valores se pueden ajustar por entorno sin reconstruir la imagen. Ver
docs/fase-12-despliegue.md.
"""
import os

bind = "0.0.0.0:8000"

# Workers síncronos: (2 × núcleos) + 1 es la referencia habitual. Con 3 se
# cubre un VPS pequeño; súbelo si el SMTP lento (envío dentro de la petición,
# riesgo aceptado P2-3) llega a bloquearlos todos.
workers = int(os.environ.get("GUNICORN_WORKERS", "3"))

# Por encima de EMAIL_TIMEOUT (10 s por defecto) para que un SMTP lento falle
# con su propio error y no con la muerte del worker (P2-3).
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "30"))
graceful_timeout = 30
keepalive = 5

# Recicla los workers de vez en cuando (fugas de memoria de dependencias).
max_requests = 1000
max_requests_jitter = 100

# El sistema de ficheros del contenedor es de solo lectura: latidos en memoria.
worker_tmp_dir = "/dev/shm"

# Sin log de accesos: ya lo registra Nginx con un formato sin cabeceras de
# autenticación ni cadenas de consulta. Errores a la salida estándar.
accesslog = None
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# Sin socket de control (Gunicorn 25.1+): no se usa y el sistema de ficheros es de solo lectura.
control_socket_disable = True

# Límites de la línea de petición y de las cabeceras (valores por defecto de Gunicorn, explícitos).
limit_request_line = 4094
limit_request_fields = 100
