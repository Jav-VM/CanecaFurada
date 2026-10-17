# Fase 21 — Contenido editable de las secciones y artículos en «A cervexaría»

**Estado:** Completa (revisión visual en el navegador pendiente; ver §7).
**Fecha:** 2026-10-17.
**Depende de:** [Fase 20](fase-20-orden-secciones.md) (orden de las secciones) y [Fase 15](fase-15-idioma-gallego.md) (idiomas).

## 1. Objetivo y decisiones

- En **Dashboard → Contenido**, el bloque «Orden de las secciones» queda **separado** del formulario de textos (línea y margen).
- Cada fila tiene un botón **«Editar»** que abre la página de esa sección.

| Decisión (con el usuario, 2026-10-17) | Motivo |
|---|---|
| **Inicio:** se editan los **textos** (antetítulo, título, texto). | Las listas automáticas (cervezas, eventos, datos del local) siguen saliendo solas. |
| **A cervexaría:** textos e **imágenes**, y **artículos** del propietario. | Lo pidió el usuario. |
| Una imagen se muestra junto al texto; **dos o más forman una galería bajo el texto**. Máximo 12 por sección. | Lo pidió el usuario. Sin imágenes, «Nuestra historia» mantiene el cartel del X aniversario. |
| Los artículos son **secciones más** de A cervexaría: aparecen al final al crearlos y se ordenan u ocultan con las mismas flechas y casilla. | Lo pidió el usuario. |
| Artículos: **editar, ocultar y eliminar**. Eliminar pide confirmación, borra también los ficheros y queda en la auditoría sin el texto. | Lo pidió el usuario. Para quitarlo sin borrar: desmarcar «Mostrar». |
| **Campo vacío = texto de siempre, traducido.** Lo escrito se muestra tal cual en gallego y castellano. | Regla de la Fase 15 para el contenido del propietario. |
| En «Somos Caneca Furada» y «Nuestra historia», un texto vacío usa la «Presentación de la cervecería» de Contenido y, si tampoco hay, el texto por defecto. | Compatible con lo que ya había. |
| Texto plano (una línea en blanco separa párrafos), escapado. | Sin HTML del propietario en la web (XSS). |

## 2. Archivos

| Archivo | Cambio |
|---|---|
| `apps/web/models.py` + migración `0005_page_blocks` | `PageBlock` (página, clave, artículo, antetítulo, título, texto) y `PageBlockImage` (imagen validada, descripción, posición). Aditiva. |
| `apps/web/layout.py` | Textos por defecto de cada sección (`DEFAULT_TEXTS`). |
| `apps/web/blocks.py` (nuevo) | `save_block`, `create_article`, `delete_article` (solo propietario, en una transacción, auditados) y `page_sections` (textos resueltos para las páginas). |
| `apps/web/services.py` | `sections_for(page)`: lista blanca de A cervexaría = secciones fijas + artículos; `invalidate_cache`. |
| `apps/web/views.py`, `templates/web/home.html`, `about.html` | Las vistas arman `sections` y la página incluye la plantilla que elige el servidor. |
| `templates/web/home/_*.html`, `templates/web/about/_*.html` | Textos desde `section`; nuevos `_article.html`, `_figure.html`, `_gallery.html`. |
| `apps/dashboard/forms.py` | `PageBlockForm` con subida de varias imágenes (`MultipleImageField`). |
| `apps/dashboard/views.py`, `urls.py` | `section_edit` (`/dashboard/contenido/<página>/<sección>/`), `article_create`, `article_delete` (con confirmación). |
| `templates/dashboard/content.html`, `section_form.html`, `article_confirm_delete.html` | Separador, «Editar», «Nuevo artículo», formulario y confirmación. |
| `locale/gl`, `locale/es` | Cadenas nuevas traducidas. |

Sin variables de entorno nuevas. Las imágenes van a `media/pages/` con nombre aleatorio.

## 3. Uso

1. Dashboard → Contenido → «Orden de las secciones» → **Editar** en la sección.
2. Escribe solo lo que quieras cambiar: lo vacío muestra el texto de siempre (aparece en gris como ejemplo).
3. En A cervexaría: **Nuevo artículo** (título obligatorio). Puedes subir varias imágenes a la vez, describirlas y quitarlas.
4. Para eliminar un artículo: «Editar» → «Eliminar artículo» → confirmar.

Tras actualizar: `python manage.py migrate` y `python scripts/i18n.py compile`.

## 4. Seguridad

- Solo propietario (vistas y servicios); CSRF.
- Página y sección contra la lista blanca o un artículo existente; si no, 404.
- Solo se pueden quitar o describir imágenes de la sección editada.
- Imágenes con extensión y contenido real validados; una imagen falsa → 400.
- Texto escapado. Auditoría `SITE_CONTENT_UPDATED` con página, sección y evento, sin textos.

## 5. Tests

`tests/web/test_page_blocks.py` (15 tests):

- textos por defecto, cambio y vuelta al valor por defecto, escapado;
- Inicio sin imágenes; «Somos Caneca Furada» con la presentación de Contenido;
- una imagen como figura, varias como galería, descripción, quitar solo imágenes propias (también el fichero), imagen falsa y límite;
- artículos: crear al final con galería, título obligatorio, ordenar, ocultar, editar y eliminar (ficheros incluidos), secciones fijas no eliminables;
- accesos: 404 con página o sección desconocida, 403 a empleado y cliente, login para anónimo;
- separador y enlaces en Contenido.

## 6. Resultados

| Orden | Resultado |
|---|---|
| `python manage.py check` / `makemigrations --check --dry-run` | Sin incidencias / sin cambios |
| `python scripts/i18n.py check` | Traducciones al día y completas |
| `python manage.py spectacular --validate --fail-on-warn` | Idéntico a `docs/api/openapi.yaml` |
| `python manage.py test --settings=config.settings.test --noinput` | **1058 tests OK** (1043 previos + 15 nuevos), SQLite, 2026-10-17 |
| `python manage.py migrate` (PostgreSQL de desarrollo y `pruebas_dev/demo.sqlite3`) | `web.0005_page_blocks` aplicada |

## 7. Limitaciones y pendientes

- **Revisión visual** de la galería, las figuras y el formulario.
- El texto es plano: sin negritas ni enlaces.
- Lo escrito por el propietario no se traduce (Fase 15).
- Los textos de las secciones se leen de la base de datos en cada visita a Inicio y A cervexaría (dos consultas); no se cachean.
- La galería abre cada imagen en su URL; no hay visor a pantalla completa. Desde el 2026-10-17 es un carrusel (ver apartado 9).

## 8. Ajuste posterior: horario en su propia columna del pie (2026-10-17)

- **Petición:** separar el horario de «Visítanos» en el pie y mostrarlo a la derecha, como otra columna.
- **Cambios:**
  - `templates/components/business_info.html` admite `hide_hours`;
  - `templates/components/footer.html` usa `hide_hours` en «Visítanos» y añade la columna «Horario» (`data-footer-hours`), con «Pendiente de publicar» si no hay horario;
  - la separación entre columnas en escritorio pasa de `gap-x-20` a `gap-x-16` para que quepan las cinco;
  - `static/css/app.css` recompilado.
- Contacto e Inicio («El local») siguen mostrando el horario dentro de los datos del local.
- **Test:** `tests/web/test_public_pages.py::test_footer_shows_opening_hours_in_its_own_column`.
- **Suite completa:** **1059 tests OK**.
- **Pendiente:** revisión visual en escritorio y móvil.
- **Ajuste (2026-10-17):** cada franja del horario del pie va en una línea, con la hora a la derecha del día. Se probó también repartir el contenido del pie en subcolumnas para que no creciera hacia abajo, pero el usuario pidió revertirlo.

## 9. Ajuste posterior: galería en carrusel (2026-10-17)

- **Petición:** en A cervexaría, que la galería de una sección o artículo muestre una sola imagen a la vez, con el mismo tamaño, proporción y lugar que una imagen sola (primero se hizo a todo el ancho; el usuario lo cambió el mismo día), con una flecha a la izquierda (anterior) y otra a la derecha (siguiente). Los botones, transparentes: solo se ve la flecha.
- **Cambio:**
  - `templates/web/about/_gallery.html`: en vez de la cuadrícula de miniaturas, una pista horizontal con *scroll-snap* (`data-carousel`). El carrusel va en el sitio de la imagen sola: a la derecha del texto en pantallas grandes (`lg:grid-cols-2 lg:items-center`) y debajo en móvil, con ancho máximo `max-w-md`. Cada foto conserva su proporción (`h-auto w-full object-cover`, como `_figure.html`) y enlaza a su URL, que se abre en otra pestaña (`target="_blank"`, `rel="noopener noreferrer"`). Cada imagen se anuncia como «Imagen N de total» y la galería como carrusel (`aria-roledescription`).
  - `static/js/app.js`: muestra las flechas («Imagen anterior» / «Imagen siguiente»). Pasan una imagen, en bucle (de la última a la primera y al revés), con desplazamiento suave, o inmediato si el usuario prefiere reducir el movimiento. Con el foco en la galería también funcionan ← y →.
  - `assets/css/input.css` → `static/css/app.css` (`python scripts/tailwind.py build`): `.carousel-track`, sin barra de scroll, y `.carousel-arrow`, flecha blanca sobre un círculo oscuro translúcido (`bg-ink/45`, borde fino `ring-paper/20`, ligero desenfoque), que se oscurece al pasar el ratón (`bg-ink/70`) y pone la flecha dorada; separada 8 px del borde, con el anillo de foco general y un área de 56 px.
- **Sin JavaScript:** las flechas no se ven y las imágenes se pasan deslizando.
- Afecta a todas las galerías de A cervexaría: artículos (`_article.html`), Historia (`_historia.html`, que ahora va siempre en dos columnas: imagen, carrusel o el cartel del aniversario) y Cómo trabajamos (`_como.html`). Con una sola imagen no hay galería: se sigue usando la figura.
- **Traducciones:** «carrusel», «Imagen %(number)s de %(total)s», «Imagen anterior» e «Imagen siguiente» añadidas a mano en `locale/gl` («Imaxe … de …», «Imaxe anterior», «Imaxe seguinte») y `locale/es`, en el orden de `makemessages`. **Pendiente:** `python scripts/i18n.py check` y `compile` donde haya gettext (lo hace el CI). Mientras no se compilen los `.mo` en local, en gallego esos textos salen en castellano.
- **Tests:** 3 nuevos en `tests/web/test_page_blocks.py` (`test_gallery_is_a_carousel_one_image_at_a_time`, `test_gallery_alt_text_is_escaped`, `test_article_carousel_sits_next_to_the_text_like_a_single_image`). `python manage.py test --settings=config.settings.test --noinput` → **1085 tests OK**. El JavaScript no tiene tests automáticos en el repositorio, ni se ha podido comprobar su sintaxis con Node (no está instalado).
- **Pendiente:** revisión manual en navegador: flechas, paso en bucle, teclado, móvil y sin JS.
