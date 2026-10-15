# Fase 12 — Despliegue y endurecimiento

**Estado:** **Completa en local y en el repositorio.** La pila completa se ha construido, desplegado, copiado y restaurado en un Docker local (WSL Ubuntu 26.04). El CI pasa **en verde en GitHub** (2026-10-15, [ejecución](https://github.com/Jav-VM/CanecaFurada/actions/runs/38737894875), commit `0589cfb`). **Pendientes:** las acciones manuales en el VPS (§13).

Fecha: 2026-10-15. Antes figuraba en el [plan de fases](plan-de-fases.md) como «Sin número — Endurecimiento y despliegue». Parte del estado que dejaron la [migración a PostgreSQL](migracion-postgresql.md) y la [auditoría previa](auditoria-pre-fase-12.md). El procedimiento operativo está en [despliegue.md](despliegue.md). Todos los valores de ejemplo son ficticios.

## 1. Objetivo, alcance y exclusiones

**Objetivo:** que la plataforma se pueda desplegar y mantener en un VPS con garantías:
- imagen reproducible;
- HTTPS;
- caché compartida;
- tareas programadas;
- copias cifradas fuera del servidor con la restauración probada;
- CI con PostgreSQL real.

**Decisiones del usuario:**
- 2026-10-14: VPS Ubuntu LTS, Docker + Compose, multimedia en el disco del servidor servida por Nginx, y CI en GitHub Actions con PostgreSQL.
- 2026-10-15: **PostgreSQL 17** (la versión validada; el planteamiento decía 16), **Python 3.14** (la versión con la que se fijaron las dependencias; el planteamiento decía 3.12/3.13), copias con **restic** y verificación local con **Docker Engine en WSL**.

**Exclusiones:** app móvil, push, proveedor de SMS, Kubernetes o varias máquinas, almacenamiento de objetos, CDN y monitorización avanzada (§14). No hay cambios funcionales ni migraciones nuevas.

**Precondición verificada (2026-10-15):** la migración a PostgreSQL estaba completa. La suite se volvió a ejecutar contra PostgreSQL 17.11 antes de empezar: **817 OK, 0 omitidos**. No se repitió la migración.

## 2. Arquitectura

```text
Internet ─80/443─► nginx  (TLS Let's Encrypt, /static con hash, /media solo imágenes, límites de login)
                     │ red egress
                     ▼
                   web    Gunicorn + Django (config.settings.prod), usuario no root, FS de solo lectura
                     │ red backend (internal: sin salida a Internet)
                     ├─► db     PostgreSQL 17 (ICU es-ES), volumen pgdata, sin puertos publicados
                     └─► redis  caché compartida, sin persistencia, sin puertos publicados
                   scheduler  supercronic con las tareas programadas (misma imagen y variables que web)
                   certbot    renovación de certificados cada 12 h
                   migrate · backup · restore-media   bajo demanda (perfiles de Compose)
```

| Pieza | Fichero |
|---|---|
| Imagen de la app (`--target app`) y de Nginx con los estáticos de la misma versión (`--target nginx`) | `Dockerfile`, `.dockerignore` |
| Gunicorn | `deploy/gunicorn.conf.py` |
| Producción | `compose.yaml` |
| Pila local con Mailpit y servicio de tests | `compose.dev.yaml`, `deploy/dev.env`, `deploy/dev-backup.env` |
| Nginx | `deploy/nginx/templates/*.template`, `deploy/nginx/caneca-certs.sh`, `deploy/nginx/40-caneca-certs.sh` |
| Rol de la BD con privilegios mínimos | `deploy/postgres/10-app-role.sh` |
| Tareas programadas | `deploy/cron/crontab` |
| Despliegue, copia y restauración | `deploy/scripts/{deploy,backup,restore}.sh`, `deploy/scripts/_common.sh` |
| CI | `.github/workflows/ci.yml` |
| Variables (plantillas sin secretos) | `.env.prod.example`, `.env.backup.example` |

## 3. Decisiones técnicas

| Decisión | Motivo |
|---|---|
| Healthcheck como middleware (`apps.core.middleware.HealthCheckMiddleware`), el primero de `MIDDLEWARE` | El healthcheck interno llama a `http://127.0.0.1:8000/healthz`. Como vista, lo rechazarían `ALLOWED_HOSTS` (400) y la redirección a HTTPS (301). Solo responde `ok`/`error` tras un `SELECT 1`, con `no-store`. Nginx devuelve 404 en `/healthz`. |
| `ManifestStaticFilesStorage` en `prod` | Nginx sirve `/static` con `Cache-Control: immutable` de un año. Los nombres llevan el hash del contenido, así que un despliegue nunca sirve CSS o JS antiguos. `collectstatic` en el build falla si falta un fichero referenciado. |
| Estáticos dentro de la imagen de Nginx, sin volumen `static` (el planteamiento preveía uno) | Cada versión lleva sus propios estáticos y el rollback los recupera. Con un volumen compartido, una versión nueva dejaría restos o el rollback serviría estáticos que no le corresponden. |
| Rol `caneca` sin privilegios (`10-app-role.sh`); superusuario `postgres` solo para copias y administración | La imagen oficial convierte `POSTGRES_USER` en superusuario. Así se cumple el mínimo privilegio de [migracion-postgresql.md §8](migracion-postgresql.md). La app no recibe la contraseña del superusuario: `compose.yaml` la vacía en sus contenedores. |
| `DATABASE_URL`, `CACHE_URL`, `DJANGO_BEHIND_TLS_PROXY=True` y `DJANGO_TRUSTED_PROXY_COUNT=1` fijados en `compose.yaml` | Dependen de la topología, no de la persona que despliega. Nginx es el único proxy y **sustituye** `X-Forwarded-For` por la IP real, sin conservar lo que mande el cliente. |
| Contraseñas de PostgreSQL en hexadecimal (`openssl rand -hex 32`) | Van dentro de `DATABASE_URL`; así no hace falta codificar caracteres especiales. |
| Red `backend` con `internal: true` para db y redis | Sin salida a Internet ni puertos publicados. Docker se salta UFW al publicar puertos; aquí solo Nginx publica (80/443). |
| `read_only: true`, `cap_drop: ALL` y `no-new-privileges` en web, scheduler y migrate | Una ejecución de código arbitrario no podría modificar el código ni escalar privilegios. Solo se puede escribir en `/tmp` (tmpfs) y `/app/media`. |
| Gunicorn: 3 workers síncronos, `timeout` 30 > `EMAIL_TIMEOUT` 10, sin access log, `control_socket_disable` | Riesgo aceptado P2-3: un SMTP lento falla por su timeout y no mata al worker. Nginx ya registra los accesos. El socket de control de Gunicorn 25 intentaba escribir en un `$HOME` de solo lectura (encontrado al probar). |
| `pull_policy: never` en las imágenes propias | `compose up` nunca reconstruye ni descarga `caneca-furada` (Docker Hub podría tener una imagen ajena con ese nombre). Solo `deploy.sh` construye. Con `pull_policy: build`, un rollback habría reconstruido la versión nueva. |
| Etiquetas `:<commit>`, `:current` y `:previous` | Rollback en segundos sin reconstruir (§8.3). |
| supercronic v0.2.48 (SHA1 verificado en el build) | Corre sin root, envía la salida a stdout y no solapa ejecuciones de la misma tarea. Usa la misma imagen y las mismas variables que web. |
| restic en contenedor (`restic/restic:0.18.1`) | Cifrado, deduplicación, retención y destinos S3, B2 o rest-server con una sola herramienta. El volcado pasa por la entrada estándar: **nunca queda sin cifrar en el disco del servidor** fuera del contenedor de PostgreSQL. Tiene sus propias variables (`.env.backup`), que la app no recibe. |
| `pg_dump -Fc` como superusuario y `pg_restore --no-owner --role=caneca` | Copia completa; la restauración deja las tablas a nombre del rol de la app. |
| Nginx: `upstream … resolve` con el DNS de Docker | **Encontrado al probar la restauración:** al recrear `web` cambia su IP y Nginx seguía usando la antigua (502). |
| Nginx: se quita el `access_log` del `nginx.conf` base | **Encontrado al probar:** registraba cada petición dos veces, una en el formato `main`, con la cadena de consulta y el Referer. |
| Logs de Nginx con `[token]` en las rutas `/cuenta/verificar-email/…`, `/cuenta/contrasena/restablecer/…` y `/comunicaciones/baja/…` | Esas URL llevan un token de un solo uso. Tampoco se registran cabeceras, cuerpos, cadena de consulta ni Referer. |
| `limit_req` de Nginx (30/min por IP, ráfaga 20) en login, registro, recuperación y reenvíos de la web, el admin y la API | Segunda capa por delante de Django (auditoría §10). Es más holgado que Django porque los clientes comparten la wifi del local. |
| Hosts desconocidos: 444 (cierre sin respuesta) y `ssl_reject_handshake` | Evita servir la web con un `Host` falso y responder a escaneos por IP. |
| `.gitattributes` con LF en scripts, Dockerfile y Compose | Con `core.autocrlf=true` (este equipo), un clon de Windows convertiría los scripts a CRLF y fallarían en el contenedor. |
| `compose.dev.yaml` como capa encima de `compose.yaml` y no como fichero independiente | La prueba local ejercita la misma definición que producción. Solo cambian los puertos (`127.0.0.1`), el certificado (autofirmado), certbot (desactivado) y Mailpit. |

## 4. Configuración de producción (`config/settings/prod.py`)

Cambios mínimos:
- `STORAGES`: `ManifestStaticFilesStorage` para los estáticos y `FileSystemStorage` para `media/`.
- `MIDDLEWARE[0]` es `HealthCheckMiddleware` (en `base.py`, para todos los entornos).

Se mantiene lo que ya había:
- `prod` no arranca si falta la clave (o mide menos de 32 bytes), `ALLOWED_HOSTS`, PostgreSQL, una caché compartida, un SMTP real o un `SITE_BASE_URL` https;
- HSTS de 1 año sin *preload* (W021 aceptado);
- cookies `Secure`.

Revisado: `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` y `SITE_BASE_URL` llevan el mismo dominio que `NGINX_SERVER_NAME`, y `SECURE_PROXY_SSL_HEADER` solo se activa con `DJANGO_BEHIND_TLS_PROXY` (test).

## 5. Variables de entorno

Plantillas con valores ficticios: [.env.prod.example](../.env.prod.example) y [.env.backup.example](../.env.backup.example). En el VPS se copian a `.env.prod` y `.env.backup` con permisos `600`; nunca se versionan (`.gitignore`) ni entran en la imagen (`.dockerignore`).

| Variable | Nueva | Uso |
|---|---|---|
| `NGINX_SERVER_NAME` | Sí | Dominio(s) de Nginx; el primero da nombre al certificado |
| `POSTGRES_SUPERUSER`, `POSTGRES_SUPERUSER_PASSWORD` | Sí | Superusuario del contenedor db (copias y administración) |
| `APP_DB_NAME`, `APP_DB_USER`, `APP_DB_PASSWORD` | Sí | Rol y BD de la app; con ellas `compose.yaml` construye `DATABASE_URL` |
| `GUNICORN_WORKERS`, `GUNICORN_TIMEOUT`, `GUNICORN_LOG_LEVEL` | Sí (opcionales) | 3 / 30 / info |
| `CANECA_ENV_FILE`, `CANECA_BACKUP_ENV_FILE`, `COMPOSE_FILES`, `IMAGE_TAG`, `CANECA_IMAGE` | Sí (opcionales) | Ficheros y etiquetas de los scripts; los valores por defecto sirven en el VPS |
| `RESTIC_REPOSITORY`, `RESTIC_PASSWORD` y las credenciales del destino | Sí (`.env.backup`) | Copias |
| `BACKUP_KEEP_DAILY`, `BACKUP_KEEP_WEEKLY` | Sí (opcionales) | Retención: 7 y 4 |
| `DATABASE_URL`, `CACHE_URL`, `DJANGO_BEHIND_TLS_PROXY`, `DJANGO_TRUSTED_PROXY_COUNT` | Cambio | Ya no se escriben a mano: los fija `compose.yaml` |

El resto, igual que en [despliegue.md §2](despliegue.md#2-variables-de-entorno).

## 6. Tareas programadas

`deploy/cron/crontab`, ejecutado por supercronic en el servicio `scheduler` con `TZ=Europe/Madrid`:

| Tarea | Cuándo |
|---|---|
| `process_notifications` | Cada 5 min |
| `run_birthday_promotions` y después `process_notifications` | 09:00 |
| `expire_redemptions` | 04:30 |
| `purge_email_tokens`, `flushexpiredtokens` y `clearsessions` | 04:45. **`clearsessions` es nueva** (P3-5) |

supercronic no lanza una tarea si la anterior sigue en marcha. La protección contra dobles envíos ya estaba en los propios comandos (claves `dedup_key`, estado «enviando» con caducidad). Las órdenes registran recuentos y `public_id`, no datos personales.

Las copias **no** van en el scheduler: el contenedor de la app no tiene acceso a Docker ni al superusuario. Se programan en el host (§8.4).

## 7. Copias de seguridad

- **Qué se copia:**
  - la BD, con `pg_dump -Fc`, comprobada con `pg_restore --list` antes de subirla;
  - `media/`.

  Son dos *snapshots* de restic por ejecución, con las etiquetas `db` y `media` y el host fijo `caneca`.
- **Cifrado y destino:**
  - restic cifra en el cliente (AES-256);
  - el destino es externo y configurable: S3 compatible, B2 o rest-server;
  - el repositorio se crea con `backup.sh init`.
- **Retención:** `restic forget --keep-daily 7 --keep-weekly 4 --prune`, configurable.
- **Datos personales:** la BD contiene datos personales, hashes de contraseñas y los refresh tokens de la app (`token_blacklist_outstandingtoken`). Las copias necesitan la misma protección que la BD:
  - `RESTIC_PASSWORD` se guarda fuera del servidor;
  - la clave del destino solo puede escribir en ese bucket;
  - se recomienda el bloqueo de objetos si el proveedor lo ofrece.

  Cuando se implemente la supresión de cuentas (P2-9), las copias seguirán conteniendo los datos hasta que caduquen según la retención. Hay que documentarlo en la política de privacidad.
- **Restauración:**
  - `restore.sh check`: prueba sin tocar nada;
  - `restore.sh full --yes`: sustituye los datos.

  Ver §8.5.

## 8. Procedimientos

Todos se ejecutan en el VPS como el usuario de despliegue (grupo `docker`), desde el clon del repositorio. En lo sucesivo, `dc` es una abreviatura:

```bash
alias dc='docker compose --env-file .env.prod'
```

### 8.1 Primer despliegue

1. Preparar el servidor (§12) y apuntar el DNS (registros A/AAAA) del dominio al VPS.
2. `git clone` del repositorio. Después:
   ```bash
   cp .env.prod.example .env.prod
   cp .env.backup.example .env.backup
   chmod 600 .env.prod .env.backup
   ```
   Rellena los valores reales (§5).
3. `deploy/scripts/deploy.sh --first`. Construye las imágenes, levanta db y redis, aplica `migrate` una sola vez y arranca web, scheduler, nginx y certbot. Nginx arranca con un certificado autofirmado provisional.
4. **Certificado de Let's Encrypt** (una vez):
   ```bash
   dc run --rm --entrypoint certbot certbot certonly --webroot -w /var/www/certbot \
      -d www.example.com --email admin@example.com --agree-tos --no-eff-email
   dc exec nginx caneca-certs reload
   ```
   Después lo renueva el servicio `certbot` cada 12 h y Nginx lo recarga cada 6 h.
5. **Primer propietario.** Las variables solo existen durante el comando; no se escriben en `.env.prod` ni quedan en el historial de la shell gracias al espacio inicial (con `HISTCONTROL=ignorespace`):
   ```bash
    read -rs CANECA_OWNER_PASSWORD; export CANECA_OWNER_PASSWORD
    dc run --rm -e CANECA_OWNER_EMAIL=propietaria@example.com -e CANECA_OWNER_FIRST_NAME=Nombre \
       -e CANECA_OWNER_LAST_NAME=Apellidos -e CANECA_OWNER_PASSWORD web python manage.py create_owner --noinput
    unset CANECA_OWNER_PASSWORD
   ```
6. **Copias:** `deploy/scripts/backup.sh init`, una primera `backup.sh run` y la programación diaria (§8.4).
7. **Comprobaciones:**
   - `dc exec web python manage.py check --deploy`: solo W021;
   - registro de prueba con un email propio, para confirmar que el SMTP real entrega (§11);
   - `restore.sh check`.

### 8.2 Actualización de versión (con migraciones)

```bash
git pull --ff-only
deploy/scripts/deploy.sh
```

Pasos del script:
1. Copia de seguridad (`backup.sh run`). Si falla, no se despliega.
2. Build de `caneca-furada:<commit>`.
3. `migrate` en un único contenedor. Nunca hay dos a la vez.
4. Etiqueta la versión en marcha como `:previous` y la nueva como `:current`.
5. `up -d --wait` de web, scheduler y nginx, que esperan a estar sanos.

Durante unos segundos el web antiguo convive con el esquema nuevo. Por eso las migraciones deben ser **compatibles hacia atrás**: añadir antes que quitar, y quitar columnas en una versión posterior. Es la práctica que ya siguen las migraciones del proyecto: pequeñas y revisadas.

### 8.3 Rollback

```bash
deploy/scripts/deploy.sh rollback
```

Vuelve a poner `:previous` como `:current` y reinicia web, scheduler y nginx (con sus estáticos) sin reconstruir nada. La versión retirada queda como `:rolled-back`. **Las migraciones no se deshacen:**
- si la versión nueva no tenía migraciones, o son compatibles hacia atrás, el rollback basta;
- si no, hay que restaurar la copia tomada antes del despliegue (§8.5) **y** volver al código anterior (`git checkout <commit>` + `deploy.sh`). Se pierde lo escrito después de la copia.

Para volver atrás el código fuente: `git checkout <commit-anterior>`. El commit de cada imagen está en su etiqueta (`docker image ls caneca-furada`).

### 8.4 Copias programadas (host)

Con un temporizador de systemd o el cron del usuario de despliegue. Ejemplo de cron con el log fuera del repositorio:

```cron
15 3 * * * cd /srv/caneca && deploy/scripts/backup.sh run >> /var/log/caneca-backup.log 2>&1
30 3 * * 0 cd /srv/caneca && deploy/scripts/restore.sh check >> /var/log/caneca-backup.log 2>&1
```

El segundo hace una **prueba de restauración semanal** en una BD temporal. Si cualquiera de los dos falla, el script sale con error. Conviene que ese error llegue a alguien: §14.

### 8.5 Restauración desde copia

- **Prueba, sin tocar nada:** `deploy/scripts/restore.sh check`. Restaura la última copia en `caneca_restore_check`, compara recuentos con la BD en uso y la borra.
- **Real:**
  1. Lista las copias con `deploy/scripts/backup.sh check`.
  2. Ejecuta `DB_SNAPSHOT=<id> MEDIA_SNAPSHOT=<id> deploy/scripts/restore.sh full --yes`. Por defecto restaura la última.

  El script:
  1. para web y scheduler (Nginx devuelve 502 mientras tanto);
  2. vuelve a crear la BD con ICU `es-ES` y restaura el volcado en una sola transacción;
  3. sustituye `media/`;
  4. aplica `migrate`;
  5. vuelve a levantar los servicios.
- **Servidor nuevo:** primer despliegue (§8.1, pasos 1-3) con el mismo `.env.backup` y, después, `restore.sh full --yes`. **Sin `RESTIC_PASSWORD` no hay restauración posible.**

### 8.6 Rotación de secretos

En todos los casos: edita `.env.prod` y ejecuta `dc up -d web scheduler`.

| Secreto | Cómo | Efecto |
|---|---|---|
| `DJANGO_SECRET_KEY` | Valor nuevo y reinicio | Cierra las **sesiones web**. Invalida los **enlaces de recuperación de contraseña** y de **baja de comunicaciones** pendientes. Si no hay `API_JWT_SIGNING_KEY`, invalida además **todos los tokens de la app**: los usuarios tienen que volver a entrar. Los enlaces de verificación de email **siguen valiendo**: son tokens aleatorios guardados en la BD, no firmados. Django 5.2 admite `SECRET_KEY_FALLBACKS` para una transición sin cortes; no está configurado. |
| `API_JWT_SIGNING_KEY` | Valor nuevo (≥ 32 bytes) | Invalida todos los access y refresh de la app. La web no se ve afectada. |
| `APP_DB_PASSWORD` | `dc exec db psql -U postgres -c "ALTER ROLE caneca PASSWORD '<nueva>'"`, después actualizar `.env.prod` y reiniciar web y scheduler | Corte de segundos |
| `POSTGRES_SUPERUSER_PASSWORD` | `ALTER ROLE postgres PASSWORD …` y actualizar `.env.prod` | Ninguno para la app |
| `EMAIL_HOST_PASSWORD` | En el proveedor, después en `.env.prod` | Ninguno |
| `RESTIC_PASSWORD` | `restic key add`, comprobar, `restic key remove <antigua>` | Ninguno. **Guarda la nueva fuera del servidor antes de borrar la antigua.** |

## 9. Problemas encontrados en PostgreSQL y cómo se resolvieron

La suite ya pasaba en PostgreSQL desde la migración. En esta fase se añadieron las pruebas que faltaban; **ninguna ha revelado un fallo de la aplicación**.

| Prueba | Resultado |
|---|---|
| Agrupación geográfica con `UPPER` y letras no ASCII (Fase 9): «A CORUÑA» y «a coruña» | En PostgreSQL con ICU se agrupan en una sola zona (test nuevo, solo en PostgreSQL). En SQLite seguirían separadas: es la limitación ya documentada de la Fase 9 y solo afecta al desarrollo. |
| Rotación simultánea del mismo refresh (4 hilos) | Solo un hilo obtiene un par nuevo. El refresh usado queda revocado una vez y solo hay un token vigente. El `select_for_update` de `rotate_refresh_token` funciona. |
| Solicitudes de reserva simultáneas: misma clave de idempotencia, tope de 3 activas y mismo evento | Una sola reserva por clave; exactamente 3 de 4 con el tope; una sola por evento. Lo garantizan el bloqueo del cliente y las restricciones únicas. |
| Los 14 tests de concurrencia (10 previos + 4 nuevos), 5 ejecuciones seguidas en PostgreSQL | Sin interbloqueos ni recuentos inexactos (§10) |

Los problemas encontrados en esta fase fueron de infraestructura y están corregidos (§3):
- Nginx con la IP antigua de `web`;
- el log duplicado de Nginx;
- el socket de control de Gunicorn;
- el `pull_policy` que anulaba el rollback;
- la contraseña del superusuario visible para la app;
- el `Host` desconocido con un SNI válido.

## 10. Pruebas ejecutadas y resultados reales (2026-10-15)

Entornos:
- **Windows 11:** Python 3.14.2, PostgreSQL 17.11 local.
- **WSL Ubuntu 26.04:** Docker Engine 29.1.3, Compose 2.40.3. Imagen con Python 3.14.8 y `postgres:17-trixie`.

| Comando o prueba | Resultado |
|---|---|
| Suite completa, SQLite en memoria (`DATABASE_URL=sqlite://:memory:`) | **833 OK, 15 omitidos**: los 14 de concurrencia, que necesitan una BD compartida, y el de `UPPER` no ASCII, solo para PostgreSQL (19,6 s) |
| Suite completa, PostgreSQL 17.11 local (`manage.py test --settings=config.settings.test --parallel 1`) | **833 OK, 0 omitidos** (40,5 s) |
| Suite completa **dentro del contenedor** contra el PostgreSQL 17 de Compose con ICU (`--profile test run --rm tests`) | **833 OK, 0 omitidos** (46,9 s) |
| Tests de concurrencia (14), 5 ejecuciones seguidas en PostgreSQL | **14 OK en las 5 ejecuciones** |
| `manage.py check` / `makemigrations --check --dry-run` | Sin incidencias / `No changes detected` (también dentro del contenedor) |
| `spectacular --validate --fail-on-warn` + comparación con `docs/api/openapi.yaml` | Válido e idéntico |
| `check --deploy` dentro del contenedor con HSTS de producción | Solo `security.W021` |
| `collectstatic` con `ManifestStaticFilesStorage` | 172 ficheros, 172 procesados con hash |
| Build de la imagen | OK. Imagen de 450 MB, usuario `app` (uid 10001), `DJANGO_SETTINGS_MODULE=config.settings.prod`, sin `.env`, `*.sqlite3*`, `*.bak` ni secretos en el entorno |
| `docker compose config` (producción y local) | Válidos |
| Inicialización de la BD | Rol `caneca` sin atributos (ni superusuario ni `CREATEDB`); BD con ICU `es-ES` |
| Prueba de humo por HTTPS a través de Nginx (script fuera del repositorio, datos `@example.com`) | **25/25 OK.** Cubre:<ul><li>redirección 80→443 y cabeceras de seguridad;</li><li>CSS con hash e `immutable`;</li><li>`/healthz` y `/media/*.php` dan 404, y no hay listado;</li><li>hosts desconocidos cerrados;</li><li>registro por la API con el email recibido en Mailpit y un enlace `https`;</li><li>verificación, login, `/me`, rotación del refresh y rechazo del reutilizado;</li><li>cookie CSRF `Secure`;</li><li>`limit_req` devuelve 429.</li></ul> |
| Logs de Nginx | Una línea por petición, sin cadena de consulta y con `/cuenta/verificar-email/[token]/` |
| Procedimientos completos sobre la pila local (desde volúmenes vacíos) | Ver la tabla siguiente |
| CI de GitHub Actions: suite en PostgreSQL 17 sin omitidos, `check --deploy`, OpenAPI, build, pila Compose, prueba de humo y copia/restauración | **en verde en GitHub** (2026-10-15, [ejecución](https://github.com/Jav-VM/CanecaFurada/actions/runs/38737894875), commit `0589cfb`). La primera ejecución falló antes de empezar por un error de sintaxis YAML del workflow (`--only-binary=:all:` sin comillas), corregido en `0589cfb` |
| Scheduler | `process_notifications` lanzado por supercronic a las 14:40:00 (Europe/Madrid): «job succeeded». El log solo contiene recuentos. |

Detalle de los procedimientos sobre la pila local:

| Paso | Resultado |
|---|---|
| `deploy.sh --first` | OK |
| `create_owner` con variables solo durante el comando | Propietario creado |
| Imagen ficticia en `media/` | Servida por Nginx (`image/png`) |
| `backup.sh init/run/check` | 2 *snapshots* (`db` y `media`), retención aplicada, `no errors were found` |
| `restore.sh check` | Recuentos idénticos: 32 tablas, 56 migraciones, 2 usuarios |
| Desastre: se borran la BD y la imagen | La imagen da 404 y la BD tiene 0 tablas |
| `restore.sh full --yes` | 2 usuarios, 1 propietaria y 56 migraciones; la imagen vuelve con propietario 10001 y la portada da 200 |
| `deploy.sh` con copia previa | OK |
| `deploy.sh rollback` | Cambia a la imagen anterior; la portada da 200 |
| Recrear solo `web` | Nginx lo sigue encontrando (200) |

**Tests añadidos:**
- `tests/core/test_health.py` (8): salud, métodos, host interno, sin redirección a HTTPS, BD caída devuelve 503 sin detalles, ruta exacta y hosts no permitidos que siguen rechazados.
- `tests/core/test_audit_and_settings.py` (+3): estáticos con hash, valores de producción detrás del proxy y `X-Forwarded-Proto` ignorado sin proxy.
- `tests/api/test_concurrency.py` (1): rotación simultánea del refresh.
- `tests/events/test_concurrency.py` (+3): misma clave de idempotencia, tope de activas y mismo evento.
- `tests/dashboard/test_stats.py` (+1): `UPPER` no ASCII, solo en PostgreSQL.

**No ejecutado aquí:**
- **Lo que necesita el VPS real:** DNS, el certificado de Let's Encrypt, un SMTP real (§11) y un destino externo de restic (en local se usó un repositorio en disco).
- **La revisión visual en navegador y la cámara en dispositivos:** sigue pendiente desde la auditoría.

## 11. Correo (SMTP real)

- Solo se configura con variables (`EMAIL_*` en `.env.prod`). No hay credenciales en el repositorio. `prod` rechaza los backends simulados y exige `EMAIL_HOST`.
- **DNS del dominio remitente** (`DEFAULT_FROM_EMAIL`):
  - **SPF:** un registro TXT que autoriza al proveedor, p. ej. `v=spf1 include:_spf.proveedor.example ~all`. Solo uno por dominio.
  - **DKIM:** los registros (CNAME o TXT) que da el proveedor; firma cada mensaje.
  - **DMARC:** TXT en `_dmarc.<dominio>`. Empieza por `v=DMARC1; p=none; rua=mailto:dmarc@<dominio>` para observar y pasa a `p=quarantine` cuando SPF y DKIM pasen.
- **Verificación manual:** registro de una cuenta de prueba con un email propio, revisando la cabecera `Authentication-Results` (spf=pass, dkim=pass, dmarc=pass). **No hay evidencia de ningún envío real:** en local todos los emails fueron a Mailpit.
- Riesgo aceptado P2-3: el envío va dentro de la petición. Está mitigado con `timeout` 30 > `EMAIL_TIMEOUT` 10 y 3 workers.

## 12. Endurecimiento del servidor (no automatizado)

Se documenta en lugar de automatizarlo porque depende del proveedor y se hace una sola vez. Ubuntu 24.04 LTS o posterior:

1. **Usuario sin root:**
   ```bash
   adduser deploy
   usermod -aG sudo,docker deploy
   ```
   El despliegue se hace como `deploy`. Pertenecer a `docker` equivale a ser root en la práctica: no añadas a nadie más.
2. **SSH solo con clave**, en `/etc/ssh/sshd_config.d/10-caneca.conf`:
   ```text
   PermitRootLogin no
   PasswordAuthentication no
   KbdInteractiveAuthentication no
   ```
   Después `systemctl reload ssh`, **probando antes una segunda sesión**. Opcional: `fail2ban`.
3. **Firewall:**
   ```bash
   ufw default deny incoming
   ufw allow 22/tcp
   ufw allow 80/tcp
   ufw allow 443/tcp
   ufw enable
   ```
   **Docker se salta UFW con los puertos publicados.** Por eso solo Nginx publica puertos; db y redis no publican ninguno y están en la red interna. No añadas `ports:` a otros servicios.
4. **Actualizaciones de seguridad automáticas:**
   ```bash
   apt install unattended-upgrades
   dpkg-reconfigure -plow unattended-upgrades
   ```
   Las imágenes base se actualizan al reconstruir (`deploy.sh`). Conviene hacerlo al menos una vez al mes.
5. **Docker:** instalación desde el repositorio oficial o el paquete de Ubuntu (`docker.io`, `docker-compose-v2`). No expongas el socket de Docker ni la API por TCP.
6. **Rotación de logs:**
   - los contenedores usan `json-file` con `max-size: 10m` y `max-file: 5` (`compose.yaml`), unos 50 MB por servicio;
   - el log del cron de copias, con `logrotate`;
   - los logs de Nginx contienen IPs (dato personal) y el log de Docker los conserva hasta que rota: eso limita la retención.
7. **Hora:** zona `Europe/Madrid` en los contenedores; el host puede quedarse en UTC. Con NTP (`systemd-timesyncd`).

## 13. Acciones manuales pendientes en el VPS

- [ ] Contratar el VPS y aplicar §12.
- [ ] DNS: registros A/AAAA del dominio; SPF, DKIM y DMARC del remitente (§11).
- [ ] `.env.prod` y `.env.backup` con valores reales (`chmod 600`). `RESTIC_PASSWORD`, guardada además fuera del servidor.
- [ ] Destino externo de restic (bucket con una clave limitada a él).
- [ ] Primer despliegue, certificado y propietario (§8.1).
- [ ] Registro de prueba que confirme la entrega por el SMTP real.
- [ ] Programar `backup.sh run` (diaria) y `restore.sh check` (semanal) en el host (§8.4).
- [x] Subir la rama y comprobar que el CI pasa en GitHub.
- [ ] Revisión visual y de la cámara en dispositivos reales.

## 14. Limitaciones, riesgos y siguientes pasos

- **Sin monitorización ni alertas** (exclusión de esta fase). Son el siguiente paso recomendado:
  - un comprobador externo de disponibilidad (HTTPS de la portada);
  - aviso si fallan las copias o la restauración semanal;
  - Sentry o similar para errores 500;
  - aviso de caducidad del certificado.
- **Un solo servidor:** sin alta disponibilidad. Una caída del VPS deja el servicio parado hasta restaurar en otro (§8.5).
- **Rollback con migraciones incompatibles:** requiere restaurar la copia y se pierde lo escrito después (§8.3).
- **Imágenes base fijadas por etiqueta, no por digest.** Una reconstrucción puede traer parches de la misma versión. Es lo que se busca para la seguridad, pero no es reproducible bit a bit. Fijar el digest es una mejora posible si se prefiere reproducibilidad total.
- **Acciones de GitHub fijadas por versión principal** (`@v4`, `@v5`), no por SHA.
- **Redis sin contraseña:** solo es accesible desde la red interna `backend`. Contiene contadores con hash, no datos personales.
- **El certificado autofirmado provisional** dura 7 días. Si no se obtiene el real, los navegadores muestran un aviso.
- **Las copias contienen datos personales hasta que caducan** (retención de 4 semanas). Hay que tenerlo en cuenta en la supresión de cuentas (P2-9) y en la política de privacidad.
- **Swagger UI** (`/api/v1/docs/`) sigue cargando su JavaScript desde jsDelivr.
- **Pendientes de la auditoría que siguen abiertos:** P2-9 (derechos del interesado, fase propia antes de abrir al público) y los P3 pospuestos (CSP, EXIF, `List-Unsubscribe-Post`…).

## 15. Criterios de aceptación

| Criterio | Estado |
|---|---|
| Dockerfile multietapa, slim, no root, sin secretos, `collectstatic` en el build, Gunicorn | **Completo** |
| Compose de producción (web, db, redis, nginx, scheduler) con volúmenes, healthchecks y db y redis sin puertos | **Completo** |
| Compose local con PostgreSQL, Mailpit y suite | **Completo** |
| Nginx: TLS, cabeceras de proxy, `/static` con caché larga, `/media` solo imágenes con `nosniff`, `client_max_body_size`, logs sin `Authorization` | **Completo** (TLS real pendiente del VPS) |
| `prod` rechaza la caché local; endpoint de salud; migraciones como paso único | **Completo** |
| Suite completa en SQLite y en PostgreSQL, concurrencia sin omitir; tests nuevos de tokens y reservas | **Completo** |
| Tareas programadas sin solapes y sin datos personales en los logs | **Completo** (verificado en local) |
| Copia cifrada, retención, destino configurable, restauración probada | **Completo** en local (destino externo pendiente del VPS) |
| SMTP por variables; SPF, DKIM y DMARC documentados | **Completo** (envío real sin verificar) |
| Workflow de CI | **Completo**: en verde en GitHub |
| Endurecimiento del VPS y procedimientos documentados | **Completo** |
| Despliegue real en el VPS | **Pendiente** (§13) |
