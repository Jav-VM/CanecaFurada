# Fase 7 — Recompensas y canjes

**Estado:** Completa (pendiente de confirmar el plazo de recogida; ver §11). La concurrencia con bloqueos de fila se validó en PostgreSQL 17 el 2026-10-15: los 3 tests de `test_concurrency.py` pasan ([migracion-postgresql.md](migracion-postgresql.md)).
**Fecha:** 2026-10-14.
**Depende de:** [Fase 6](fase-06-fidelizacion.md) (ledger de puntos) y [Fase 5](fase-05-qr-compras.md) (panel del personal y lector QR).

## 1. Objetivo y decisiones

Crear el catálogo de recompensas y el sistema de canje: el cliente cambia puntos por una recompensa y recibe un código de un solo uso que el personal valida en la barra. El canje y el descuento de puntos forman una única operación transaccional, registrada en el ledger.

No se detectaron contradicciones entre el prompt de la fase, el [plan](plan-de-fases.md) y la [arquitectura](arquitectura.md) (que ya preveía la app `apps.rewards`). Decisiones adoptadas, con su motivo:

| Cuestión no especificada | Decisión | Motivo |
|---|---|---|
| ¿Cuándo se descuentan los puntos? | **Al solicitar el canje**, en la misma transacción que crea el canje y su código | Un código emitido siempre está respaldado por puntos: el saldo no puede gastarse dos veces mientras el código espera a ser recogido. Era lo previsto en la Fase 6 (§13) |
| ¿Qué pasa con un código que no se recoge? | **Caduca** a los `REWARDS_CODE_VALIDITY_DAYS` días (30 por defecto, **pendiente de confirmar por el propietario**) y los puntos se devuelven con un movimiento compensatorio | Evita puntos bloqueados para siempre; el plan pedía tests de "código caducado" |
| ¿Puede el cliente arrepentirse? | **Sí**, cancela un canje pendiente y recupera los puntos | Mismo mecanismo que la caducidad; sin él, un canje por error bloquearía puntos 30 días |
| "Ausencia de duplicados" | Referencia de idempotencia generada por el servidor (doble envío o reintento) **y** como máximo **un código pendiente por cliente y recompensa** (restricción única en BD) | Cubre el doble clic, el reintento y dos pestañas a la vez |
| "Disponibilidad" | Unidades (`stock`) opcionales: vacío = sin límite. Baja con cada canje y sube si se cancela o caduca | Lo más sencillo que permite agotar una recompensa |
| "Estado" | `DRAFT`, `ACTIVE`, `PAUSED`, `ARCHIVED`. Solo `ACTIVE` se ve y se canjea | Mismo patrón que la carta y las promociones; nada se borra |
| ¿Se puede validar un código si la recompensa se pausa o termina su periodo? | **Sí**, mientras el código esté vigente | El cliente ya pagó con puntos; las fechas y el estado limitan las **solicitudes**, no la entrega |
| Gestión del catálogo | En el admin de Django (solo propietario), como la carta | El dashboard propio llega en la Fase 9 |
| Datos visibles para el personal | Recompensa, estado, fechas y el nombre corto del cliente («Lúa F.») | Lo mínimo para entregar la recompensa y confirmar que el código es suyo, igual que en las compras |

## 2. Alcance y exclusiones

**Incluye:** modelos `Reward` y `Redemption`; catálogo público en `/recompensas/`; solicitud de canje, historial, estado y cancelación para el cliente; panel del personal para validar códigos (escaneo o tecleo); caducidad con devolución de puntos (en la validación y con el comando `expire_redemptions`); descuento y devolución en el ledger; auditoría; admin del propietario; API documentada (§8); tests.

**Excluye:**
- Programación periódica de `expire_redemptions` y notificaciones de canje por email (Fase 10).
- Interfaz propia de gestión y estadísticas de canjes (Fase 9; hoy, admin).
- API REST (Fase 11).
- Límites por cliente (p. ej. "una vez al mes") distintos del pendiente único: no se pidieron.

## 3. Proceso de canje

```text
Cliente                         Servidor                                  Personal
  │  /recompensas/ → «Canjear»     │                                         │
  │  GET /cuenta/recompensas/<id>/ │ saldo, coste, ¿puede canjear?           │
  │  POST …/canjear/ (ref. idem.) ─▶ TRANSACCIÓN:                            │
  │                                │  bloquea cliente → recompensa           │
  │                                │  revalida todo (§3.1)                   │
  │                                │  −1 unidad, movimiento REDEMPTION       │
  │                                │  crea canje PENDING + código            │
  │  ◀── /cuenta/canjes/<id>/: QR y código «ABCD-EFGH-JKMN»                  │
  │  enseña el QR en la barra ───────────────────────────────────────────────▶ /panel/canjes/
  │                                │ ◀── POST consultar/ (código)  → recompensa, estado, «Lúa F.»
  │                                │ ◀── POST validar/ (código)                │
  │                                │  UPDATE … SET USED WHERE status=PENDING  │
  │                                │  validated_by, validated_at, auditoría   │
  │                                │ ──▶ «Canje validado. Entrega la recompensa.»
```

### 3.1 Validaciones de la solicitud (servidor)
`services.request_redemption(customer, reward, idempotency_key)`, dentro de la transacción y con las filas bloqueadas:

| Validación | Error (`code`) |
|---|---|
| Cliente autenticado, activo, rol `CUSTOMER` y email verificado | `PermissionDenied` |
| Referencia de idempotencia válida | `idempotency_invalid` |
| Misma referencia con otros datos | `idempotency_conflict` |
| Recompensa `ACTIVE` y dentro de `valid_from`/`valid_until` | `reward_unavailable` |
| Sin otro código pendiente de esa recompensa | `duplicate_pending` |
| Unidades disponibles (resta condicionada `stock >= 1`) | `out_of_stock` |
| Saldo suficiente, recalculado dentro de la transacción | `insufficient_points` |

El coste, los puntos, el cliente y el estado **nunca** llegan del navegador: el formulario solo envía la referencia de idempotencia; el servicio no acepta otros argumentos (`TypeError`) y la vista ignora campos extra (test). El canje guarda una copia del coste: cambiarlo después no afecta a los canjes existentes.

### 3.2 Código
- 12 caracteres elegidos con `secrets` de un alfabeto de 31 símbolos sin los que se confunden (0/O, 1/I/L): ≈59 bits; no se puede adivinar ni deducir de otros códigos. No contiene datos del cliente ni de la recompensa.
- Se muestra como QR (`CFR1:<código>`, generado en el servidor con `segno`) y como texto `ABCD-EFGH-JKMN`. El prefijo es distinto del QR personal (`CF1:`): un QR leído en el panel equivocado se rechaza.
- Único en BD (`UNIQUE` + `CHECK` de formato). Solo se muestra al cliente mientras está pendiente y vigente.
- Nunca aparece en URLs, logs, auditoría, mensajes de error ni en el admin (tests).

### 3.3 Estados del canje

| Estado | Significado | Transición |
|---|---|---|
| `PENDING` (Pendiente de recoger) | Puntos descontados, código vigente | Al solicitar |
| `USED` (Canjeado) | Entregado; guarda `validated_by` y `validated_at` | Validación del personal, solo desde `PENDING` y antes de caducar |
| `CANCELLED` (Cancelado) | Puntos y unidad devueltos | El cliente, solo desde `PENDING` |
| `EXPIRED` (Caducado) | Puntos y unidad devueltos | Al intentar validarlo o consultarlo fuera de plazo, o con `expire_redemptions` |

`USED`, `CANCELLED` y `EXPIRED` son finales. Las coherencias están también en la BD (`CHECK`): `USED` ⇔ con quién y cuándo; `CANCELLED`/`EXPIRED` ⇔ con movimiento de devolución y fecha; quien valida no puede ser el propio cliente.

### 3.4 Validación por el personal
1. `/panel/canjes/` (empleados y propietarios): escanear con la cámara (mismo lector que las compras) o teclear el código.
2. `services.lookup_redemption`: muestra recompensa, estado, fechas y el nombre corto del cliente. **No valida.** Si el código ya venció, lo caduca y devuelve los puntos.
3. `services.validate_redemption`: pasa el canje a `USED` con un `UPDATE … WHERE status = 'PENDING' AND expires_at > ahora`. De dos validaciones simultáneas solo una cambia la fila; la otra recibe "Este código ya se utilizó el dd/mm/aaaa hh:mm". Se registra el evento de auditoría `REDEMPTION_VALIDATED` (personal, canje, recompensa y puntos; sin el código).
4. Errores: `invalid_code` (no existe o el cliente ya no está activo; mismo mensaje), `code_used`, `code_expired`, `code_not_pending` (cancelado). Tras `REWARDS_MAX_CODE_FAILURES` códigos no válidos seguidos en `REWARDS_CODE_FAILURE_WINDOW_SECONDS`, ese miembro del personal debe esperar (429).

### 3.5 Puntos en el ledger
- **Canje:** `ledger.spend_points` crea un movimiento `REDEMPTION` negativo con el saldo resultante; si no alcanza, `InsufficientPoints` y toda la transacción (unidad incluida) se deshace.
- **Devolución:** `ledger.refund_spent_points` crea una compensación (`REVERSAL`, `reverses` = el movimiento del canje), una sola vez (`OneToOne`). `created_by` es el cliente si cancela y vacío si caduca.
- **Validar no toca los puntos:** ya se descontaron al solicitar.
- **"Mis puntos":** *Utilizados* = canjes menos devoluciones de canjes; *Obtenidos* no incluye esas devoluciones. Se mantiene saldo = obtenidos − utilizados − corregidos. La devolución aparece como "Devolución de canje". Las estadísticas del propietario (`points_stats`) usan las mismas definiciones.

## 4. Concurrencia, duplicados e integridad

| Riesgo | Medida |
|---|---|
| Doble envío o reintento de la solicitud | Referencia de idempotencia única: se devuelve el canje existente sin descontar otra vez |
| Dos solicitudes simultáneas de la misma recompensa | Comprobación con filas bloqueadas + `UNIQUE (cliente, recompensa) WHERE status = PENDING` |
| Gastar el mismo saldo dos veces | Bloqueo de la fila del cliente y saldo recalculado dentro de la transacción; `CHECK balance_after >= 0` del ledger |
| Última unidad pedida a la vez | Bloqueo de la recompensa y resta condicionada (`stock >= 1`) + `CHECK stock >= 0` |
| Fallo a mitad de la operación | Una sola transacción: sin canje no hay movimiento ni unidad restada (tests con fallo en el `INSERT`) |
| Doble validación del código | `UPDATE` condicionado al estado `PENDING`: solo una petición cambia la fila |
| Cancelar o caducar mientras se valida | La devolución se deshace si el `UPDATE` condicionado no cambia la fila; nunca se devuelve un canje entregado |
| Devolver dos veces | `refund_movement` y `reverses` son `OneToOne`; cancelar o caducar dos veces no hace nada |

Orden de bloqueo, siempre el mismo: cliente → recompensa → canje.

## 5. Cómo probarlo (desarrollo)

```powershell
python manage.py migrate
python manage.py runserver
```

1. Sigue la [guía de la Fase 5](fase-05-qr-compras.md#5-cómo-probar-el-flujo-de-compra) para tener un empleado y un cliente verificado con datos ficticios, y registra alguna compra para que tenga puntos.
2. Como propietario, admin → *Recompensas* → *Añadir*: "Caña de la casa", 10 puntos, estado *Activa*, desde ahora (unidades vacías = sin límite).
3. Con la sesión del cliente, abre `/recompensas/` → *Canjear* → *Canjear por 10 puntos*. Verás el QR y el código; en *Mis puntos* el saldo baja y aparece el canje.
4. Con la sesión del empleado, *Mi cuenta* → **Validar canje** (`/panel/canjes/`): escanea el QR o teclea el código → *Validar y entregar*.
5. Repite el paso 4 con el mismo código: "Este código ya se utilizó…".
6. Pide otro canje y cancélalo desde *Mis canjes*: recuperas los puntos ("Devolución de canje").
7. Caducidad: `python manage.py expire_redemptions` caduca los vencidos y devuelve los puntos.

## 6. Seguridad y privacidad

- **Servidor como única fuente:** coste, saldo, unidades, estado y código se deciden en el servidor con las filas bloqueadas.
- **Autorización en cada operación:** solicitar, ver y cancelar exigen cliente activo con email verificado (en la vista y en el servicio); los canjes se buscan siempre filtrando por `request.user` y los ajenos dan 404 (sin revelar que existen). Consultar y validar: solo empleados y propietarios activos (en el servicio); el detalle de un canje validado lo ve quien lo validó o el propietario. Gestión del catálogo: solo propietario (`save_reward`). Tests de denegación para anónimo, cliente no verificado, empleado, propietario e IDOR.
- **CSRF:** todas las operaciones son `POST` con token; las vistas de lectura son `GET`.
- **Código:** aleatorio de `secrets`, de un solo uso, con caducidad, fuera de URLs, logs, auditoría y admin; límite de intentos fallidos por miembro del personal.
- **Exposición mínima:** el personal ve el nombre corto del cliente, nunca su email, teléfono, saldo, dirección ni fecha de nacimiento (test). El cliente no ve quién validó su canje.
- **Sin caché** (`never_cache`) en las páginas con códigos o saldos.
- **Logs** solo con identificadores públicos y puntos (test con `assertLogs`).
- **Auditoría:** `REWARD_SAVED` (campos cambiados, sin textos) y `REDEMPTION_VALIDATED`. Las solicitudes, cancelaciones y caducidades quedan en el ledger y en el propio canje.
- **Imágenes:** mismos validadores que la carta (contenido real JPEG/PNG/WebP, tamaño y dimensiones) y nombre aleatorio.

## 7. Configuración

- **Migraciones:** `rewards/0001_rewards_redemptions` (dos tablas nuevas con sus restricciones) y `core/0006_audit_actions_phase7` (dos acciones nuevas en los `choices`, sin tocar datos). Aditivas y reversibles (probado: aplicar → revertir → aplicar sobre una copia de la BD de desarrollo). Ejecuta `python manage.py migrate`.
- **Settings nuevos** en `base.py` (no son variables de entorno): `REWARDS_CODE_VALIDITY_DAYS` (30, pendiente de confirmar), `REWARDS_MAX_CODE_FAILURES` (20), `REWARDS_CODE_FAILURE_WINDOW_SECONDS` (900). El límite de intentos usa la caché (`CACHE_URL`); en producción con varios procesos debe ser compartida (igual que en la Fase 5).
- **App nueva** `apps.rewards` en `INSTALLED_APPS`.
- **Rutas nuevas:** `/cuenta/recompensas/<id>/`, `/cuenta/recompensas/<id>/canjear/`, `/cuenta/canjes/`, `/cuenta/canjes/<id>/`, `/cuenta/canjes/<id>/cancelar/` y `/panel/canjes/` (`consultar/`, `validar/`, `<id>/`).
- **Comando:** `python manage.py expire_redemptions` (para programarlo periódicamente en la Fase 10/12; no es imprescindible para la seguridad).
- **Sin dependencias nuevas.**

## 8. Preparación para la app y la API (Fase 11)

Los servicios no dependen de la petición ni de las plantillas:

| Módulo | Uso |
|---|---|
| `rewards.services` | `request_redemption`, `cancel_redemption`, `lookup_redemption`, `validate_redemption`, `expire_pending_redemptions`, `save_reward`, `visible_redemptions_for_staff` |
| `rewards.selectors` | `public_rewards`, `public_reward`, `customer_redemptions`, `customer_redemption`, `pending_redemption_for`, `recent_validations_by` |
| `rewards.codes` | Formato, normalización y contenido del QR del código |
| `loyalty.ledger` | `spend_points`, `refund_spent_points` (solo desde `rewards.services`) |

Endpoints propuestos:

| Endpoint | Quién | Servicio | Respuesta / notas |
|---|---|---|---|
| `GET /api/v1/rewards/` | Público | `public_rewards()` | `public_id`, `name`, `description`, `image_url`, `points_cost`, `valid_until`, `in_stock` (sin el número de unidades si no se quiere publicar) |
| `POST /api/v1/rewards/{public_id}/redeem/` | Cliente verificado | `request_redemption(request.user, reward, key)` | Cabecera `Idempotency-Key` (UUID generado por la app). 201 con el canje; 200 si es un reintento |
| `GET /api/v1/me/redemptions/?page=N` | Cliente verificado | `customer_redemptions(request.user)` | `public_id`, `reward` (`public_id`, `name`), `points_cost`, `status`, `created_at`, `expires_at`, `validated_at` |
| `GET /api/v1/me/redemptions/{public_id}/` | Cliente verificado | `customer_redemption(request.user, id)` | Lo anterior + `code` y `qr_payload` **solo** si está pendiente y vigente; 404 si no es suyo |
| `POST /api/v1/me/redemptions/{public_id}/cancel/` | Cliente verificado | `cancel_redemption` | 200 con el canje |
| `POST /api/v1/staff/redemptions/lookup/` | Personal | `lookup_redemption` | Cuerpo `{"code": "…"}` (nunca en la URL). Campos de `RedemptionPreview` |
| `POST /api/v1/staff/redemptions/validate/` | Personal | `validate_redemption` | Cuerpo `{"code": "…"}` |

Errores: `PermissionDenied` → 403; `insufficient_points`, `reward_unavailable`, `out_of_stock`, `invalid_code`, `code_expired` y demás `ValidationError` → 400 con `code`; `duplicate_pending`, `code_used`, `code_not_pending` e `idempotency_conflict` → 409; `TooManyFailedAttempts` → 429. Nunca exponer `id`, `idempotency_key`, `spend_movement`, `refund_movement` ni datos del cliente en los endpoints del personal más allá del nombre corto.

## 9. Archivos creados o modificados

- **Nueva app `apps/rewards/`:** `models.py` (`Reward`, `Redemption`), `codes.py`, `services.py`, `selectors.py`, `forms.py`, `views.py`, `urls.py` (cliente), `panel_urls.py` (personal), `admin.py`, `apps.py`, `management/commands/expire_redemptions.py`, `migrations/0001_rewards_redemptions.py`.
- **`apps/loyalty/`:** `ledger.py` (`lock_customer`, `spend_points`, `refund_spent_points`; la compensación común se extrajo a `_compensate` sin cambiar el comportamiento de `reverse_movement`), `selectors.py` (utilizados/obtenidos netos de devoluciones de canjes), `models.py` (solo el comentario de `REDEMPTION`; sin migración).
- **`apps/core/`:** `models.py` (acciones `REWARD_SAVED`, `REDEMPTION_VALIDATED`) y `migrations/0006_audit_actions_phase7.py`.
- **`apps/web/views.py`:** la página Recompensas muestra el catálogo real.
- **Configuración:** `config/settings/base.py`, `config/urls.py`.
- **Plantillas:** nuevas `templates/rewards/` (`reward_detail`, `redemption_detail`, `my_redemptions`, `staff_scan`, `staff_confirm`, `staff_detail`); `web/rewards.html` (catálogo; "Cómo funciona" sin "Próximamente"), `accounts/profile.html` y `loyalty/my_points.html` (enlaces y "Devolución de canje"), `accounts/staff_home.html` (botón *Validar canje*). `static/css/app.css` recompilado.
- **Tests:** nuevos `tests/rewards/` (`factories.py`, `test_services.py`, `test_views.py`, `test_concurrency.py`).
- **Documentación:** este documento, `README.md`, `plan-de-fases.md`, `arquitectura.md`.

## 10. Tests y resultados reales

Nuevos (83):
- **Servicios** (`test_services.py`, 54): códigos (aleatorios, únicos en 2000 muestras, formato, sin caracteres ambiguos, normalización del QR y del texto, rechazo del QR personal); solicitud (descuento y movimiento, caducidad configurable, **saldo insuficiente** sin efectos, saldo exacto, estados y fechas de la recompensa, unidades y agotada, resta condicionada, sin límite, **pendiente único**, nuevo canje tras usar el anterior, **reintento sin doble cargo**, conflicto de referencia, referencia no válida, **carreras simuladas** con la misma referencia y con referencias distintas, rollback de puntos y unidades si falla el `INSERT`, bloqueo del cliente, puntos no aceptados del cliente, coste copiado, **permisos**, logs sin código ni datos personales); validación (registro de quién y cuándo con auditoría, propietario, **doble canje** rechazado, **validación concurrente simulada**, **código no válido**, límite de intentos por miembro del personal, cliente inactivo, **código caducado** con devolución, cancelado, **solo personal**, datos mínimos de la consulta, código usado no validable); cancelación y caducidad (devolución de puntos y unidad, idempotencia, canje ajeno o usado, carrera cancelar/validar sin devolución, comando `expire_redemptions` solo sobre vencidos); resumen de puntos neto de devoluciones; restricciones de BD (pendiente único, `USED` con quién/cuándo, cierre con devolución, formato y unicidad del código, autovalidación, coste y fechas de la recompensa); `save_reward` (auditoría, permisos, validación).
- **Vistas y admin** (`test_views.py`, 26): catálogo público (solo activas en periodo, agotadas, estado vacío); login, 403 para no verificados, empleados y propietarios; 404 para recompensas ocultas; flujo completo con QR y código fuera de la URL; doble envío; saldo insuficiente también forzando el `POST`; asignación masiva ignorada; `POST` obligatorio y referencia válida; recompensa retirada antes de confirmar; pendiente existente; historial propio e **IDOR** (ver y cancelar canjes ajenos → 404); código oculto tras usarlo o caducar; cancelación y "Devolución de canje" en *Mis puntos*; panel del personal (acceso, datos mínimos sin email ni saldo, flujo de validación y uso único, mensaje genérico, visibilidad del detalle, enlace en *Mi cuenta*); admin (alta auditada, sin borrado, canjes de solo lectura sin el código, sin acceso para empleados).
- **Concurrencia real con hilos** (`test_concurrency.py`, 3): 4 hilos validando el mismo código, 4 canjes simultáneos que superarían el saldo y 4 solicitudes simultáneas de la misma recompensa. Se omiten con la BD de test en memoria (la de por defecto).

| Comando o prueba (SQLite, Python 3.14.2, Django 5.2.18) | Resultado |
|---|---|
| `python manage.py check` | Sin incidencias |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| `python manage.py test --settings=config.settings.test` | **549 tests, OK (3 omitidos: los de hilos)** (466 anteriores + 83 nuevos) |
| `tests.rewards.test_concurrency` con una BD de test SQLite **en fichero** (settings temporales fuera del repositorio, `DATABASES["default"]["TEST"]["NAME"]`), 5 ejecuciones seguidas de la versión final | 3 tests OK en las 5 |
| `migrate` → revertir (`rewards zero`, `core 0005`) → `migrate` sobre una copia temporal de la BD de desarrollo; `expire_redemptions` | OK; "Canjes caducados: 0" |
| `check --deploy --settings=config.settings.prod` (variables ficticias) | Solo `W021` (HSTS preload, intencionado, ya existente) |
| `python scripts/tailwind.py build` | OK |

**Qué demuestran y qué no las pruebas con hilos:** en SQLite, de cada 4 hilos uno completa la operación y los otros 3 los rechaza la propia BD con `database is locked` (SQLite solo admite un escritor). Así que demuestran que no hay doble consumo ni saldo negativo con peticiones simultáneas reales, pero **no** ejercitan los bloqueos de fila (`select_for_update` no hace nada en SQLite) ni los `UPDATE` condicionados bajo concurrencia. Esas carreras a nivel de negocio están cubiertas con simulaciones y con las restricciones de BD. En PostgreSQL las mismas pruebas se ejecutan sin omitirse y no admiten errores de bloqueo.

**No probado:** concurrencia con PostgreSQL; escaneo del QR del canje en dispositivos físicos (el lector es el de la Fase 5, sin cambios); revisión visual manual en el navegador (las páginas se renderizan en los tests).

## 11. Limitaciones, riesgos y pendientes

- **Concurrencia en PostgreSQL** pendiente de verificar (Fase 12): ejecutar `tests.rewards.test_concurrency` con `DATABASE_URL` de PostgreSQL. La integridad la garantizan además las restricciones únicas, los `CHECK` y los `UPDATE` condicionados.
- **Plazo de recogida** (30 días) pendiente de confirmar por el propietario (`REWARDS_CODE_VALIDITY_DAYS`).
- **Caducidad sin programar:** hasta la Fase 10, los puntos de un código vencido se devuelven cuando alguien intenta usarlo o al ejecutar `expire_redemptions` a mano. El código vencido nunca se acepta.
- **El código es "al portador":** quien lo tenga puede recogerlo. Mitigación: el personal ve el nombre corto del cliente y se le indica que lo confirme; el cliente puede cancelarlo.
- **Límite de intentos por proceso** con la caché en memoria por defecto (igual que la Fase 5): en producción, caché compartida.
- **Sin notificaciones** de canje (Fase 10) ni interfaz de gestión fuera del admin (Fase 9).
- **Textos legales** del programa (bases, condiciones de las recompensas) los aporta el propietario.
- El bloque "Programa de puntos" del Inicio sigue mostrando "Próximamente" (es contenido de la Fase 3, fuera del alcance de esta fase); conviene revisarlo con el propietario.

## 12. Estado de los criterios de aceptación

| Criterio | Estado |
|---|---|
| Recompensa con nombre, descripción, imagen, coste, estado, fechas de validez y disponibilidad | Completo |
| Cliente: consultar recompensas, solicitar canjes, historial y estado | Completo (además, cancelar) |
| Servidor valida autenticación, recompensa activa, disponibilidad, periodo, saldo y duplicados | Completo (§3.1, con tests) |
| Transacciones y controles de concurrencia | Completo (bloqueos, `UPDATE` condicionados, restricciones; concurrencia real en PostgreSQL pendiente) |
| Código único, impredecible y de un solo uso | Completo (`secrets`, ≈59 bits, `UNIQUE`, `UPDATE` condicionado) |
| El empleado valida desde su panel; un código usado no se reutiliza | Completo (`/panel/canjes/`) |
| Registro de quién realizó el canje y cuándo | Completo (`validated_by`, `validated_at`, auditoría) |
| Deducción registrada en el ledger, coherente y transaccional con el canje | Completo (`REDEMPTION` y devolución con `REVERSAL`) |
| Sin información personal innecesaria durante el canje | Completo (nombre corto; test) |
| Servicios reutilizables desde la futura API | Completo (§8) |
| Pruebas de saldo insuficiente, código inválido, doble canje, concurrencia y permisos | Completo (83 tests) |
| Proceso de canje documentado | Completo (§3) |

## 13. Dependencias para las fases siguientes

- **Fase 8 (Eventos y reservas):** sin dependencias de esta fase.
- **Fase 9 (Dashboard):** interfaz de gestión de recompensas y canjes sobre `save_reward`, `visible_redemptions_for_staff` y los selectores; estadísticas de canjes a partir de `points_stats` (ya incluye los utilizados netos).
- **Fase 10 (Notificaciones):** programar `expire_redemptions`; avisos de canje y de caducidad próxima.
- **Fase 11 (API):** endpoints de §8.
- **Fase 12:** ejecutar `tests.rewards.test_concurrency` contra PostgreSQL.

### Cómo ejecutar las pruebas con hilos en local
Crea, **fuera del repositorio**, un módulo de settings que herede de `config.settings.test` y defina `DATABASES["default"]["TEST"] = {"NAME": "<ruta temporal>.sqlite3"}`, y ejecútalo con `PYTHONPATH=<su carpeta>`:

```powershell
$env:PYTHONPATH="C:uta	emporal"; python manage.py test tests.rewards.test_concurrency --settings=test_settings_file --noinput
```
