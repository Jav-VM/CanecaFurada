# Despliegue y operación

Guía operativa de Caneca Furada en un VPS Linux (Ubuntu LTS) con **Docker Compose**. Servicios: Nginx, Gunicorn y Django, PostgreSQL 17, Redis, scheduler y certbot.
- Diseño, decisiones y resultados de las pruebas: [Fase 12](fase-12-despliegue.md).
- Origen: la revisión de la [Fase 11](fase-11-api-auditoria.md) y la [auditoría previa](auditoria-pre-fase-12.md).

**Sin secretos reales:** todos los valores son de ejemplo.

## 1. Estado

| Elemento | Estado |
|---|---|
| Imagen (`Dockerfile`), Compose de producción y local, Nginx, scheduler, copias, CI | **Listos y probados en local** (2026-10-15) |
| Settings de producción | Listos. No arrancan sin clave (≥ 32 bytes), `ALLOWED_HOSTS`, PostgreSQL, caché compartida, SMTP real o `SITE_BASE_URL` https. |
| `check --deploy` | Solo `security.W021` (HSTS *preload* desactivado a propósito) |
| Suite | 833 OK en PostgreSQL 17 (local y en contenedor, 0 omitidos) y en SQLite |
| CI (GitHub Actions) | **en verde en GitHub** (2026-10-15, [ejecución](https://github.com/Jav-VM/CanecaFurada/actions/runs/38737894875), commit `0589cfb`) |
| VPS, DNS, certificado, SMTP real, destino de copias | **Pendiente** ([Fase 12 §13](fase-12-despliegue.md#13-acciones-manuales-pendientes-en-el-vps)) |

## 2. Variables de entorno

- `.env.prod`: plantilla [.env.prod.example](../.env.prod.example). La reciben Compose y los contenedores de la app.
- `.env.backup`: plantilla [.env.backup.example](../.env.backup.example). Solo la recibe restic.

Las dos con `chmod 600`, nunca en Git ni en la imagen. Lista y efecto de cada grupo:

| Grupo | Variables |
|---|---|
| Dominio | `NGINX_SERVER_NAME`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `SITE_BASE_URL` (los cuatro con el mismo dominio), `DJANGO_ADMIN_URL` |
| Django | `DJANGO_SECRET_KEY`, `DJANGO_LOG_LEVEL`, `DJANGO_SECURE_HSTS_*`, `DJANGO_SECURE_SSL_REDIRECT` |
| Base de datos | `POSTGRES_SUPERUSER(_PASSWORD)`, `APP_DB_NAME`, `APP_DB_USER`, `APP_DB_PASSWORD`, `DATABASE_CONN_MAX_AGE=60`, `DATABASE_CONN_HEALTH_CHECKS=True` |
| Fijadas por `compose.yaml` | `DATABASE_URL`, `CACHE_URL=redis://redis:6379/1`, `DJANGO_BEHIND_TLS_PROXY=True`, `DJANGO_TRUSTED_PROXY_COUNT=1`, `TZ=Europe/Madrid`, `DJANGO_SETTINGS_MODULE=config.settings.prod` (imagen) |
| Correo | `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`/`EMAIL_USE_SSL`, `EMAIL_TIMEOUT`, `DEFAULT_FROM_EMAIL` |
| Gunicorn | `GUNICORN_WORKERS` (3), `GUNICORN_TIMEOUT` (30, siempre > `EMAIL_TIMEOUT`) |
| API | `API_ACCESS_TOKEN_MINUTES`, `API_REFRESH_TOKEN_DAYS`, `API_JWT_SIGNING_KEY`, `API_THROTTLE_*`, `API_DOCS_PUBLIC` |
| Otras | `SMS_BACKEND` (vacío), `NOTIFICATIONS_BATCH_SIZE`, `EMAIL_VERIFICATION_TOKEN_TTL_HOURS`, `ACCOUNTS_MIN_CUSTOMER_AGE` |
| Copias (`.env.backup`) | `RESTIC_REPOSITORY`, `RESTIC_PASSWORD` y las credenciales del destino; en el host, `BACKUP_KEEP_DAILY` (7) y `BACKUP_KEEP_WEEKLY` (4) |

`manage.py` usa `config.settings.dev` por defecto, pero dentro de la imagen `DJANGO_SETTINGS_MODULE` es `prod`. Los comandos de gestión se lanzan siempre en el contenedor: `dc exec web python manage.py …` o `dc run --rm web python manage.py …`.

## 3. Órdenes habituales

```bash
alias dc='docker compose --env-file .env.prod'    # en el directorio del clon

deploy/scripts/deploy.sh --first      # primer despliegue (sin copia previa)
deploy/scripts/deploy.sh              # actualizar: copia → build → migrate → arranque
deploy/scripts/deploy.sh rollback     # volver a las imágenes anteriores (no deshace migraciones)
deploy/scripts/backup.sh init|run|check
deploy/scripts/restore.sh check       # restauración de prueba en una BD temporal
deploy/scripts/restore.sh full --yes  # restaurar de verdad (sustituye BD y media)

dc ps                                  # estado y healthchecks
dc logs -f --tail 100 web nginx        # logs (rotados: 10 MB × 5 por servicio)
dc exec web python manage.py check --deploy
```

Procedimientos paso a paso ([Fase 12 §8](fase-12-despliegue.md#8-procedimientos)):
- primer despliegue, con el certificado y `create_owner`;
- actualización con migraciones;
- rollback;
- copias programadas en el host;
- restauración;
- rotación de secretos y sus efectos.

## 4. HTTPS, proxy y cookies

- Nginx termina TLS (Let's Encrypt por webroot) y redirige 80→443. Además:
  - sustituye `X-Forwarded-For` por la IP real y fija `X-Forwarded-Proto`;
  - cierra las peticiones a hosts desconocidos.
- Django, ya en `prod`:
  - HSTS de 1 año sin *preload*;
  - `SESSION_COOKIE_SECURE` y `CSRF_COOKIE_SECURE`;
  - `SameSite=Lax`, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: same-origin`.
- `DJANGO_TRUSTED_PROXY_COUNT=1` es correcto mientras **Nginx sea el único proxy**. Si se añade un CDN o un balanceador delante, hay que subirlo y configurar Nginx para que confíe en él (`real_ip`).
- Límite de Nginx (30/min por IP) en login, registro, recuperación y reenvíos de la web, el admin y la API, además de los límites de Django.

## 5. Estáticos y multimedia

- **Estáticos:**
  - `collectstatic` se ejecuta al construir la imagen, con nombres con hash (`ManifestStaticFilesStorage`);
  - van dentro de la imagen de Nginx, en `/static/`, con caché de un año (`immutable`);
  - cada versión lleva los suyos, también en un rollback.
- **Multimedia:**
  - volumen `media`, que escribe `web` y lee Nginx;
  - Nginx solo sirve `/media/*.{jpg,jpeg,png,webp}`, con `nosniff` y `Content-Security-Policy: default-src 'none'; sandbox`; cualquier otra ruta da 404;
  - `client_max_body_size 6m`, con `CATALOG_IMAGE_MAX_BYTES` en 5 MB;
  - las imágenes conservan sus metadatos EXIF (P3-7, pospuesto).

## 6. Copias de seguridad

restic cifra la BD (`pg_dump -Fc`) y `media/` y las envía a un destino externo, con una retención de 7 diarias y 4 semanales. El volcado nunca queda sin cifrar en el disco del servidor.
- **Programación:** en el host, una copia diaria y una prueba de restauración semanal ([Fase 12 §8.4](fase-12-despliegue.md#84-copias-programadas-host)).
- **Datos protegidos:** la BD contiene datos personales, hashes de contraseñas y los refresh tokens de la app. Las copias requieren la misma protección.
- **`RESTIC_PASSWORD`:** se guarda además fuera del servidor. Sin ella no hay restauración.

## 7. Correo

- Proveedor SMTP con TLS, configurado solo por variables. `DEFAULT_FROM_EMAIL` usa el dominio propio.
- SPF, DKIM y DMARC: [Fase 12 §11](fase-12-despliegue.md#11-correo-smtp-real).
- Emails que envía la plataforma:
  - verificación y cambio de email, y aviso al email anterior;
  - intento de registro con un email existente;
  - recuperación de contraseña;
  - avisos de reservas, campañas y cumpleaños (cola con reintentos).

  Las promociones solo van a clientes con consentimiento y siempre con enlace de baja. Detalle: [Fase 10](fase-10-eventos-reservas-notificaciones.md).
- **Riesgo aceptado (P2-3):** el SMTP se llama dentro de la petición. Está mitigado con el timeout de Gunicorn (30 s), que supera a `EMAIL_TIMEOUT` (10 s), y con 3 workers. [Auditoría, §5](auditoria-pre-fase-12.md#5-riesgo-aceptado-envío-de-correo-dentro-de-la-petición-p2-3).
- SMS desactivado (`SMS_BACKEND` vacío). Sin push.

## 8. Tareas programadas

Servicio `scheduler` (supercronic, `deploy/cron/crontab`, `TZ=Europe/Madrid`). No hay solapes y los logs solo llevan recuentos.

| Comando | Cuándo |
|---|---|
| `process_notifications` | Cada 5 min |
| `run_birthday_promotions` y después `process_notifications` | 09:00 |
| `expire_redemptions` | 04:30 |
| `purge_email_tokens`, `flushexpiredtokens` y `clearsessions` | 04:45 |

Ejecución manual: `dc exec scheduler python manage.py <comando>`.

## 9. Logs y privacidad

- **Django y Gunicorn:** solo a la consola del contenedor. No registran contraseñas, tokens, códigos de canje, contenido del QR, emails ni direcciones; solo `public_id` y tipos de error.
- **Nginx:** registra IP, fecha, método, ruta **sin cadena de consulta**, estado, tamaño, tiempo y user-agent. Las rutas con token (`/cuenta/verificar-email/`, `/cuenta/contrasena/restablecer/`, `/comunicaciones/baja/`) aparecen como `[token]`. No registra `Authorization`, cookies, cuerpos ni Referer.
- **Rotación:** Docker la hace con `json-file` (10 MB × 5 por servicio). Así queda limitada la retención de las IPs, que son dato personal.

## 10. Dependencias externas

| Dependencia | Necesaria | Notas |
|---|---|---|
| VPS con Docker | Sí | Ubuntu LTS, endurecido según [Fase 12 §12](fase-12-despliegue.md#12-endurecimiento-del-servidor-no-automatizado) |
| Dominio y DNS | Sí | A/AAAA, SPF, DKIM y DMARC |
| Let's Encrypt | Sí | Renovación automática (certbot) |
| Proveedor SMTP | Sí | Credenciales solo en `.env.prod` |
| Destino de copias (S3, B2 o rest-server) | Sí | Credenciales solo en `.env.backup` |
| Docker Hub | Al construir | Imágenes base fijadas por etiqueta |
| CDN jsDelivr | Solo para `/api/v1/docs/` | |
| Proveedor de SMS | No | Sin integrar |

## 11. Lista de comprobación del despliegue

- [x] Imagen sin `.env`, `*.sqlite3*`, `media/`, `.venv/` ni `.tools/` (`.dockerignore`, comprobado).
- [x] Suite contra PostgreSQL (local, contenedor) y `check --deploy` (solo W021).
- [x] Copia y restauración probadas en local.
- [x] CI en verde en GitHub.
- [ ] VPS endurecido; DNS apuntando.
- [ ] `.env.prod` y `.env.backup` reales (`chmod 600`); `RESTIC_PASSWORD` guardada también fuera del servidor.
- [ ] `deploy.sh --first`, certificado de Let's Encrypt y `create_owner`, sin dejar sus variables en ningún fichero.
- [ ] `dc exec web python manage.py check --deploy` en el VPS.
- [ ] SMTP real probado (registro → email de verificación, SPF/DKIM/DMARC en `pass`).
- [ ] `backup.sh init`, primera copia y programación diaria; `restore.sh check` semanal.
