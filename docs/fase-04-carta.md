# Fase 4 — Carta y cervezas

**Estado:** Completa (pendiente de validar en PostgreSQL y de definir el almacenamiento de imágenes en producción; ver §10).
**Fecha:** 2026-10-14.
**Depende de:** [Fase 0](fase-00-fundacion.md), [Fase 1](fase-01-proyecto-base.md) y [Fase 3](fase-03-sistema-diseno-web-publica.md).

## 1. Objetivo y decisiones previas

Crear una carta que el propietario gestiona desde el panel administrativo sin tocar código: productos fijos, cervezas propias, invitadas y rotativas, categorías, descripciones, precios, imágenes, estilos, graduación, disponibilidad, publicación y archivo. La web muestra una única sección principal, **Carta**, con las categorías dentro.

Antes de empezar se resolvieron con el usuario estas cuestiones:

| Cuestión | Decisión |
|---|---|
| El [plan](plan-de-fases.md) incluía "14 grifos", pero el prompt de la fase no los menciona | **Sin modelo de grifos.** El propietario sube cuando quiera una **imagen de la carta de grifos** (`TapMenu`). Mientras no la suba, la Carta muestra el hueco reservado ("La carta de grifos se publicará aquí"). No hay imagen de prueba, para no publicar datos inventados. |
| Precios | **Un único precio por producto** (`DecimalField`, 2 decimales) con un texto opcional de formato ("33 cl", "Ración"). |
| Cerveza agotada | **Visible con la etiqueta "Agotada"**, al final de su categoría; nunca se presenta como disponible. No aparece en la selección del Inicio. |
| Dónde se gestiona | **Admin de Django**, que ya está restringido a propietarios. El dashboard propio llega en la Fase 9. |

Decisiones menores (con su motivo):

- **Pillow** (`>=12.0,<13`) en `requirements/base.txt`: Django lo exige para `ImageField` y para verificar el contenido de las imágenes. No se añade ninguna otra dependencia.
- **Estilos como modelo** (`BeerStyle`) y no como texto libre: el propietario mantiene una lista sin duplicados ("IPA" e "ipa" son el mismo) que la API podrá usar como filtro.
- **Campo `brewery` (cervecera) opcional:** una cerveza invitada sin elaborador quedaría incompleta para el cliente.
- **Destacadas en el Inicio** con la casilla `is_featured`, porque el Inicio de la Fase 3 ya tenía la sección "Nuestras cervezas" esperando datos. Solo se pueden destacar cervezas.
- **Las transiciones de estado no tienen restricciones** (un archivado puede volver a borrador o publicarse): las pidió solo el archivo, sin un flujo de aprobación.
- **Auditoría solo de publicación y disponibilidad** (`AuditEvent`). El resto de las ediciones (precio, textos, imagen) quedan en el historial nativo del admin (`LogEntry`, visible en "Historial" de cada producto), con quién y qué campos cambió.

## 2. Alcance y exclusiones

**Incluye:** app `apps.catalog` (modelos, validadores, selectores, servicios y admin), migraciones, imagen de la carta de grifos, página pública `/carta/` con categorías, selección de cervezas del Inicio, componentes `product_card` y `tap_menu`, servir imágenes subidas en desarrollo, tests y documentación.

**Excluye:** modelo de grifos o asignación de cervezas a grifos (decisión del usuario); varios precios o formatos por producto; dashboard propio del propietario (Fase 9); API REST (Fase 11, solo se documenta aquí, §7); almacenamiento de imágenes en producción (Fase 12); alérgenos (no pedidos; ver §10).

## 3. Modelo de datos

| Modelo | Campos principales | Notas |
|---|---|---|
| `Category` | `name`, `slug` (ancla `/carta/#slug`), `description`, `position`, `is_published` | Nombre único sin distinguir mayúsculas. Si se despublica, desaparecen todos sus productos de la web. |
| `BeerStyle` | `name` | Único sin distinguir mayúsculas. |
| `Product` | **Permanente:** `public_id` (UUID), `category`, `kind`, `name`, `description`, `style`, `abv`, `brewery`, `price`, `serving`, `image` (+ `image_width`/`image_height`), `position`, `is_featured`. **Publicación:** `status` (`DRAFT`/`PUBLISHED`/`ARCHIVED`), `published_at`, `archived_at`. **Disponibilidad actual:** `is_available`, `availability_changed_at`. | Ver reglas abajo. |
| `TapMenu` | `title`, `image`, `text_alternative`, `is_published` | En la web se muestra la publicada más reciente. Las antiguas se conservan despublicadas. |

Tipos de producto (`kind`): `FIXED` (producto fijo), `HOUSE_BEER` (cerveza propia), `GUEST_BEER` (cerveza invitada), `ROTATING_BEER` (cerveza rotativa).

### Reglas y dónde se protegen

| Regla | Modelo (`clean`/validadores) | Base de datos |
|---|---|---|
| Precio `DecimalField(6, 2)`: mínimo 0,01 € y máximo 9999,99 €, dos decimales | Sí | `CHECK price >= 0.01` |
| Graduación entre 0,0 y 100,0 % vol. (un decimal) | Sí | `CHECK` |
| Las cervezas tienen estilo y graduación; los productos fijos no tienen estilo (pueden tener graduación, p. ej. un vermut) | Sí | `CHECK catalog_product_beer_fields` |
| Solo se destacan cervezas | Sí | — |
| `kind` y `status` válidos | `choices` | `CHECK` |
| `ARCHIVED` ⇔ `archived_at` relleno | Lo fija el servicio | `CHECK` |
| No se borra el historial | El admin no permite borrar | `on_delete=PROTECT` en categoría y estilo |

La **información permanente** (qué es el producto y si está publicado) está separada de la **disponibilidad actual** (`is_available`). Agotar un producto no cambia su publicación, su precio ni sus textos (hay un test).

### Visibilidad pública (`apps/catalog/selectors.py`)

- Un producto es público si está **publicado** y su **categoría está publicada**. Borradores y archivados nunca salen.
- En cada categoría, los disponibles van primero (por `position` y nombre) y los agotados al final, con `is_available=False`.
- Las categorías sin productos públicos no se muestran.
- Inicio: hasta 6 cervezas destacadas, públicas **y disponibles**.
- Carta de grifos: la `TapMenu` publicada más reciente, o ninguna.
- Propiedades de dominio en el modelo: `is_beer`, `is_publicly_visible`, `is_currently_available`.

## 4. Gestión de la carta (guía para el propietario)

Entra en el admin (`/<DJANGO_ADMIN_URL>`, por defecto `/admin/`) con tu cuenta de propietario. La sección **Carta** tiene cuatro apartados.

1. **Estilos de cerveza:** crea los estilos que vayas a usar (IPA, Stout, Lager…).
2. **Categorías:** crea las categorías en el orden en que quieres verlas (campo *orden*: de menor a mayor). El *identificador en la URL* se rellena solo a partir del nombre. Puedes cambiar el orden y la publicación desde la propia lista.
3. **Productos → Añadir producto:**
   - Elige categoría y tipo. En las cervezas son obligatorios **estilo** y **graduación**. En las invitadas, rellena la **cervecera**.
   - **Precio** con punto decimal (p. ej. `3.50`). En la web se ve como "3,50 €".
   - **Imagen** opcional: JPEG, PNG o WebP, de hasta 5 MB y 5000 px por lado.
   - **Estado:** *Borrador* (no se ve), *Publicado* (se ve) o *Archivado* (no se ve y queda como historial).
   - **Disponible ahora:** desmárcalo cuando se agote. Seguirá en la carta como "Agotada".
   - **Destacada en el inicio:** para que aparezca en "Nuestras cervezas" de la página principal (solo cervezas publicadas y disponibles).
4. **Acciones rápidas en la lista de productos:** selecciona uno o varios y elige *Publicar*, *Pasar a borrador (ocultar)*, *Archivar*, *Marcar como agotado* o *Marcar como disponible*. Los filtros de la derecha muestran, por ejemplo, solo los archivados o solo los agotados.
5. **Cartas de grifos → Añadir:** sube la foto o imagen de la carta de grifos y marca *Publicada*. Se recomienda escribir también la *versión en texto* (las cervezas de la imagen), que la web ofrece en "Ver la carta de grifos en texto" para quien usa lector de pantalla. Cuando la cambies, sube una nueva y publícala: se mostrará la más reciente. Desmarca *Publicada* en las antiguas si no quieres que vuelvan a salir.

**No se puede borrar nada desde el admin.** Para retirar un producto, archívalo; para ocultar una categoría, desmarca *Publicada*. Así se conserva el historial (y, en fases posteriores, las compras y estadísticas que hagan referencia a ellos).

## 5. Seguridad y privacidad

- **Autorización en servidor:** solo los propietarios entran en el admin (`is_staff` solo existe en el rol OWNER, garantizado en BD desde la Fase 0). Además, los `ModelAdmin` de la carta comprueban `is_owner` en cada permiso (`OwnerOnlyAdminMixin`) y los servicios vuelven a comprobarlo (`ensure_can_manage_catalog`): un empleado, un cliente, un anónimo o un propietario desactivado reciben `PermissionDenied` (hay tests de acceso denegado en vistas, acciones y servicios).
- **Operaciones de estado y disponibilidad:** atómicas, con `select_for_update` sobre la fila e idempotentes (repetir no duplica auditoría). Se apoyan en el estado de la BD, no en el objeto que llega (test con instancia desactualizada). Desde el formulario del admin, el estado y la disponibilidad también pasan por los servicios.
- **Validación de imágenes** (`apps/catalog/validators.py`): extensión permitida y **contenido real** verificado con Pillow (JPEG, PNG o WebP). Se rechazan SVG (pueden contener scripts), HTML disfrazado, GIF, ficheros truncados, ficheros de más de 5 MB e imágenes de más de 5000 px por lado (protección frente a bombas de descompresión). Los mensajes de error no repiten el nombre del fichero.
- **Nombres de fichero aleatorios** (`catalog/products/<uuid>.jpg`): el nombre original, que puede contener datos personales, no se publica.
- **Validación de precios y datos** en el modelo (lo usan el admin y lo usará la API) y restricciones `CHECK` en la BD.
- **XSS:** autoescape de Django en todo el contenido; las descripciones solo pasan por `linebreaksbr`. Hay un test con `<script>` en el nombre.
- **Exposición mínima:** la web usa `public_id` (UUID) y nunca el `id` interno. La carta no contiene datos personales.
- **Imágenes servidas desde el mismo dominio:** el riesgo de que se suba algo ejecutable se limita con la validación de contenido y la cabecera `X-Content-Type-Options: nosniff`, ya activa.

## 6. Configuración

- **Dependencia nueva:** `Pillow>=12.0,<13` (`pip install -r requirements/dev.txt`).
- **Migraciones:** `catalog/0001_initial` (tablas nuevas) y `core/0003_audit_actions_phase4` (solo amplía los `choices` de `AuditEvent.action` con `PRODUCT_STATUS_CHANGED` y `PRODUCT_AVAILABILITY_CHANGED`; no altera datos). Aplicar con `python manage.py migrate`. Son aditivas y reversibles.
- **Settings nuevos** (en `base.py`, no son variables de entorno): `CATALOG_IMAGE_MAX_BYTES` (5 MB) y `CATALOG_IMAGE_MAX_DIMENSION` (5000 px).
- **Imágenes en desarrollo:** `config/urls.py` añade `static(MEDIA_URL, …)`, que solo sirve `media/` con `DEBUG=True`. **En producción no se sirven** hasta definir el almacenamiento en la Fase 12. `media/` está en `.gitignore`.
- No hay variables de entorno nuevas.

## 7. Preparación para la app móvil y la futura API (Fase 11)

Modelos y reglas de disponibilidad no dependen de las plantillas: la web solo llama a `selectors` y la API debe hacer lo mismo.

Endpoints propuestos (solo lectura y públicos, porque la carta es pública):

| Endpoint | Fuente | Contenido |
|---|---|---|
| `GET /api/v1/catalog/menu/` | `selectors.public_menu()` | Categorías publicadas con sus productos públicos |
| `GET /api/v1/catalog/featured-beers/` | `selectors.featured_beers()` | Selección del Inicio |
| `GET /api/v1/catalog/tap-menu/` | `selectors.current_tap_menu()` | Imagen de la carta de grifos (o `null`) |
| `GET /api/v1/catalog/products/{public_id}/` | `selectors.public_products()` filtrado por `public_id` | Un producto público; 404 si es borrador o archivado |

Pautas:
- Serializadores con campos explícitos: `public_id`, `name`, `kind`, `description`, `style` (nombre), `abv`, `brewery`, `price` (como cadena decimal "3.50", nunca `float`), `serving`, `image` (URL absoluta), `image_width`, `image_height`, `is_available`. Para las categorías: `slug`, `name`, `description`, `products`.
- **No exponer** `id`, `status`, `published_at`, `archived_at`, `position`, `is_featured` ni la fecha de disponibilidad: son datos de gestión.
- `lookup_field = "public_id"`. Un borrador o archivado devuelve 404, no 403, para no revelar su existencia.
- La gestión desde la app (si llega) usará `services.set_product_status` y `services.set_product_availability`, con permiso DRF que envuelva `is_owner`. Los `ValidationError`/`PermissionDenied` se traducen a 400/403.
- Caché HTTP corta (p. ej. 60 s): la disponibilidad cambia durante el servicio.

## 8. Archivos creados o modificados

- **App nueva `apps/catalog/`:** `apps.py`, `models.py`, `validators.py`, `selectors.py`, `services.py`, `admin.py`, `migrations/0001_initial.py`.
- **Core:** `apps/core/models.py` (dos acciones de auditoría) y `migrations/0003_audit_actions_phase4.py`.
- **Web:** `apps/web/views.py` (`HomeView` y `MenuView` usan los selectores).
- **Plantillas:** `templates/web/menu.html`, `templates/web/home.html`, nuevas `templates/components/product_card.html` y `templates/components/tap_menu.html`.
- **Configuración:** `config/settings/base.py` (`apps.catalog` y límites de imagen), `config/urls.py` (media en desarrollo), `requirements/base.txt` (Pillow).
- **CSS:** `static/css/app.css` recompilado.
- **Tests:** `tests/catalog/` (`factories.py`, `test_models.py`, `test_validators.py`, `test_services.py`, `test_selectors.py`, `test_admin.py`) y `tests/web/test_menu_page.py`.
- **Documentación:** este documento, `README.md`, `plan-de-fases.md`, `arquitectura.md`.

## 9. Tests y resultados reales

Nuevos (71):
- `test_models.py`: precios (0, negativos, 3 decimales, más de 9999,99), `Decimal` con dos decimales, graduación, campos obligatorios de las cervezas, productos fijos sin estilo y no destacables, estado inicial, disponibilidad actual; restricciones de BD con `update()` (precio, graduación, campos de cerveza, estado y tipo válidos, `archived_at`), unicidad sin distinguir mayúsculas y `PROTECT`.
- `test_validators.py`: JPEG/PNG/WebP válidos; rechazo de HTML con extensión `.png`, SVG, GIF, ficheros truncados, tamaño y dimensiones excesivos; mensajes sin el nombre del fichero; nombre almacenado aleatorio.
- `test_services.py`: denegado para anónimo, `None`, empleado, cliente y propietario inactivo; estado no válido; publicación con fecha y auditoría; idempotencia (doble envío); archivo sin borrado y restauración; republicar un archivado; instancia desactualizada; agotado sigue publicado pero no disponible; la disponibilidad no toca la información permanente.
- `test_selectors.py`: borradores, archivados y categorías ocultas no salen; categorías vacías omitidas y ordenadas; agotados al final; destacadas solo públicas, disponibles y cervezas; límite; número de consultas constante (2); carta de grifos publicada más reciente.
- `test_admin.py`: el propietario accede; empleado, cliente y anónimo no (vistas y acciones); no se puede borrar nada; alta publicada mediante el servicio con auditoría e imagen renombrada; precios e imágenes no válidos rechazados; cerveza sin estilo ni graduación rechazada; disponibilidad y archivo desde el formulario pasan por servicios; acciones de la lista; archivados visibles en el filtro; categorías, estilos y carta de grifos (y rechazo de SVG).
- `test_menu_page.py`: categorías dentro de la Carta con anclas, precio "3,50 €", formato, graduación y estilo; borradores, archivados y categorías ocultas no se muestran; "Agotada"/"Agotado"; escape de HTML; hueco de la carta de grifos y su imagen al publicarla (con versión en texto); imagen no publicada no se ve; estado vacío; sin `id` interno; selección del Inicio solo con destacadas disponibles.

| Comando (SQLite, Python 3.14.2, Django 5.2.18, Pillow 12.3.0) | Resultado |
|---|---|
| `python manage.py check` | Sin incidencias |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| `python manage.py test --settings=config.settings.test` | **302 tests, OK** (231 anteriores + 71 nuevos) |
| `check --deploy --settings=config.settings.prod` (variables ficticias) | Solo `W021` (HSTS preload, intencionado, ya existente) |
| `python scripts/tailwind.py build` | OK |
| Capturas con Edge headless (BD temporal con datos ficticios, fuera del repositorio): Carta a 1280 px y 500 px, Inicio a 1280 px | Maquetación correcta; agotada al final y etiquetada; hueco de la carta de grifos visible. A 375 px Edge headless recorta la ventana, así que esa captura no es válida (en la Fase 3 se usó emulación por DevTools). |

Ajuste tras la revisión visual: se quitó la atenuación (`opacity`) de las tarjetas agotadas porque bajaba el contraste del texto gris por debajo de AA; el estado se comunica con la etiqueta de texto.

## 10. Limitaciones, riesgos y pendientes

- **Concurrencia probada solo en SQLite**, donde `select_for_update` no bloquea. La idempotencia está probada; el bloqueo real se comprobará contra PostgreSQL (Fase 12).
- **Imágenes en producción:** sin almacenamiento ni servidor de `media/` definidos (Fase 12). Hasta entonces las imágenes solo se ven en desarrollo.
- **Metadatos EXIF** (p. ej. ubicación GPS de una foto de móvil) no se eliminan: las imágenes no se recodifican. Conviene subir imágenes exportadas o sin ubicación. Recodificar al subir es una mejora posible.
- **Accesibilidad de la carta de grifos:** una imagen no es legible para lectores de pantalla. Se mitiga con la *versión en texto* opcional; depende de que el propietario la rellene.
- **Imágenes no recortadas ni redimensionadas:** se muestran en 4:3 con `object-cover`. Una imagen grande (hasta 5 MB) pesa lo mismo en la web; optimizarla es responsabilidad de quien la sube por ahora.
- **Cartas de grifos antiguas** se acumulan (no se borran). Si ocupan demasiado, se podrá definir una política de limpieza.
- **Alérgenos:** no se pidieron en la fase. Si la carta incluye comida, la información de alérgenos puede ser una obligación del local; el propietario debe confirmarlo (esta documentación no es asesoramiento legal).
- **Precios:** se muestran con "€" e IVA incluido según indica el campo; el propietario es responsable de su exactitud.
- **Validación visual:** sin dispositivos físicos ni lectores de pantalla reales.

## 11. Estado de los criterios de aceptación

| Criterio | Estado |
|---|---|
| Productos fijos, cervezas propias, invitadas y rotativas | Completo |
| Categorías, descripciones, precios (`DecimalField`), imágenes, estilos y graduación cuando corresponde | Completo |
| Disponibilidad, publicación y archivo | Completo |
| El propietario modifica la carta sin editar código | Completo (admin; guía en §4) |
| Información permanente separada de la disponibilidad actual | Completo |
| Una cerveza agotada no aparece como disponible | Completo (con tests en selectores, Inicio y Carta) |
| No se borra el historial de productos archivados | Completo (sin borrado en admin + `PROTECT`; con tests) |
| Una única sección Carta con las categorías dentro | Completo |
| Solo usuarios autorizados (propietarios) gestionan el catálogo | Completo (admin + servicios; tests de acceso denegado) |
| Validación de imágenes, precios y datos | Completo |
| Modelos y reglas independientes de las plantillas; API documentada | Completo (§7) |
| Pruebas de publicación, disponibilidad, permisos y visualización | Completo (71 tests) |
| Carta de grifos (plan: 14 grifos) | Sustituida por imagen subida por el propietario, por decisión del usuario |

## 12. Dependencias para la fase siguiente (Fase 5 — Fidelización)

- La Fase 5 no depende de la carta. Si en el futuro las compras referencian productos, usar `Product.public_id` y respetar que los productos no se borran.
- La Fase 9 (dashboard) podrá sustituir el admin con vistas propias que llamen a los mismos `services` y `selectors`.
- La Fase 11 implementará los endpoints de §7; la Fase 12, el almacenamiento de imágenes y las pruebas en PostgreSQL.
