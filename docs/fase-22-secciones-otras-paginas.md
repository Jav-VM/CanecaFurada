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

- **Revisión visual** de las cuatro páginas, sobre todo Contacto.

## 7. Ajuste posterior: Contacto en dos columnas (2026-10-17)

- **Petición:** las dos secciones de Contacto («El local» y «¿Tienes cuenta?»), una al lado de la otra.
- **Cambio:** en `templates/web/contact.html` las secciones van dentro de una rejilla (`data-contact-sections`) con dos columnas desde `md` (48rem); en móvil se apilan. Se mantiene el orden que elige el propietario. Si solo hubiera una sección, ocupa todo el ancho. El aviso de reservas por teléfono sigue arriba, a todo el ancho.
- Sin CSS nuevo: las clases ya estaban en `static/css/app.css`.
- **Espacio en «El local»:** `components/business_info.html` acepta `spaced`. Contacto lo activa y añade `mt-5` (una línea de espacio) entre cada título (Dirección, Horario, Contacto, Redes) y su contenido. Inicio y el pie no cambian.
- **Teléfono y email etiquetados:** con `spaced`, el campo «Contacto» muestra «Teléfono: …» y, justo debajo, «E-mail: …» (cada uno solo si el propietario lo ha rellenado; sin ninguno, «Pendiente de publicar»). Inicio y el pie siguen igual.
- **Horario y títulos:** con `spaced`, los días del horario van resaltados en `text-paper`, sin negrita (como «Teléfono» y «E-mail»), y los títulos de «El local» (Dirección, Horario, Contacto, Redes) pasan de `text-sm` a `text-base`. Inicio y el pie siguen igual. Ajustado `test_content_is_published_on_the_public_site` (`tests/dashboard/`) al día resaltado.
- **Dirección en Google Maps:** con `spaced`, si hay dirección, enlaza a la ficha del local en Google Maps (`https://maps.app.goo.gl/1azgzDRChyNmEtHy8`), con `rel="noopener noreferrer"` como las redes. La URL es un dato fijo de la marca en `apps/web/content.py` (`BUSINESS["maps_url"]`): no se edita desde el dashboard (para eso haría falta un campo nuevo en `BusinessInfo` y su migración). Sin dirección no hay enlace. No se carga nada de Google hasta que el visitante pulsa.
- **Pie:** la dirección de «Visítanos» enlaza a la misma ficha (opción `map_link` de `components/business_info.html`, que solo activa ese enlace). «El local» de Inicio no cambia.
- **Traducciones:** «Teléfono» ya estaba en el catálogo; se ha movido a la posición que le corresponde ahora que `business_info.html` lo usa. «E-mail» se ha añadido (traducción: «E-mail»). Las dos cosas se han hecho a mano en `locale/gl` y `locale/es`, en el orden que genera `makemessages`, porque GNU gettext no está instalado en este equipo. **Pendiente:** ejecutar `python scripts/i18n.py check` donde haya gettext (lo hace el CI).
- **Tests:** 7 nuevos en `tests/web/test_public_pages.py` (`test_contact_sections_are_side_by_side`, `test_contact_local_has_a_line_between_title_and_content`, `test_contact_local_labels_phone_and_email`, `test_contact_local_email_only_has_no_phone_line`, `test_contact_local_highlighted_days_and_larger_titles`, `test_contact_local_address_links_to_google_maps`, `test_contact_local_without_address_has_no_map_link`). `python manage.py test --settings=config.settings.test --noinput` → **1080 tests OK**.
- **Pendiente:** revisión visual de `/contacto/`.
- Lo escrito por el propietario no se traduce (Fase 15).
- Los botones (Canjear, Solicitar reserva, Entrar…) no se editan.

## 8. Ajuste posterior: versión en texto de la carta de grifos (2026-10-17)

- **Petición:** en Carta, que la versión en texto de la carta de grifos (la que escribe el administrador en el admin, `TapMenu.text_alternative`) se vea directamente debajo de la imagen, sin el enlace desplegable «Ver la carta de grifos en texto».
- **Cambio:** `templates/components/tap_menu.html` ya no usa `<details>`/`<summary>`. El texto se muestra en un párrafo (`data-tap-menu-text`) con `linebreaksbr`, escapado por Django. Si no hay texto, no se pinta nada. El `alt` de la imagen sigue avisando de que la versión en texto está a continuación.
- **Traducciones:** se ha quitado a mano la cadena «Ver la carta de grifos en texto» de `locale/gl` y `locale/es`, porque ya no se usa y `makemessages --no-obsolete` la eliminaría. **Pendiente:** `python scripts/i18n.py check` donde haya gettext (lo hace el CI).
- `docs/fase-04-carta.md` actualizado.
- **Tests:** 2 nuevos en `tests/web/test_menu_page.py` (`test_tap_menu_text_is_shown_directly`, `test_tap_menu_without_text_has_no_caption`). `python manage.py test --settings=config.settings.test --noinput` → **1082 tests OK**.
- **Pendiente:** revisión visual de `/carta/`.
