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
- La galería abre cada imagen en su URL; no hay visor a pantalla completa.
