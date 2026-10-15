# Migración de SQLite a PostgreSQL

**Estado:** Completa en desarrollo (PostgreSQL 17.11 local, 2026-10-15). **Pendiente** la instalación en el VPS, que forma parte de la fase de despliegue (§8).

Forma parte de la fase sin número «Endurecimiento y despliegue» del [plan de fases](plan-de-fases.md). Todos los valores de ejemplo son ficticios.

## 1. Objetivo, alcance y exclusiones

**Objetivo:** validar la aplicación sobre PostgreSQL, el motor objetivo desde la Fase 0, antes de la memoria técnica y del despliegue en un VPS Linux. Hasta ahora todas las pruebas se habían ejecutado en SQLite.

**Incluye:** auditoría de compatibilidad, PostgreSQL en desarrollo, esquema generado con las migraciones, suite completa contra PostgreSQL, corrección de los fallos encontrados, comprobación de que producción no puede arrancar con SQLite, prueba de copia y restauración, y documentación.

**Excluye:** servidor WSGI, proxy, systemd, estáticos y multimedia, tareas programadas e instalación en el VPS (fase de despliegue). Tampoco se migran datos (§4).

## 2. Hallazgos de la auditoría y resultado

| # | Hallazgo | Resultado |
|---|---|---|
| H1 | `db.sqlite3.bak` estaba versionado (commit `a85ce95`) y subido al repositorio remoto, que es privado. Contenía cuentas de desarrollo con hashes de contraseña y sesiones. `.gitignore` solo cubría `*.sqlite3`. | Retirado del índice (`git rm --cached`) y `.gitignore` ampliado (`*.sqlite3*`, `*.bak`, `*.dump`). El historial no se ha reescrito porque el repositorio es privado: el archivo sigue en los commits antiguos. |
| H2 | `apps/events/services.py` bloqueaba la reserva con `select_for_update().select_related("event", …)`. `event` admite nulos (reservas de mesa), así que se generaba un `LEFT OUTER JOIN`, y PostgreSQL no admite `FOR UPDATE` en el lado anulable. SQLite ignora `FOR UPDATE`, por eso no se había detectado. | **Confirmado en PostgreSQL** con 15 tests en error: no funcionaba ningún cambio de estado de una reserva. Se corrige con `select_for_update(of=("self",))`; el evento ya se bloqueaba aparte cuando hace falta. |
| H3 | Sin `DATABASE_URL`, `config.settings.prod` heredaba en silencio el SQLite de desarrollo. | `prod.py` lanza `ImproperlyConfigured` si el motor no es PostgreSQL. Se añade un test. |
| H4 | Posibles *deadlocks* entre validar y cancelar canjes con bloqueos reales. | No se reproduce: los 3 tests de concurrencia con hilos (`tests/rewards/test_concurrency.py`) se ejecutan en PostgreSQL y pasan. |
| H5 | Diferencias de collation y del plegado de mayúsculas Unicode (`Lower`, `iexact`, `icontains`). | Ningún test falla. En PostgreSQL `lower()` también pliega letras acentuadas (Á/á), así que las restricciones únicas sin distinguir mayúsculas son más estrictas que en SQLite. |
| — | Un test de restricciones (`tests/loyalty/test_promotions.py`) usaba `"INVENTADO"` (9 caracteres) en un campo de 8. PostgreSQL rechazaba la longitud (`DataError`) antes de llegar a la CHECK. | El test usa `"INVALIDO"` (8 caracteres), así que prueba la CHECK en las dos BD. No era un fallo de la aplicación. |

Otras comprobaciones sin incidencias: todos los `select_for_update` están dentro de `transaction.atomic()`; las capturas de `IntegrityError` usan *savepoints*; los textos se truncan antes de guardarse (`reason[:200]`, `last_error[:100]`); las CHECK con regex usan expresiones POSIX compatibles; solo hay una migración de datos (`accounts/0003`, RunPython portable) y ninguna con `RunSQL`.

## 3. Decisiones

| Decisión | Motivo |
|---|---|
| SQLite se mantiene como alternativa en **desarrollo y tests** cuando no hay `DATABASE_URL`. Producción exige PostgreSQL. | Es el cambio mínimo: quien clone el proyecto puede trabajar sin PostgreSQL. Las pruebas de concurrencia solo son reales con PostgreSQL. |
| No se migran datos de `db.sqlite3`. | Solo había datos de desarrollo (3 cuentas, sin carta, compras ni puntos). La BD de PostgreSQL empieza vacía y el propietario se crea con `create_owner`. |
| BD creada con ICU `es-ES` y UTF8. | Ordenación española independiente del sistema operativo, igual en Windows y en Linux. |
| `CONN_HEALTH_CHECKS` configurable (`DATABASE_CONN_HEALTH_CHECKS`, `False` por defecto). | Con conexiones persistentes (`DATABASE_CONN_MAX_AGE` > 0) en el VPS, evita reutilizar conexiones caídas. |
| `select_for_update(of=("self",))` en lugar de quitar `select_related`. | Mantiene una sola consulta y bloquea solo la fila que se modifica. |

## 4. Procedimiento (esquema y datos)

1. Crear el rol y la BD (§5 o §8).
2. Definir `DATABASE_URL` en el entorno (o en un `.env` local, que no se versiona).
3. `python manage.py migrate --plan` para revisar y después `python manage.py migrate`. El esquema se genera con las migraciones de Django; no se traduce desde SQLite.
4. `python manage.py create_owner`.

**Si alguna vez hubiera que migrar datos** desde SQLite (no es el caso ahora):

```powershell
# Con DATABASE_URL apuntando a SQLite
python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.permission -e sessions -e admin.logentry -e token_blacklist -o <ruta-fuera-del-repo>\datos.json
# Con DATABASE_URL apuntando a PostgreSQL ya migrado
python manage.py loaddata <ruta-fuera-del-repo>\datos.json
python manage.py sqlsequencereset accounts catalog loyalty purchases rewards notifications events core web | python manage.py dbshell
```

El volcado contiene datos personales y hashes de contraseñas: guárdalo fuera del repositorio y bórralo al terminar.

## 5. Configuración en desarrollo (Windows)

1. Instalar PostgreSQL 17 (instalador de EDB o `winget install PostgreSQL.PostgreSQL.17`). La instalación desatendida con winget asigna una contraseña al usuario `postgres` sin preguntarla. Cámbiala nada más instalar con `\password postgres` dentro de `psql`.
2. Recomendado: en `C:\Program Files\PostgreSQL\17\data\postgresql.conf`, `listen_addresses = 'localhost'` (por defecto escucha en todas las interfaces) y reiniciar el servicio `postgresql-x64-17`.
3. En `psql -U postgres -h localhost` (los comandos de `psql` empiezan por `\`; el SQL termina en `;`):

   ```sql
   CREATE ROLE caneca LOGIN CREATEDB;   -- CREATEDB solo en desarrollo: Django crea la BD de test
   \password caneca
   CREATE DATABASE caneca_furada OWNER caneca ENCODING 'UTF8'
     LOCALE_PROVIDER icu ICU_LOCALE 'es-ES' LOCALE 'C' TEMPLATE template0;
   ```

4. En el `.env` local: `DATABASE_URL=postgres://caneca:contrasena-ficticia@localhost:5432/caneca_furada`. Los caracteres especiales de la contraseña se escriben codificados: `@` → `%40`, `:` → `%3A`, `/` → `%2F`, `#` → `%23`.
5. `python manage.py migrate`.

**Tests contra PostgreSQL:** `python manage.py test --settings=config.settings.test`. Con `DATABASE_URL` definida se usa PostgreSQL y Django crea y borra `test_caneca_furada`. La BD de test se copia de `template1`, que en Windows usa la collation de libc (`Spanish_Spain.1252`) y no ICU. No ha afectado a ningún test.

## 6. Variables de entorno

| Variable | Cambio | Valor recomendado |
|---|---|---|
| `DATABASE_URL` | Obligatoria en producción y debe ser PostgreSQL | `postgres://caneca:<contraseña>@localhost:5432/caneca_furada` |
| `DATABASE_CONN_MAX_AGE` | Sin cambios | `0` en desarrollo; `60` en el VPS |
| `DATABASE_CONN_HEALTH_CHECKS` | **Nueva** (por defecto `False`) | `True` si `DATABASE_CONN_MAX_AGE` > 0 |

Ejemplos ficticios en [.env.example](../.env.example).

## 7. Archivos modificados

| Archivo | Cambio |
|---|---|
| `apps/events/services.py` | `_transition`: `select_for_update(of=("self",))` (H2) |
| `config/settings/prod.py` | Rechaza cualquier motor que no sea PostgreSQL (H3) |
| `config/settings/base.py` | `CONN_HEALTH_CHECKS` desde `DATABASE_CONN_HEALTH_CHECKS` |
| `.env.example` | Ejemplo y notas de PostgreSQL, nueva variable |
| `.gitignore` | `*.sqlite3*`, `*.bak`, `*.dump` (H1) |
| `db.sqlite3.bak` | Retirado del repositorio; se conserva solo en local (H1) |
| `tests/core/test_audit_and_settings.py` | Test `test_prod_rejects_sqlite`. Los tests de `prod` fijan un `DATABASE_URL` ficticio para no depender del `.env` local. |
| `tests/loyalty/test_promotions.py` | Valor de `status` inválido que cabe en el campo |
| `docs/migracion-postgresql.md` (este documento), `docs/despliegue.md`, `README.md`, `docs/fase-07-recompensas-canjes.md`, `docs/defensa_proyecto/05_limitaciones_y_pendientes.md` | Documentación |

No hay migraciones nuevas: `makemigrations --check` no detecta cambios.

## 8. VPS Linux (pendiente: fase de despliegue)

1. PostgreSQL 16 o superior (paquete de la distribución o repositorio PGDG) en el mismo servidor. Django 5.2 requiere PostgreSQL 14 o superior.
2. `listen_addresses = 'localhost'`; en `pg_hba.conf` solo conexiones locales con `scram-sha-256`.
3. Rol con privilegios mínimos, sin `CREATEDB` ni `SUPERUSER`:

   ```sql
   CREATE ROLE caneca LOGIN;
   \password caneca
   CREATE DATABASE caneca_furada OWNER caneca ENCODING 'UTF8'
     LOCALE_PROVIDER icu ICU_LOCALE 'es-ES' LOCALE 'C' TEMPLATE template0;
   REVOKE ALL ON DATABASE caneca_furada FROM PUBLIC;
   ```

4. Variables en un `EnvironmentFile` de systemd con permisos `600`, nunca en el repositorio: `DATABASE_URL`, `DATABASE_CONN_MAX_AGE=60`, `DATABASE_CONN_HEALTH_CHECKS=True`. Si la BD estuviera en otro servidor, añade `?sslmode=verify-full`.
5. `python manage.py migrate --settings=config.settings.prod` y `create_owner`.
6. Los tests **no** se ejecutan en producción (el rol no puede crear BD). Se ejecutan en desarrollo o en un entorno de pruebas con la misma versión de PostgreSQL.
7. Copias de seguridad: [despliegue.md §7](despliegue.md#7-copias-de-seguridad-pendiente).

## 9. Pruebas ejecutadas y resultados reales (2026-10-15)

Entorno: Windows 11, Python 3.14.2, Django 5.2.18, psycopg 3.3.6, PostgreSQL 17.11.

| Comando o prueba | Resultado |
|---|---|
| `manage.py check` | Sin incidencias |
| `manage.py migrate --plan` + `migrate` (BD vacía de PostgreSQL) | 56 migraciones aplicadas sin errores |
| `manage.py makemigrations --check --dry-run` | `No changes detected` |
| Suite completa contra PostgreSQL **antes** de las correcciones | 802 tests: **16 errores** (15 de H2 y 1 del test de longitud), 0 omitidos |
| Suite completa contra PostgreSQL **después** (`manage.py test --settings=config.settings.test --parallel 1`) | **803 tests OK, 0 omitidos** (32,1 s); incluye los 3 de concurrencia con hilos |
| Suite completa con SQLite (`DATABASE_URL=sqlite:///…`) | **803 tests OK, 3 omitidos** (los de concurrencia, que necesitan una BD compartida) |
| `check --deploy --settings=config.settings.prod` (valores ficticios, BD PostgreSQL) | Solo avisos esperados: W021 (HSTS *preload* desactivado a propósito) y W009, debido a la clave ficticia de la prueba |
| `check --settings=config.settings.prod` con `DATABASE_URL=sqlite:///…` | Falla con `ImproperlyConfigured` y no crea ningún archivo |
| Esquema en PostgreSQL | 86 CHECK, 38 FK, 35 únicas, 6 índices únicos parciales (las 6 restricciones condicionales de los modelos), 3 únicas con `lower()`, 2 CHECK con regex |
| `pg_dump -Fc` → `pg_restore` en una BD temporal | Restauración idéntica (32 tablas, 191 restricciones, 56 migraciones). BD temporal y volcado eliminados después |

**Prueba de humo por HTTP (2026-10-15):** hecha contra el servidor real y una BD de PostgreSQL temporal, con el flujo registro → verificación → QR → compra → canje → reservas. Detalle: [auditoría previa a la Fase 12, §6.1](auditoria-pre-fase-12.md#61-prueba-de-humo-por-http-sobre-postgresql). **No probado:** el aspecto visual en el navegador, la cámara en dispositivos y la instalación en el VPS.

## 10. Seguridad y privacidad

- Las credenciales solo están en el `.env` local (ignorado por Git) o en el entorno del servidor. Ningún documento ni test contiene contraseñas reales.
- El rol de la aplicación no es superusuario. En producción tampoco tendrá `CREATEDB`.
- Las restricciones de integridad (CHECK, únicas parciales, FK `PROTECT`) se aplican igual en PostgreSQL. Además, PostgreSQL aplica las longitudes de `varchar` y bloquea filas de verdad.
- H1: aunque el repositorio es privado, `db.sqlite3.bak` sigue en el historial de Git. Si el repositorio se hiciera público o se compartiera, habría que reescribir el historial (por ejemplo, con `git filter-repo`) y cambiar las contraseñas de esas cuentas.

## 11. Criterios de aceptación

| Criterio | Estado |
|---|---|
| Esquema generado en PostgreSQL sin errores | **Completo** |
| Suite completa en PostgreSQL, sin omitidos | **Completo** (803 OK) |
| Suite completa en SQLite sin regresiones | **Completo** |
| Producción no arranca sin PostgreSQL | **Completo** (con test) |
| Copia y restauración comprobadas | **Completo** (en desarrollo) |
| Documentación actualizada | **Completo** |
| Prueba de humo en PostgreSQL | **Completa** por HTTP; la revisión visual y la cámara siguen pendientes |
| PostgreSQL en el VPS | **Pendiente** (fase de despliegue) |

## 12. Limitaciones y pendientes

- Instalar y configurar PostgreSQL en el VPS (§8), con copias de seguridad automatizadas y cifradas fuera del servidor.
- En el VPS, la BD de test (si se usa un entorno de pruebas) heredará la collation de `template1`. Para que coincida con ICU `es-ES`, crea el clúster con `--locale-provider=icu --icu-locale=es-ES`.
- ~~`requirements/base.txt` usa rangos de versiones~~: resuelto en la [auditoría previa a la Fase 12](auditoria-pre-fase-12.md) (versiones exactas y `requirements/constraints.txt`).
- `db.sqlite3.bak` sigue en el historial de Git (§10).
