# Fase 10 — Eventos, reservas, contenido y notificaciones

**Estado:** Completa (pendiente de configurar un proveedor SMTP real y programar las tareas en el servidor, de validar en PostgreSQL y de la revisión visual en navegador; ver §13).
**Fecha:** 2026-10-14.
**Depende de:** Fases 2 (cuentas, verificación, preferencias), 3 (sistema de diseño), 6 (ledger y cumpleaños), 7 (canjes) y 9 (dashboard).

## 1. Objetivo y decisiones

Completar eventos, reservas con confirmación manual, edición de los contenidos principales de la web y un sistema reutilizable de notificaciones (verificación del email, recuperación de la cuenta, reservas, transaccionales, promociones autorizadas y cumpleaños).

**Ajuste de alcance (decidido por el usuario con el prompt de la fase):** el [plan](plan-de-fases.md) tenía las notificaciones y el envío de cumpleaños como fase «sin número»; el prompt de la Fase 10 los incluye, así que se implementan aquí. La fase «Endurecimiento y despliegue» sigue sin número.

Decisiones del usuario al empezar la fase (2026-10-14):

| Cuestión | Decisión |
|---|---|
| ¿Qué se reserva y quién? | **Mesa o plaza en un evento**, solo **clientes con email verificado**. No se piden datos personales nuevos: el contacto es el del perfil. |
| Cumpleaños: la Fase 6 daba la bonificación al registrar una compra en la ventana del cumpleaños; el prompt pide que el flujo «cree la recompensa o beneficio» | **Regalo de puntos el día del cumpleaños** (movimiento nuevo `BIRTHDAY_GIFT`). Se concede a todo cliente activo con email verificado; el consentimiento solo condiciona el aviso. La bonificación en compra se retira para no duplicar. |
| Tareas programadas | **Comandos de gestión + programador del sistema** (cron / Programador de tareas de Windows) con una cola de notificaciones en la base de datos. Sin Celery ni Redis. |
| Promociones autorizadas y contenido | **Campañas por email** (SMS solo con proveedor) redactadas por el propietario en el dashboard y **textos del inicio editables**. |

Otras decisiones (menores, adoptadas y documentadas aquí):

| Cuestión | Decisión | Motivo |
|---|---|---|
| ¿Quién confirma las reservas? | Solo el **propietario**, desde el dashboard. | Confirmación manual pedida; los empleados no ven datos de clientes (Fase 8). |
| Aforo | Lo ocupan solo las reservas **confirmadas**; se comprueba al solicitar y otra vez al confirmar con el evento bloqueado. | Las pendientes pueden superar el aforo: decide el propietario. |
| Reservas de mesa | Antelación mínima de 2 h, máximo 90 días, 1–20 personas, máximo 3 reservas activas por cliente, 10 solicitudes por hora. Ajustables en `config/settings/base.py`. | Valores razonables pendientes de confirmar por el propietario. El horario del local es texto libre y no se valida contra él. |
| Cambiar la hora de un evento | Las reservas activas pasan a la nueva hora; **no** se avisa automáticamente. | Evita reservas con una hora falsa; el aviso lo decide el propietario. |
| Mensajes de cuentas (verificación, cambio de email, recuperación, avisos de seguridad) | Se envían **al momento** y se registran **sin contexto ni destinatario**; no se reintentan. | Llevan un enlace con token: guardarlo para reintentar lo expondría. El usuario pide otro enlace. |
| Avisos de reservas | Se encolan y se envían al confirmar la transacción; si el proveedor falla, los reintenta `process_notifications`. | El cliente recibe el aviso al momento y no se pierde si el SMTP cae. |
| Promociones | Solo las envía `process_notifications`, nunca la petición web. Sin saludo por el nombre y siempre con enlace de baja. | Prompt: no enviar campañas masivas desde la web; minimización de datos. |
| Baja | Enlace firmado por Django (`signing`, 365 días) que pide confirmar con un botón; también desde el perfil. | Retirar el consentimiento debe ser sencillo; el botón evita bajas por antivirus que abren enlaces. |
| SMS | Interfaz `SMS_BACKEND` sin proveedor real. Sin proveedor no se crea ningún SMS. | Prompt: no afirmar que los SMS funcionan sin proveedor. |

## 2. Alcance y exclusiones

**Incluye:** apps `apps.events` (eventos y reservas) y `apps.notifications` (registro, envío, campañas, baja); regalo de cumpleaños en `apps.loyalty`; integración de los emails de cuentas en el registro de notificaciones; textos del inicio editables; secciones Eventos, Reservas y Comunicaciones del dashboard; páginas públicas de eventos y de reservas del cliente; comandos `process_notifications` y `run_birthday_promotions`; tests y documentación.

**Excluye:**
- Proveedor de SMS real (solo la interfaz).
- Recordatorios automáticos de reservas, lista de espera y reservas sin cuenta.
- Gestión de reservas por empleados.
- Emails HTML (todos son texto plano, como los de la Fase 2).
- API REST (Fase 11; ver §10).
- Configuración del servidor de correo y del programador de tareas en producción (fase de despliegue).

## 3. Eventos

- Modelo `events.Event`: título, resumen, descripción, inicio y fin, imagen opcional (mismas validaciones que la carta), destacado en el inicio, admite reservas, plazas (vacío = sin límite) y estado.
- Estados: `DRAFT` (borrador) → `PUBLISHED` (publicado) → `ARCHIVED` (archivado); desde publicado se puede volver a borrador y desde archivado recuperar como borrador. Solo se publica un evento que no ha empezado. **Nada se borra.**
- Gestión: dashboard `/dashboard/eventos/` (crear, editar, publicar, retirar, archivar). El admin permite editar la ficha (pasa por el mismo servicio) pero no cambiar el estado.
- Web pública: `/eventos/` lista los publicados que no han terminado (sin hora de fin, se dan por terminados a las 6 h de empezar) y `/eventos/<id>/` su detalle, con plazas libres y botón de reserva. El inicio muestra hasta 3 destacados (o los próximos si no hay destacados).

## 4. Reservas

### Flujo

1. El cliente (email verificado) pide mesa en `/cuenta/reservas/nueva/` (día, hora, personas, comentarios) o plaza en un evento desde su página. La reserva queda **PENDING**.
2. Recibe «Hemos recibido tu solicitud» y los propietarios un aviso **sin datos del cliente** con enlace al dashboard.
3. El propietario la abre en `/dashboard/reservas/<id>/` (ve nombre, email y teléfono; la consulta queda auditada) y la **confirma**, **rechaza** o **cancela**, con un mensaje opcional para el cliente. Cada cambio envía un email al cliente.
4. A partir del día de la reserva puede marcarla **completada**.
5. El cliente ve sus reservas en `/cuenta/reservas/` y puede cancelar una pendiente o confirmada antes de la hora (se avisa también al propietario).

### Estados y transiciones (validadas en el servidor con la fila bloqueada)

| Desde | Puede pasar a | Quién |
|---|---|---|
| `PENDING` | `CONFIRMED`, `REJECTED`, `CANCELLED` | Propietario (y el cliente, a `CANCELLED`) |
| `CONFIRMED` | `CANCELLED`, `COMPLETED` | Propietario (y el cliente, a `CANCELLED`) |
| `REJECTED`, `CANCELLED`, `COMPLETED` | — (finales) | — |

Repetir la misma transición no hace nada (doble clic). Confirmar exige que la fecha no haya pasado y que quepa en el aforo; completar, que haya llegado su día; el cliente no cancela después de la hora.

### Integridad y anti-abuso

- `idempotency_key` única: un doble envío del formulario devuelve la misma reserva sin duplicar avisos.
- Restricción única en BD: **una reserva activa por cliente y evento**.
- El cliente se bloquea al solicitar (límite de reservas activas) y el evento al confirmar (aforo).
- Límite de solicitudes por cliente y hora (`EVENTS_RESERVATION_MAX_REQUESTS_PER_HOUR`).
- Las comprobaciones de concurrencia se basan en `select_for_update`, que SQLite ignora: hay que validarlas en PostgreSQL.

### Privacidad de las reservas

- La reserva no copia datos personales: el contacto sale del perfil y solo aparece en el detalle del dashboard (auditado con `RESERVATION_DATA_VIEWED`, sin los datos).
- El listado del dashboard muestra nombre y primera inicial del apellido, sin email ni teléfono. Los empleados no tienen acceso.
- Los emails no incluyen comentarios, teléfonos ni direcciones; el aviso al propietario no lleva el nombre del cliente.
- El cliente solo accede a sus reservas: una ajena responde 404.
- Los comentarios advierten de no incluir datos de salud ni otros datos sensibles.

## 5. Contenido editable

`/dashboard/contenido/` (Fase 9) añade **texto de bienvenida del inicio** y **aviso destacado** (franja al principio del inicio). Con los campos de la Fase 9 (dirección, horario, contacto, redes, presentación), el propietario edita sin tocar código los textos principales; los eventos, la carta y las recompensas tienen sus propias secciones. Todo se escapa al mostrarse (sin HTML).

## 6. Notificaciones

### Qué funciona realmente y qué necesita configuración externa

| Notificación | Canal | ¿Funciona? |
|---|---|---|
| Verificación del email, cambio de email y aviso a la dirección anterior | Email, al momento | **Sí, con un proveedor SMTP** configurado (`EMAIL_*`). En desarrollo se muestran en la consola, en tests se guardan en memoria; nada de eso es un envío real y producción rechaza esos backends. |
| Recuperación de la cuenta (contraseña) | Email, al momento | Igual que la anterior. |
| Aviso de intento de registro con un email existente | Email, al momento | Igual. |
| Reserva recibida, confirmada, rechazada, cancelada; aviso al propietario | Email, al confirmar la transacción, con reintentos | Envío inmediato con SMTP. **Los reintentos necesitan `process_notifications` programado.** |
| Campañas promocionales | Email | Necesitan SMTP **y** `process_notifications` programado. |
| Regalo de cumpleaños (puntos) y su aviso | Ledger + email | El regalo necesita `run_birthday_promotions` programado a diario; el aviso, además, SMTP y `process_notifications`. |
| Cualquier SMS (campañas, cumpleaños) | SMS | **No funciona:** no hay proveedor integrado. Requiere contratar uno y escribir su adaptador (§6.4). Sin él no se crea ningún SMS. |

### 6.1 Registro (`notifications.Notification`)

Cada mensaje queda con su tipo, categoría (transaccional/promocional, derivada del tipo y comprobada en BD), canal, estado, intentos, último error (tipo de error o motivo, nunca el texto) y fechas. **No guarda destinatarios ni el texto**: se toman del usuario y de las plantillas al enviar.

| Estado | Significado |
|---|---|
| `PENDING` | En cola (o esperando reintento en `next_attempt_at`). |
| `SENDING` | Reclamada por un proceso. Si se queda así más de 30 min se recupera: las de la cola vuelven a `PENDING`; las de cuentas pasan a `FAILED` (no tienen contexto para recomponerlas). |
| `SENT` | El proveedor **aceptó** el mensaje (no implica que se haya leído). |
| `FAILED` | Agotó los intentos (5, con espera de 5, 10, 20 y 40 min) o fue un mensaje de cuentas que falló. |
| `SKIPPED` | No se envió a propósito: `sin_consentimiento`, `cuenta_inactiva`, `sms_sin_proveedor`, `telefono_no_valido`, `sin_email`. |

Idempotencia: `dedup_key` única por cumpleaños y año, campaña y cliente, o reserva y estado. Dos procesos no envían la misma notificación: cada uno la reclama con un `UPDATE … WHERE status = 'PENDING'`.

### 6.2 Preferencias y consentimiento

- Las comunicaciones promocionales (campañas y cumpleaños) exigen **consentimiento vigente del canal** y **email verificado**, comprobados al crear la notificación y **otra vez justo antes de enviarla** (`services.deliver`). Verificar el email no es consentir publicidad.
- Los SMS exigen además proveedor configurado y un teléfono E.164 válido en el perfil.
- **Retirar las preferencias:** desde el perfil (Fase 2) o con el enlace de baja de cada mensaje (`/comunicaciones/baja/<token>/`), que registra el cambio en el historial con origen «Enlace de baja de un mensaje». Las promociones también llevan la cabecera `List-Unsubscribe`.
- Los mensajes transaccionales (cuentas y reservas) no dependen del consentimiento promocional.

### 6.3 Campañas

En `/dashboard/comunicaciones/` el propietario ve el estado real de los canales (avisa si el email es simulado o no hay SMS), el número de clientes que recibirían hoy una campaña, sus campañas y el registro de notificaciones (sin destinatarios). Flujo: **Nueva campaña** (borrador, editable) → **Programar envío** (la petición no envía nada) → `process_notifications` la reparte entre los clientes activos, verificados y con consentimiento, y la envía por lotes (200 por ejecución). Se puede cancelar mientras esté en borrador o programada. Un cliente recibe cada campaña una vez. Se audita sin el texto.

### 6.4 SMS: cómo integrar un proveedor

1. Escribir una clase con `send(self, *, to, body)` que llame a la API del proveedor y lance una excepción si no acepta el mensaje (por ejemplo en `apps/notifications/sms.py`, heredando de `BaseSmsBackend`), con sus credenciales en variables de entorno nuevas.
2. Definir `SMS_BACKEND=ruta.a.la.Clase`. Producción rechaza `LocmemSmsBackend` (solo tests).
3. Añadir tests del adaptador con el proveedor simulado y documentar sus costes y límites.

### 6.5 Logs

Solo el `public_id` de la notificación, su tipo, el intento y el tipo de error. Nunca destinatarios, tokens, enlaces de verificación o recuperación ni el texto. Los tokens de verificación solo existen en claro dentro del email (en BD, su hash; Fase 2).

## 7. Cumpleaños

`run_birthday_promotions` (diario) sigue el flujo pedido:

1. **Detecta** los cumpleaños del día. **29 de febrero:** en los años no bisiestos se celebra el **28** (`accounts.birthdays`).
2. Requiere una promoción de cumpleaños **activa** (solo de puntos fijos; el modelo y la BD rechazan multiplicadores).
3. Comprueba **cliente activo, rol cliente y email verificado**.
4. Comprueba que **no se generó ya** (restricción única cliente+año en el ledger) y el anti-abuso de la Fase 6: fecha de nacimiento sin cambios en 30 días y al menos 300 días desde el último regalo.
5. **Crea el beneficio:** movimiento `BIRTHDAY_GIFT` con los puntos fijos de la promoción, con cliente y promoción bloqueados (respeta `max_total_uses`).
6. **Comprueba las preferencias** y encola el aviso solo si el cliente lo autorizó (email; SMS solo con proveedor).
7. **Registra el resultado:** movimiento, notificaciones y un `AuditEvent BIRTHDAY_PROMOTIONS_RUN` con los totales, sin datos personales.

Repetirlo el mismo día (o lanzarlo dos veces a la vez) no duplica regalos ni avisos. `--days-back N` (máximo 7) recupera días en que no se ejecutó; `--date AAAA-MM-DD` procesa un día concreto (no futuro).

Cambio respecto a la Fase 6: las promociones de cumpleaños **ya no dan puntos al registrar una compra**; `birthday_window_days` queda sin uso (oculto en el admin). La migración `loyalty.0003` se detiene con un mensaje claro si existiera alguna promoción de cumpleaños con multiplicador (no había ninguna en la BD de desarrollo).

## 8. Tareas programadas

Ninguna tarea se ejecuta sola: hay que programarlas en el servidor (fase de despliegue).

| Comando | Frecuencia recomendada | Qué hace |
|---|---|---|
| `python manage.py process_notifications` | Cada 5 minutos | Reparte campañas programadas, envía notificaciones pendientes y reintentos, recupera envíos interrumpidos. Seguro si se solapan dos ejecuciones. |
| `python manage.py run_birthday_promotions` | Una vez al día (p. ej. 09:00) | Regalos y avisos de cumpleaños del día. |
| `python manage.py expire_redemptions` | Una vez al día | Caduca canjes vencidos y devuelve los puntos (Fase 7). |

Ejemplo con cron (Linux), con el entorno virtual y las variables de producción cargadas:

```cron
*/5 * * * * cd /srv/caneca && .venv/bin/python manage.py process_notifications --settings=config.settings.prod
0 9 * * *   cd /srv/caneca && .venv/bin/python manage.py run_birthday_promotions --settings=config.settings.prod && .venv/bin/python manage.py process_notifications --settings=config.settings.prod
30 4 * * *  cd /srv/caneca && .venv/bin/python manage.py expire_redemptions --settings=config.settings.prod
```

En Windows, el Programador de tareas ejecuta los mismos comandos con `.venv\Scripts\python.exe`. Dependencias: solo Django y la base de datos; ninguna cola externa.

## 9. Configuración

Variables de entorno nuevas (en [.env.example](../.env.example), sin secretos):

| Variable | Por defecto | Uso |
|---|---|---|
| `SMS_BACKEND` | vacío (SMS desactivado) | Ruta a la clase del proveedor de SMS. |
| `NOTIFICATIONS_BATCH_SIZE` | 200 | Notificaciones por ejecución de `process_notifications`. |

Siguen siendo necesarias las de email de la Fase 2 (`EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`/`EMAIL_USE_SSL`, `DEFAULT_FROM_EMAIL`, `SITE_BASE_URL`). Cualquier proveedor con SMTP sirve. Ajustes fijos nuevos en `config/settings/base.py`: `EVENTS_*` (§1) y `NOTIFICATIONS_MAX_ATTEMPTS`, `NOTIFICATIONS_RETRY_BASE_MINUTES`, `NOTIFICATIONS_STALE_SENDING_MINUTES`, `NOTIFICATIONS_UNSUBSCRIBE_MAX_AGE_DAYS`.

**Cómo probarlo en desarrollo:** `python manage.py migrate`; como propietario crea y publica un evento en `/dashboard/eventos/`; como cliente verificado reserva en `/eventos/<id>/` o `/cuenta/reservas/nueva/`; los emails aparecen en la consola de `runserver`; confirma la reserva en `/dashboard/reservas/`. Para campañas: crea y programa una en `/dashboard/comunicaciones/` y ejecuta `python manage.py process_notifications`. Para cumpleaños: crea una promoción de cumpleaños activa en el admin y ejecuta `python manage.py run_birthday_promotions`.

## 10. Preparación para la app y la API (Fase 11)

Toda la lógica está en servicios que no reciben `request` y lanzan `ValidationError`/`PermissionDenied` (400/403; `rate_limited` → 429). Operaciones previstas, siempre sobre el usuario autenticado e identificando objetos por `public_id`:

| Operación | Método y ruta prevista | Servicio / selector |
|---|---|---|
| Eventos publicados | `GET /api/v1/events/` | `events.selectors.public_events` |
| Detalle de un evento | `GET /api/v1/events/{id}/` | `public_event`, `seats_left`, `is_bookable` |
| Mis reservas | `GET /api/v1/me/reservations/` | `customer_reservations` |
| Solicitar reserva | `POST /api/v1/me/reservations/` (`event?`, `requested_for?`, `party_size`, `notes`, `idempotency_key`) | `events.services.request_reservation` |
| Detalle / cancelar mi reserva | `GET`, `POST /api/v1/me/reservations/{id}/cancel/` | `customer_reservation`, `cancel_own_reservation` |
| Mis preferencias | `GET`/`PATCH /api/v1/me/preferences/` | `accounts.services.set_communication_preferences` |
| Propietario: reservas y cambios de estado | `GET /api/v1/owner/reservations/`, `POST …/{id}/confirm|reject|cancel|complete/` | `reservations_for_management`, `confirm_`/`reject_`/`cancel_`/`complete_reservation` |
| Propietario: eventos | `POST/PATCH /api/v1/owner/events/`, `POST …/{id}/status/` | `save_event`, `set_event_status` |
| Propietario: campañas | `POST /api/v1/owner/campaigns/`, `POST …/{id}/queue|cancel/` | `notifications.campaigns.*` |

Serializadores con campos explícitos: el cliente nunca envía `status`, `customer`, `requested_for` de un evento ni el estado de una campaña. Las notificaciones push de la app serían un canal más en `notifications` (como SMS), con su propio consentimiento.

## 11. Archivos creados o modificados

- **Nuevos:** `apps/events/` (modelos, servicios, selectores, formularios, vistas, URLs, admin, migración `0001`), `apps/notifications/` (modelos, servicios, campañas, selectores, SMS, baja, vistas, URLs, admin, comando `process_notifications`, migración `0001`), `apps/loyalty/birthdays.py`, `apps/loyalty/management/commands/run_birthday_promotions.py`, migraciones `accounts.0007`, `core.0008`, `loyalty.0003`, `web.0002`; plantillas `templates/events/`, `templates/notifications/` (textos de email/SMS y página de baja), `templates/components/event_card.html`, `templates/dashboard/{events,event_form,reservations,reservation_detail,communications,campaign_form}.html`.
- **Modificados:** `apps/accounts/{emails,forms,models,services,views}.py` (envío por notificaciones, recuperación con registro, origen de baja, `withdraw_promotional_consent`), `apps/core/models.py` (5 acciones de auditoría), `apps/loyalty/{models,ledger,promotions,selectors,admin}.py` (regalo de cumpleaños), `apps/web/{models,services,content,views}.py` (textos del inicio y eventos públicos), `apps/dashboard/{views,forms,urls}.py`, `config/settings/{base,prod,test}.py`, `config/urls.py`, plantillas del inicio, eventos, perfil y dashboard, `static/css/app.css` (recompilado).
- **Eliminado:** `templates/dashboard/pending_phase.html` (ya no se usa).

## 12. Tests y resultados reales

Nuevos: `tests/events/test_services.py`, `tests/events/test_views.py`, `tests/notifications/test_notifications.py`, `tests/loyalty/test_birthdays.py`. Actualizados: `tests/loyalty/test_promotions.py` (la bonificación de cumpleaños en compra se sustituye por el regalo), `tests/accounts/test_email_verification.py`, `tests/dashboard/test_access.py`, `tests/dashboard/test_stats.py`.

Cubren: reservas (estado inicial, avisos sin notas ni contacto, email verificado, empleados y propietarios no reservan, antelación, zona horaria, personas, notas, idempotencia y conflicto, límite de activas y por hora, aforo al solicitar y al confirmar, una activa por evento también en BD, eventos no reservables, cambio de hora del evento); transiciones válidas e inválidas, repetición sin duplicar avisos, completar solo desde su día, cancelación del cliente (propia, ajena, fuera de hora), solo el propietario cambia estados, auditoría sin textos; vistas (eventos públicos, 404 en borradores, IDOR, GET de cancelar → 405, doble envío del formulario, escapado de los textos del inicio, dashboard sin contacto en el listado y detalle auditado, acciones y escalada de empleado/cliente → 403); notificaciones (registro sin contexto ni dirección, fallos sin datos en logs, deduplicación, contexto simple, reclamación única, reintentos con espera y fallo final, cuenta inactiva, consentimiento al enviar, SMS sin proveedor y con teléfono no válido, recuperación de envíos interrumpidos, límite por lote, comando); campañas (solo propietario, validación, programar no envía, reparto solo a verificados, activos y con consentimiento, sin duplicados, SMS sin proveedor, edición solo en borrador, auditoría sin texto); baja (GET no cambia nada, POST retira e historial, idempotente, tokens manipulados o caducados, tokens de personal); recuperación de contraseña por el registro; cumpleaños (regalo único aunque se repita, varias promociones, otros días y sin fecha, no verificados/inactivos/personal, sin promoción activa, `max_total_uses`, anti-abuso, restricción única y forma en BD, 29-F en años comunes y bisiestos, auditoría sin datos, sin consentimiento → regalo sin aviso, aviso único y enviado por la tarea con enlace de baja y sin nombre, consentimiento retirado antes de enviar, SMS sin y con proveedor, comando y límites de `--date`/`--days-back`).

Comandos ejecutados y resultado:

```text
python manage.py check                                   → System check identified no issues (0 silenced).
python manage.py makemigrations --check --dry-run        → No changes detected
python manage.py test --settings=config.settings.test    → Ran 719 tests … OK (skipped=3)
python scripts/tailwind.py build                         → Done
```

Las migraciones se aplicaron, se revirtieron (`events zero`, `notifications zero`, `loyalty 0002`, `web 0001`, `accounts 0006`, `core 0007`) y se volvieron a aplicar sobre **una copia** de `db.sqlite3`, sin errores. La BD de desarrollo original no se ha migrado: ejecuta `python manage.py migrate`. Los 3 tests omitidos son los de concurrencia que solo corren en PostgreSQL (Fase 7). **No se ha probado** con un SMTP real, en PostgreSQL ni en un navegador.

## 13. Estado de los criterios de aceptación

| Criterio | Estado |
|---|---|
| Eventos: crear, editar, publicar y archivar | **Completa** |
| Reservas con confirmación manual y estados `PENDING/CONFIRMED/REJECTED/CANCELLED/COMPLETED` validados en servidor | **Completa** |
| Datos personales de las reservas protegidos | **Completa** |
| Contenidos principales editables sin tocar código | **Completa** |
| Sistema reutilizable de notificaciones (verificación, recuperación, reservas, transaccionales, promociones, cumpleaños) | **Completa** en código; el envío real **requiere SMTP** configurado |
| Email por proveedor configurado en variables de entorno, sin simular envíos | **Completa** (producción rechaza backends simulados; el dashboard indica si el email es simulado) |
| SMS opcional, solo con teléfono válido y consentimiento | **Completa** como interfaz; **sin proveedor integrado** (no se envía ningún SMS) |
| Preferencias comprobadas antes de enviar, retirada posible | **Completa** |
| Flujo de cumpleaños sin duplicados y con 29-F | **Completa** |
| Sin campañas masivas desde la web; tareas programadas documentadas | **Completa** en código; **pendiente programarlas** en el servidor |
| Sin datos personales innecesarios en mensajes ni tokens en logs | **Completa** |
| Servicios reutilizables y operaciones API documentadas | **Completa** (§10) |
| Pruebas de reservas, estados, preferencias, notificaciones y duplicados | **Completa** |

## 14. Limitaciones, riesgos y pendientes

- **SMTP real pendiente:** hasta configurarlo, ningún email sale de verdad (en desarrollo se imprimen en consola).
- **Tareas sin programar:** sin `process_notifications` no hay reintentos ni campañas; sin `run_birthday_promotions` no hay regalos de cumpleaños.
- **SMS:** sin proveedor; integrarlo (§6.4) tiene coste por mensaje y exige revisar su tratamiento de datos.
- **Concurrencia:** aforo, límite de activas y reclamación de notificaciones dependen de bloqueos que SQLite ignora; validar en PostgreSQL.
- **Duplicado posible** si un proceso cae justo después de que el proveedor acepte un mensaje y antes de marcarlo enviado (se recupera como pendiente a los 30 min).
- **Token de baja en la URL:** puede quedar en logs del servidor web; solo permite darse de baja y caduca a los 365 días.
- **Valores por defecto** de antelación, personas, reservas activas y plazos: pendientes de confirmar por el propietario.
- Cambiar la hora de un evento no avisa a los clientes con reserva.
- El texto de la portada «Programa de puntos — Próximamente» (Fase 3) quedó desfasado desde las Fases 5–7; no se ha tocado por estar fuera del alcance.
- La normativa sobre comunicaciones comerciales (consentimiento, baja sencilla, identificación del remitente) debe revisarla el propietario con asesoría; este código no garantiza por sí solo su cumplimiento.
- Revisión visual en navegador y dispositivos pendiente.

## 15. Dependencias para la fase siguiente

- **Fase 11 (API, auditoría, seguridad y app):** exponer las operaciones de §10 sobre los servicios existentes; añadir throttling de DRF (las reservas ya tienen límite propio); revisar la auditoría de `EVENT_SAVED`, `RESERVATION_*`, `CAMPAIGN_UPDATED` y `BIRTHDAY_PROMOTIONS_RUN`; decidir si las notificaciones push de la app son un canal nuevo de `apps.notifications`.
- **Despliegue (sin número):** SMTP real, programación de los tres comandos, almacenamiento de las imágenes de eventos y pruebas en PostgreSQL.
