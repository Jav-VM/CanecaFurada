#!/usr/bin/env bash
# Despliegue de Caneca Furada en el VPS (Fase 12). Ver docs/fase-12-despliegue.md.
#
#   deploy/scripts/deploy.sh             actualización: copia → build → migrate → arranque
#   deploy/scripts/deploy.sh --first     primer despliegue (sin copia previa: aún no hay datos)
#   deploy/scripts/deploy.sh rollback    vuelve a las imágenes del despliegue anterior
#
# Imágenes: caneca-furada:<commit> y caneca-furada-nginx:<commit>. `current` es la que
# está en marcha y `previous` la anterior (para el rollback). Las migraciones se aplican
# una sola vez, con el servicio `migrate`, antes de cambiar la versión de web.
source "$(dirname "$0")/_common.sh"

APP_IMAGE="${CANECA_IMAGE:-caneca-furada}"
IMAGES=("$APP_IMAGE" "$APP_IMAGE-nginx")

retag() {  # retag <origen> <destino> para las dos imágenes
    local image
    for image in "${IMAGES[@]}"; do docker tag "$image:$1" "$image:$2"; done
}

start_services() {
    IMAGE_TAG=current compose up -d --wait web scheduler nginx
    # certbot no tiene sentido sin dominio real (p. ej. en la pila local).
    if compose config --services | grep -qx certbot; then compose up -d certbot; fi
}

case "${1:-}" in
    ""|--first)
        tag="$(git rev-parse --short=12 HEAD)"
        if [ -n "$(git status --porcelain)" ]; then
            # Solo para probar en local: en el servidor el despliegue sale de un commit.
            [ "${DEPLOY_ALLOW_DIRTY:-0}" = "1" ] || die "Hay cambios sin confirmar; el despliegue debe salir de un commit."
            tag="$tag-dirty"
        fi
        if [ "${1:-}" = "--first" ]; then
            log "Primer despliegue: sin copia previa"
        else
            log "Copia de seguridad antes de actualizar"
            "$(dirname "$0")/backup.sh" run
        fi
        log "Construyendo las imágenes $tag"
        IMAGE_TAG="$tag" compose build web nginx
        compose up -d --wait db redis
        log "Aplicando migraciones (un único proceso)"
        IMAGE_TAG="$tag" compose run --rm migrate
        if docker image inspect "$APP_IMAGE:current" >/dev/null 2>&1; then
            retag current previous
        fi
        retag "$tag" current
        log "Arrancando la versión $tag"
        start_services
        log "Desplegado $tag"
        ;;
    rollback)
        docker image inspect "$APP_IMAGE:previous" >/dev/null 2>&1 || die "No hay una versión anterior (previous)."
        log "Volviendo a la versión anterior. Las migraciones NO se deshacen (ver procedimiento de rollback)."
        retag current rolled-back
        retag previous current
        start_services
        log "Rollback hecho; la versión retirada queda como :rolled-back"
        ;;
    *)
        die "Uso: $0 [--first|rollback]"
        ;;
esac
