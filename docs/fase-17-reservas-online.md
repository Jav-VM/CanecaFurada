# Fase 17 — Interruptor de reservas online

**Estado:** Completa (revisión visual en el navegador pendiente; ver §8).
**Fecha:** 2026-10-17.
**Depende de:** [Fase 9](fase-09-dashboard-propietario.md) (dashboard y contenido del local), [Fase 10](fase-10-eventos-reservas-notificaciones.md) (reservas), [Fase 11](fase-11-api-auditoria.md) (API) y [Fase 15](fase-15-idioma-gallego.md) (traducciones).

## 1. Objetivo y decisiones

El propietario activa o desactiva las reservas online desde **Dashboard → Configuración → Reservas online**.

- **Activadas** (valor por defecto, comportamiento anterior): los botones de reserva llevan al formulario de reservas.
- **Desactivadas:** esos botones llevan a **Contacto** (`/contacto/#reservas`), que muestra el bloque «Reservas por teléfono» con un botón `tel:` al teléfono del local.

| Decisión | Motivo |
|---|---|
| Afecta a **todas** las reservas nuevas (mesa y eventos), en la web y en la API. | Un único interruptor, sin casos intermedios. |
| **Por defecto activadas.** | Desplegar la fase no cambia nada hasta que el propietario lo decida. |
| **Las reservas existentes no cambian.** El cliente las ve y las cancela; el propietario las confirma o rechaza. | Desactivar no debe dejar reservas a medias. |
| **Bloqueo también en el servidor**, no solo en los enlaces. | Ocultar un botón no impide abrir la URL ni llamar a la API. |
| Se guarda en `BusinessInfo` (fila única, ya cacheada) y **no** en `EDITABLE_FIELDS`. | Reutiliza caché e invalidación; el formulario de Contenido no puede cambiarlo (asignación masiva). |
| Auditoría con la acción existente `SITE_CONTENT_UPDATED` (`metadata = {"fields": ["online_reservations_enabled"], "enabled": …}`). | Evita una migración de `AuditEvent.Action` solo para un booleano; queda identificable por `fields`. |
| Si no hay teléfono publicado, Contacto muestra un texto genérico y Configuración avisa. | Nunca se inventan datos del local. |

## 2. Alcance y exclusiones

- **Incluye:** modelo y migración, servicio, formulario y vista del dashboard, enlaces públicos (Eventos, detalle de evento, Mis reservas), bloque de Contacto, bloqueo en vistas, servicio y API, `bookable` de la API, traducciones, OpenAPI y tests.
- **No incluye:** cerrar reservas por fechas o franjas, un teléfono distinto para reservas ni cambios en la app Flutter (debe tratar `bookable = false` y el error `reservations_disabled`).

## 3. Archivos modificados

| Archivo | Cambio |
|---|---|
| `apps/web/models.py`, `apps/web/migrations/0003_online_reservations.py` | `BusinessInfo.online_reservations_enabled` (`BooleanField`, `default=True`). Migración `AddField`, no destructiva. |
| `apps/web/services.py` | `online_reservations_enabled()` (desde la caché de `business_info()`) y `set_online_reservations(actor, enabled)`: solo propietario, `select_for_update`, idempotente (sin cambio no guarda ni audita), invalida la caché al confirmar. |
| `apps/dashboard/forms.py`, `views.py`, `urls.py` | `OnlineReservationsForm` (prefijo `reservas`) y vista `settings_reservations` (`POST /dashboard/configuracion/reservas/`, solo propietario). |
| `templates/dashboard/settings.html` | Sección «Reservas online» con el estado vigente y aviso si falta el teléfono. |
| `templates/web/events.html`, `templates/events/event_detail.html`, `templates/events/my_reservations.html` | Con reservas desactivadas, «Reservar por teléfono» → `/contacto/#reservas`. |
| `templates/web/contact.html` | Bloque `#reservas` «Reservas por teléfono». |
| `apps/events/views.py` | `reservation_new` y `event_reservation_new` (GET y POST) redirigen a Contacto con un aviso. |
| `apps/events/services.py` | `request_reservation` rechaza con el código `reservations_disabled` (cubre web y API). Un reintento con la misma clave de idempotencia de una reserva ya creada sigue devolviéndola. |
| `apps/api/exceptions.py`, `apps/api/views/events.py`, `apps/api/serializers/events.py`, `docs/api/openapi.yaml` | `reservations_disabled` → **409**; `bookable` es `false` con reservas desactivadas; esquema regenerado. |
| `locale/gl`, `locale/es` | 21 cadenas nuevas traducidas al gallego. |

Sin variables de entorno nuevas.

## 4. Uso

1. Dashboard → **Configuración** → **Reservas online**.
2. Desmarca «Reservas online activadas» y pulsa «Gardar reservas en liña».
3. Comprueba que en **Contenido** hay un teléfono publicado (si no, la sección lo avisa).

Para volver a activarlas, marca la casilla y guarda.

Tras actualizar el código: `python manage.py migrate` y `python scripts/i18n.py compile`.

## 5. Seguridad y privacidad

- Vista solo `POST`, con CSRF y `owner_required`; el servicio vuelve a comprobar `is_owner`. Empleado y cliente → 403; anónimo → login.
- El valor no llega por el formulario de Contenido (lista blanca `EDITABLE_FIELDS`).
- La creación de reservas se bloquea en el servicio de dominio, así que la web y la API no pueden saltárselo.
- La auditoría solo guarda el nombre del campo y el valor booleano. No hay datos personales nuevos.

## 6. Tests

`tests/dashboard/test_settings_reservations.py` (16 tests):

- valor por defecto; activar y desactivar con auditoría; repetir el mismo valor no audita;
- solo `POST`; empleado y cliente → 403; anónimo → login; el servicio rechaza a quien no es propietario;
- el formulario de Contenido no cambia el valor;
- desactivadas: los enlaces de Eventos, detalle y Mis reservas van a Contacto; Contacto muestra el bloque y el `tel:`; aviso en Configuración sin teléfono;
- desactivadas: GET y POST de los formularios redirigen sin crear reservas; el servicio lanza `reservations_disabled`; la API responde 409 y `bookable = false`;
- las reservas existentes se siguen viendo y cancelando.

Los tests comprueban marcadores `data-*` en lugar de textos, para no depender del idioma activo.

Órdenes ejecutadas y resultados: ver §7.

## 7. Resultados

| Orden | Resultado |
|---|---|
| `python manage.py check` | Sin incidencias |
| `python manage.py makemigrations --check --dry-run` | Sin cambios pendientes |
| `python scripts/i18n.py check` | Traducciones al día y completas |
| `python manage.py spectacular --validate --fail-on-warn` | Válido; `docs/api/openapi.yaml` regenerado |
| `python manage.py test tests.dashboard.test_settings_reservations --settings=config.settings.test` | 16 tests OK |
| `python manage.py test --settings=config.settings.test --noinput` | **996 tests OK** (980 previos + 16 nuevos), SQLite, 2026-10-17 |

## 8. Limitaciones y pendientes

- **Revisión visual** de la sección de Configuración y del bloque de Contacto en el navegador.
- La app Flutter debe mostrar «Reservar por teléfono» cuando `bookable` sea `false` en un evento con `accepts_reservations`, y tratar el error `reservations_disabled`.
- El estado se lee de la caché de `business_info()` (5 min, se invalida al guardar); en varios procesos con caché local cada proceso puede tardar hasta 5 min en verlo (igual que el resto del contenido del local).
