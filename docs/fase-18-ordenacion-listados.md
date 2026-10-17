# Fase 18 — Ordenar los listados del dashboard por columnas

**Estado:** Completa (revisión visual en el navegador pendiente; ver §7).
**Fecha:** 2026-10-17.
**Depende de:** [Fase 9](fase-09-dashboard-propietario.md) (dashboard) y [Fase 15](fase-15-idioma-gallego.md) (traducciones).
**Siguiente:** [Fase 19](plan-de-fases.md) (filtro «sin gasto», selección de clientes y campañas con imagen y puntos).

## 1. Objetivo

Cada columna ordenable de los listados del dashboard tiene dos flechas (↑ ascendente, ↓ descendente) junto a su título. Se pueden combinar con los filtros y el periodo de la página.

## 2. Decisiones

| Decisión | Motivo |
|---|---|
| **Lista blanca por listado** (`{clave: campos}` en `apps/dashboard/views.py`). La URL solo lleva la clave (`?orden=fecha&dir=desc`). | Los nombres de campo del ORM nunca salen de la petición: no se puede ordenar por campos internos (p. ej. `password`) ni inyectar nada. Una clave o dirección desconocida deja el orden por defecto, sin error. |
| **Enlaces, sin JavaScript.** | Funciona igual sin JS, con teclado y con lector de pantalla (`aria-sort` y texto oculto «Ordenar por … ascendente»). |
| Al ordenar se **conservan los filtros** y se vuelve a la página 1; la paginación conserva el orden (`{% querystring %}`). | Cambiar el orden en la página 5 no tiene sentido. |
| Nulos siempre al final y `id` como desempate. | Paginación estable. |
| Las columnas de estado o tipo se ordenan por su **valor interno**, no por la etiqueta traducida. | El orden de la etiqueta cambiaría con el idioma. Agrupa igual los mismos valores. |
| Empleados y zonas se ordenan **en memoria** (`Sort.apply_list`). | Sus filas ya se calculan en Python (cifras de varios selectores). Son listados cortos. |
| Páginas con dos listados usan **prefijo**: recompensas (`r_orden`) y campañas (`c_orden`). | Ordenar una tabla no cambia la otra. |
| Sin flechas: columnas de acciones, «Detalle», «Bonificación», «Proporción»/«%» de zonas y las tablas de la ficha de cliente. | Son texto compuesto o derivado, o tablas que solo muestran los últimos movimientos (ordenarlas reordenaría solo esas filas). |

## 3. Listados y columnas

| Listado | Columnas ordenables |
|---|---|
| Clientes | cliente, email, verificación, alta, estado |
| Zonas de clientes | zona, clientes |
| Empleados | nombre, email, rol, estado, compras, importe, canjes |
| Compras | fecha, cliente, importe, puntos, registrada por, estado |
| Puntos | fecha, cliente, tipo, puntos |
| Recompensas | recompensa, coste, estado, unidades, utilizadas, pendientes |
| Canjes | solicitado, cliente, recompensa, puntos, estado, validado |
| Promociones | promoción, tipo, vigencia, estado, usos |
| Carta y cervezas | producto, categoría, precio, publicación, disponibilidad |
| Eventos | evento, empieza, estado, reservas, pendientes, personas confirmadas |
| Reservas | fecha, cliente, personas, evento, estado, solicitada |
| Campañas | campaña, canal, estado, destinatarios, enviadas, no enviadas, fallidas |
| Registro de notificaciones | fecha, tipo, canal, estado, intentos |

## 4. Archivos

| Archivo | Cambio |
|---|---|
| `apps/dashboard/sorting.py` (nuevo) | `Sort`: lee y valida `orden`/`dir`, `apply(queryset)` y `apply_list(filas)`. |
| `apps/dashboard/templatetags/dashboard_sort.py` (nuevo) + `templates/dashboard/_sort_th.html` | Etiqueta `{% sort_th sort "clave" _("Título") "num" %}`: cabecera con las dos flechas. |
| `apps/dashboard/views.py` | Columnas de cada listado y aplicación del orden en cada vista. |
| `templates/dashboard/*.html` (11 plantillas) | Cabeceras con `sort_th`. |
| `assets/css/input.css`, `static/css/app.css` | Clases `.sort-th`, `.sort-arrows`, `.sort-link` (compilado con `python scripts/tailwind.py build`). |
| `locale/gl`, `locale/es` | 2 cadenas nuevas. |

Sin migraciones ni variables de entorno nuevas.

## 5. Seguridad

- Lista blanca: nada de la petición llega a `order_by`.
- Los listados siguen exigiendo propietario en la vista y en los selectores (test de regresión 403).
- Los enlaces solo copian la consulta actual (filtros visibles). La búsqueda por nombre o email sigue en la sesión, no en la URL.

## 6. Tests y resultados

`tests/dashboard/test_sorting.py` (13 tests):

- unitarios de `Sort`: clave válida, valores desconocidos o maliciosos, prefijo, nulos al final;
- clientes: ascendente y descendente, columna desconocida, flechas y conservación de filtros, 403 a empleado y cliente;
- compras, puntos y empleados ordenados de verdad; dos listados independientes en Comunicaciones;
- **todas las columnas de todos los listados** en ambas direcciones responden 200.

| Orden | Resultado |
|---|---|
| `python manage.py check` | Sin incidencias |
| `python manage.py makemigrations --check --dry-run` | Sin cambios |
| `python scripts/i18n.py check` | Traducciones al día y completas |
| `python manage.py test tests.dashboard.test_sorting --settings=config.settings.test` | 13 tests OK |
| `python manage.py test --settings=config.settings.test --noinput` | **1009 tests OK** (996 previos + 13 nuevos), SQLite, 2026-10-17 |

## 7. Limitaciones y pendientes

- **Revisión visual** de las flechas en el navegador.
- En eventos, carta y cervezas, por debajo de 1280 px las filas se muestran como tarjetas y la cabecera se oculta (Fase 9): ahí no hay flechas. Para ordenar en el móvil, girar la pantalla o usar el ordenador.
- El orden de estados y tipos es el del valor interno, no el alfabético de la etiqueta.
