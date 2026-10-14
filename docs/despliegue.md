# Despliegue, correo y tareas programadas

Revisión de la preparación para producción hecha en la [Fase 11](fase-11-api-auditoria.md). Recoge lo que ya está configurado en el código, lo que hay que hacer en el servidor y lo que queda pendiente para la fase de despliegue (sin número). **No incluye secretos reales:** todos los valores son de ejemplo.

## 1. Estado

| Elemento | Estado |
|---|---|
| Settings de producción (`config.settings.prod`) | Listo: falla al arrancar si falta `DJANGO_SECRET_KEY` (o mide < 32 bytes), `DJANGO_ALLOWED_HOSTS`, `EMAIL_HOST`, un `SITE_BASE_URL` https o si el email/SMS es simulado. `wsgi.py` y `asgi.py` usan `prod` por defecto. |
| `check --deploy` | Ejecutado con valores ficticios (2026-10-14): solo `security.W021` (HSTS *preload* desactivado a propósito; activarlo es irreversible en la práctica). |
| HTTPS y cookies | Listo en código (§4). Falta el certificado y el proxy en el servidor. |
| PostgreSQL | Soportado (`DATABASE_URL`). **Falta ejecutar la suite contra PostgreSQL.** |
| Servidor WSGI | **Pendiente de elegir** (p. ej. Gunicorn en Linux o Waitress en Windows). No se ha añadido a `requirements/prod.txt`. |
| Estáticos y multimedia | **Pendiente** (§5–6). |
| Correo | Configurable por entorno (§8). Falta un proveedor SMTP real. |
| Tareas programadas | Comandos listos (§9). Falta programarlos. |
| Copias de seguridad | **Pendiente** (§7). |

## 2. Variables de entorno

Lista completa con valores ficticios en [.env.example](../.env.example). En producción las variables llegan del entorno del servicio (no de un `.env` en el repositorio).

| Grupo | Variables |
|---|---|
| Django | `DJANGO_SETTINGS_MODULE=config.settings.prod`, `DJANGO_SECRET_KEY` (≥ 50 caracteres aleatorios), `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_ADMIN_URL` (ruta no obvia), `DJANGO_LOG_LEVEL` |
| HTTPS y proxy | `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SECURE_HSTS_SECONDS`, `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS`, `DJANGO_SECURE_HSTS_PRELOAD`, `DJANGO_BEHIND_TLS_PROXY`, `DJANGO_TRUSTED_PROXY_COUNT` |
| Base de datos y caché | `DATABASE_URL`, `DATABASE_CONN_MAX_AGE`, `CACHE_URL` |
| Correo | `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`/`EMAIL_USE_SSL`, `EMAIL_TIMEOUT`, `DEFAULT_FROM_EMAIL`, `SITE_BASE_URL` |
| Notificaciones | `SMS_BACKEND` (vacío = desactivado), `NOTIFICATIONS_BATCH_SIZE` |
| Cuentas | `EMAIL_VERIFICATION_TOKEN_TTL_HOURS`, `ACCOUNTS_MIN_CUSTOMER_AGE` |
| API (Fase 11) | `API_ACCESS_TOKEN_MINUTES`, `API_REFRESH_TOKEN_DAYS`, `API_JWT_SIGNING_KEY` (opcional, ≥ 32 bytes), `API_THROTTLE_ANON`, `API_THROTTLE_USER`, `API_THROTTLE_AUTH`, `API_DOCS_PUBLIC` |

`manage.py` usa `config.settings.dev` por defecto: en el servidor, ejecuta los comandos con `DJANGO_SETTINGS_MODULE=config.settings.prod` o `--settings=config.settings.prod`.

Rotar `DJANGO_SECRET_KEY` invalida sesiones web, enlaces de recuperación y de baja pendientes y, si no hay `API_JWT_SIGNING_KEY`, todos los tokens de la app.

## 3. PostgreSQL

1. Crear base de datos y usuario propio con permisos solo sobre ella: `DATABASE_URL=postgres://caneca:<contraseña>@<host>:5432/caneca_furada`.
2. `python manage.py migrate --settings=config.settings.prod` (antes, `migrate --plan` para revisar). Las migraciones son pequeñas y revisadas; la Fase 11 añade `core/0009` (solo opciones) y las tablas de `token_blacklist`.
3. **Ejecutar la suite contra PostgreSQL** antes de abrir al público: `DATABASE_URL=… python manage.py test --settings=config.settings.test` (comprueba los bloqueos de compras, canjes, reservas, notificaciones y renovación de tokens, que SQLite ignora).
4. `DATABASE_CONN_MAX_AGE=60` reduce conexiones si el servidor lo permite.
5. Caché compartida para los límites de intentos y el throttling de la API: `CACHE_URL=redis://…` (requiere instalar `redis`) o `CACHE_URL=dbcache://django_cache` + `python manage.py createcachetable`.

## 4. HTTPS, proxy y cookies

- Ya en `prod`: `SECURE_SSL_REDIRECT`, HSTS (1 año), `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, cookies `HttpOnly` y `SameSite=Lax`, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: same-origin`.
- Detrás de un proxy que termina TLS (Nginx, Caddy, balanceador): `DJANGO_BEHIND_TLS_PROXY=True` **solo** si el proxy fija `X-Forwarded-Proto`, y `DJANGO_TRUSTED_PROXY_COUNT=1` (o el número real de proxies) para que los límites por IP usen la IP del cliente. Con un valor mayor que el real, un cliente podría falsear su IP.
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://www.example.com`.
- La API no usa cookies; los tokens viajan en `Authorization`. Asegúrate de que el proxy no registra esa cabecera.

## 5. Archivos estáticos

`python manage.py collectstatic --settings=config.settings.prod` copia todo a `STATIC_ROOT` (`staticfiles/`). Django no sirve estáticos con `DEBUG=False`: hay que servir `/static/` desde el proxy web o añadir WhiteNoise (pendiente de decidir). El CSS de Tailwind ya está compilado y versionado. La documentación Swagger (`/api/v1/docs/`) carga su JavaScript desde jsDelivr.

## 6. Archivos multimedia

Imágenes de la carta, recompensas y eventos en `MEDIA_ROOT` (`media/`). En producción `static()` no las sirve: servir `/media/` desde el proxy (con `Content-Disposition` y tipos restringidos a imagen) o usar almacenamiento de objetos. Incluir `media/` en las copias de seguridad. Las imágenes no se recodifican (los metadatos EXIF se conservan, ver Fase 4).

## 7. Copias de seguridad (pendiente)

- Base de datos: `pg_dump --format=custom` diario, con retención (p. ej. 7 diarias + 4 semanales), cifrado y fuera del servidor.
- `media/`: copia diaria sincronizada.
- La BD contiene datos personales, hashes de contraseñas y los refresh tokens de la app (`token_blacklist_outstandingtoken`): las copias requieren el mismo nivel de protección que la BD.
- **Probar la restauración** periódicamente en un entorno aparte.

## 8. Correo

- Cualquier proveedor SMTP con TLS: `EMAIL_HOST`, `EMAIL_PORT=587`, `EMAIL_USE_TLS=True`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` (solo en el entorno del servidor), `DEFAULT_FROM_EMAIL=no-reply@<dominio>`.
- Configurar SPF, DKIM y DMARC del dominio remitente para que los emails no acaben en spam.
- `SITE_BASE_URL=https://<dominio>`: con él se construyen los enlaces de verificación, recuperación y baja (nunca con la cabecera `Host`).
- Emails que envía la plataforma: verificación y cambio de email, aviso al email anterior, intento de registro con email existente, recuperación de contraseña (al momento y sin guardar el enlace); avisos de reservas, campañas y cumpleaños (cola con reintentos). Las promociones solo a clientes con consentimiento y siempre con enlace de baja. Detalle: [Fase 10](fase-10-eventos-reservas-notificaciones.md).
- SMS: desactivado hasta integrar un proveedor (`SMS_BACKEND`).
- Push en la app: no implementado.

## 9. Tareas programadas

| Comando | Frecuencia | Qué hace |
|---|---|---|
| `process_notifications` | Cada 5 min | Envía la cola de notificaciones, campañas y reintentos. |
| `run_birthday_promotions` | Diario (09:00) | Regalos y avisos de cumpleaños. |
| `expire_redemptions` | Diario | Caduca canjes vencidos y devuelve puntos. |
| `purge_email_tokens` (Fase 11) | Diario | Borra los tokens de verificación caducados hace más de 30 días (`--days`). |
| `flushexpiredtokens` (simplejwt) | Diario | Borra de la lista negra los refresh ya caducados. |

```cron
*/5 * * * * cd /srv/caneca && .venv/bin/python manage.py process_notifications --settings=config.settings.prod
0 9 * * *   cd /srv/caneca && .venv/bin/python manage.py run_birthday_promotions --settings=config.settings.prod && .venv/bin/python manage.py process_notifications --settings=config.settings.prod
30 4 * * *  cd /srv/caneca && .venv/bin/python manage.py expire_redemptions --settings=config.settings.prod
45 4 * * *  cd /srv/caneca && .venv/bin/python manage.py purge_email_tokens --settings=config.settings.prod && .venv/bin/python manage.py flushexpiredtokens --settings=config.settings.prod
```

En Windows, el Programador de tareas ejecuta los mismos comandos con `.venv\Scripts\python.exe`. Las variables de producción deben estar disponibles para la tarea.

## 10. Logs

- Solo consola (`LOGGING` en `base.py`), nivel con `DJANGO_LOG_LEVEL`. El gestor de servicios (systemd, etc.) los recoge.
- El código no registra contraseñas, tokens, códigos de canje, contenido del QR, emails ni direcciones: solo `public_id` y tipos de error.
- Revisa que el proxy no registre la cabecera `Authorization` ni cuerpos de petición. Las rutas `/cuenta/verificar-email/<token>/` y `/comunicaciones/baja/<token>/` llevan un token en la URL: si el proxy guarda URLs completas, limita la retención de esos logs.

## 11. Dependencias externas

| Dependencia | Necesaria | Notas |
|---|---|---|
| PostgreSQL | Sí | |
| Proveedor SMTP | Sí (para cualquier email) | Credenciales solo en el entorno. |
| Redis (o caché en BD) | Recomendable con varios procesos | Límites de intentos y throttling. |
| Proveedor de SMS | No (opcional) | Sin integrar. |
| CDN jsDelivr | Solo para `/api/v1/docs/` | El resto de la web no carga recursos de terceros. |

## 12. Lista de comprobación del despliegue

- [ ] Variables de producción definidas, sin `.env` en el servidor si se usan variables del sistema.
- [ ] `python manage.py check --deploy --settings=config.settings.prod` sin errores.
- [ ] `migrate` aplicado y suite ejecutada contra PostgreSQL.
- [ ] `collectstatic` y `/static/`, `/media/` servidos.
- [ ] HTTPS con certificado válido; `DJANGO_BEHIND_TLS_PROXY` y `DJANGO_TRUSTED_PROXY_COUNT` según la topología real.
- [ ] `CACHE_URL` compartida.
- [ ] SMTP real probado (registro → email de verificación).
- [ ] Tareas programadas activas.
- [ ] Copias de seguridad y restauración probadas.
- [ ] Primer propietario creado con `create_owner` y variables `CANECA_OWNER_*` eliminadas después.
