#!/usr/bin/env bash
# Copia de seguridad cifrada de Caneca Furada con restic (Fase 12).
#
#   deploy/scripts/backup.sh init        crea el repositorio (una sola vez)
#   deploy/scripts/backup.sh [run]       copia de la BD (pg_dump -Fc) y de media/ + retención
#   deploy/scripts/backup.sh check       verifica el repositorio y lista las copias
#
# Destino, contraseña y credenciales de restic: .env.backup (plantilla .env.backup.example).
# Retención: BACKUP_KEEP_DAILY (7) y BACKUP_KEEP_WEEKLY (4).
# La BD contiene datos personales, hashes de contraseñas y refresh tokens de la app:
# el volcado nunca se escribe en el disco del servidor sin cifrar fuera del contenedor
# de PostgreSQL, y se borra al terminar.
source "$(dirname "$0")/_common.sh"

KEEP_DAILY="${BACKUP_KEEP_DAILY:-7}"
KEEP_WEEKLY="${BACKUP_KEEP_WEEKLY:-4}"

cleanup() { compose exec -T db rm -f /tmp/caneca-backup.dump >/dev/null 2>&1 || true; }

case "${1:-run}" in
    init)
        log "Creando el repositorio de restic"
        restic init
        ;;
    run)
        trap cleanup EXIT
        log "Volcado de PostgreSQL (pg_dump -Fc) y comprobación de su lectura"
        compose exec -T db sh -ec '
            umask 077
            pg_dump --format=custom -U "$POSTGRES_USER" -d "$APP_DB_NAME" -f /tmp/caneca-backup.dump
            pg_restore --list /tmp/caneca-backup.dump > /dev/null
        '
        log "Subiendo el volcado al repositorio (cifrado por restic)"
        compose exec -T db cat /tmp/caneca-backup.dump \
            | restic backup --host "$RESTIC_HOST" --tag db --stdin --stdin-filename caneca.dump
        cleanup
        log "Copia de media/"
        restic backup --host "$RESTIC_HOST" --tag media /backup/media
        log "Retención: $KEEP_DAILY diarias y $KEEP_WEEKLY semanales"
        restic forget --host "$RESTIC_HOST" --group-by host,tags \
            --keep-daily "$KEEP_DAILY" --keep-weekly "$KEEP_WEEKLY" --prune
        log "Copia terminada"
        ;;
    check)
        restic check
        restic snapshots --host "$RESTIC_HOST"
        ;;
    *)
        die "Uso: $0 [init|run|check]"
        ;;
esac
