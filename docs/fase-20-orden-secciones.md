# Fase 20 — Ordenar y ocultar las secciones de «Inicio» y «La cervecería»

**Estado:** Completa (revisión visual en el navegador pendiente; ver §7).
**Fecha:** 2026-10-17.
**Depende de:** [Fase 9](fase-09-dashboard-propietario.md) (Contenido del local) y [Fase 10](fase-10-eventos-reservas-notificaciones.md) (textos del inicio).

## 1. Objetivo y decisiones

En **Dashboard → Contenido → Orden de las secciones** el propietario sube, baja u oculta las secciones de las dos páginas.

| Decisión (con el usuario, 2026-10-17) | Motivo |
|---|---|
| En **Dashboard → Contenido**, no en el admin técnico. | Allí ya edita los textos de esas páginas. |
| **Ordenar y ocultar** (flechas ↑/↓ y casilla «Mostrar»). | Permite quitar, p. ej., «Eventos destacados» si no hay eventos. |
| **Fijos arriba:** el aviso destacado y la portada del inicio; la cabecera de La cervecería. | La página siempre empieza por la presentación. |
| **Lista blanca** de secciones por página (`apps/web/layout.py`). Lo guardado se normaliza: claves desconocidas o repetidas fuera, las que falten se añaden al final visibles. | Nada de la petición elige qué plantilla se incluye, y la página nunca se rompe aunque cambien las secciones del código. |
| Sin JavaScript: cada flecha envía el formulario y guarda al momento, también las casillas «Mostrar». | Funciona igual con teclado y sin JS. |
| Se guarda en `BusinessInfo` (fila única, cacheada) y **no** entra en `EDITABLE_FIELDS`. | Reutiliza caché e invalidación; el formulario de textos no puede cambiar el orden. |
| La carta y «El local» llevan ahora margen vertical propio (`py-10`). | Antes dependían de sus vecinas; al moverlas podían quedar pegadas a la portada o a otra tarjeta. |

## 2. Secciones

| Página | Secciones movibles (orden por defecto) |
|---|---|
| Inicio | Somos Caneca Furada · La carta de la casa · Nuestras cervezas · Programa de puntos · Eventos destacados · El local |
| La cervecería | Nuestra historia · Cómo trabajamos |

## 3. Archivos

| Archivo | Cambio |
|---|---|
| `apps/web/models.py` + migración `0004_page_layouts` | `BusinessInfo.home_layout` y `about_layout` (`JSONField`, vacío = orden por defecto). Aditiva. |
| `apps/web/layout.py` (nuevo) | Lista blanca, `normalize`, `move`, `with_visibility`, `visible_keys`, `rows`. |
| `apps/web/services.py` | `business_info()` expone `home_sections` / `about_sections`; `page_layout(page)` y `update_page_layout(...)` (solo propietario, idempotente, auditado, invalida la caché). |
| `templates/web/home.html`, `about.html` + `templates/web/home/_*.html`, `templates/web/about/_*.html` | Una plantilla parcial por sección; la página las incluye en el orden guardado. Contenido igual que antes. |
| `apps/dashboard/views.py`, `urls.py`, `templates/dashboard/content.html` | Vista `content_layout` (`POST /dashboard/contenido/orden/`) y bloque «Orden de las secciones». |
| `locale/gl`, `locale/es` | Cadenas nuevas. |

Sin variables de entorno nuevas.

## 4. Seguridad

- Solo propietario (vista y servicio); CSRF; `GET` → 405.
- Páginas y secciones validadas contra la lista blanca: una desconocida (incluido un intento de ruta como `../../base`) → 400 sin cambios.
- Auditoría `SITE_CONTENT_UPDATED` con el nombre del campo, sin más datos.

## 5. Tests

`tests/web/test_page_layout.py` (12 tests):

- normalización, movimientos en los extremos y visibilidad;
- orden por defecto igual al anterior;
- subir y ocultar cambia el orden real de la home; aviso y portada siguen primeros;
- orden de La cervecería y ocultar una sección;
- flechas en el dashboard;
- página o sección desconocidas → 400;
- repetir sin cambios no audita;
- accesos: 405, 403 a empleado y cliente, login para anónimo;
- el formulario de Contenido no toca el orden.

## 6. Resultados

| Orden | Resultado |
|---|---|
| `python manage.py check` / `makemigrations --check --dry-run` | Sin incidencias / sin cambios |
| `python scripts/i18n.py check` | Traducciones al día y completas |
| `python manage.py spectacular --validate --fail-on-warn` | Idéntico a `docs/api/openapi.yaml` |
| `python manage.py test --settings=config.settings.test --noinput` | **1043 tests OK** (1031 previos + 12 nuevos), SQLite, 2026-10-17 |
| `python manage.py migrate` (PostgreSQL de desarrollo y `pruebas_dev/demo.sqlite3`) | `web.0004_page_layouts` aplicada |

## 7. Limitaciones y pendientes

- **Revisión visual:** «Programa de puntos» y «Cómo trabajamos» tienen fondo de banda; según el orden pueden quedar dos bandas seguidas o una banda pegada a la portada.
- Con caché local en varios procesos, el cambio puede tardar hasta 5 minutos en verse (igual que el resto del contenido).
- Solo se ordenan secciones completas; su contenido interno no cambia.
