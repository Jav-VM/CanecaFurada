# Auditoría técnica previa a la Fase 12 (despliegue y endurecimiento)

**Estado:** **Completa.** Correcciones aplicadas y verificadas en SQLite y en PostgreSQL 17.11 (§6). Los hallazgos que corresponden a la Fase 12 o que dependen de una decisión siguen abiertos (§2).

Fecha: 2026-10-15. Forma parte de la fase «Endurecimiento y despliegue» del [plan de fases](plan-de-fases.md), que aquí se llama Fase 12. Destino previsto: VPS Linux (Ubuntu LTS) con Docker Compose, PostgreSQL, Redis, Gunicorn y Nginx. Todos los valores de ejemplo son ficticios.

## 1. Objetivo, alcance y exclusiones

**Objetivo:** detectar y corregir, de forma controlada, lo que pueda comprometer la seguridad, la integridad de los datos, las pruebas o el despliegue antes de la Fase 12.

**Incluye:**
- Auditoría completa del código, los tests y la documentación (Fase A).
- Informe priorizado (Fase B).
- Correcciones aprobadas de los bloques «antes de PostgreSQL en el VPS» y «antes de la Fase 12» (Fase C).

**Excluye:**
- Lo que corresponde a la propia Fase 12: Dockerfile y Compose, Nginx, copias de seguridad, timeouts de Gunicorn, healthcheck, CI y programación de tareas.
- Los hallazgos P3.
- Reescribir el historial de Git (P2-6).
- Los derechos del interesado (P2-9), que son una decisión legal.

No se cambian reglas de negocio ni contratos de la API, no hay migraciones nuevas y no se ha tocado `db.sqlite3`.

## 2. Resumen de hallazgos

Escala: **P0** crítico · **P1** importante · **P2** recomendable antes o durante el despliegue · **P3** se puede posponer. **D** = demostrado · **S** = sospecha que hay que confirmar.

No se encontró ningún P0.

| ID | Hallazgo | Tipo | Estado |
|---|---|---|---|
| P1-1 | El login del admin (`/<DJANGO_ADMIN_URL>/login/`) no tenía límite de intentos; el propietario es superusuario | D | **Corregido** |
| P1-2 | Caché local por proceso (`locmem`) admitida en producción: con varios workers, los límites de intentos y el throttling se multiplican y la caché del contenido del local queda desfasada | D | **Corregido** (producción exige una caché compartida) |
| P1-3 | Sin copias de seguridad ni restauración en el VPS | D | Pendiente (Fase 12) |
| P2-1 | `validate_redemption` bloqueaba canje, cliente y recompensa a la vez (`select_for_update` sobre el JOIN), fuera del orden de `_close`: posible interbloqueo | S | **Corregido** (`of=("self",)`), con test verificado en PostgreSQL |
| P2-2 | Solo había tests de concurrencia con hilos para los canjes | D | **Corregido** (compras, ajustes y reservas), verificado en PostgreSQL |
| P2-3 | El SMTP se llama dentro de la petición: bloquea workers y el tiempo de respuesta de la recuperación de contraseña puede revelar si un email existe | D / S | **Riesgo aceptado** (§5); los timeouts quedan para la Fase 12 |
| P2-4 | Dependencias con rangos, sin `gunicorn` ni `redis` | D | **Corregido** |
| P2-5 | `manage.py` usa `config.settings.dev` por defecto (`DEBUG=True`) | D | Pendiente (Fase 12: `DJANGO_SETTINGS_MODULE` en la imagen) |
| P2-6 | `db.sqlite3.bak` sigue en el historial de Git (hashes de cuentas de desarrollo) | D | Pendiente (requiere autorización expresa) |
| P2-7 | Sin monitorización, alertas, healthcheck ni CI | D | Pendiente (Fase 12) |
| P2-8 | `despliegue.md` hablaba de «Gunicorn o Waitress», systemd y un cron con `.venv` | D | **Corregido** (§4) |
| P2-9 | Sin exportación ni supresión de datos personales | D | Pendiente (decisión legal; antes de abrir al público) |
| P3-1 | `is_limited` + `register_attempt` no es atómico | D | Pospuesto |
| P3-2 | `create_owner` sin actor no serializa dos ejecuciones simultáneas del comando (`select_for_update` sobre un conjunto vacío) | D | Pospuesto |
| P3-3 | Orden de bloqueo opuesto entre `save_event` (evento → reservas) y confirmar una reserva (reserva → evento) | S | Pospuesto |
| P3-4 | Si el proceso muere entre el regalo de cumpleaños y su aviso, el aviso no se recupera | S | Pospuesto |
| P3-5 | `clearsessions` no está en las tareas programadas | D | Pendiente (Fase 12) |
| P3-6 | Sin Content-Security-Policy | D | Pospuesto |
| P3-7 | No se eliminan los metadatos EXIF de las imágenes | D | Pospuesto |
| P3-8 | Sin `List-Unsubscribe-Post` (baja en un clic) | D | Pospuesto |
| P3-9 | `ledger.balance()` hace un `SUM` completo en cada escritura | D | Pospuesto |
| P3-10 | La clave de idempotencia de la compra se regenera al volver atrás (D19) | D | Pospuesto |
| P3-11 | Logs INFO en la salida de los tests; código muerto (`CancelReservationForm`, `birthday_window_days`) | D | Pospuesto |

## 3. Decisiones técnicas

| Decisión | Motivo |
|---|---|
| `LoginThrottleMixin` en `apps/accounts/forms.py`, compartido por `ThrottledAuthenticationForm` (web) y `ThrottledAdminAuthenticationForm` (admin, `admin.site.login_form` en `config/urls.py`) | Una sola implementación. Web, admin y API usan los mismos contadores por email e IP (`services.login_throttle_keys`): fallar en uno cuenta para todos. |
| En el admin, un usuario sin acceso (p. ej. un cliente) que acierta la contraseña también cuenta como intento fallido | Es lo que ya hace `AuthenticationForm`: el admin rechaza el login con un `ValidationError`. Evita usar el admin para comprobar contraseñas de clientes. |
| `prod.py` rechaza las cachés `locmem`, `dummy` y `filebased`; acepta Redis y `dbcache` | Las tres primeras no se comparten entre workers ni entre contenedores. Redis es la opción recomendada; `dbcache` queda como alternativa sin servicio extra. |
| `select_for_update(of=("self",))` en `rewards.services._find` | Bloquea solo el canje, como la corrección H2 de las reservas. Validar y cancelar siguen serializados porque las dos operaciones bloquean la fila del canje. |
| Versiones exactas en `requirements/base.txt` y `prod.txt`; las transitivas, en `requirements/constraints.txt` (`-c`) | Builds reproducibles con las versiones con las que pasa la suite. `constraints.txt` solo limita versiones, no instala nada. |
| `gunicorn==25.3.0` y `redis==7.4.1` | Versiones maduras, no las recién publicadas. `pip install --dry-run` resuelve sin conflictos. Gunicorn no funciona en Windows: se probará en la imagen Linux (Fase 12). |
| Helper común `tests/concurrency.py` (`ConcurrencyTestCase`) | Evita duplicar la gestión de hilos en cuatro archivos. El test de canjes existente pasa a usarlo sin cambiar sus aserciones. |
| Recuentos exactos en los tests de concurrencia solo con PostgreSQL (`row_locking()`); en SQLite, solo los invariantes | SQLite rechaza las escrituras simultáneas (`database is locked`) en lugar de esperar. Lo que debe cumplirse en las dos BD es que nunca haya saldo negativo, doble consumo ni aforo superado. |

## 4. Archivos modificados

| Archivo | Cambio |
|---|---|
| `apps/accounts/forms.py` | `LoginThrottleMixin` y `ThrottledAdminAuthenticationForm` (P1-1) |
| `config/urls.py` | `admin.site.login_form = ThrottledAdminAuthenticationForm` (P1-1) |
| `config/settings/prod.py` | Rechaza una caché local (P1-2) |
| `apps/rewards/services.py` | `_find`: `select_for_update(of=("self",))` (P2-1) |
| `requirements/base.txt`, `requirements/prod.txt`, `requirements/constraints.txt` (nuevo) | Versiones fijadas; `gunicorn` y `redis` en producción (P2-4) |
| `tests/accounts/test_auth_views.py` | 5 tests del límite del login del admin |
| `tests/core/test_audit_and_settings.py` | `CACHE_URL` en la configuración mínima de producción; 2 tests de la caché compartida |
| `tests/concurrency.py` (nuevo) | Base común de los tests con hilos |
| `tests/rewards/test_concurrency.py` | Usa la base común; test nuevo de validar y cancelar a la vez (P2-1) |
| `tests/purchases/test_concurrency.py`, `tests/loyalty/test_concurrency.py`, `tests/events/test_concurrency.py` (nuevos) | Doble envío y compras simultáneas; ajustes simultáneos; confirmaciones que superan el aforo y confirmar mientras el cliente cancela (P2-2) |
| `.env.example` | `CACHE_URL` obligatoria en producción |
| `docs/despliegue.md` | Pila objetivo (Docker Compose, Gunicorn, Redis, Nginx), caché obligatoria, riesgo de P2-3 y nota sobre el cron (P2-8) |
| `docs/auditoria-pre-fase-12.md` (este documento), `docs/plan-de-fases.md`, `README.md`, `docs/migracion-postgresql.md`, `docs/defensa_proyecto/_trabajo/resultados_pruebas.md` | Documentación |

Sin migraciones: `makemigrations --check` → `No changes detected`.

## 5. Riesgo aceptado: envío de correo dentro de la petición (P2-3)

**Decisión del usuario (2026-10-15): se acepta y se documenta.** El diseño del envío no cambia.

- **Qué pasa.** Los emails de cuentas (verificación, cambio de email, recuperación, aviso de cuenta existente) y los avisos de reservas se envían por SMTP en el mismo proceso que atiende la petición. En la recuperación de contraseña, el SMTP solo se llama si la cuenta existe. Si el proveedor tarda, la respuesta tarda más y un atacante podría deducir midiendo tiempos qué emails están registrados. El mensaje es idéntico en los dos casos; solo cambia el tiempo.
- **Mitigaciones actuales.** Límite de 20 solicitudes por IP y hora en la web y en la API, `API_THROTTLE_AUTH` (10/min) y un timeout de SMTP de 10 s.
- **Para la Fase 12:**
  - `--timeout` de Gunicorn por encima de `EMAIL_TIMEOUT`;
  - suficientes workers para que un SMTP lento no bloquee la web;
  - un proveedor SMTP con baja latencia.
- **Si se quisiera cerrar del todo:** enviar los emails de cuentas en segundo plano, con un hilo o una cola. Es un cambio de diseño y no se ha hecho.

## 6. Pruebas ejecutadas y resultados reales (2026-10-15)

Entorno: Windows 11, Python 3.14.2, Django 5.2.18.

| Comando | Resultado |
|---|---|
| Antes de los cambios: `manage.py test --settings=config.settings.test` (SQLite en memoria) | 803 tests OK, 3 omitidos |
| `manage.py check` / `makemigrations --check --dry-run` | Sin incidencias / `No changes detected` |
| `check --deploy --settings=config.settings.prod` (valores ficticios) | Solo `security.W021` (HSTS preload, desactivado a propósito) |
| `spectacular --validate` + `diff` con `docs/api/openapi.yaml` | Válido e idéntico (la API no cambia) |
| `pip install --dry-run -r requirements/prod.txt` y `-r requirements/dev.txt` | Se resuelven sin conflictos (producción añadiría `gunicorn`, `redis` y `packaging`) |
| Después de los cambios: suite completa con SQLite en memoria | **817 tests OK, 10 omitidos** (los de concurrencia) |
| Tests de concurrencia con SQLite **en fichero** (settings temporal fuera del repositorio), 3 ejecuciones seguidas | **10 OK** en las tres |
| Primer intento con **PostgreSQL** | No se pudo conectar: la contraseña del `.env` no coincidía con la del rol `caneca`. El usuario la corrigió. |
| `manage.py test --settings=config.settings.test --parallel 1` con **PostgreSQL 17.11** (psycopg 3.3.6) | **817 tests OK, 0 omitidos** (36,4 s) |
| Los 10 tests de concurrencia en PostgreSQL, **5 ejecuciones seguidas** | **10 OK** en las cinco: recuentos exactos y sin interbloqueos |

Con SQLite en fichero, la prueba demuestra que no hay saldo negativo, doble consumo ni aforo superado, pero no ejercita los bloqueos de fila. En PostgreSQL sí: las operaciones esperan su turno y se cumplen los recuentos exactos. Para repetirlo:

```powershell
python manage.py test --settings=config.settings.test --parallel 1
```

### 6.1 Prueba de humo por HTTP sobre PostgreSQL

**Qué se hizo:**
- Servidor real (`runserver`, settings de desarrollo, correo por consola) contra una BD de PostgreSQL **temporal** (`caneca_smoke`), creada con `migrate` y **eliminada al terminar**. No se tocaron `caneca_furada` ni `db.sqlite3`.
- Recorrido con un script HTTP que se comporta como un navegador (cookies, CSRF, formularios), con una sesión por persona: cliente, propietaria y empleado. El script queda fuera del repositorio.
- Todos los datos son ficticios (`@example.com`). La recompensa de prueba se creó con `rewards.services.save_reward`, el servicio que usa el admin.

**Resultado: 39 de 39 comprobaciones funcionales OK.**

| Área | Qué se comprobó |
|---|---|
| Web pública | Las 6 páginas y los estáticos responden 200; 404 con página propia; `/dashboard/` sin sesión lleva al login |
| Registro | Alta de cliente, email de verificación enviado y confirmado con el enlace (GET + POST) |
| Cliente | Login y QR personal en SVG generado en el servidor |
| Propietaria y empleado | Login de la propietaria, dashboard, alta de un empleado desde el dashboard y login del empleado |
| Compras | Un cliente recibe 403 en el panel del personal; identificación por QR («Lúa F.»); compra de 30,00 € registrada; el **doble envío** del mismo formulario no la duplica; detalle de la compra |
| Puntos y canje | Saldo de 30; canje de 20; código visible; saldo de 10; consulta y validación por el empleado; el **segundo uso** del código se rechaza |
| Reservas | Reserva de mesa solicitada, confirmada desde el dashboard y vista como «Confirmada» por el cliente; sin sesión no se accede |
| Otros | Login del admin disponible y cierre de sesión |

**Log del servidor:**
- 0 respuestas 500. Las únicas trazas son el 403 provocado a propósito, que Django registra con traza en desarrollo.
- No aparecen el token del QR, el código de canje ni emails en las líneas de log de la aplicación.
- El enlace de verificación solo aparece porque, en desarrollo, el backend de correo es la consola. Producción rechaza ese backend.

**No cubierto:**
- Aspecto visual y diseño responsive.
- Cámara y lector de QR en dispositivos reales (JavaScript).
- SMTP real.
- Gunicorn, Nginx y HTTPS (Fase 12).

## 7. Seguridad y privacidad

- El límite del admin protege la cuenta con más privilegios. Los contadores siguen guardándose como hash (`apps.core.throttling`), sin emails ni IPs en claro.
- Sin una caché compartida, producción no arranca. Así se evita desplegar con límites por proceso sin darse cuenta.
- No se han añadido secretos ni datos personales. Los tests usan emails `@example.com` y URLs ficticias, y la comprobación de la `DATABASE_URL` local no mostró la contraseña.

## 8. Criterios de aceptación

| Criterio | Estado |
|---|---|
| Informe priorizado con evidencia, impacto, solución y verificación | **Completo** |
| Login del admin limitado, con tests | **Completo** |
| Producción rechaza una caché local, con tests | **Completo** |
| Bloqueo de `_find` limitado al canje, con test de concurrencia | **Completo** (verificado en PostgreSQL) |
| Tests de concurrencia para compras, ajustes y reservas | **Completo** (verificado en PostgreSQL) |
| Dependencias fijadas, con `gunicorn` y `redis` | **Completo** (instalación real en Linux: Fase 12) |
| Documentación de despliegue alineada con Docker Compose | **Completo** (la guía detallada es parte de la Fase 12) |
| Suite completa en PostgreSQL, 0 omitidos | **Completo** (817 OK) |

## 9. Lista de comprobación antes de ejecutar la Fase 12

- [x] Suite completa en PostgreSQL con 0 omitidos, incluidos los 10 tests de concurrencia (817 OK).
- [x] `check --deploy` en producción sin errores (W021 aceptado).
- [x] `makemigrations --check` sin cambios.
- [x] Login del admin limitado (con test).
- [x] Producción no arranca con caché local (con test).
- [x] Dependencias fijadas (`pip install` real en la imagen Linux: Fase 12).
- [x] Esquema OpenAPI idéntico a `docs/api/openapi.yaml`.
- [ ] `.dockerignore` que excluya `.env`, `*.sqlite3*`, `media/`, `.venv/` y `.tools/` (Fase 12).
- [x] Decidido P2-3 (riesgo aceptado, §5).
- [x] Prueba de humo por HTTP sobre PostgreSQL (§6.1). Falta la revisión visual y de la cámara en dispositivos.

## 10. Dependencias para la Fase 12

- Redis en Compose y `CACHE_URL=redis://redis:6379/1`.
- `DJANGO_SETTINGS_MODULE=config.settings.prod` en la imagen (P2-5).
- Gunicorn con timeout mayor que `EMAIL_TIMEOUT` (P2-3).
- Nginx con `limit_req` en el login (web y admin) como segunda capa.
- Copias de seguridad y restauración probadas (P1-3).
- Healthcheck, alertas y CI (P2-7).
- Tareas programadas, incluido `clearsessions` (P3-5).
