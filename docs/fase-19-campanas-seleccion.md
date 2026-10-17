# Fase 19 — Filtro «sin gasto», selección de clientes y campañas con imagen y puntos

**Estado:** Completa (revisión visual en el navegador y prueba con un SMTP real pendientes; ver §9).
**Fecha:** 2026-10-17.
**Depende de:** [Fase 10](fase-10-eventos-reservas-notificaciones.md) (campañas y notificaciones), [Fase 14](fase-14-caducidad-puntos-cumpleanos.md) (caducidad de puntos) y [Fase 18](fase-18-ordenacion-listados.md) (listados).

## 1. Objetivo

- En **Clientes**: filtro **Gasto** («Sin gasto (ninguna compra)» / «Con compras») y una columna **«Envío»** a la derecha con una casilla por cliente y una casilla general. Al marcar alguno aparece abajo una barra con el botón **«Comunicaciones»**, que abre el formulario de campaña para esos clientes.
- **Formulario de campaña único** (también el de las campañas normales): nombre\*, asunto\*, destinatarios, canal, texto\*, imagen y puntos de regalo con o sin caducidad. Botones «Guardar borrador» y **«Crear y enviar»**, que se activa cuando nombre, asunto y texto tienen contenido. Todo queda en el historial de Comunicaciones.

## 2. Decisiones (tomadas con el usuario el 2026-10-17)

| Decisión | Motivo |
|---|---|
| **Formulario único** con el campo **Destinatarios**: «Todos los clientes con consentimiento» o «Clientes seleccionados (N)». Sin apartado nuevo. | Filtrar y elegir se hace donde ya están los filtros (Clientes). Un apartado aparte duplicaría filtros y formularios. |
| **Consentimiento:** de los seleccionados, solo reciben el mensaje los que aceptaron comunicaciones promocionales por ese canal. El formulario muestra «De los N seleccionados, recibirán el mensaje X…». | Una campaña promocional solo puede enviarse con consentimiento. Se comprueba al repartir y otra vez al entregar. |
| **Puntos de regalo:** a **todos los seleccionados** (activos y con email verificado), tengan o no consentimiento. En «Todos», a los destinatarios. | Decisión del usuario. Los puntos no son una comunicación. |
| **Caducidad:** «Caducan según la configuración de caducidad» (Fase 14) o «No caducan nunca». | Sin fechas por campaña: no hace falta otro modelo de caducidad. |
| Los puntos sin caducidad (`never_expires`) **no forman lote** y los gastos consumen **antes los que caducan**. | Regalar puntos que no caducan nunca adelanta el vencimiento de los demás. |
| Regalo **idempotente**: clave `uuid5(campaña, cliente)` en el campo único `idempotency_key`. | Reintentos del reparto o doble clic no duplican puntos. |
| **Asunto obligatorio** también en SMS. | Lo pidió el usuario. En SMS no se envía: solo identifica el envío en el historial. |
| **Imagen solo en email**, incrustada (`cid:`), con alternativa HTML. En SMS se descarta. | No depende de que `media/` sea pública ni de cargar imágenes remotas. |
| Selección guardada en la **sesión** (no en la URL), con un máximo de **5000** clientes. «Elegir los N clientes filtrados» toma todos los del filtro actual. | Sin identificadores en la URL ni en los logs. El servidor recalcula la lista: solo cuentan clientes. |
| «Crear y enviar» **guarda y programa en una transacción**. El reparto lo sigue haciendo `process_notifications`. | Si no se puede programar (p. ej. SMS sin proveedor), no queda ni el borrador. La petición web no envía nada. |
| La demo no incluye campañas con regalo (el test de la demo excluye `CAMPAIGN_GIFT`). | Cambiaría los saldos de la demo de los que dependen otros tests. |

## 3. Flujo

1. Clientes → filtrar (p. ej. **Gasto: Sin gasto**) → marcar en **Envío** (o la casilla general) → **Comunicaciones**. Alternativa: «Elegir los N clientes filtrados».
2. `POST /dashboard/clientes/seleccion/` guarda la selección en la sesión y lleva a `/dashboard/comunicaciones/nueva/?destinatarios=seleccion`.
3. Rellenar el formulario y pulsar **Crear y enviar** (o Guardar borrador).
4. `python manage.py process_notifications` reparte: crea los mensajes para los destinatarios con consentimiento y concede los puntos. Después envía.
5. Comunicaciones muestra la campaña con «Para» (todos o N seleccionados) y «Puntos de regalo» (a cuántos clientes).

Una selección sin usar se puede descartar desde Clientes.

## 4. Archivos

| Archivo | Cambio |
|---|---|
| `apps/notifications/models.py` + migración `0003_campaign_audience_image_gift` | `Campaign.audience`, `image`, `gift_points`, `gift_points_expire`, `gifted_count` con CHECKs; modelo `CampaignRecipient` (único por campaña y cliente). Aditiva. |
| `apps/loyalty/models.py` + migración `0005_campaign_gift` | Tipo `CAMPAIGN_GIFT`, campo `never_expires` y CHECKs (forma del regalo; `never_expires` solo en regalos). Aditiva. |
| `apps/loyalty/expiry.py` | FIFO: los créditos `never_expires` no forman lote y se consumen los últimos. |
| `apps/loyalty/ledger.py` | `grant_campaign_gift(...)` y `campaign_gift_key(...)`. |
| `apps/notifications/campaigns.py` | Campos nuevos, validación, `selectable_customers`, `create_and_queue`, reparto con selección y puntos. |
| `apps/notifications/services.py`, `templates/notifications/campaign_body.{txt,html}`, `campaign_sms.txt` | Email con alternativa HTML e imagen en línea; aviso de los puntos regalados. |
| `apps/notifications/selectors.py` | `selected_reach` (alcance de la selección); contadores con `distinct`. |
| `apps/accounts/selectors.py` | `search_customers(spent=…)`. |
| `apps/dashboard/forms.py`, `views.py`, `urls.py` | Filtro «Gasto», `customer_selection`, `customer_selection_clear`, formulario único de campaña. |
| `templates/dashboard/customers.html`, `campaign_form.html`, `communications.html` | Columna «Envío», barra de selección, formulario y columnas del historial. |
| `static/js/app.js`, `assets/css/input.css`, `static/css/app.css` | Casilla general, contador y barra; activar «Crear y enviar». |
| `docs/api/openapi.yaml` | El tipo de movimiento `CAMPAIGN_GIFT`. |
| `locale/gl`, `locale/es` | Cadenas nuevas traducidas. |

Sin variables de entorno nuevas. Las imágenes se guardan en `media/campaigns/` con nombre aleatorio.

## 5. Seguridad y privacidad

- Todas las vistas exigen propietario (`owner_required`) y los servicios lo vuelven a comprobar. Hay CSRF en todos los `POST`.
- **IDOR:** los `public_id` recibidos se filtran a clientes. Empleados, propietarios e identificadores desconocidos o mal formados se ignoran. La selección no va en la URL.
- **Consentimiento** comprobado al repartir (`eligible_recipients`) y al entregar (`deliver`). Los enlaces de baja siguen en el texto, el HTML y la cabecera `List-Unsubscribe`.
- **XSS:** el HTML del email escapa el texto de la campaña.
- **Imagen:** extensión y contenido real validados (Pillow, tamaño y dimensiones), con nombre aleatorio. Una imagen falsa se rechaza (400).
- **Destinatarios por defecto:** si el formulario llega sin el campo, se usa «Todos los clientes con consentimiento» (comportamiento anterior).
- **Puntos:** idempotentes, con el cliente bloqueado, solo a clientes activos con email verificado, máximo 10 000 por campaña.
- **Auditoría:** campaña creada, editada o repartida con número de seleccionados y puntos, sin textos ni identificadores de clientes.

## 6. Tests

`tests/notifications/test_campaign_selection.py` (22 tests):

- FIFO con puntos sin caducidad;
- regalo idempotente y solo a clientes válidos;
- campaña a seleccionados: mensaje solo con consentimiento, puntos a todos los seleccionados, sin duplicados al repetir el reparto;
- campaña a todos con puntos;
- selección que ignora personal e identificadores desconocidos;
- obligatorios y límites;
- «Crear y enviar» todo o nada;
- email con imagen en línea, texto escapado y enlace de baja;
- SMS sin imagen;
- dashboard: filtro «Gasto», columna «Envío», selección en sesión, «todos los filtrados», selección vacía, 403 a empleado y cliente, crear y enviar a seleccionados con imagen y puntos, borrador, imagen falsa, «seleccionados» sin selección y botón con `data-requires`.

Tests existentes ajustados:

- `tests/loyalty/test_expiry.py`: el ayudante de movimientos admite `never_expires`.
- `tests/notifications/test_notifications.py`: el SMS de prueba lleva asunto.
- `tests/demo/test_seed_demo_data.py`: excluye `CAMPAIGN_GIFT`.

## 7. Resultados

| Orden | Resultado |
|---|---|
| `python manage.py check` | Sin incidencias |
| `python manage.py makemigrations --check --dry-run` | Sin cambios pendientes |
| `python scripts/i18n.py check` | Traducciones al día y completas |
| `python manage.py spectacular --validate --fail-on-warn` | Válido; `docs/api/openapi.yaml` regenerado |
| `python manage.py test tests.notifications.test_campaign_selection --settings=config.settings.test` | 22 tests OK |
| `python manage.py test --settings=config.settings.test --noinput` | **1031 tests OK** (1009 previos + 22 nuevos), SQLite, 2026-10-17 |
| `python manage.py migrate` (PostgreSQL de desarrollo y `pruebas_dev/demo.sqlite3`) | `loyalty.0005` y `notifications.0003` aplicadas |

## 8. Uso y operación

- Tras actualizar: `python manage.py migrate`, `python scripts/i18n.py compile`.
- El reparto y el envío siguen en `process_notifications` (tarea programada).

## 9. Limitaciones y pendientes

- **Revisión visual** de Clientes (columna, barra) y del formulario.
- **Prueba con un SMTP real** del email con imagen (en tests se usa el backend en memoria).
- La selección es por página más «todos los filtrados»: marcar a mano en varias páginas no se acumula (cada envío de la barra sustituye la selección).
- Las tablas en tarjeta (móvil) no aplican aquí: Clientes sigue siendo una tabla con scroll horizontal en pantallas estrechas.
- La demo no incluye campañas con puntos de regalo.
