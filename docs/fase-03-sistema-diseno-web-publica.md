# Fase 3 — Sistema de diseño y web pública

**Estado:** Completa (los contenidos del negocio están pendientes de que los aporte el propietario; ver §9).
**Fecha:** 2026-10-14.
**Depende de:** [Fase 0](fase-00-fundacion.md), [Fase 1](fase-01-proyecto-base.md) y [Fase 2](fase-02-registro-perfil-verificacion.md).

## 1. Objetivo, contexto y decisiones previas

Crear la estructura visual completa de la web pública con la identidad de Caneca Furada: sistema de diseño, plantilla base, páginas públicas y rediseño de las páginas de cuenta de la Fase 2. Debe ser responsive y accesible y no incluir reglas de negocio en el frontend.

Contradicciones detectadas entre el prompt de la fase y el [plan](plan-de-fases.md), resueltas por el usuario antes de empezar:

| Cuestión | Decisión |
|---|---|
| El plan excluía Carta, Recompensas y Eventos (sus modelos llegan en las Fases 4, 7 y 8), pero el prompt pide esas páginas y las secciones "Selección de cervezas" y "Eventos destacados" del Inicio | **Estructura sin datos.** Se crean las páginas y secciones con su diseño final y un estado vacío ("Próximamente"). No hay cervezas, precios, recompensas ni eventos inventados. Las vistas ya pasan listas vacías (`featured_beers`, `featured_events`, `categories`, `rewards`, `events`) que las fases siguientes rellenarán. |
| No hay datos reales del local (dirección, horario, contacto, redes) | **Pendientes.** Se marcan como "Pendiente de publicar" desde un único punto (`apps/web/content.py`). Tampoco hay formulario de contacto (necesitaría almacenamiento y protección antiabuso). |
| Herramienta de CSS | **Tailwind CSS con la CLI standalone**, como indica el plan (sin Node). |

Decisiones menores adoptadas (motivo entre paréntesis):

- **Versión fijada de Tailwind (v4.3.3) con checksum.** `scripts/tailwind.py` descarga el binario oficial y lo rechaza si su SHA-256 no coincide con el publicado (para evitar binarios alterados y que el resultado cambie entre equipos). El binario va en `.tools/` (ignorado por Git).
- **CSS compilado versionado** (`static/css/app.css`, unos 30 KB minificado): el proyecto funciona, se prueba y se despliega sin el binario. Si se cambian plantillas o `assets/css/input.css`, hay que recompilar.
- **Sin fuentes externas** (Google Fonts u otras): se usa la pila tipográfica del sistema (privacidad, porque no se envía la IP del visitante a terceros, y rendimiento). La personalidad la aportan los titulares en mayúsculas, el espaciado de las etiquetas y las líneas doradas inspiradas en el logo.
- **Logos JPEG con fondo negro** (no hay SVG ni PNG transparente): se integran con `mix-blend-mode: lighten`, que funde el negro puro del JPEG con el negro de marca `#080808`.
- **`appejemplo.jpeg` no se publica:** es una referencia visual de otra marca ("La Brújula"), no un recurso de Caneca Furada.
- **JavaScript mínimo sin framework** (`static/js/app.js`): Alpine.js y HTMX no aportaban nada concreto en esta fase.
- **Secciones del registro numeradas 1–4** por la plantilla (indicador visual y "Paso N:" para lectores de pantalla). Los títulos del formulario pierden el prefijo "A./B./C./D.".
- **Colores funcionales** fuera de la paleta: rojo de error `#FF7A7A` (7,9:1 sobre negro), verde de confirmación `#6EE7A0` y borde `#2C2C2C`. Son necesarios para comunicar estados con contraste suficiente.

## 2. Alcance y exclusiones

**Incluye:** sistema de diseño (tokens y componentes), plantilla base (cabecera, menú móvil, mensajes, footer), páginas Inicio, La cervecería, Carta, Recompensas, Eventos y Contacto, páginas de error 400/403/404/500, rediseño de todas las plantillas de cuenta (registro, confirmación, login, verificación, reenvío, perfil, cambio de email y contraseña, recuperación de contraseña, inicio de empleado), estados de carga de los formularios, tests y documentación.

**Excluye:** modelos y gestión de carta, recompensas y eventos (Fases 4, 7 y 8); contenido editable por el propietario (Fase 9); app móvil; textos legales (aviso legal, privacidad, cookies), que debe aportar el propietario; formulario de contacto; plantilla `403_csrf.html` (se mantiene la página de Django).

## 3. Sistema de diseño

Fuente: [`assets/css/input.css`](../assets/css/input.css). Salida: `static/css/app.css`.

### Tokens (`@theme`)

| Token | Valor | Uso |
|---|---|---|
| `ink` | `#080808` (Negro) | Fondo principal |
| `coal` | `#171717` (Carbón) | Superficies: tarjetas, footer, secciones |
| `gold` | `#FFB800` (Dorado) | Acento, botón principal, foco, marcas de obligatorio |
| `paper` | `#FFFFFF` (Blanco) | Texto principal |
| `mist` | `#A5A5A5` (Gris) | Texto secundario |
| `line` | `#2C2C2C` | Bordes |
| `danger` / `ok` | `#FF7A7A` / `#6EE7A0` | Errores / confirmaciones |

**Contraste (WCAG 2.1, calculado):** blanco sobre negro 20:1; dorado sobre negro 11,6:1 y sobre carbón 10,3:1; gris sobre negro 8,1:1 y sobre carbón 7,3:1; negro sobre dorado (botón principal) 11,6:1; error sobre negro 7,9:1 y sobre carbón 7,1:1. Todos superan AA (4,5:1). **Regla:** nunca texto blanco sobre dorado (1,7:1).

### Componentes CSS (`@layer components`)

`container-page`, `eyebrow`, `heading-xl/lg/md`, `lead`, `link`, `btn` + `btn-primary` / `btn-secondary` / `btn-ghost` / `btn-block` (con spinner cuando `aria-busy="true"`), `card` (+ `card-hover`), `badge` (+ `badge-muted`), `step-number`, `alert` + `alert-info/success/error/warning`, `pending`, `form-section`, `form-legend`, `field` (estilos de `input`/`select`/checkbox, incluido `aria-invalid`), `errorlist`, `required-mark`, `optional-mark`, `nav-link` (+ `aria-current`), `nav-panel`, `logo-blend`, `sr-only-focusable`.

Las variantes se usan junto a su clase base (`btn btn-primary`, `alert alert-error`), porque Tailwind v4 no permite `@apply` sobre clases de `@layer components`.

### Componentes de plantilla (`templates/components/`)

| Componente | Uso |
|---|---|
| `footer.html` | Footer: logo, lema, navegación, enlaces de cuenta, datos del local, aviso de consumo responsable |
| `business_info.html` | Dirección, horario, contacto y redes desde `content.BUSINESS`, con "Pendiente de publicar" para lo que falte |
| `page_header.html` | Cabecera de página (`eyebrow`, `title`, `intro`) |
| `section_heading.html` | Encabezado de sección con `id` para `aria-labelledby` |
| `empty_state.html` | Estado vacío "Próximamente" con llamada a la acción opcional |
| `pending.html` | Contenido que debe aportar el propietario |
| `loyalty_steps.html` | Los tres pasos del programa de puntos, sin cifras ni recompensas concretas |
| `form_errors.html` | Resumen de errores accesible (`role="alert"`, enfocable, con enlaces a cada campo) |
| `error_page.html` | Cuerpo común de las páginas de error |

Además, `templates/accounts/_layout.html` (columna centrada de las páginas de cuenta) y `templates/accounts/_field.html` (campo accesible).

## 4. Páginas

| Ruta | Nombre | Plantilla | Contenido |
|---|---|---|---|
| `/` | `web:home` | `web/home.html` | Hero (lema oficial y logo), presentación de la marca, acceso a la carta, selección de cervezas (vacía), programa de puntos ("Próximamente"), eventos destacados (vacío), información del local y footer |
| `/la-cerveceria/` | `web:about` | `web/about.html` | Historia (pendiente) e imagen oficial del X aniversario |
| `/carta/` | `web:menu` | `web/menu.html` | Estado vacío hasta la Fase 4 |
| `/recompensas/` | `web:rewards` | `web/rewards.html` | Cómo funcionará el programa, catálogo vacío, condiciones pendientes, llamada a registrarse |
| `/eventos/` | `web:events` | `web/events.html` | Estado vacío hasta la Fase 8 |
| `/contacto/` | `web:contact` | `web/contact.html` | Datos del local (pendientes) y acceso a la cuenta |
| `/cuenta/…` | `accounts:*` | `accounts/*.html` | Registro, confirmación, login, verificación, reenvío, perfil y demás (rutas de la Fase 2, sin cambios) |
| — | — | `400/403/404/500.html` | Páginas de error con la marca. `500.html` no depende del contexto de la petición |

Las vistas públicas son `TemplateView` de solo lectura (`GET`/`HEAD`; `POST` devuelve 405) y no tocan la base de datos.

### Formulario de registro

- Cuatro `fieldset` numerados: 1. Datos personales, 2. Dirección postal, 3. Acceso a la cuenta, 4. Preferencias de comunicación. Rejilla de dos columnas desde tablet.
- Obligatorios con `*` dorado y "(obligatorio)" para lectores de pantalla. Opcionales (teléfono móvil, dirección línea 2) con "(opcional)". Aviso al principio: "El teléfono móvil es opcional".
- Errores: resumen al principio que recibe el foco y enlaza a cada campo, y mensaje bajo cada campo. Django 5.2 añade `aria-invalid="true"` y enlaza ayuda y errores con `aria-describedby`.
- Tras un error se conservan los datos no sensibles y **las contraseñas no se vuelven a rellenar** (`PasswordInput` no renderiza su valor; hay tests).
- Confirmación (`register_done.html`): "Falta un paso: verificar tu email" y "Tu cuenta quedará pendiente de verificación…". Ninguna página dice que la cuenta esté activada antes de verificar el email (hay un test).

## 5. Responsive, accesibilidad e interacción

- Móvil primero; puntos de corte de Tailwind (`sm` 640, `md` 768, `lg` 1024). Menú plegable por debajo de `lg`.
- Sin JavaScript, el menú se muestra desplegado y los formularios funcionan igual (mejora progresiva con la clase `no-js`/`js` en `<html>`).
- Enlace "Saltar al contenido", `aria-current="page"` en la navegación, `aria-expanded` y `Escape` en el menú, foco visible dorado, regiones con `aria-labelledby`, un único `h1` por página, `alt` descriptivo en los logos y respeto a `prefers-reduced-motion`.
- **Estados de carga:** los formularios con `data-loading` desactivan el botón, muestran `data-loading-text` y un spinner (`aria-busy`), e impiden el doble envío desde el navegador. El servidor sigue siendo la protección real (límites e idempotencia de la Fase 2). El estado se restablece al volver con "atrás" (`pageshow`).

## 6. Preparación para la app móvil

- Las plantillas solo presentan. Las reglas (validación, verificación, permisos) siguen en servicios y formularios de la Fase 2, que usará también la API.
- `app.js` no contiene validaciones ni reglas de negocio (hay un test que lo comprueba). Desde la Fase 16 tiene dos ayudas que no deciden nada: el aviso inmediato de edad mínima (no bloquea el envío; decide el servidor) y una única consulta de lectura a la lista pública de localidades por CP. El test lo acota a eso ([fase-16-registro-cp-sexo.md](fase-16-registro-cp-sexo.md)).
- Las vistas pasan al contexto las colecciones con los nombres que usarán las Fases 4, 7 y 8. Los datos del local están en un solo módulo (`apps/web/content.py`) que la Fase 9 sustituirá por contenido editable.
- Los tokens de color están documentados (§3) para reutilizarlos en Flutter.

## 7. Configuración e instrucciones

No hay variables de entorno nuevas ni migraciones.

```powershell
python scripts/tailwind.py install   # descarga Tailwind v4.3.3 en .tools/ y verifica su SHA-256
python scripts/tailwind.py build     # regenera static/css/app.css (minificado)
python scripts/tailwind.py watch     # recompila al guardar mientras se desarrolla
```

- Después de cambiar clases en plantillas o `assets/css/input.css`, ejecuta `build` y versiona `static/css/app.css`.
- Para publicar los datos del local, edita `BUSINESS` en `apps/web/content.py` (dirección, `opening_hours` como lista de pares (días, horario), email, teléfono, redes, texto de presentación). Los valores `None` se muestran como pendientes.
- Plataformas con checksum en el script: Windows x64, Linux x64/arm64 y macOS x64/arm64.

## 8. Seguridad y privacidad

- Sin datos personales en las páginas públicas (hay un test con un cliente autenticado). El perfil muestra solo los datos del propio usuario.
- Logout solo por `POST` con CSRF en la cabecera. Todos los formularios mantienen `{% csrf_token %}`.
- Se mantiene `X-Frame-Options: DENY` (se comprobó al intentar incrustar las páginas en un iframe para las pruebas visuales).
- Sin recursos de terceros (fuentes, CDN, mapas, analítica): no hay cookies ni transferencias de IP a terceros.
- Enlaces externos de redes con `rel="noopener noreferrer"`.
- Autoescape de Django en todo el contenido (no se usa `|safe`).
- El binario de Tailwind solo se ejecuta en desarrollo, se verifica por checksum y no forma parte del despliegue.

## 9. Limitaciones, riesgos y pendientes

- **Contenido pendiente del propietario:** dirección, horario, email, teléfono, redes, texto de presentación e historia, condiciones del programa de puntos y textos legales (aviso legal, privacidad, cookies). Los textos legales no están enlazados en el footer porque no existen.
- **Textos de la casa:** las frases de las páginas ("Cerveza artesana en A Coruña…", "Cada visita suma"…) son propuestas de interfaz basadas solo en el lema oficial; conviene que el propietario las revise. El aviso "Prohibida la venta de alcohol a menores de 18 años" del footer debe revisarlo el propietario; no se presenta como garantía de cumplimiento legal.
- **Logo:** solo en JPEG. Un SVG o un PNG transparente mejorarían la nitidez y el peso (`logoknkany.jpeg` pesa 1 MB y se carga con `loading="lazy"` solo en La cervecería). Lo ideal es que el propietario aporte versiones vectoriales u optimizadas.
- **CSS compilado versionado:** si alguien cambia clases y no recompila, faltarán estilos. Mitigación: `build` documentado. Se podría añadir una comprobación en CI en la Fase 12.
- **Parpadeo del menú sin JS:** `app.js` se carga con `defer`, así que en móvil el menú puede verse desplegado un instante antes de plegarse. Se evitó a propósito un script inline para no complicar una futura CSP.
- **Validación visual:** capturas con Edge headless emulando 375 px, 768 px, 1280 px y 1440 px. No se ha probado en dispositivos físicos ni con lectores de pantalla reales.

## 10. Tests y resultados reales

Nuevos en `tests/web/`:
- `test_public_pages.py`: las 6 páginas públicas responden 200 sin sesión, con su plantilla y un único `h1`; `aria-current` en la navegación; recursos de marca y enlace de salto; todas las secciones del Inicio; sin datos inventados (sin "€", con estados vacíos y pendientes); los datos del local se muestran al aportarlos; cabecera anónima y autenticada (logout por POST con CSRF); sin datos personales en páginas públicas; `POST` → 405; páginas 403 y 404 con la marca; `500.html` sin contexto; CSS y JS servidos por `staticfiles`; paleta presente en el CSS compilado; la imagen de otra marca no se usa; `app.js` sin reglas de negocio.
- `test_account_forms_ui.py`: cuatro secciones numeradas y en orden; obligatorios y teléfono opcional marcados; estado de carga y CSRF; errores accesibles (resumen, `aria-invalid`, `aria-describedby`) y datos no sensibles conservados; contraseñas nunca rellenadas; confirmación del registro sin mensajes de "cuenta activada"; páginas de cuenta con el layout; páginas de verificación sin el token en el HTML; login con error que conserva el email y no la contraseña; aviso de verificación pendiente y distintivo "Verificado".

Modificado: `tests/accounts/test_registration.py` (títulos de sección sin el prefijo "A.–D.").

| Comando (SQLite, Python 3.14.2, Django 5.2.18) | Resultado |
|---|---|
| `python manage.py check` | Sin incidencias |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| `python manage.py test --settings=config.settings.test` | **231 tests, OK** (203 anteriores + 28 nuevos) |
| `check --deploy --settings=config.settings.prod` (variables ficticias) | Solo `W021` (HSTS preload, intencionado, ya existente) |
| `python scripts/tailwind.py build` | OK; checksum del binario verificado |
| Capturas con Edge headless y emulación de dispositivo por DevTools Protocol (Inicio, Registro con y sin errores, Login a 375 px; Recompensas a 768 px; Contacto a 1280 px; Inicio a 1440 px; menú móvil abierto) | Sin desbordamiento horizontal (`scrollWidth == clientWidth`); maquetación correcta |

## 11. Archivos creados o modificados

- **App nueva `apps/web/`:** `apps.py`, `content.py`, `context_processors.py`, `views.py`, `urls.py`.
- **Configuración:** `config/settings/base.py` (`apps.web` y su context processor), `config/urls.py` (rutas públicas en la raíz), `.gitignore` (`.tools/`).
- **Sistema de diseño:** `assets/css/input.css`, `static/css/app.css` (compilado), `static/js/app.js`, `scripts/tailwind.py`. Se elimina `static/css/base.css`.
- **Plantillas:** `templates/base.html`, `templates/components/*`, `templates/web/*`, `templates/400.html`, `403.html`, `404.html`, `500.html`, `templates/accounts/_layout.html` y todas las de `templates/accounts/`.
- **Formularios:** `apps/accounts/forms.py` (solo títulos de sección).
- **Tests:** `tests/web/`, `tests/accounts/test_registration.py`.
- **Documentación:** este documento, `plan-de-fases.md`, `arquitectura.md`, `README.md`.

## 12. Estado de los criterios de aceptación

| Criterio | Estado |
|---|---|
| Paleta oficial y estética minimalista y premium con los recursos gráficos oficiales | Completo |
| Páginas: Inicio, La cervecería, Carta, Recompensas, Eventos, Contacto, Registro, Login, Verificación, Reenvío y Perfil | Completo (Carta, Recompensas y Eventos con estado vacío hasta sus fases) |
| Inicio con hero, marca, acceso a la carta, cervezas, programa de puntos, eventos, local y footer | Completo (cervezas y eventos vacíos; datos del local pendientes) |
| Registro en 4 secciones con obligatorios, teléfono opcional, errores, confirmación y aviso de verificación pendiente | Completo |
| Sin mensajes de cuenta activada antes de verificar el email | Completo (con test) |
| Responsive móvil, tablet y escritorio | Completo (verificado con emulación; sin dispositivos físicos) |
| Etiquetas visibles, errores accesibles, contraste, estados de carga, conservación de datos, contraseñas no rellenadas | Completo |
| Sin datos inventados | Completo (con test) |
| Componentes desacoplados y sin reglas de negocio en JavaScript | Completo |
| Páginas de error y tests de vistas públicas | Completo |

## 13. Dependencias para la fase siguiente (Fase 4 — Carta y cervezas)

- Rellenar `categories` en `MenuView` y `featured_beers` en `HomeView` desde servicios de `apps.catalog`. Las plantillas ya tienen el bucle y el estado vacío; sustituir el contenido provisional del `<li class="card">` por un componente `beer_card`.
- Usar los componentes existentes (`card`, `badge`, `page_header`, `section_heading`, `empty_state`) y recompilar el CSS tras añadir clases.
- Los precios se mostrarán con el formato que defina la Fase 4. Cuando existan precios reales habrá que ajustar el test `test_no_invented_business_data` (que comprueba que no aparece "€").

## 14. Ajuste de la cabecera (2026-10-15)

Pedido por el usuario después de la versión `v1.0-defensa`.

**Problema:** con una ventana de unos 1180 px, «La cervecería» se partía en dos líneas y los botones del propietario se montaban en dos filas.

**Cambios** (`templates/base.html`, `assets/css/input.css` y `static/css/app.css` recompilado):
- **Propietario:** se quita el botón «Dashboard». Quedan **Mi cuenta · Panel · Salir**, en ese orden. «Mi cuenta» (`/cuenta/`) ya lleva al propietario a su dashboard (`apps/accounts/views.py`, `home`). Cliente y empleado conservan sus botones.
- **Una sola línea:**
  - `.nav-link` no admite saltos de línea («La cervecería» va en una línea);
  - el bloque de botones no se parte ni se comprime, y sus botones no cortan el texto.
- **Cabecera más ancha:** usa `max-w-7xl` (1280 px) en lugar de `container-page` (1152 px), con 24 px de margen lateral. El resto de la página no cambia.
- **Punto de corte propio `nav` (69 rem = 1104 px)** en `@theme`, en lugar de `lg` (1024 px):
  - desde ese ancho, cabecera en línea;
  - por debajo, el botón «Menú» desplegable de siempre.
- **Espacios en el modo en línea:** 8 px a los lados de cada enlace (antes 12), 16 px de relleno en los botones con fondo o borde (antes 24) y 16 px entre el logo y el menú (antes 24). Tamaño de letra y logo, sin cambios.

**Medición** (Chrome sin interfaz, ancho mínimo de ventana para una sola línea):

| Rol | Ancho mínimo |
|---|---|
| Propietario | 1098 px |
| Visitante | 1053 px |
| Cliente | 1009 px |
| Empleado | 972 px |

El punto de corte (1104 px) cubre el caso más ancho.

**Verificación:**
- Capturas de los cuatro roles a 1024, 1104, 1134, 1181 y 1440 px: todo en una línea desde 1104 px; a 1024 px, el botón «Menú»; el menú desplegado, correcto.
- Test: `tests/dashboard/test_access.py::test_owner_lands_on_dashboard_and_header_has_account_panel_logout` (botones y orden del propietario, sin «Dashboard»; el cliente conserva «Mi cuenta»).
- Suite en PostgreSQL 17: **849 OK**.

**Pie** (`templates/components/footer.html`):
- el logo es un enlace al inicio (`aria-label="Caneca Furada, ir al inicio"`);
- logo y lema van centrados entre sí;
- **columnas juntas y simétricas en escritorio** (`lg`):
  - antes eran cuatro columnas de un cuarto de página cada una, con el contenido alineado a la izquierda y huecos desiguales;
  - ahora el bloque del logo, Explora, Tu cuenta y Visítanos miden lo que su contenido y van centrados, con la misma separación entre cada par (`lg:flex lg:justify-center lg:gap-x-20`, 80 px);
  - Visítanos tiene un ancho máximo de 240 px (`lg:max-w-60`) para que una dirección u horario largos no descuadren el conjunto;
  - en móvil y tablet no cambia;
  - medido con Chrome a 1280 y 1440 px, con los datos del local pendientes y con datos ficticios completos: huecos de 80, 80 y 80 px y el conjunto centrado.

Lo comprueba `tests/web/test_public_pages.py::test_layout_includes_brand_assets_and_skip_link`, y está verificado con captura a 1280 px.

**Documentación de la defensa:** actualizada. La memoria (C8.2 y el logout del cap. 7.3) y el README de la defensa recogen la cabecera nueva y las líneas actuales de `base.html`.
