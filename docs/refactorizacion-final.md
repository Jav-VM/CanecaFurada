# Refactorización final controlada

**Estado:** **Completa.** Aplicada y verificada en PostgreSQL 17 (local y en el contenedor de la pila Compose) y en SQLite (§6). El riesgo previo R-1 (interbloqueo en la regla del último propietario) se corrigió después, con aprobación expresa del usuario (§7.1). Esa corrección sí cambia el comportamiento en un caso de concurrencia.

Fecha: 2026-10-15. Se hizo después de la [Fase 12](fase-12-despliegue.md), antes de congelar la versión que se documenta en la memoria técnica. Todos los datos de ejemplo y de los tests son ficticios.

## 1. Objetivo, alcance y exclusiones

**Objetivo:** mejorar la mantenibilidad, la consistencia y la eficiencia del código **sin cambiar el comportamiento observable**.

**Restricciones respetadas:**
- La arquitectura general no cambia.
- No hay dependencias nuevas ni migraciones.
- No cambian reglas de negocio, permisos, mensajes, contratos de la API ni el esquema OpenAPI.
- No se han tocado secretos, `db.sqlite3` ni datos de producción.
- Las mejoras de rendimiento que se citan se han medido (§5).

**Procedimiento:**
1. Línea base de pruebas antes de cambiar nada.
2. Diagnóstico y plan, aprobados por el usuario.
3. Tests de caracterización para las zonas que no tenían cobertura suficiente.
4. Cambios por grupos pequeños, con la suite completa tras cada grupo.
5. Comprobaciones de producción.

## 2. Estado inicial (línea base)

| Comprobación | Resultado |
|---|---|
| `python manage.py check` | Sin incidencias |
| `makemigrations --check --dry-run` | Sin cambios |
| Suite contra PostgreSQL 17 (`--parallel 1`) | **833 OK, 0 omitidos, 0 fallos** |
| `spectacular --validate --fail-on-warn` | Válido e idéntico a `docs/api/openapi.yaml` |
| `check --deploy` con variables ficticias (las del CI) | Solo `security.W021` |

No había fallos previos que separar de posibles regresiones.

## 3. Diagnóstico

Se revisaron los selectores, los servicios y las vistas (web, panel, dashboard y API) en busca de duplicaciones, responsabilidades mal separadas, complejidad innecesaria y consultas ineficientes. Se midieron las consultas SQL de las páginas principales con 5 y con 15 clientes (§5): **no hay consultas N+1**, porque el número de consultas no crece con los datos.

| # | Hallazgo | Impacto | Coste | Decisión |
|---|---|---|---|---|
| A | `redemption_stats` lanzaba 4 `count()` y `reservation_stats` 1 agregado y 3 `count()`, en lugar de un único `aggregate` con `Count(filter=…)` (el patrón que ya usaba `customer_counts`) | Medio (se puede medir) | Bajo | Hecho |
| B | El filtro de periodo `[start, end)` estaba copiado unas 9 veces en 5 módulos de selectores, con dos `_in_period` de firmas distintas | Medio (mantenibilidad) | Bajo | Hecho |
| C | El bloqueo y recuento de propietarios activos (regla del último propietario) estaba duplicado en `change_role` y `set_user_active` | Bajo-medio (regla crítica) | Bajo | Hecho |

## 4. Cambios realizados

### Grupo 0. Tests de caracterización (antes de refactorizar)

Se escribieron y pasaron **con el código original**, en PostgreSQL y en SQLite:

- `tests/dashboard/test_stats_selectors.py`:
  - **Límites del periodo** de los 17 selectores y cifras que filtran por fechas (compras, canjes, puntos, clientes, distribución geográfica y reservas). Un dato registrado exactamente en el instante `T` se incluye en `[T, …)` y se excluye en `[…, T)`.
  - **Cada campo de `RedemptionStats`** con su propia fecha (solicitud, validación o cierre), incluidos los canjes caducados.
  - **Cada campo de `ReservationStats`**: periodo por fecha de solicitud, y pendientes, confirmadas próximas y eventos próximos según `now`.
  - Que `reservation_stats` rechaza a empleados y clientes.
- `tests/accounts/test_services.py`:
  - Se mantienen el mensaje del último propietario y la retirada de un propietario inactivo.
  - Nueva clase `SetUserActiveTests`: el servicio, y no solo el admin, impide desactivar al último propietario activo. También cubre la auditoría de activación y desactivación y la operación sin cambios.
- `tests/accounts/test_concurrency.py`: dos propietarios que se retiran mutuamente a la vez (desactivación y cambio de rol) dejan exactamente un propietario activo. Se amplió al corregir R-1 (§7.1).

### Grupo A+B. Helper de periodo y agregados condicionales

- **Nuevo** `apps/core/querysets.py` con `period_q(field, start=None, end=None)`. Devuelve la condición `Q` del periodo `[start, end)`, o `Q()` si no hay límites. Sirve para `filter()` y para el `filter` de un agregado. `core` sigue sin depender de ninguna otra app.
- Se usa en:
  - `apps/purchases/selectors.py`: se elimina `_in_period`;
  - `apps/rewards/selectors.py`: se elimina `_in_period`;
  - `apps/loyalty/selectors.py`, `apps/events/selectors.py` y `apps/accounts/selectors.py`.
- `redemption_stats`: **1 consulta** (antes 4).
- `reservation_stats`: **2 consultas** (antes 4): una para las reservas y otra para los eventos, que son otro modelo.
- Tests que fijan esos recuentos (`assertNumQueries`) para que no vuelvan a subir sin que se note.

### Grupo C. Regla del último propietario

`apps/accounts/services.py`: nuevo `_lock_active_owners()`, que bloquea con `SELECT … FOR UPDATE` las filas de los propietarios activos y devuelve cuántos hay. Lo usan `change_role` y `set_user_active`. Las condiciones, el orden de los bloqueos y los mensajes no cambian. Se comprobó que la consulta generada sigue terminando en `FOR UPDATE` (`count()` no lo admite; por eso se materializan los ids).

### Archivos afectados

| Archivo | Cambio |
|---|---|
| `apps/core/querysets.py` | Nuevo: `period_q` |
| `apps/purchases/selectors.py`, `apps/rewards/selectors.py`, `apps/loyalty/selectors.py`, `apps/events/selectors.py`, `apps/accounts/selectors.py` | Usan `period_q`; agregados condicionales en `redemption_stats` y `reservation_stats` |
| `apps/accounts/services.py` | `_lock_active_owners()` |
| `tests/dashboard/test_stats_selectors.py` | Nuevo (7 tests) |
| `tests/accounts/test_services.py` | +6 tests |
| `tests/accounts/test_concurrency.py` | Nuevo (3 tests, solo con BD compartida; ampliado en §7.1) |
| `apps/accounts/admin.py` | Corrección de R-1 (§7.1): la activación pasa por el servicio antes de guardar el resto de campos |

Sin cambios en modelos, migraciones, vistas, plantillas, URL, serializadores, settings, Docker ni CI. La corrección de R-1 (§7.1) refuerza la comprobación del actor en dos servicios; las reglas de permisos no cambian.

## 5. Mejoras verificadas (mediciones)

Número de consultas SQL por petición, medido con el cliente de pruebas de Django y `CaptureQueriesContext` sobre PostgreSQL 17, con 5 y con 15 clientes con compras, canjes y reservas. Script de medición fuera del repositorio; los recuentos que importan quedan fijados por `assertNumQueries`.

| Página | Antes (N=5 / N=15) | Después (N=5 / N=15) |
|---|---|---|
| Dashboard, resumen (`/dashboard/`) | 17 / 16 | **12 / 11** |
| API, estadísticas del propietario (`/api/v1/owner/stats/`) | 12 / 12 | **7 / 7** |
| Dashboard, recompensas (`/dashboard/recompensas/`) | 9 / 9 | **6 / 6** |
| Resto de secciones del dashboard y panel del personal | Constantes | Sin cambios |

No se dan cifras de tiempo de respuesta: con estos volúmenes de datos la diferencia no es medible de forma fiable. La mejora demostrada es el número de consultas.

Mantenibilidad:
- El filtro de periodo está en un único sitio (antes, unas 9 copias con dos firmas distintas).
- La regla del último propietario bloquea en un único sitio.
- `apps/` tiene 16 líneas netas menos, contando el módulo nuevo.
- Los selectores de estadísticas siguen todos el mismo patrón.

## 6. Pruebas después de los cambios

| Comprobación | Resultado |
|---|---|
| Suite tras el Grupo A+B, PostgreSQL 17 | 844 OK |
| Suite tras el Grupo C, PostgreSQL 17 | 846 OK |
| Tests de concurrencia nuevos, 6 ejecuciones seguidas en PostgreSQL | OK en las 6 |
| Suite al terminar la refactorización, PostgreSQL 17 local / SQLite / contenedor | 848 OK / 848 OK, 17 omitidos / 848 OK |
| **Suite final tras corregir R-1, PostgreSQL 17 local** (`manage.py test --settings=config.settings.test --parallel 1`) | **849 OK, 0 omitidos** (42 s) |
| **Suite final tras corregir R-1, SQLite** | **849 OK, 18 omitidos** (los de concurrencia, 3 de ellos nuevos, y el de `UPPER` no ASCII, que es solo de PostgreSQL) |
| **Suite final tras corregir R-1, dentro del contenedor** (`--profile test run --rm tests`, PostgreSQL 17 de Compose) | **849 OK** (48 s) |
| `manage.py check` | Sin incidencias |
| `makemigrations --check --dry-run` | Sin cambios |
| `spectacular --validate --fail-on-warn` y diff con `docs/api/openapi.yaml` | Válido e idéntico |
| `check --deploy` con las variables ficticias del CI | Solo `security.W021` |
| Pila Compose local: `migrate`, `up --wait`, portada y carta por HTTPS (8443) | Todos los servicios *healthy*; `/` y `/carta/` responden 200 |
| CI de GitHub Actions tras el merge en `main` (los dos trabajos: suite en PostgreSQL con `check --deploy` y OpenAPI; imagen, pila Compose, prueba de humo y copia/restauración) | **En verde** ([ejecución](https://github.com/Jav-VM/CanecaFurada/actions/runs/38776430860), commit `decff8f`) |

`check --deploy` dentro del contenedor de la pila **local** da `security.W004` porque `deploy/dev.env` desactiva HSTS a propósito (el navegador lo recordaría para `localhost`). Con las variables de producción solo queda W021, como en la Fase 12.

**Revisión del diff:** salvo la corrección de R-1 en situaciones de concurrencia (§7.1), no cambian permisos, reglas de negocio, mensajes, contratos de la API, el esquema OpenAPI, las migraciones ni las firmas públicas de los selectores y servicios. Solo desaparecen los dos `_in_period`, que eran privados. No hay secretos, datos personales reales ni registros nuevos en los logs.

## 7. Riesgos y pendientes

- **R-1 (previo a esta tarea): interbloqueo si dos propietarios se retiran mutuamente a la vez. Corregido; ver §7.1.**
- La documentación de la defensa (`docs/defensa_proyecto/`) cita 802 tests (cifra anterior a la Fase 12). Hay que actualizarla al congelar la versión: ahora son 849.
- La pila Compose se probó en local (WSL); el despliegue en el VPS sigue pendiente ([Fase 12 §13](fase-12-despliegue.md#13-acciones-manuales-pendientes-en-el-vps)).

### 7.1. Corrección de R-1 (aprobada por el usuario)

**Problema 1. Interbloqueo:**
- `change_role` y `set_user_active` bloqueaban primero la fila del usuario afectado y después las de todos los propietarios activos.
- Si A desactivaba a B mientras B desactivaba a A, los bloqueos se cruzaban: PostgreSQL abortaba una de las dos operaciones con `OperationalError`, que en la web sería un error 500.
- La invariante se mantenía (siempre quedaba un propietario activo).
- Se reproducía con el código original en 3 de 5 ejecuciones.

**Problema 2, encontrado al corregir el anterior. Actor retirado mientras esperaba:**
- El permiso del actor se comprobaba antes de esperar el bloqueo.
- Con tres propietarios, si A desactivaba a B mientras B intentaba desactivar a C, la operación de B esperaba y, cuando A confirmaba, **se completaba aunque B ya estuviera desactivado**.
- Se reprodujo de forma determinista con el código anterior.

**Corrección:**
- `apps/accounts/services.py`: `_lock_active_owners(actor)` bloquea los propietarios activos **en orden de pk** y comprueba, con los bloqueos tomados, que el actor sigue siendo uno de ellos (si no, `PermissionDenied`). `change_role` y `set_user_active` lo llaman **antes** de bloquear al usuario afectado. Con un único orden de bloqueo, las operaciones simultáneas esperan su turno.
- `apps/accounts/admin.py`: al editar un usuario, la activación o desactivación pasa por el servicio **antes** de guardar el resto de campos. Antes era al revés y bloqueaba en el orden contrario. El estado final y la auditoría son los mismos. Si el servicio rechaza el cambio, la transacción del admin se deshace igual que antes.
- Sin cambios en mensajes, migraciones ni API.

**Cambio de comportamiento, intencionado y limitado a la concurrencia:**
- Quien pierde la carrera recibe el rechazo normal (`PermissionDenied` o la regla del último propietario) en lugar de un error de base de datos.
- Un propietario retirado ya no completa operaciones que tuviera pendientes.
- Coste: cambiar el rol o la activación de **cualquier** usuario bloquea un instante las filas de los propietarios activos (pocas filas, operación poco frecuente) y hace una consulta más.

**Tests** (`tests/accounts/test_concurrency.py`):
- Desactivación mutua y cambio de rol mutuo, 5 rondas cada uno, sin admitir interbloqueos.
- Actor desactivado mientras espera el bloqueo.
- Los tres **fallaban con el código anterior** y pasan con la corrección: 8 ejecuciones seguidas (80 intentos concurrentes) sin ningún interbloqueo.

## 8. Lo que se decidió no refactorizar

| Candidato | Motivo |
|---|---|
| Los 8 `_require_owner` de selectores y servicios | Cada uno tiene un mensaje propio de su dominio. Unificarlos ahorra 2 líneas por módulo y acopla todos los módulos a un mismo helper. |
| Los `_require_customer` de las vistas de eventos, puntos y recompensas | Sustituirlos por `role_required` cambiaría qué se comprueba primero (sesión, rol, email verificado) y, con ello, la respuesta (redirección o 403). |
| El patrón `try/except ValidationError → messages` de las vistas del dashboard | Es explícito y cada acción tiene su propio mensaje de éxito; un helper genérico lo haría menos legible. |
| El resumen del dashboard y `/api/v1/owner/stats/`, que repiten las mismas 5 llamadas | Son dos capas de presentación con formatos distintos; la lógica ya está en los selectores. |
| La comprobación del último propietario en el formulario del admin | Es una validación previa para mostrar el error en el formulario; la regla con autoridad (con bloqueo) está en el servicio. |
| `points_stats` (2 consultas) | Combinar el periodo y el total histórico en un agregado complicaría `_totals()` para ahorrar una sola consulta. |
| Docker, Nginx, scripts de despliegue y CI | Recién probados en la Fase 12; fuera del alcance de una refactorización de código. |

## 9. Siguiente paso

Congelar la versión y actualizar las cifras de `docs/defensa_proyecto/` (849 tests).
