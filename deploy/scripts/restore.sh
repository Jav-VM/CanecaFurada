#!/usr/bin/env bash
# Restauración desde una copia de restic (Fase 12).
#
#   deploy/scripts/restore.sh check
#       Restaura la BD en una BD TEMPORAL (caneca_restore_check), compara recuentos con
#       la BD en uso y la borra. No toca los datos reales ni para el servicio.
#
#   deploy/scripts/restore.sh full --yes
#       SUSTITUYE la BD y media/ por los de la copia: para web y scheduler, restaura,
#       aplica migrate y vuelve a levantar. Se pierde todo lo posterior a la copia.
#
# Copia a restaurar: DB_SNAPSHOT y MEDIA_SNAPSHOT (id de `backup.sh check`; por defecto latest).
source "$(dirname "$0")/_common.sh"

DB_SNAPSHOT="${DB_SNAPSHOT:-latest}"
MEDIA_SNAPSHOT="${MEDIA_SNAPSHOT:-latest}"
CHECK_DB="caneca_restore_check"

# Restaura el volcado de la copia en la BD $1 (la borra y la crea de nuevo, con ICU es-ES).
restore_db_into() {
    local target="$1"
    log "Descargando el volcado ($DB_SNAPSHOT) al contenedor de PostgreSQL"
    restic dump --host "$RESTIC_HOST" --tag db "$DB_SNAPSHOT" /caneca.dump \
        | compose exec -T db sh -ec 'umask 077; cat > /tmp/caneca-restore.dump'
    log "Restaurando en la BD $target"
    compose exec -T -e TARGET_DB="$target" db sh -ec '
        trap "rm -f /tmp/caneca-restore.dump" EXIT
        pg_restore --list /tmp/caneca-restore.dump > /dev/null
        psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d postgres \
            -v db="$TARGET_DB" -v owner="$APP_DB_USER" <<'"'"'SQL'"'"'
DROP DATABASE IF EXISTS :"db" WITH (FORCE);
CREATE DATABASE :"db" OWNER :"owner" ENCODING '"'"'UTF8'"'"'
    LOCALE_PROVIDER icu ICU_LOCALE '"'"'es-ES'"'"' LOCALE '"'"'C.UTF-8'"'"' TEMPLATE template0;
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE :"db" TO :"owner";
SQL
        pg_restore -U "$POSTGRES_USER" -d "$TARGET_DB" --no-owner --role="$APP_DB_USER" \
            --exit-on-error --single-transaction /tmp/caneca-restore.dump
    '
}

# Recuentos para comparar dos BD (sin datos personales: solo números).
counts() {
    compose exec -T -e TARGET_DB="$1" db sh -ec '
        psql -At -U "$POSTGRES_USER" -d "$TARGET_DB" -c "
            SELECT '"'"'tablas'"'"', count(*) FROM information_schema.tables WHERE table_schema = '"'"'public'"'"'
            UNION ALL SELECT '"'"'migraciones'"'"', count(*) FROM django_migrations
            UNION ALL SELECT '"'"'usuarios'"'"', count(*) FROM accounts_user
            UNION ALL SELECT '"'"'movimientos_puntos'"'"', count(*) FROM loyalty_pointstransaction
            UNION ALL SELECT '"'"'compras'"'"', count(*) FROM purchases_purchase
            UNION ALL SELECT '"'"'canjes'"'"', count(*) FROM rewards_redemption
            UNION ALL SELECT '"'"'reservas'"'"', count(*) FROM events_reservation"
    '
}

case "${1:-}" in
    check)
        app_db="$(compose exec -T db sh -c 'printf %s "$APP_DB_NAME"')"
        restore_db_into "$CHECK_DB"
        live="$(counts "$app_db")"
        restored="$(counts "$CHECK_DB")"
        printf '%-20s %10s %10s\n' "" "en uso" "copia" >&2
        paste -d'|' <(printf '%s\n' "$live") <(printf '%s\n' "$restored") \
            | awk -F'|' '{ printf "%-20s %10s %10s\n", $1, $2, $4 }' >&2
        compose exec -T -e TARGET_DB="$CHECK_DB" db sh -ec \
            'psql -q -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE \"$TARGET_DB\" WITH (FORCE)"'
        log "Restauración de prueba correcta; BD temporal borrada"
        ;;
    full)
        [ "${2:-}" = "--yes" ] || die "Sustituye los datos reales. Repite con: $0 full --yes"
        app_db="$(compose exec -T db sh -c 'printf %s "$APP_DB_NAME"')"
        log "Parando web y scheduler (Nginx mostrará un error 502 mientras tanto)"
        compose stop web scheduler
        restore_db_into "$app_db"
        log "Restaurando media/ ($MEDIA_SNAPSHOT)"
        compose --profile restore run --rm -T --entrypoint sh restore-media -ec "
            restic restore '$MEDIA_SNAPSHOT' --host '$RESTIC_HOST' --tag media --target /tmp/restore
            find /backup/media -mindepth 1 -delete
            cp -a /tmp/restore/backup/media/. /backup/media/
        "
        log "Aplicando migraciones (por si la copia es de una versión anterior)"
        compose run --rm migrate
        compose up -d --wait web scheduler nginx
        log "Restauración completa"
        ;;
    *)
        die "Uso: $0 check | $0 full --yes"
        ;;
esac
