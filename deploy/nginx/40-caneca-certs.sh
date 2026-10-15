#!/bin/sh
# Lo ejecuta el entrypoint de la imagen oficial de Nginx antes de arrancar.
# 1. Prepara el certificado (Let's Encrypt o provisional).
# 2. Cada 6 horas vuelve a enlazarlo y recarga Nginx, para tomar el primer
#    certificado y las renovaciones que deja certbot en el volumen compartido.
set -eu

: "${NGINX_SERVER_NAME:?NGINX_SERVER_NAME es obligatoria}"
: "${DJANGO_ADMIN_URL:?DJANGO_ADMIN_URL es obligatoria (la misma que usa Django)}"

/usr/local/bin/caneca-certs

(
    while :; do
        sleep 6h
        /usr/local/bin/caneca-certs reload || echo "caneca-certs: la recarga ha fallado" >&2
    done
) &
