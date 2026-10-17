# Fase 23 — Artículos en Inicio y Eventos, y ajustes visuales

**Estado:** Completa (2026-10-17). Código, tests y CI en verde (commits `4fb5def` y `c57021d`); revisada en el navegador por el usuario.

## 1. Objetivo y alcance

1. **Artículos también en Inicio y Eventos**, con las mismas características que en La cervecería (Fase 21): título obligatorio, antetítulo, texto e imágenes (hasta 12). Una imagen va junto al texto y, con varias, un carrusel. Se crean, editan, ordenan, ocultan y eliminan desde Dashboard → Contenido.
2. **Copiar un artículo de otra página:** en «Nuevo artículo», debajo del formulario, la lista de artículos de las otras páginas con artículos. «Copiar aquí» crea en esta página una copia independiente (textos, imágenes y descripciones) y la abre para editarla.
3. **QR de canje con la cámara:** el QR de un canje no se leía con la cámara del panel (sí el del perfil). Corregido.
4. **Limitaciones conocidas corregidas:** idempotencia de «Copiar aquí» en el servidor, URL de Google Maps editable, comprobación de sintaxis del JavaScript con Node y test intermitente de compras.
5. **Ajustes visuales** pedidos el mismo día, documentados en el apartado de su fase:
   - **Contacto:** las dos secciones una al lado de la otra; en «El local», una línea de espacio entre cada título y su contenido, títulos algo más grandes, días del horario resaltados, «Teléfono: …» y debajo «E-mail: …», y la dirección enlazada a la ficha del local en Google Maps (también en el pie) → [Fase 22, §7](fase-22-secciones-otras-paginas.md#7-ajuste-posterior-contacto-en-dos-columnas-2026-10-17).
   - **Carta:** la versión en texto de la carta de grifos se ve directamente, sin desplegable → [Fase 22, §8](fase-22-secciones-otras-paginas.md#8-ajuste-posterior-versión-en-texto-de-la-carta-de-grifos-2026-10-17).
   - **A cervexaría:** galería en carrusel (una imagen a la vez, flechas, imagen en otra pestaña), con el tamaño y el sitio de una imagen sola → [Fase 21, §9](fase-21-contenido-secciones.md#9-ajuste-posterior-galería-en-carrusel-2026-10-17).

**Exclusiones:** crear y editar productos, categorías, estilos, carta de grifos, recompensas y promociones desde el dashboard sin pasar por el admin (será la **Fase 24**); artículos en Carta, Recompensas y Contacto; imágenes en las secciones fijas de Inicio y Eventos (siguen solo con textos); traducción de lo que escribe el propietario (Fase 15).

## 2. Criterios de aceptación

| Criterio | Estado |
|---|---|
| «Nuevo artículo» en Inicio, La cervecería y Eventos (y en ninguna otra página) | Completa (tests) |
| El artículo aparece al final de su página, visible, y entra en su lista de orden y visibilidad | Completa (tests) |
| Imágenes: una junto al texto, varias en carrusel; también en Inicio y Eventos | Completa (tests) |
| Editar y eliminar (con sus ficheros) desde su página | Completa (tests) |
| Solo el propietario; las páginas sin artículos dan 404; no se borra un artículo desde la URL de otra página | Completa (tests) |
| La base de datos rechaza artículos en otras páginas o sin título | Completa (tests) |
| «Nuevo artículo» lista solo los artículos de las otras páginas | Completa (tests) |
| «Copiar aquí» crea una copia independiente, con ficheros de imagen propios, al final de la página | Completa (tests) |
| Copiar: solo el propietario, solo POST, origen válido de otra página (si no, error sin cambios) | Completa (tests) |
| El QR de un canje es un QR normal (no Micro QR) y lo lee la cámara del panel | Completa (tests y comprobación con cámara) |
| Un doble envío de «Copiar aquí» crea una sola copia | Completa (tests) |
| La URL de Google Maps se edita en Contenido y solo admite enlaces de Google Maps | Completa (tests) |
| Sintaxis del JavaScript propio comprobada (local y CI) | Completa (local; el CI la repite) |
| Revisión visual en navegador | Completa (revisada en el navegador por el usuario el 2026-10-17) |

## 3. Decisiones técnicas

| Decisión | Motivo |
|---|---|
| `layout.ARTICLE_PAGES = (HOME, ABOUT, EVENTS)` como lista blanca única | Un solo sitio decide dónde hay artículos: servicios, vistas, plantilla del panel y restricción de BD lo usan (la restricción repite los valores, porque una migración no debe depender del código). |
| Los artículos llevan imágenes en cualquier página (`blocks.images_allowed(page, is_article)`); las secciones fijas, solo en La cervecería (`allows_images`) | «Mismas características» que en La cervecería, sin cambiar las secciones fijas, que no tienen hueco para imágenes en su diseño. |
| Misma plantilla `web/about/_article.html` para las tres páginas | Mismo aspecto y comportamiento (figura o carrusel). En Eventos las secciones ya van dentro de un `container-page`, así que ahí el artículo no abre otro (`border-t pt-10` en vez de `container-page … py-20`). |
| Rutas con la página: `contenido/<page>/articulos/nuevo/` y `contenido/<page>/<key>/eliminar/` | Sustituyen a las de `cerveceria` fija. `delete_article` filtra por página **y** clave (contra IDOR entre páginas). |
| Copia, no artículo compartido (decisión del usuario) | Cada copia se edita, ordena, oculta y elimina por separado. `copy_article` duplica los **ficheros** de imagen (nombre aleatorio con `upload_to`), así eliminar una copia no borra las imágenes de la otra. Si falla la copia de una imagen, se borran los ficheros ya escritos y la transacción deshace las filas. |
| Origen por `public_id` y fuera de la página destino | El formulario envía el UUID público, no el `pk`. El servicio lo busca con `select_for_update` entre los artículos de `ARTICLE_PAGES` **excluyendo** la página destino; cualquier otro valor da `ValidationError`. |
| Tras copiar, se abre la edición de la copia | Para retocar textos o imágenes enseguida. |
| QR de canje: `segno.make_qr` en `apps/core/qr.py` | **Causa:** `segno.make` crea un **Micro QR** si el contenido cabe; `CFR1:` + 12 caracteres salía como Micro QR M4, que no leen ni `BarcodeDetector` (`qr_code`) ni jsQR. El QR personal (`CF1:` + 32) salía como QR normal (2-M), por eso sí se leía. Ahora los dos QR se generan con `qr_data_uri`, que siempre usa `make_qr` (mismo tamaño y colores). |
| Doble envío de «Copiar aquí»: idempotencia en el servidor | Cada fila de la lista lleva su `idempotency_key` (UUID). `PageBlock.copy_key` es único: un segundo envío con la misma clave devuelve la copia ya hecha (misma redirección, una sola auditoría). Si llegan a la vez, la restricción única decide y el perdedor devuelve la del ganador (savepoint + `IntegrityError`). `data-loading` sigue desactivando el botón. |
| URL de Maps editable, solo de Google Maps | `BusinessInfo.maps_url`, validada en el modelo (`is_google_maps_url`): https, sin usuario, contraseña ni puerto, y host `maps.app.goo.gl` o `maps.google.com` (cualquier ruta), o `goo.gl`, `google.com` y `www.google.com` (ruta `/maps…`). Vacía: se usa la de `content.BUSINESS`. Así no se puede poner un enlace a otra web en la dirección. |
| Node solo para comprobar la sintaxis | `node --check` del JavaScript propio (no `static/vendor`), en local y en el CI (`actions/setup-node`). No se añaden tests de navegador (sin dependencias nuevas en el proyecto); el comportamiento se revisa con la lista del §8. |
| Migración solo de la restricción | `RemoveConstraint` + `AddConstraint` de `web_pageblock_article_shape`; no toca datos y los artículos que ya hay (todos en `cerveceria`) cumplen la nueva condición. Reversible. |

## 4. Archivos

- **Dominio:** `apps/web/layout.py` (`ARTICLE_PAGES`), `apps/web/blocks.py` (`images_allowed`, `create_article(page=…)`, `delete_article(page=…)`, `copyable_articles`, `copy_article`, `is_editable`, `Section.page`), `apps/web/services.py` (`sections_for`), `apps/web/models.py` (restricción y docstring).
- **Migraciones:** `apps/web/migrations/0007_articles_on_more_pages.py` (restricción) y `0008_copy_key_and_maps_url.py` (dos `AddField`: `PageBlock.copy_key`, UUID único y nulo, y `BusinessInfo.maps_url`, en blanco; no tocan datos y son reversibles).
- **QR:** nuevo `apps/core/qr.py`; `apps/rewards/views.py` (QR del canje) y `apps/loyalty/views.py` (QR personal) lo usan.
- **URL de Maps:** `apps/web/models.py` (`maps_url`, `is_google_maps_url`), `apps/web/services.py` (`EDITABLE_FIELDS`), `apps/web/content.py` (valor por defecto), `apps/dashboard/forms.py` (`BusinessInfoForm.maps_url`).
- **CI:** `.github/workflows/ci.yml` (paso «Sintaxis del JavaScript propio»).
- **Panel:** `apps/dashboard/urls.py` (nueva `contenido/<page>/articulos/copiar/`), `apps/dashboard/views.py` (`article_create(page)`, `article_copy(page)`, `article_delete(page, key)`, `_layouts`, `_block_form_view` con `copy_sources`), `templates/dashboard/content.html` (botón en las tres páginas), `section_form.html` (lista «Usar un artículo de otra página» y enlaces con la página) y `article_confirm_delete.html`, `apps/dashboard/forms.py` (ayuda del campo de imágenes: «dos o más, en un carrusel en su lugar»).
- **Web:** `templates/web/about/_article.html`.
- **Traducciones:** cambiada la ayuda de imágenes y añadidos los 8 textos de la copia en `locale/gl` y `locale/es` (más las cadenas de los ajustes visuales, ver sus apartados).
- **Tests:** `tests/web/test_page_blocks.py`, `tests/web/test_public_pages.py`, `tests/core/test_qr.py` (nuevo), `tests/rewards/test_views.py`, `tests/loyalty/test_qr.py` y `tests/purchases/test_views.py`.

Sin variables de entorno nuevas.

## 5. Uso

Dashboard → Contenido → «Orden de las secciones» → en **Inicio**, **La cervecería** o **Eventos**, «Nuevo artículo». Título obligatorio; texto e imágenes opcionales. Al guardar aparece al final de esa página y se puede subir, bajar, ocultar («Mostrar»), editar o eliminar (desde «Editar» → «Eliminar artículo»).

Para reutilizar un artículo de otra página: en «Nuevo artículo», bloque «Usar un artículo de otra página» → «Copiar aquí». Se abre la copia para revisarla; aparece al final de la página, visible.

Enlace de la dirección: Dashboard → Contenido → «Enlace a Google Maps» (en Google Maps: «Compartir» → «Copiar enlace»). Vacío: el de siempre.

Antes de usarlo en una base que ya existe: `python manage.py migrate` (aplica `web.0007_articles_on_more_pages` y `web.0008_copy_key_and_maps_url`).

Comprobar el JavaScript en local (requiere Node.js; en Windows: `winget install --id OpenJS.NodeJS.LTS --exact`):

```powershell
Get-ChildItem static/js/*.js | ForEach-Object { node --check $_.FullName }
```

## 6. Seguridad y privacidad

- Todas las operaciones pasan por los servicios de `apps/web/blocks.py`: solo propietario (`_require_owner`, además de `@owner_required` en las vistas), en una transacción y auditadas sin textos (`metadata`: página, sección y evento).
- La página se comprueba contra la lista blanca en la vista (404) y en el servicio (`ValidationError`). La BD también la protege (restricción `web_pageblock_article_shape`).
- Las imágenes usan los mismos validadores (extensión, contenido real de imagen, máximo 12) y nombres aleatorios. Los textos y descripciones se escapan en las plantillas.
- Formularios con CSRF; eliminar pide confirmación y solo acepta POST para borrar. Copiar solo acepta POST (`@require_POST`) y devuelve 404 si la página no admite artículos.
- La auditoría de la copia guarda página y clave de destino y de origen, nunca los textos. La clave de idempotencia es un UUID al azar, sin datos personales.
- La URL de Maps solo admite enlaces https de Google Maps (validada en el modelo, también si se guarda desde otro sitio) y se pinta con autoescape y `rel="noopener noreferrer"`.
- El QR sigue generándose en el servidor como SVG en data URI: sin peticiones a terceros. El contenido del QR no cambia, solo el tipo de símbolo.

## 7. Pruebas y resultados

| Comando | Resultado (2026-10-17) |
|---|---|
| `python manage.py makemigrations --check --dry-run --settings=config.settings.test` | Sin cambios pendientes |
| `python manage.py check --settings=config.settings.test` | Sin problemas |
| `python manage.py test --settings=config.settings.test --noinput` | **1108 tests OK** (SQLite) |
| `python manage.py spectacular --validate --fail-on-warn` + comparación con `docs/api/openapi.yaml` | Idéntico |
| `node --check` del JavaScript propio | Sin errores en `app.js` y `qr-scanner.js` (Node 24.20.0) |
| `python scripts/i18n.py check` | Al día y completas: en el CI de `4fb5def` y `c57021d` (en verde) y en local tras instalar gettext (Fase 24) |

Tests nuevos (`ArticlesOnMorePagesTests`, 10): artículos con carrusel en Inicio y Eventos, sin contenedores anidados en Eventos, figura con una imagen, editar y eliminar con borrado de ficheros, 404 en páginas sin artículos, no borrar desde la URL de otra página, solo el propietario, secciones fijas de Inicio/Eventos sin imágenes, botón en Contenido solo en las tres páginas y restricción de BD. Adaptados los de la Fase 21 a las rutas con página.

Tests del cierre: `tests/core/test_qr.py` (3: la causa con `segno.make`, `qr_symbol` nunca es Micro QR, el SVG tiene 21 módulos), el QR de la página del canje con 21 módulos (`tests/rewards`), el QR personal construido con `qr_data_uri` (`tests/loyalty`), doble envío con la misma clave = una copia y clave no válida = 400 (`CopyArticleTests`), URL de Maps editable con vuelta al valor por defecto y rechazo de http, otros dominios, subdominios falsos, rutas que no son de Maps, credenciales, puerto y `javascript:` (`tests/web/test_public_pages.py`). El test intermitente de compras quita del HTML el UUID aleatorio de `idempotency_key` antes de buscar los datos ficticios (podía contener «1996» por azar).

Tests de la copia (`CopyArticleTests`, 6): la lista solo muestra artículos de otras páginas (y no sale al editar), mensaje sin artículos, copia independiente con textos, descripciones y ficheros propios (eliminar la copia no toca el original), orígenes no válidos (misma página, sección fija, UUID inexistente o mal formado, vacío) → 400 sin cambios, página sin artículos → 404, solo propietario y solo POST.

## 8. Limitaciones y pendientes

- **Revisión en el navegador:** hecha por el usuario (QR de canje con la cámara, carrusel, artículos en Inicio y Eventos, «Copiar aquí», Contacto, Carta y la URL de Maps).
- **Traducciones:** comprobadas con gettext en local y en el CI.
- El JavaScript solo tiene comprobación de sintaxis (`node --check`), no tests de comportamiento en navegador.
- Los artículos de Inicio usan el mismo diseño que en La cervecería; si se quiere otro estilo para el inicio, sería un cambio aparte.
- **Siguiente fase:** [Fase 24](fase-24-dashboard-sin-admin.md) (crear y editar en el dashboard sin pasar por el admin).
