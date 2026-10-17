# Fase 23 — Artículos en Inicio y Eventos, y ajustes visuales

**Estado:** En curso (2026-10-17). Código y tests hechos; falta la revisión visual en el navegador y la comprobación de traducciones con gettext (ver §7).

## 1. Objetivo y alcance

1. **Artículos también en Inicio y Eventos**, con las mismas características que en La cervecería (Fase 21): título obligatorio, antetítulo, texto e imágenes (hasta 12). Una imagen va junto al texto y, con varias, un carrusel. Se crean, editan, ordenan, ocultan y eliminan desde Dashboard → Contenido.
2. **Copiar un artículo de otra página:** en «Nuevo artículo», debajo del formulario, la lista de artículos de las otras páginas con artículos. «Copiar aquí» crea en esta página una copia independiente (textos, imágenes y descripciones) y la abre para editarla.
3. **Ajustes visuales** pedidos el mismo día, documentados en el apartado de su fase:
   - **Contacto:** las dos secciones una al lado de la otra; en «El local», una línea de espacio entre cada título y su contenido, títulos algo más grandes, días del horario resaltados, «Teléfono: …» y debajo «E-mail: …», y la dirección enlazada a la ficha del local en Google Maps (también en el pie) → [Fase 22, §7](fase-22-secciones-otras-paginas.md#7-ajuste-posterior-contacto-en-dos-columnas-2026-10-17).
   - **Carta:** la versión en texto de la carta de grifos se ve directamente, sin desplegable → [Fase 22, §8](fase-22-secciones-otras-paginas.md#8-ajuste-posterior-versión-en-texto-de-la-carta-de-grifos-2026-10-17).
   - **A cervexaría:** galería en carrusel (una imagen a la vez, flechas, imagen en otra pestaña), con el tamaño y el sitio de una imagen sola → [Fase 21, §9](fase-21-contenido-secciones.md#9-ajuste-posterior-galería-en-carrusel-2026-10-17).

**Exclusiones:** artículos en Carta, Recompensas y Contacto; imágenes en las secciones fijas de Inicio y Eventos (siguen solo con textos); traducción de lo que escribe el propietario (Fase 15).

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
| Revisión visual en navegador | Pendiente |

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
| Doble envío: solo en el cliente | `data-loading` desactiva el botón al enviar. En el servidor no hay restricción: dos envíos seguidos crearían dos copias (inofensivo; la sobrante se elimina). No se añade un campo ni una migración para esto. |
| Migración solo de la restricción | `RemoveConstraint` + `AddConstraint` de `web_pageblock_article_shape`; no toca datos y los artículos que ya hay (todos en `cerveceria`) cumplen la nueva condición. Reversible. |

## 4. Archivos

- **Dominio:** `apps/web/layout.py` (`ARTICLE_PAGES`), `apps/web/blocks.py` (`images_allowed`, `create_article(page=…)`, `delete_article(page=…)`, `copyable_articles`, `copy_article`, `is_editable`, `Section.page`), `apps/web/services.py` (`sections_for`), `apps/web/models.py` (restricción y docstring).
- **Migración:** `apps/web/migrations/0007_articles_on_more_pages.py`.
- **Panel:** `apps/dashboard/urls.py` (nueva `contenido/<page>/articulos/copiar/`), `apps/dashboard/views.py` (`article_create(page)`, `article_copy(page)`, `article_delete(page, key)`, `_layouts`, `_block_form_view` con `copy_sources`), `templates/dashboard/content.html` (botón en las tres páginas), `section_form.html` (lista «Usar un artículo de otra página» y enlaces con la página) y `article_confirm_delete.html`, `apps/dashboard/forms.py` (ayuda del campo de imágenes: «dos o más, en un carrusel en su lugar»).
- **Web:** `templates/web/about/_article.html`.
- **Traducciones:** cambiada la ayuda de imágenes y añadidos los 8 textos de la copia en `locale/gl` y `locale/es` (más las cadenas de los ajustes visuales, ver sus apartados).
- **Tests:** `tests/web/test_page_blocks.py`.

Sin variables de entorno nuevas.

## 5. Uso

Dashboard → Contenido → «Orden de las secciones» → en **Inicio**, **La cervecería** o **Eventos**, «Nuevo artículo». Título obligatorio; texto e imágenes opcionales. Al guardar aparece al final de esa página y se puede subir, bajar, ocultar («Mostrar»), editar o eliminar (desde «Editar» → «Eliminar artículo»).

Para reutilizar un artículo de otra página: en «Nuevo artículo», bloque «Usar un artículo de otra página» → «Copiar aquí». Se abre la copia para revisarla; aparece al final de la página, visible.

Antes de usarlo en una base que ya existe: `python manage.py migrate` (aplica `web.0007_articles_on_more_pages`).

## 6. Seguridad y privacidad

- Todas las operaciones pasan por los servicios de `apps/web/blocks.py`: solo propietario (`_require_owner`, además de `@owner_required` en las vistas), en una transacción y auditadas sin textos (`metadata`: página, sección y evento).
- La página se comprueba contra la lista blanca en la vista (404) y en el servicio (`ValidationError`). La BD también la protege (restricción `web_pageblock_article_shape`).
- Las imágenes usan los mismos validadores (extensión, contenido real de imagen, máximo 12) y nombres aleatorios. Los textos y descripciones se escapan en las plantillas.
- Formularios con CSRF; eliminar pide confirmación y solo acepta POST para borrar. Copiar solo acepta POST (`@require_POST`) y devuelve 404 si la página no admite artículos.
- La auditoría de la copia guarda página y clave de destino y de origen, nunca los textos.

## 7. Pruebas y resultados

| Comando | Resultado (2026-10-17) |
|---|---|
| `python manage.py makemigrations --check --dry-run --settings=config.settings.test` | Sin cambios pendientes |
| `python manage.py check --settings=config.settings.test` | Sin problemas |
| `python manage.py test --settings=config.settings.test --noinput` | **1101 tests OK** (SQLite) |
| `python scripts/i18n.py check` | **No ejecutado**: GNU gettext no está instalado en este equipo. Las entradas de los `.po` se han editado a mano siguiendo el orden de `makemessages`; lo comprobará el CI |

Tests nuevos (`ArticlesOnMorePagesTests`, 10): artículos con carrusel en Inicio y Eventos, sin contenedores anidados en Eventos, figura con una imagen, editar y eliminar con borrado de ficheros, 404 en páginas sin artículos, no borrar desde la URL de otra página, solo el propietario, secciones fijas de Inicio/Eventos sin imágenes, botón en Contenido solo en las tres páginas y restricción de BD. Adaptados los de la Fase 21 a las rutas con página.

Tests de la copia (`CopyArticleTests`, 6): la lista solo muestra artículos de otras páginas (y no sale al editar), mensaje sin artículos, copia independiente con textos, descripciones y ficheros propios (eliminar la copia no toca el original), orígenes no válidos (misma página, sección fija, UUID inexistente o mal formado, vacío) → 400 sin cambios, página sin artículos → 404, solo propietario y solo POST.

## 8. Limitaciones y pendientes

- **Doble clic en «Copiar aquí»** sin JavaScript podría crear dos copias (ver §3).
- **Revisión visual** de los artículos en Inicio y Eventos, la lista de copia y de los ajustes visuales (Contacto, Carta, carrusel). El JavaScript del carrusel no tiene tests automáticos.
- **Traducciones:** ejecutar `python scripts/i18n.py check` y `compile` donde haya gettext.
- Los artículos de Inicio usan el mismo diseño que en La cervecería; si se quiere otro estilo para el inicio, sería un cambio aparte.
- **Siguiente paso:** revisión visual, `migrate` en la base local y commit de la fase.
