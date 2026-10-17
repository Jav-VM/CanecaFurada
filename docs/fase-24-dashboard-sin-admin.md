# Fase 24 — Crear y editar en el dashboard sin pasar por el admin

**Estado:** Completa (2026-10-17). Código, traducciones, tests y CI en verde (commits `ffb60d8` y `416a833`); revisada en el navegador por el usuario.

## 1. Objetivo y alcance

En el dashboard del propietario, crear o editar productos, categorías, estilos de cerveza, la carta de grifos, recompensas y promociones abría el admin de Django. Ahora se hace con formularios de la web, como ya ocurría con eventos, artículos o campañas. El admin queda como **«Administración avanzada»** en Configuración.

| Sección del dashboard | Antes (admin) | Ahora (dashboard) |
|---|---|---|
| Carta / Cervezas | Nuevo producto, Editar | `carta/productos/nuevo/`, `carta/productos/<public_id>/editar/` |
| Carta | Categorías | `carta/categorias/` (lista, nueva, editar) |
| Cervezas | Estilos | `cervezas/estilos/` (lista, nuevo, editar) |
| Cervezas | Carta de grifos | `cervezas/grifos/` (historial, nueva, editar) |
| Recompensas | Nueva recompensa, Editar | `recompensas/nueva/`, `recompensas/<public_id>/editar/` |
| Promociones | Nueva promoción, Editar | `promociones/nueva/`, `promociones/<public_id>/editar/` |

**Exclusiones (decididas por el usuario):** borrar categorías y estilos. En el dashboard las categorías se ocultan («Publicada») y los estilos se quedan; los que no se usan se borran en la administración avanzada. Productos, recompensas y promociones siguen sin borrarse: se archivan, se pausan o se finalizan con los botones de estado que ya existen. El admin no se elimina.

## 2. Criterios de aceptación

| Criterio | Estado |
|---|---|
| Crear y editar las seis fichas desde el dashboard | Completa (tests) |
| Ninguna plantilla del dashboard enlaza al admin salvo Configuración | Completa (test de regresión) |
| Configuración enlaza a la administración avanzada | Completa (tests) |
| Producto nuevo en borrador y disponible; editarlo no cambia su publicación ni su disponibilidad | Completa (tests) |
| Recompensas y promociones nuevas en borrador; editarlas no cambia su estado | Completa (tests) |
| Validaciones del dominio en el servidor (cerveza sin estilo o graduación, fijo destacado, precio, nombres repetidos, imagen falsa, carta sin imagen, fechas, cumpleaños con multiplicador) | Completa (tests) |
| Solo el propietario (empleado y cliente 403, anónimo al login, inexistente 404) | Completa (tests) |
| Auditoría sin textos | Completa (tests) |
| Traducciones al gallego al día y completas | Completa (`scripts/i18n.py check`) |
| Revisión manual en navegador | Completa (revisada en el navegador por el usuario el 2026-10-17) |

## 3. Decisiones técnicas

| Decisión | Motivo |
|---|---|
| Mismo patrón que los eventos | El `ModelForm` solo convierte la entrada; el servicio de cada dominio valida (`full_clean`), guarda en una transacción, comprueba el permiso de propietario y audita. Las vistas llevan `@owner_required`, `@never_cache` y CSRF, y devuelven 400 con los errores en el formulario. |
| Servicios nuevos del catálogo: `save_product`, `save_category`, `save_beer_style`, `save_tap_menu` (`apps/catalog/services.py`) | Hasta ahora estas fichas solo se guardaban desde el admin. Con una lista blanca de campos por modelo (contra la asignación masiva) y el objeto bloqueado con `select_for_update` al editar. `save_product` replica `ProductAdmin.save_model`: un producto nuevo empieza en borrador y disponible, y la publicación y la disponibilidad solo cambian con `set_product_status` y `set_product_availability`. |
| Recompensas y promociones reutilizan `save_reward` y `save_promotion` | Ya validaban, auditaban y comprobaban el permiso; el admin los usaba igual (`form.save(commit=False)` y campos cambiados). |
| El estado no está en los formularios | Se cambia con los botones de cada listado, como antes. Un `status` enviado a mano en el POST se ignora (test). |
| Identificador de la categoría opcional | Si queda vacío, se genera del nombre (`slugify`, con `-2`, `-3`… si ya existe). Al editar se conserva, para no romper los enlaces `/carta/#identificador`. |
| Acción de auditoría nueva `CATALOG_SAVED` («Carta modificada») | `metadata = {"model": "product" \| "category" \| "beer_style" \| "tap_menu", "created", "fields"}`: los nombres de los campos cambiados, nunca su contenido. Las recompensas y promociones siguen con `REWARD_SAVED` y `PROMOTION_SAVED`. |
| Plantilla común `templates/dashboard/object_form.html` | Una sola plantilla para las seis fichas (título, introducción, campos, «Guardar», «Volver»). |
| Identificadores en la URL | `public_id` (UUID) en productos, recompensas y promociones; el `slug` en las categorías; el id en estilos y cartas de grifos, que no tienen `public_id`. Todas las rutas son solo para el propietario, que ve todos los objetos. |
| Imagen | Mismos validadores que el admin (extensión y contenido real de imagen). Al editar sin subir otra se conserva; «Eliminar» la quita (productos). Igual que en el admin, el fichero anterior no se borra del disco al sustituirlo. |

## 4. Archivos

- **Dominio:** `apps/catalog/services.py` (servicios nuevos), `apps/core/models.py` (`CATALOG_SAVED`).
- **Migración:** `apps/core/migrations/0011_audit_action_catalog_saved.py` (`AlterField` de `AuditEvent.action`: solo cambian las opciones; no toca datos).
- **Dashboard:** `apps/dashboard/forms.py` (`ProductForm`, `CategoryForm`, `BeerStyleForm`, `TapMenuForm`, `RewardForm`, `PromotionForm`), `apps/dashboard/views.py` (vistas nuevas y `_catalog_form_view` / `_model_form_view`), `apps/dashboard/urls.py`.
- **Plantillas:** nuevas `object_form.html`, `categories.html`, `beer_styles.html`, `tap_menus.html`; cambiadas `products.html`, `rewards.html`, `promotions.html` (sin enlaces al admin) y `settings.html` (bloque «Administración avanzada»).
- **Traducciones:** `locale/gl` y `locale/es`, generadas con `scripts/i18n.py make` (GNU gettext). De paso, el mensaje de error de la URL de Maps (Fase 23) ya no lleva URLs dentro del texto traducible.
- **Tests:** nuevo `tests/dashboard/test_phase24_forms.py`; `tests/dashboard/test_access.py` añade las rutas nuevas a las de acceso.

Sin variables de entorno nuevas.

## 5. Uso

- **Carta:** «Nuevo producto», «Categorías» y «Editar» en cada fila.
- **Cervezas:** «Nueva cerveza» (empieza como «Cerveza propia»), «Estilos», «Carta de grifos» y «Editar».
- **Recompensas** y **Promociones:** «Nueva…» y «Editar».

Lo nuevo se guarda como borrador; se publica o se activa con los botones de la lista. **Configuración → Administración avanzada** abre el admin, para la auditoría o para borrar categorías y estilos sin uso.

Antes de usarlo en una base que ya existe: `python manage.py migrate` (aplica `core.0011_audit_action_catalog_saved`).

## 6. Seguridad y privacidad

- Permiso en dos niveles: `@owner_required` en las vistas y la comprobación de propietario en cada servicio (`ensure_can_manage_catalog`, `save_reward`, `save_promotion`).
- Validación en el servidor con las reglas del modelo y las restricciones de la base de datos (nombres únicos sin distinguir mayúsculas, reglas de cerveza, precio, fechas).
- Listas blancas de campos: no se puede cambiar el estado, la disponibilidad ni los campos internos enviando datos de más.
- CSRF en todos los formularios; `never_cache` en las páginas del dashboard.
- La auditoría guarda el actor, el objeto (`public_id` si lo tiene), el tipo y los nombres de los campos, nunca los textos.

## 7. Pruebas y resultados

| Comando | Resultado (2026-10-17) |
|---|---|
| `python manage.py makemigrations --check --dry-run --settings=config.settings.test` | Sin cambios pendientes (tras crear `core.0011`) |
| `python manage.py test --settings=config.settings.test --noinput` | **1130 tests OK** (SQLite) |
| `python scripts/i18n.py check` y `compile` | Al día y completas; compiladas |
| `python manage.py spectacular --validate --fail-on-warn` + comparación con `docs/api/openapi.yaml` | Idéntico |
| `node --check` del JavaScript propio | Sin errores (sin cambios) |

`tests/dashboard/test_phase24_forms.py` (22 tests):
- productos: crear (borrador y disponible, con imagen), volver a Carta o a Cervezas, editar sin cambiar estado ni disponibilidad, rechazos e imagen falsa, estado ignorado, 404;
- categorías: identificador generado y único, nombre repetido, ocultar y editar, 404;
- estilos: crear, editar, repetidos y 404;
- cartas de grifos: imagen obligatoria, publicada en la web, conservar la imagen al editar;
- recompensas y promociones: crear en borrador, validaciones, editar sin cambiar estado, 404;
- accesos: empleado y cliente 403, anónimo al login, sin cambios ni auditoría;
- los listados enlazan al dashboard y no al admin; Configuración sí enlaza al admin; ninguna plantilla del dashboard salvo `settings.html` usa `{% url 'admin:… %}`.

## 8. Limitaciones y pendientes

- **Revisión manual:** hecha por el usuario (fichas del dashboard, Empleados y Promociones, enviar una campaña ya creada, eliminar y reactivar campañas).
- Borrar categorías y estilos sigue en la administración avanzada (decisión de la fase).
- Al sustituir una imagen, el fichero anterior se queda en `media/`, como ya pasaba con el admin.
- La creación de empleados ya estaba en el dashboard (Fase 9); alguna guía antigua del README todavía lo describe en el admin.
- **Siguiente paso propuesto:** una fase de conservación de datos (plazos y anonimización de cuentas; ver §11).

## 9. Ajuste posterior: Empleados y Promociones sin scroll horizontal (2026-10-17)

- **Petición:** que el contenido de Empleados y Promociones se ajuste al ancho de la sección, sin scroll lateral.
- **Cambio:** sus tablas usan `.data-table-fit` (el mismo patrón que Eventos, Carta y Cervezas). Desde `xl` (80rem) son tablas compactas; por debajo, una tarjeta por fila con la etiqueta de cada dato (`data-label`), el nombre como título (`cell-title`) y las acciones al final (`cell-buttons` / `cell-actions`). Plantillas: `templates/dashboard/employees.html` y `promotions.html`; en `assets/css/input.css` solo cambia el comentario (sin clases nuevas, `app.css` igual).
- Sin textos nuevos que traducir: las etiquetas son las de las cabeceras.
- **Tests:** `FitTablesTests` en `tests/dashboard/test_phase24_forms.py` (las dos tablas usan `data-table-fit` y todas sus celdas llevan etiqueta).
- **Revisión:** hecha en el navegador a varios anchos.

## 10. Ajuste posterior: enviar una campaña ya creada a los clientes seleccionados (2026-10-17)

- **Petición:** al pulsar «Comunicaciones» con clientes seleccionados (Fase 19), poder crear una campaña con el formulario, como ahora, **o** elegir una ya creada. La creada con el formulario queda en Comunicaciones como una campaña más, exclusiva de los seleccionados; la ya creada se envía con sus condiciones actuales.
- **Decisiones del usuario:**
  - Enviar una creada hace una **copia nueva**, «Nombre (seleccionados)», con el mismo canal, asunto, texto, imagen y puntos de regalo, solo para los seleccionados, y la programa. La original no cambia.
  - Si regala puntos, la copia también, a todos los seleccionados (regla de la Fase 19), aunque alguno ya los recibiera con la original. Se avisa antes de enviar.
- **Formulario desde Clientes:** los destinatarios quedan fijados en «Clientes seleccionados (N)» (sin la opción «Todos»); el servidor fuerza `SELECTED` aunque llegue otro valor.
- **Servicio** `campaigns.send_copy_to_selection` (`apps/notifications/campaigns.py`):
  - copia los campos editables del origen y su imagen (un fichero nuevo);
  - llama a `create_and_queue`, así que aplica las mismas validaciones y la programación es todo o nada (por ejemplo, un SMS sin proveedor no deja nada);
  - deja auditoría `copied_to_selection` con el `public_id` del origen, el número de seleccionados y los puntos.
- **Idempotencia:** `Campaign.copy_key` (UUID único, migración `notifications.0004_campaign_copy_key`, un `AddField` sin datos). Cada fila de la lista lleva su clave; un doble envío devuelve la copia ya hecha y no regala los puntos dos veces. Si dos envíos llegan a la vez, decide la restricción única.
- **Vista** `campaign_send_copy` (`comunicaciones/enviar-existente/`, solo POST, propietario, CSRF): necesita la selección de la sesión y la borra al terminar.
- **Plantilla** `campaign_form.html`: bloque «Enviar una campaña ya creada» (las 20 más recientes, con canal, estado y puntos) y, debajo, «O crea una campaña nueva para ellos».
- **Traducciones:** 11 entradas nuevas (con plurales), generadas con `scripts/i18n.py make`; `check` al día y completas.
- **Tests:** `SendExistingCampaignTests` en `tests/notifications/test_campaign_selection.py` (6): lista y destinatarios fijos; formulario siempre `SELECTED`; copia programada con los mismos datos, imagen propia y la original intacta; reparto (mensaje con consentimiento, puntos a todos los seleccionados); misma clave = una copia; rechazos sin cambios (sin selección, UUID no válido, campaña inexistente, SMS sin proveedor); solo propietario y solo POST. Suite completa: **1137 tests OK**.
- **Revisión:** probado en el navegador y repartido con `python manage.py process_notifications`.

## 11. Ajuste posterior: «Eliminar» campañas y Comunicaciones sin scroll lateral (2026-10-17)

- **Petición:**
  - un botón «Eliminar» en Comunicaciones que solo se active cuando la campaña está cancelada o ya repartida;
  - que la sección y el contenido de las campañas se ajusten al recuadro, sin scroll lateral;
  - saber qué datos convendría borrar con el tiempo.
- **Decisiones del usuario:** «Eliminar» **quita la campaña del dashboard pero la conserva** en la base de datos; «caducada» = repartida (`DISPATCHED`).
- **Por qué no se borra de verdad:** cada mensaje enviado está ligado a su campaña (`Notification.campaign`, `PROTECT`), los destinatarios forman parte del historial, los puntos regalados están en el ledger (que no se modifica nunca) y la auditoría la referencia.
- **Cambios:**
  - `Campaign.hidden_at` (migración `notifications.0005_campaign_hidden_at`, un `AddField` nulo) y la propiedad `can_be_hidden`;
  - servicio `campaigns.hide_campaign`: solo propietario, con bloqueo, solo canceladas o repartidas, idempotente y auditado (`event="hidden"`);
  - `notification_selectors.campaigns_for_owner` excluye las quitadas, así que salen del historial y de «Enviar una campaña ya creada»;
  - vista `campaign_hide` (`comunicaciones/<public_id>/eliminar/`): confirmación con GET y acción con POST; las ya quitadas dan 404;
  - en la tabla, «Eliminar» está activo solo en canceladas y repartidas; en el resto aparece desactivado, con la explicación para lectores de pantalla.
- **Sin scroll lateral:**
  - **Campañas:** siempre en **tarjetas**, a cualquier ancho (nueva variante `.data-table-cards` en `assets/css/input.css`). Con 10 columnas no caben ni en pantallas anchas junto al menú lateral del dashboard, y `.data-table-fit` solo pasa a tarjetas por debajo de `xl`, que era el motivo del scroll que quedaba. En tarjetas no se ven las flechas de ordenar; el orden por defecto es el de siempre (las más recientes primero).
  - **Registro de notificaciones:** `.data-table-fit` (6 columnas: compacta desde `xl`, tarjetas por debajo).
  - Etiqueta en cada celda y `break-words` en los textos largos.
- **Admin:** nuevo `CampaignAdmin` en **solo lectura** y solo para propietarios (`apps/notifications/admin.py`, base común `ReadOnlyOwnerAdmin`, también para `NotificationAdmin`). Lista, filtros (estado, canal, «quitada del dashboard») y ficha sin editar ni borrar. Ahí se consultan también las campañas quitadas del dashboard.
- **Traducciones:** 11 entradas nuevas; `check` al día y completas.
- **Tests:** `tests/notifications/test_campaign_hide.py` (8 tests):
  - botón activo o desactivado según el estado;
  - quitar sin perder mensajes ni destinatarios, con auditoría e idempotente;
  - deja de verse en el historial y en la lista de copia;
  - borrador y programada rechazadas; 404;
  - solo el propietario;
  - campañas en tarjetas y registro con `data-table-fit`, todas las celdas con etiqueta;
  - admin solo lectura para el propietario e invisible para empleados.
- **Suite completa:** 1145 tests OK.
- (Esta implementación se revirtió una vez a petición del usuario y se volvió a aplicar el mismo día, añadiendo las tarjetas de las campañas.)
- **Reactivar campañas canceladas:** servicio `campaigns.reactivate_campaign` (solo propietario, con bloqueo, solo canceladas y no quitadas del dashboard, auditado `event="reactivated"`) y vista `campaign_reactivate` (`comunicaciones/<public_id>/reactivar/`, solo POST). La campaña vuelve a **borrador**: se edita con «Editar» y se programa con «Programar envío». Es seguro porque una cancelada nunca se repartió (solo se cancelan borradores y programadas), así que no tiene mensajes ni puntos regalados.
- **Fecha a la derecha:** en cada tarjeta, el nombre a la izquierda y la fecha de creación a la derecha del todo.
- **Comentario visible:** el comentario de plantilla de la tabla ocupaba dos líneas y se pintaba en la página (Django solo trata `{# … #}` como comentario en una línea). Ahora va en una; además, un test (`TemplateCommentsTests`) comprueba que ninguna plantilla de `templates/` tiene comentarios `{#` de varias líneas.
- **Tests:** `test_campaign_hide.py` pasa a 13 (reactivar: a borrador, editable y programable; solo canceladas no quitadas; solo propietario y POST; fecha a la derecha; plantillas sin comentarios multilínea). Suite completa: **1150 tests OK**.

### Conservación de datos: qué guardar y qué convendría borrar (recomendación, sin implementar)

- **Conservar:** compras, ledger de puntos, canjes, auditoría de acciones administrativas, campañas y su resultado, catálogo, eventos, recompensas y promociones (se archivan, no se borran). Explican los saldos y permiten atender reclamaciones.
- **Convendría purgar o anonimizar con un plazo** (lo fija el asesoramiento legal):
  - **Registro de notificaciones:** guarda el destinatario de cada envío; pasado un plazo (por ejemplo, 12–24 meses) se podría desligar del cliente, dejando los totales en la campaña.
  - **Auditoría de consultas de datos personales** (`CUSTOMER_DATA_VIEWED`, `RESERVATION_DATA_VIEWED`): con un plazo de conservación definido.
  - **Notas libres de reservas pasadas** (`notes`): pueden contener datos personales.
  - **Cuentas que pidan la supresión** (decisión P2-9 de `docs/auditoria-pre-fase-12.md`): falta implementar la anonimización del perfil.
  - **Ficheros huérfanos en `media/`** (imágenes sustituidas): no son datos personales, pero ocupan espacio.
  - **Ya se purgan:** tokens de verificación, sesiones y tokens de la API (`docs/despliegue.md`).
- Si se implementa, sería una fase propia: comando de retención con plazos configurables, tarea programada, tests y documentación de la política.

## 12. Ajuste posterior: enlaces de «Visítanos» en el pie (2026-10-17)

- **Petición:** que los enlaces de «Visítanos» (dirección, email, teléfono y redes) se vean como los de «Explora» y «A túa conta»: grises, sin subrayado y dorados al pasar el ratón.
- **Cambio:** `templates/components/business_info.html` elige la clase de los enlaces según el modo. En el pie (`compact`) usa `text-mist no-underline hover:text-gold`; en Contacto e Inicio, `link`, como hasta ahora. Sin CSS nuevo.
- **Test:** `test_footer_visit_links_look_like_the_footer_menu` (`tests/web/test_public_pages.py`). Suite completa: 1151 tests OK.
- **Nota de Comunicaciones:** bajo las campañas solo queda «"Eliminar" se activa en las campañas canceladas o ya repartidas…». Se quita la frase sobre `process_notifications` (en producción el reparto es automático cada 5 minutos, `deploy/cron/crontab`; en local se lanza a mano). Su cadena sale de los catálogos (`i18n.py make`).
