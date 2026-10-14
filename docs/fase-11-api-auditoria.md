# Fase 11 — API, auditoría, seguridad y preparación para la app móvil

**Estado: Completa** (con los pendientes de §10). Fecha: 2026-10-14.

Documentos relacionados:
- [Guía para el desarrollador de la app Flutter](guia-app-flutter.md)
- [Despliegue, correo y tareas programadas](despliegue.md)
- Esquema OpenAPI versionado: [docs/api/openapi.yaml](api/openapi.yaml) (también en `/api/v1/schema/` y, con interfaz, en `/api/v1/docs/`)

## 1. Objetivo, alcance y exclusiones

**Objetivo:** auditar la plataforma, corregir los problemas reales encontrados y publicar la primera versión de la API REST para la futura app móvil.

**Incluye:**
- Auditoría de arquitectura, modelos, migraciones, cuentas, datos personales, compras, puntos, canjes, promociones, reservas, permisos, dashboard y notificaciones (§2), con las correcciones de §3.
- Django REST Framework en `/api/v1/` (app `apps.api`, solo presentación) con autenticación JWT para móvil (§5), serializadores explícitos, paginación, errores coherentes, throttling y documentación OpenAPI.
- Endpoints de cliente (registro, verificación, login, recuperación, perfil, email, puntos, compras, QR, recompensas, canjes, eventos y reservas) y solo las operaciones de personal y propietario justificadas (§4.3).
- Revisión de seguridad (§6) y de despliegue ([despliegue.md](despliegue.md)).

**Exclusiones:**
- La app móvil (Flutter): no se desarrolla.
- Gestión completa del propietario por API (clientes, empleados, puntos, catálogo, contenidos, campañas): sigue en el dashboard y el admin (§4.3).
- Endpoints de la carta: no estaban en el prompt de la fase; quedan previstos en [Fase 4, §7](fase-04-carta.md#7-preparación-para-la-app-móvil-y-la-futura-api-fase-11).
- Notificaciones push, servidor WSGI, almacenamiento de estáticos/medios y ejecución contra PostgreSQL: fase de despliegue (sin número).

## 2. Resumen de la auditoría

Revisión del código y la configuración de cada área, apoyada en la suite de tests existente (719 tests en verde antes de empezar). El dashboard (≈1000 líneas de vistas) se revisó de forma dirigida (permisos, selectores, datos personales), no línea a línea.

| Área | Resultado |
|---|---|
| Arquitectura | Monolito modular coherente: lógica en servicios y selectores, vistas solo de presentación, permisos centralizados. Sin dependencias cruzadas indebidas. La API se añade como otra capa de presentación. |
| Modelos y migraciones | Invariantes protegidas en BD (`CHECK`, únicas condicionales, `PROTECT`, ledger inmutable). `makemigrations --check` limpio. Única migración nueva: opciones de auditoría (`core/0009`), solo cambia `choices` (sin cambios de esquema relevantes). La lista negra de tokens añade sus propias migraciones (`token_blacklist`). |
| Registro | **Hallazgo 1** (enumeración por contraseña débil) y **hallazgo 2** (diferencia de tiempos): corregidos. |
| Verificación del email | Correcta: hash SHA-256, un solo uso atómico, caducidad, revocación, anti-enumeración. **Hallazgo 5** (tokens caducados conservan el email): corregido con una purga. |
| Perfiles, dirección, fecha de nacimiento, teléfono | Correctos: lista blanca de campos, normalización y validación en servicio, edad mínima, 29-F, bloqueo anual de la fecha de nacimiento, E.164. |
| Preferencias de comunicación | Correctas: desactivadas por defecto, historial inmutable, retirada automática del SMS al borrar el teléfono, nueva comprobación del consentimiento justo antes de enviar. |
| Privacidad | Correcta en web: el personal solo ve el nombre corto; los datos completos solo en la ficha del propietario (consulta auditada); logs sin datos personales. La API mantiene las mismas reglas (§7). |
| Compras y puntos | Correctos: idempotencia por UUID único, bloqueo del cliente, puntos calculados en el servidor dentro de la misma transacción, ledger con saldo no negativo en BD. |
| Canjes | Correctos: un pendiente por cliente y recompensa (BD), `UPDATE` condicionado al validar, devolución por compensación, código nunca en logs ni URLs. |
| Promociones | Correctas: condiciones y límites validados en servidor; cumpleaños uno por cliente y año (restricción única). Sin hallazgos. |
| Reservas | Correctas: transiciones validadas con la fila bloqueada, aforo, límite de activas, una activa por evento (BD), notas fuera de los emails. |
| Permisos | Correctos en web (decoradores + comprobación en servicios/selectores). **Hallazgo 3** (IP detrás de proxy) afecta a los límites por IP. |
| Dashboard | Cada selector vuelve a exigir propietario; sin direcciones completas en estadísticas. Sin hallazgos. |
| Notificaciones | Correctas: reclamación atómica, reintentos, consentimiento revisado al enviar, sin destinatarios ni tokens en el registro. Sin hallazgos. |
| Contraseñas | **Hallazgo 4**: los cambios y restablecimientos no quedaban auditados. Corregido. |
| Contenido | **Hallazgo 6**: la portada anunciaba el programa de puntos como «Próximamente» aunque funciona desde las Fases 5–7. Corregido. |

## 3. Problemas encontrados y correcciones

| # | Problema | Riesgo | Corrección |
|---|---|---|---|
| 1 | `register_customer` comprobaba si el email existía **antes** de validar la contraseña. Con una contraseña débil, un email existente respondía «revisa tu email» y uno libre mostraba el error: permitía saber qué emails tienen cuenta. | Medio (enumeración de clientes) | El servicio valida **todo** (perfil, nombre, email y contraseña, `_validate_registration`) y solo después mira si el email existe. Afecta igual a web y API. Tests: `tests/core/test_phase11_audit.py`, `tests/api/test_auth.py`. |
| 2 | Con un email existente el registro respondía más rápido (no calculaba el hash de la contraseña). | Bajo | Se calcula un hash equivalente (`make_password`) antes de responder. |
| 3 | Los límites por IP (login, registro, reenvíos, recuperación) usaban `REMOTE_ADDR`. Detrás de un proxy inverso todas las peticiones comparten la IP del proxy: unos pocos fallos bloquearían el login de todos. | Medio (denegación de servicio) | `apps.core.http.client_ip` con `DJANGO_TRUSTED_PROXY_COUNT`: sin proxies se ignora `X-Forwarded-For` (no se puede falsear); con N proxies se toma la entrada N desde la derecha. DRF usa el mismo valor (`NUM_PROXIES`). |
| 4 | Los cambios y restablecimientos de contraseña no dejaban rastro de auditoría. | Bajo (trazabilidad) | Acción `PASSWORD_CHANGED` con `{"via": "change"\|"reset", "channel": "web"\|"api"}`, sin secretos. |
| 5 | Los tokens de verificación caducados conservaban el email al que se enviaron indefinidamente. | Bajo (minimización) | Comando `purge_email_tokens` (borra los caducados hace más de 30 días). Programarlo a diario. |
| 6 | Texto desfasado «Próximamente» en el bloque del programa de puntos de la portada. | Contenido | Texto actualizado; el test que lo exigía se ajustó. |
| 7 | (Preventivo, API) DRF con `NUM_PROXIES = None` se fía de toda la cabecera `X-Forwarded-For`, que el cliente puede inventar para eludir el throttling. | Medio | `NUM_PROXIES = TRUSTED_PROXY_COUNT` (0 por defecto). Test `test_forwarded_for_is_ignored_without_trusted_proxies`. |
| 8 | (Preventivo, API) simplejwt: la renovación no comprueba si la contraseña cambió, y su admin muestra el refresh token completo de cada usuario (el propietario podría suplantar a un cliente). | Medio | Renovación propia que comprueba cuenta activa y versión de contraseña con la fila bloqueada; los modelos de tokens no se registran en el admin. |

**Revisado y aceptado sin cambios** (documentado en §10): el enlace de recuperación nativo de Django lleva la PK interna codificada (`uidb64`); los tokens de verificación y de baja viajan en la ruta de la URL (mitigado como en fases anteriores); la concurrencia sigue sin probarse en PostgreSQL.

## 4. API REST v1

### 4.1 Decisiones técnicas

| Decisión | Motivo |
|---|---|
| `djangorestframework` 3.16, `djangorestframework-simplejwt` 5.5 (con `token_blacklist`), `drf-spectacular` 0.28 | Dependencias mantenidas y estándar; versiones acotadas en `requirements/base.txt`. |
| App `apps.api` solo de presentación | Las vistas validan con serializadores y llaman a los **mismos servicios y selectores** que la web; no hay lógica de negocio en la API. |
| Ruta versionada `/api/v1/` | Permite que convivan versiones de la app. |
| Solo JSON (entrada y salida) | Sin formularios ni renderizador navegable: menos superficie. |
| Serializadores `Serializer` con campos explícitos | Nada de `ModelSerializer`/`__all__`. Los campos protegidos (rol, saldo, puntos, estados, auditoría, identificadores) no existen en la entrada; si se envían se ignoran. |
| Objetos por `public_id` (UUID) | La PK interna no aparece en URLs, respuestas ni tokens. Un objeto ajeno responde **404** (no revela que existe). |
| `Idempotency-Key` en cabecera | Las operaciones que crean algo (canje, reserva, compra) exigen un UUID de la app; un reintento devuelve el mismo resultado con 200 en lugar de 201. Reutiliza la idempotencia de los servicios. |
| Paginación por páginas (`page`, `page_size` ≤ 50) | Evita descargas masivas. |
| `Cache-Control: no-store, private` en todas las respuestas | Llevan datos de la cuenta, saldos o códigos. |
| Documentación restringida fuera de desarrollo | `/api/v1/schema/` y `/api/v1/docs/` solo para el propietario (sesión web o token) salvo `API_DOCS_PUBLIC=True`; en `dev` son públicas. |

### 4.2 Formato de errores

```json
{"code": "insufficient_points", "detail": "El cliente no tiene puntos suficientes para esta operación.", "fields": {"campo": ["mensaje"]}}
```

`code` es estable (la app decide con él) y `detail` se puede mostrar. `fields` solo aparece en validaciones. Traducción de los errores de dominio (`apps/api/exceptions.py`): `ValidationError` → 400 (409 si es un conflicto con el estado actual: `idempotency_conflict`, `duplicate_pending`, `code_used`, `code_not_pending`, `already_reserved`, `event_full`, `invalid_transition`; 429 si es `rate_limited`), `PermissionDenied` → 403, `Http404` → 404, límites propios de los servicios → 429. Lista completa de códigos en la [guía Flutter](guia-app-flutter.md#7-errores).

### 4.3 Endpoints

Todas las rutas cuelgan de `/api/v1/`. «Verificado» = cliente activo con el email confirmado.

| Método y ruta | Quién | Servicio / selector |
|---|---|---|
| `POST auth/register/` | Público | `accounts.register_customer` (202 siempre igual; `notify_existing_account` si el email existe) |
| `POST auth/email/verify/` | Público | `accounts.confirm_email_token` |
| `POST auth/email/resend/` | Público | `accounts.request_verification_resend` (202 siempre igual) |
| `POST auth/login/` | Público | `authenticate` + límites de `accounts.login_throttle_keys` (compartidos con la web) |
| `POST auth/token/refresh/` | Con refresh | `api.tokens.rotate_refresh_token` |
| `POST auth/logout/` · `auth/logout-all/` | Autenticado | `api.tokens.revoke_refresh_token` · `revoke_all_tokens` (auditado) |
| `POST auth/password/change/` | Autenticado | `accounts.change_password` (+ revocación y par nuevo) |
| `POST auth/password/reset/` | Público | `NotifyingPasswordResetForm` (el mismo de la web) |
| `POST auth/password/reset/confirm/` | Público | `accounts.reset_password_with_token` |
| `GET me/` | Autenticado | Datos básicos, **sin** dirección, fecha de nacimiento, teléfono ni preferencias |
| `GET`/`PATCH me/profile/` | Cliente | `accounts.update_customer_profile` |
| `GET`/`PATCH me/preferences/` | Cliente | `accounts.set_communication_preferences` |
| `POST me/email/change/` | Autenticado | `accounts.request_email_change` (202; confirmación en `auth/email/verify/`) |
| `POST me/email/resend-verification/` | Autenticado | `accounts.resend_verification_email` |
| `GET me/points/` | Verificado | `loyalty.selectors.points_summary` |
| `GET me/points/movements/` | Verificado | `loyalty.selectors.points_history` |
| `GET me/purchases/` | Verificado | `purchases.selectors.customer_purchases` |
| `GET me/qr/` · `POST me/qr/rotate/` | Verificado | `loyalty.services.get_customer_qr` · `rotate_customer_qr` |
| `GET rewards/` · `GET rewards/{id}/` | Público | `rewards.selectors.public_rewards` · `public_reward` |
| `POST rewards/{id}/redeem/` | Verificado | `rewards.services.request_redemption` (`Idempotency-Key`) |
| `GET me/redemptions/` · `GET me/redemptions/{id}/` | Verificado | `customer_redemptions` · `customer_redemption` (código solo en el detalle y si está vigente) |
| `POST me/redemptions/{id}/cancel/` | Verificado | `rewards.services.cancel_redemption` |
| `GET events/` · `GET events/{id}/` | Público | `events.selectors.public_events` · `public_event`, `seats_left`, `is_bookable` |
| `GET`/`POST me/reservations/` | Verificado | `customer_reservations` · `events.services.request_reservation` (`Idempotency-Key`) |
| `GET me/reservations/{id}/` · `POST …/cancel/` | Verificado | `customer_reservation` · `cancel_own_reservation` |
| `POST staff/purchases/identify/` | Personal | `purchases.services.identify_for_purchase` |
| `POST staff/purchases/` | Personal | `purchases.services.register_purchase` (`Idempotency-Key`) |
| `POST staff/redemptions/lookup/` · `validate/` | Personal | `rewards.services.lookup_redemption` · `validate_redemption` |
| `GET owner/stats/` | Propietario | `customer_counts`, `registered_purchases_stats`, `points_stats`, `redemption_stats`, `reservation_stats` |
| `GET owner/reservations/` | Propietario | `events.selectors.reservations_for_management` (sin contacto) |
| `POST owner/reservations/{id}/{confirm\|reject\|cancel\|complete}/` | Propietario | `events.services.*_reservation` |
| `GET schema/` · `GET docs/` | Propietario (o público si `API_DOCS_PUBLIC`) | drf-spectacular |

**Operaciones administrativas incluidas y por qué:** las del personal en barra (identificar, registrar compras, validar canjes), porque una app de empleados es el uso previsible y ya tienen servicios idempotentes y con límite de intentos; y las del propietario de consulta de estadísticas agregadas y gestión de reservas, que se atienden desde el móvil. **No incluidas:** búsqueda y fichas de clientes (datos personales completos; la consulta masiva por API no está justificada), ajustes de puntos, empleados y roles, catálogo, contenidos y campañas: siguen en el dashboard web (protegido por sesión, CSRF y auditoría).

## 5. Estrategia de autenticación de la app

| Aspecto | Decisión |
|---|---|
| Mecanismo | JWT (simplejwt): **access** de 15 min (`API_ACCESS_TOKEN_MINUTES`) y **refresh** de 30 días (`API_REFRESH_TOKEN_DAYS`), firmados con HS256 (`SECRET_KEY` o `API_JWT_SIGNING_KEY`, mínimo 32 bytes en producción). |
| Envío | Cabecera `Authorization: Bearer <access>`. **Sin cookies ni sesión** en la API, así que no hay superficie CSRF. |
| Contenido del token | `sub` = `public_id`, `jti`, `exp`, `iat`, `token_type` y `pwv` (versión de contraseña). Sin email, rol ni PK interna. El rol se lee de la BD en cada petición. |
| Inicio de sesión | `POST auth/login/` con email y contraseña; mismos límites de intentos por email e IP que la web (contadores compartidos) y mismo mensaje para email inexistente o contraseña errónea. Una cuenta pendiente de verificar puede entrar, pero no usar puntos, QR, canjes ni reservas (403 `email_not_verified`). |
| Renovación | `POST auth/token/refresh/`: rotación obligatoria; el refresh usado pasa a la lista negra con la fila bloqueada (dos renovaciones simultáneas no obtienen ambas un par). |
| Cierre de sesión | `auth/logout/` revoca el refresh del dispositivo; `auth/logout-all/` revoca todos (auditado). El access en curso caduca solo (≤ 15 min). |
| Revocación inmediata | **Cambio de contraseña** por cualquier vía (app, web, admin, recuperación): la reclamación `pwv` (HMAC de Django sobre el hash de la contraseña) deja de coincidir y access y refresh se rechazan al momento (`token_revoked`). **Cuenta desactivada:** rechazo inmediato. |
| Cambio de contraseña | `auth/password/change/` con la actual; revoca todo y devuelve un par nuevo para el dispositivo actual. Auditado. |
| Recuperación | `auth/password/reset/` (respuesta idéntica exista o no) envía el enlace nativo de Django; la app puede abrirlo (enlace universal) y completar con `auth/password/reset/confirm/`, o dejar que se complete en la web. |
| Verificación del email | El enlace del email (`/cuenta/verificar-email/<token>/`) funciona en la web; la app puede interceptarlo y llamar a `auth/email/verify/`. El cambio de email se confirma igual. |
| Secretos en la app | Ninguno: la app no lleva claves del servidor; solo guarda los tokens del usuario en almacenamiento seguro del sistema. |

**Alternativas descartadas:** `TokenAuthentication` de DRF (token sin caducidad, uno por usuario, en claro en la BD) y sesiones con cookies (CSRF y gestión de cookies en una app nativa). **Coste asumido:** la lista negra de simplejwt guarda los refresh emitidos en la BD (`OutstandingToken`); se mitiga ocultándolos del admin, con la revocación por `pwv` y con la purga `flushexpiredtokens`.

## 6. Revisión de seguridad

| Tema | Estado |
|---|---|
| CSRF | Web sin cambios (`CsrfViewMiddleware`). La API solo acepta JWT en cabecera: la sesión web **no** autentica en la API (test). Las vistas de documentación aceptan la sesión solo para `GET`. |
| Permisos | Permisos DRF que envuelven `accounts.permissions` (`IsCustomer`, `IsVerifiedCustomer`, `IsStaffMember`, `IsOwner`) y los servicios vuelven a comprobar. Tests de anónimo, rol incorrecto, cliente sin verificar y escalada (campos de rol ignorados). |
| Control de acceso a objetos (IDOR/BOLA) | Todo lo del cliente se consulta filtrando por `request.user`; lo ajeno da 404. Logout no puede revocar tokens de otro usuario. Tests de acceso a canjes y reservas ajenos. |
| CORS | No se instala `django-cors-headers`: una app nativa no lo necesita y sin cabeceras CORS ningún sitio web de terceros puede leer las respuestas desde un navegador (test). Si algún día hay un cliente web en otro dominio, añadirlo con lista blanca. |
| Validación | Serializadores + servicios (que validan todo de nuevo). Solo JSON (415 para otros formatos). |
| Asignación masiva | Campos explícitos; tests que envían `role`, `is_staff`, `points`, `status`, `points_cost`, `public_id`… y comprueban que no cambian nada. |
| Tokens | §5. Firma mínima de 32 bytes en producción; sin datos personales en el token. |
| Idempotencia y concurrencia | `Idempotency-Key` + restricciones únicas de los servicios; rotación del refresh con bloqueo de fila. |
| Abuso | Throttling DRF: anónimo 60/min, usuario 240/min, autenticación 10/min por IP (configurables), además de los límites propios de los servicios. Claves de caché con hash (sin IPs ni IDs en claro). |
| Logs | La API no registra cuerpos, tokens, QR ni códigos. Los errores no incluyen trazas. |
| Datos personales | §7. |
| Configuración de producción | `check --deploy` con valores ficticios: solo `security.W021` (HSTS preload desactivado a propósito). Detalle en [despliegue.md](despliegue.md). |

## 7. Privacidad en la API

- `GET me/` (y el `user` del login) no devuelve dirección, fecha de nacimiento, teléfono ni preferencias. Esos datos solo están en `me/profile/` y `me/preferences/`, y solo para el propio cliente.
- El personal recibe únicamente el nombre corto del cliente («Lúa F.»), nunca email, teléfono ni saldo.
- El propietario ve estadísticas **agregadas** y reservas sin datos de contacto; las fichas completas siguen solo en el dashboard (consulta auditada).
- No hay ningún endpoint que liste clientes ni datos personales de terceros; los listados están paginados (máx. 50).
- Los códigos de canje solo aparecen en el detalle del propio canje mientras se puede recoger; el QR, solo para su dueño.
- Las preferencias promocionales solo las ve y cambia su titular (cada cambio queda en el historial).

## 8. Archivos

**Nuevos:** `apps/api/` (`apps.py`, `admin.py`, `authentication.py`, `exceptions.py`, `pagination.py`, `permissions.py`, `schema.py`, `throttling.py`, `tokens.py`, `urls.py`, `serializers/`, `views/`), `apps/core/http.py`, `apps/core/migrations/0009_audit_actions_phase11.py`, `apps/accounts/management/commands/purge_email_tokens.py`, `docs/api/openapi.yaml`, `docs/fase-11-api-auditoria.md`, `docs/guia-app-flutter.md`, `docs/despliegue.md`, `tests/api/`, `tests/core/test_phase11_audit.py`.

**Modificados:** `apps/accounts/services.py` (orden de validación del registro, contraseñas, purga, límites de login compartidos), `apps/accounts/forms.py` y `views.py` (IP real, auditoría de contraseñas), `apps/core/models.py` (acciones `PASSWORD_CHANGED`, `API_SESSIONS_REVOKED`), `config/settings/{base,dev,test,prod}.py`, `config/urls.py`, `requirements/base.txt`, `templates/web/home.html`, `tests/web/test_public_pages.py`, `tests/core/test_audit_and_settings.py`, `.env.example`, `README.md`, `docs/arquitectura.md`, `docs/plan-de-fases.md`.

**Migraciones:** `core/0009_audit_actions_phase11` (solo `choices`) y las de `token_blacklist` (tablas de la librería). Ninguna toca el modelo de usuario.

## 9. Configuración y variables nuevas

| Variable | Defecto | Uso |
|---|---|---|
| `DJANGO_TRUSTED_PROXY_COUNT` | `0` | Proxies inversos de confianza (IP real del cliente). |
| `API_ACCESS_TOKEN_MINUTES` | `15` | Duración del access. |
| `API_REFRESH_TOKEN_DAYS` | `30` | Duración del refresh. |
| `API_JWT_SIGNING_KEY` | vacío (usa `SECRET_KEY`) | Clave propia para firmar los JWT (≥ 32 bytes). Cambiarla invalida todas las sesiones de la app. |
| `API_THROTTLE_ANON` / `API_THROTTLE_USER` / `API_THROTTLE_AUTH` | `60/min` / `240/min` / `10/min` | Límites de peticiones. |
| `API_DOCS_PUBLIC` | `False` (`True` en dev) | Documentación de la API sin sesión. |

Instalación: `pip install -r requirements/dev.txt` y `python manage.py migrate`.

## 10. Tests y resultados

Comandos ejecutados (Windows, Python 3.14, SQLite):

```powershell
python manage.py check                                          # sin incidencias
python manage.py makemigrations --check --dry-run               # No changes detected
python manage.py spectacular --validate --fail-on-warn --file docs/api/openapi.yaml   # sin avisos
python manage.py test --settings=config.settings.test           # ver resultado abajo
# check --deploy con config.settings.prod y variables ficticias: solo security.W021
```

Resultado de la suite completa (2026-10-14): **802 tests, OK, 3 omitidos**. Antes de la fase había 719; se han añadido 83. Los 3 omitidos son los de concurrencia real de canjes (`tests.rewards.test_concurrency`), que necesitan PostgreSQL porque la BD de tests de SQLite en memoria no admite varias conexiones.

Tests añadidos:
- `tests/api/test_auth.py`: registro (datos obligatorios, inválidos, menor de edad, campos privilegiados ignorados, email existente con la misma respuesta, contraseña débil sin enumeración), login (tokens, contenido del JWT, mismo error, límite compartido con la web, cuenta inactiva, la sesión web no autentica), rotación y reutilización del refresh, logout, logout-all, logout de token ajeno, cambio de contraseña (por API y fuera de ella), cuenta desactivada, recuperación, verificación y cambio de email.
- `tests/api/test_me.py`: respuesta general sin datos personales, perfil propio, `PATCH` parcial, campos no modificables, validación, fecha de nacimiento anual, personal sin perfil, cliente sin verificar, preferencias e historial, SMS sin teléfono.
- `tests/api/test_customer.py`: puntos, movimientos y compras solo propios, QR y límite de renovación, recompensas públicas, canje idempotente, errores (`idempotency_invalid`, `duplicate_pending`, `insufficient_points`), coste no manipulable, canjes y reservas ajenos (404), cancelaciones, eventos públicos, reservas idempotentes, validaciones, notificación encolada sin las notas.
- `tests/api/test_staff_owner.py`: permisos por rol, identificación con nombre corto, compra idempotente con puntos del servidor, conflicto de idempotencia, importe inválido, comprobar y validar canje una sola vez, estadísticas solo del propietario y sin datos personales, reservas sin contacto y transiciones.
- `tests/api/test_security.py`: acceso a la documentación, `no-store`, sin CORS, formato de errores, solo JSON, tope de paginación, throttling por IP y `X-Forwarded-For` ignorado, tokens fuera del admin.
- `tests/core/test_phase11_audit.py`: `client_ip`, enumeración en el registro web y en el servicio, auditoría de contraseñas (web), purga de tokens.
- `tests/core/test_audit_and_settings.py`: producción exige clave de firma de 32 bytes.

**No ejecutado:** tests contra PostgreSQL (no hay servidor configurado en este entorno), pruebas con un SMTP real y pruebas con una app cliente real.

## 11. Limitaciones, riesgos y pendientes

- **PostgreSQL:** los bloqueos (`select_for_update`) no se han probado en PostgreSQL (los tests usan SQLite, que los ignora). Las restricciones únicas garantizan la integridad igualmente.
- **Throttling por proceso:** con la caché en memoria por defecto, cada proceso cuenta por separado. En producción, `CACHE_URL` compartida.
- **Access tras cerrar sesión:** sigue valiendo hasta 15 min tras `logout`/`logout-all` (no tras cambiar la contraseña o desactivar la cuenta, que son inmediatos). Si se necesitara inmediatez total, habría que consultar la lista negra en cada petición.
- **Sin detección de reutilización del refresh** (revocar todo si se presenta uno ya rotado): se descartó para no expulsar al usuario por reintentos legítimos de red; candidato a mejora.
- **Refresh en la BD:** la lista negra de simplejwt guarda los refresh emitidos; quien tenga acceso de lectura a la BD podría usarlos hasta su caducidad (salvo cambio de contraseña). Restringir el acceso a la BD y a sus copias; programar `flushexpiredtokens`.
- **Enlace de recuperación:** el formato nativo de Django lleva la PK interna codificada en base64 (`uidb64`). Se acepta por usar el mecanismo nativo y mantenido.
- **Swagger UI** carga su JavaScript desde un CDN (jsDelivr). Solo lo usa el propietario fuera de desarrollo; el esquema YAML no depende del CDN.
- **Enlaces universales / App Links** (verificación y recuperación desde la app): requieren publicar `apple-app-site-association` y `assetlinks.json` cuando exista la app.
- **Notificaciones push:** no implementadas; serían un canal más en `notifications` con su propio consentimiento.
- **Endpoints pendientes** previstos en fases anteriores y no incluidos: carta (Fase 4), resultados propios del personal (Fase 8), gestión completa del propietario (Fase 9) y campañas (Fase 10).
- **Datos personales y RGPD:** siguen pendientes la política de conservación, el borrado/anonimización y la exportación de datos de la cuenta (decisión del propietario con asesoría). Este código no garantiza por sí mismo el cumplimiento legal.
- Pendientes heredados: SMTP real, programar las tareas, proveedor de SMS, servidor WSGI y almacenamiento de estáticos/medios ([despliegue.md](despliegue.md)).

## 12. Criterios de aceptación

| Criterio | Estado |
|---|---|
| Auditoría de las áreas pedidas y corrección de los problemas reales | Completa (§2–3) |
| DRF configurado en `/api/v1/` | Completa |
| Endpoints de registro, verificación, login, recuperación, perfil, cambio de email, saldo, movimientos, compras, recompensas, canjes, QR, eventos y reservas | Completa (§4.3) |
| Solo operaciones administrativas justificadas y protegidas | Completa (§4.3) |
| Serializadores explícitos; sin campos protegidos modificables | Completa (tests de asignación masiva) |
| Un cliente solo consulta sus propios datos | Completa (tests IDOR) |
| Mismos servicios que la web | Completa (las vistas solo llaman a servicios/selectores) |
| Autenticación móvil con tokens limitados, renovación y revocación, sin cookies | Completa (§5) |
| Privacidad en la API | Completa (§7) |
| Documentación OpenAPI y guía Flutter | Completa |
| Revisión de seguridad y de despliegue | Completa (§6, [despliegue.md](despliegue.md)); validación en PostgreSQL pendiente |
| Pruebas ejecutadas | Completa en SQLite (§10) |

**Dependencias para la fase siguiente (despliegue):** elegir servidor WSGI y almacenamiento de estáticos/medios, configurar PostgreSQL, caché compartida, SMTP y tareas programadas, y repetir la suite contra PostgreSQL.
