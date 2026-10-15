#!/bin/sh
# Enlaza el certificado que usa Nginx (/etc/nginx/certs/*.pem):
#   - el de Let's Encrypt si ya existe (volumen `certs`, montado en solo lectura);
#   - si no, uno autofirmado provisional (7 días) para que Nginx pueda arrancar y
#     atender el reto HTTP-01 de certbot.
# Uso: caneca-certs [reload]   (con "reload", recarga Nginx después)
set -eu

name="${NGINX_SERVER_NAME%% *}"   # el primer nombre del server_name
live="/etc/letsencrypt/live/${name}"
dir="/etc/nginx/certs"
mkdir -p "$dir"

if [ -s "$live/fullchain.pem" ] && [ -s "$live/privkey.pem" ]; then
    ln -sfn "$live/fullchain.pem" "$dir/fullchain.pem"
    ln -sfn "$live/privkey.pem" "$dir/privkey.pem"
else
    if [ ! -s "$dir/selfsigned.crt" ]; then
        echo "caneca-certs: sin certificado de Let's Encrypt para ${name}; se usa uno autofirmado provisional" >&2
        openssl req -x509 -nodes -newkey rsa:2048 -days 7 -subj "/CN=${name}" \
            -keyout "$dir/selfsigned.key" -out "$dir/selfsigned.crt" 2>/dev/null
        chmod 600 "$dir/selfsigned.key"
    fi
    ln -sfn "$dir/selfsigned.crt" "$dir/fullchain.pem"
    ln -sfn "$dir/selfsigned.key" "$dir/privkey.pem"
fi

if [ "${1:-}" = "reload" ]; then
    nginx -t -q && nginx -s reload
fi
