# syntax=docker/dockerfile:1.7
#
# Imagen de Caneca Furada (Fase 12). Dos imágenes finales:
#   --target app    Django + Gunicorn (servicios web, scheduler y migrate)
#   --target nginx  Nginx con los estáticos de esta misma versión
# Sin .env, secretos, BD ni media dentro (ver .dockerignore). Ver docs/fase-12-despliegue.md.

ARG PYTHON_IMAGE=python:3.14-slim-trixie
ARG NGINX_IMAGE=nginx:1.28-alpine

# --- Dependencias de Python en un entorno virtual aislado -----------------------
FROM ${PYTHON_IMAGE} AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY requirements/ /tmp/requirements/
# Solo ruedas binarias: si alguna dependencia necesitara compilarse, el build falla
# en vez de instalar compiladores en la imagen.
RUN pip install --only-binary=:all: -r /tmp/requirements/prod.txt

# --- supercronic (programador de tareas sin root, salida a stdout) ---------------
# Versión y SHA1 de https://github.com/aptible/supercronic/releases/tag/v0.2.48
FROM ${PYTHON_IMAGE} AS supercronic
ARG SUPERCRONIC_VERSION=v0.2.48
ARG SUPERCRONIC_SHA1SUM=016b7c9aebfc8d9fd9526e8ba33b191fc524485f
RUN python - <<'EOF'
import hashlib, os, urllib.request
version, expected = os.environ["SUPERCRONIC_VERSION"], os.environ["SUPERCRONIC_SHA1SUM"]
url = f"https://github.com/aptible/supercronic/releases/download/{version}/supercronic-linux-amd64"
data = urllib.request.urlopen(url, timeout=60).read()
if hashlib.sha1(data).hexdigest() != expected:
    raise SystemExit("La suma SHA1 de supercronic no coincide")
with open("/usr/local/bin/supercronic", "wb") as f:
    f.write(data)
os.chmod("/usr/local/bin/supercronic", 0o755)
EOF

# --- Traducciones compiladas (Fase 15) ----------------------------------------------
# gettext solo existe en esta etapa: la imagen final recibe únicamente los .mo.
FROM ${PYTHON_IMAGE} AS messages
RUN apt-get update \
 && apt-get install -y --no-install-recommends gettext \
 && rm -rf /var/lib/apt/lists/*
COPY locale/ /locale/
RUN find /locale -name '*.po' -exec sh -c 'msgfmt --check -o "${1%.po}.mo" "$1"' _ {} \;

# --- Aplicación ------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    DJANGO_SETTINGS_MODULE=config.settings.prod

# tzdata: zona horaria de supercronic (TZ=Europe/Madrid). Sin compiladores ni shells extra.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --from=supercronic /usr/local/bin/supercronic /usr/local/bin/supercronic
# El código pertenece a root: el usuario `app` solo puede leerlo.
COPY . .
COPY --from=messages /locale/ /app/locale/

# collectstatic con valores ficticios que existen solo en este paso (no quedan en
# la imagen). No se conecta a la BD ni a la caché. Falla si falta un fichero.
RUN DJANGO_SECRET_KEY=solo-build-collectstatic-no-es-una-clave-real-0123456789 \
    DJANGO_ALLOWED_HOSTS=build.invalid \
    EMAIL_HOST=smtp.build.invalid \
    SITE_BASE_URL=https://build.invalid \
    DATABASE_URL=postgres://build:build@build.invalid:5432/build \
    CACHE_URL=redis://build.invalid:6379/1 \
    python manage.py collectstatic --noinput \
 && mkdir -p /app/media \
 && chown app:app /app/media

USER app
EXPOSE 8000
CMD ["gunicorn", "--config", "deploy/gunicorn.conf.py", "config.wsgi"]

# --- Nginx con los estáticos de esta versión -------------------------------------
FROM ${NGINX_IMAGE} AS nginx
# openssl: certificado autofirmado provisional hasta tener el de Let's Encrypt.
# Se quita el access_log del nginx.conf base (formato con cadena de consulta y
# Referer): solo queda el de caneca.conf, sin datos sensibles.
RUN apk add --no-cache openssl \
 && rm -f /etc/nginx/conf.d/default.conf \
 && sed -i '/^\s*access_log\s/d' /etc/nginx/nginx.conf \
 && ! grep -q 'access_log' /etc/nginx/nginx.conf
COPY deploy/nginx/templates/ /etc/nginx/templates/
COPY --chmod=755 deploy/nginx/caneca-certs.sh /usr/local/bin/caneca-certs
COPY --chmod=755 deploy/nginx/40-caneca-certs.sh /docker-entrypoint.d/40-caneca-certs.sh
COPY --from=app /app/staticfiles /srv/static
