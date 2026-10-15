# Funciones comunes de los scripts de despliegue (se carga con `source`).
# Variables:
#   CANECA_ENV_FILE  fichero de variables (por defecto .env.prod)
#   COMPOSE_FILES    ficheros de Compose separados por espacios (por defecto compose.yaml)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ENV_FILE="${CANECA_ENV_FILE:-.env.prod}"
COMPOSE_FILES="${COMPOSE_FILES:-compose.yaml}"
RESTIC_HOST="caneca"   # nombre fijo: los contenedores tienen un hostname aleatorio

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

[ -f "$ENV_FILE" ] || die "No existe $ENV_FILE (plantilla: .env.prod.example)."

compose() {
    local args=() f
    for f in $COMPOSE_FILES; do args+=(-f "$f"); done
    docker compose "${args[@]}" --env-file "$ENV_FILE" "$@"
}

# restic en su contenedor (servicio `backup`), con las variables de .env.backup.
restic() {
    compose --profile backup run --rm -T backup "$@"
}
