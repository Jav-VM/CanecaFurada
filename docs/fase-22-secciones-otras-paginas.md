# Fase 22 — Secciones de Carta, Agasallos, Eventos y Contacto

**Estado:** Completa (revisión visual en el navegador pendiente; ver §6).
**Fecha:** 2026-10-17.
**Depende de:** [Fase 20](fase-20-orden-secciones.md) (orden) y [Fase 21](fase-21-contenido-secciones.md) (textos editables).

## 1. Objetivo y decisiones

En **Dashboard → Contenido → Orden de las secciones** aparecen también **Carta, Recompensas (Agasallos), Eventos y Contacto**, con las mismas flechas, la casilla «Mostrar» y el botón «Editar».

| Decisión (con el usuario, 2026-10-17) | Motivo |
|---|---|
| **Como Inicio:** ordenar, ocultar y editar textos (antetítulo, título, texto). Sin imágenes ni artículos. | Las listas automáticas (carta, recompensas, eventos, datos del local) siguen saliendo solas. |
| **Contacto:** «El local» y «¿Tienes cuenta?» pasan a ser dos secciones, una debajo de otra (antes iban lado a lado). | Así se pueden ordenar por separado. |
| Fijos arriba: la cabecera de cada página; en la Carta, el índice de categorías; en Contacto, el aviso «Reservas por teléfono» (Fase 17). | La página siempre empieza igual. El índice solo enlaza a «Grifos» si esa sección se muestra. |
| **Textos que dependen del estado** («Únete al club» / «Ya formas parte», el texto de «¿Quieres reservar mesa?» según las reservas online) siguen cambiando solos mientras el propietario no escriba uno propio. | No se pierde el comportamiento actual. |
| «Carta por categorías» y «Próximos eventos» no llevan encabezado salvo que el propietario escriba título o texto. | Igual que antes. |
| La pizarra de grifos usa los textos del propietario; sin ellos, «En grifo» y el título de la pizarra (o «Carta de grifos»). | `components/tap_menu.html` admite textos opcionales. |

## 2. Secciones

| Página | Secciones (orden por defecto) |
|---|---|
| Carta | Carta de grifos · Carta por categorías |
| Recompensas | Cómo funciona · Recompensas disponibles · Únete al club |
| Eventos | Próximos eventos · ¿Quieres reservar mesa? |
| Contacto | El local · ¿Tienes cuenta? |

## 3. Archivos

| Archivo | Cambio |
|---|---|
| `apps/web/models.py` + migración `0006_more_page_layouts` | `menu_layout`, `rewards_layout`, `events_layout`, `contact_layout`; `PageBlock.page` admite las 4 páginas (CHECK actualizado). Aditiva. |
| `apps/web/layout.py` | Páginas, secciones, carpetas de plantillas y textos por defecto nuevos. |
| `apps/web/services.py` | `business_info()` expone las secciones visibles de todas las páginas (`page_sections_visible`); se mantienen `home_sections`/`about_sections`. |
| `apps/web/blocks.py` | `page_sections` y la plantilla de cada sección, genéricos por página. |
| `apps/web/views.py` | `MenuView`, `RewardsView`, `EventsView`, `ContactView` añaden `sections`. |
| `templates/web/{menu,rewards,events,contact}.html` + `templates/web/{menu,rewards,events,contact}/_*.html`, `templates/components/tap_menu.html` | Una plantilla parcial por sección, con el mismo contenido que antes. |
| `locale/gl`, `locale/es` | Cadenas nuevas. |

El dashboard no necesita cambios: «Orden de las secciones» recorre todas las páginas definidas.

## 4. Seguridad

Igual que en las Fases 20–21:

- solo propietario (vistas y servicios);
- CSRF;
- lista blanca de páginas y secciones (desconocidas → 404/400);
- texto escapado;
- sin imágenes fuera de La cervecería;
- auditoría sin textos.

## 5. Tests y resultados

`tests/web/test_more_page_layouts.py` (14 tests):

- orden por defecto idéntico al anterior;
- mover y ocultar en las cuatro páginas;
- el índice de la carta enlaza a «Grifos» solo si se muestra;
- el aviso de reservas por teléfono sigue arriba;
- editar textos y volver al de siempre;
- textos que dependen de la sesión o de las reservas online;
- el texto propio sustituye al dependiente;
- encabezado del listado solo si se escribe;
- título de la pizarra;
- escapado;
- sin imágenes;
- secciones desconocidas;
- accesos;
- bloques nuevos en el dashboard.

| Orden | Resultado |
|---|---|
| `python manage.py check` / `makemigrations --check --dry-run` | Sin incidencias / sin cambios |
| `python scripts/i18n.py check` | Traducciones al día y completas |
| `python manage.py spectacular --validate --fail-on-warn` | Idéntico a `docs/api/openapi.yaml` |
| `python manage.py test --settings=config.settings.test --noinput` | **1073 tests OK** (1059 previos + 14 nuevos), SQLite, 2026-10-17 |
| `python manage.py migrate` (PostgreSQL de desarrollo y `pruebas_dev/demo.sqlite3`) | `web.0006_more_page_layouts` aplicada |

## 6. Limitaciones y pendientes

- **Revisión visual** de las cuatro páginas, sobre todo Contacto, que ahora tiene las dos tarjetas una debajo de otra.
- Lo escrito por el propietario no se traduce (Fase 15).
- Los botones (Canjear, Solicitar reserva, Entrar…) no se editan.
