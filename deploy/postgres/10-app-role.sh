#!/bin/sh
# Lo ejecuta la imagen oficial de PostgreSQL SOLO al inicializar un volumen vacío.
# Crea el rol de la aplicación con privilegios mínimos (sin SUPERUSER, CREATEDB
# ni CREATEROLE) y su BD con ICU es-ES (docs/migracion-postgresql.md §8).
# El superusuario (POSTGRES_USER) queda para administración y copias.
set -eu

: "${APP_DB_NAME:?}" "${APP_DB_USER:?}" "${APP_DB_PASSWORD:?}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
    -v app_db="$APP_DB_NAME" -v app_user="$APP_DB_USER" -v app_password="$APP_DB_PASSWORD" <<'SQL'
CREATE ROLE :"app_user" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
CREATE DATABASE :"app_db" OWNER :"app_user" ENCODING 'UTF8'
    LOCALE_PROVIDER icu ICU_LOCALE 'es-ES' LOCALE 'C.UTF-8' TEMPLATE template0;
REVOKE ALL ON DATABASE :"app_db" FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE :"app_db" TO :"app_user";
SQL
