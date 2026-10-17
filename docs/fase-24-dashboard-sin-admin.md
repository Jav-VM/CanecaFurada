# Fase 24 — Crear y editar en el dashboard sin pasar por el admin

**Estado:** En curso (2026-10-17). Código, traducciones y tests hechos; falta la revisión manual en el navegador (§8).

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
| Revisión manual en navegador | Pendiente |

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

- **Revisión manual:** crear y editar cada ficha desde el dashboard sin llegar a `/admin/`, con y sin imagen, y comprobar los mensajes de error.
- Borrar categorías y estilos sigue en la administración avanzada (decisión de la fase).
- Al sustituir una imagen, el fichero anterior se queda en `media/`, como ya pasaba con el admin.
- La creación de empleados ya estaba en el dashboard (Fase 9); alguna guía antigua del README todavía lo describe en el admin.
- **Siguiente paso:** revisión manual, `migrate` y commit de la fase.

## 9. Ajuste posterior: Empleados y Promociones sin scroll horizontal (2026-10-17)

- **Petición:** que el contenido de Empleados y Promociones se ajuste al ancho de la sección, sin scroll lateral.
- **Cambio:** sus tablas usan `.data-table-fit` (el mismo patrón que Eventos, Carta y Cervezas). Desde `xl` (80rem) son tablas compactas; por debajo, una tarjeta por fila con la etiqueta de cada dato (`data-label`), el nombre como título (`cell-title`) y las acciones al final (`cell-buttons` / `cell-actions`). Plantillas: `templates/dashboard/employees.html` y `promotions.html`; en `assets/css/input.css` solo cambia el comentario (sin clases nuevas, `app.css` igual).
- Sin textos nuevos que traducir: las etiquetas son las de las cabeceras.
- **Tests:** `FitTablesTests` en `tests/dashboard/test_phase24_forms.py` (las dos tablas usan `data-table-fit` y todas sus celdas llevan etiqueta).
- **Pendiente:** revisar las dos páginas en el navegador a varios anchos (móvil, portátil, escritorio).

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
- **Pendiente:** probarlo en el navegador y repartir con `python manage.py process_notifications`.
