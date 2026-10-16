# Fase 15 — Web en gallego con selector gallego/castellano

**Estado:** Completa (2026-10-16). Pendiente: revisión de las traducciones por una persona nativa y revisión visual en navegador (ancho de la cabecera con las banderas).

## 1. Objetivo, alcance y exclusiones

**Objetivo:** que toda la plataforma esté en gallego por defecto y que la web pública y el área de cliente puedan verse en castellano.

**Alcance:**

| Zona | Idioma |
|---|---|
| Web pública y área de cliente | Gallego por defecto. Castellano si se pulsa la bandera de España; se vuelve al gallego con la de Galicia. |
| Panel de empleados (`/panel/`), dashboard (`/dashboard/`) y admin | Siempre en gallego, sin banderas. |
| Emails y SMS | Siempre en gallego, sea cual sea la bandera de quien provoca el envío. |
| API (`/api/`) | Gallego por defecto; castellano si la app envía `Accept-Language: es`. Los códigos de error no cambian. |
| Contenido del propietario (productos, eventos, recompensas, textos del inicio, aviso de cumpleaños) | Tal como lo escriba (normalmente en gallego). No se traduce. |

**Exclusiones (decididas por el usuario):** traducción del contenido del propietario; otros idiomas. Tampoco se traducen la documentación técnica de la API (resúmenes y descripciones de OpenAPI) ni los mensajes de consola de los comandos de gestión.

## 2. Decisiones técnicas

| Decisión | Motivo |
|---|---|
| **i18n estándar de Django; el castellano es el idioma fuente** | Las cadenas que ya había en el código son los `msgid`. No se reescribe el texto: se marca (`{% translate %}`, `{% blocktranslate %}`, `gettext`, `gettext_lazy`). El gallego está en `locale/gl/LC_MESSAGES/django.po`. Django trae sus propias traducciones `es` y `gl` (admin, validadores). |
| **Catálogo castellano «identidad»** (`locale/es/LC_MESSAGES/django.po`, generado) | Cada `msgstr` repite su `msgid`. Hace falta porque Django usa el idioma por defecto (`LANGUAGE_CODE = "gl"`) como respaldo de cualquier cadena que no esté en el catálogo del idioma activo: sin él, con la bandera de España la web seguía en gallego. Lo genera `scripts/i18n.py make` a partir del gallego (no se edita a mano) y `check` verifica que está al día. |
| **`LANGUAGE_CODE = "gl"`**, `LANGUAGES = [("gl", "Galego"), ("es", "Castellano")]` | Gallego por defecto. Cada idioma figura en su propia lengua. |
| **Middleware propio** (`apps.core.middleware.SiteLanguageMiddleware`) en lugar de `LocaleMiddleware` | El de Django usa el idioma del navegador, y la web debe abrirse siempre en gallego. El propio decide por zonas (ver §1) y añade `Vary` (`Cookie` en la web, `Accept-Language` en la API) y `Content-Language`. |
| **Cambio de idioma con la vista estándar `django.views.i18n.set_language`** (`/i18n/setlang/`) | POST con CSRF; guarda la elección en la cookie `django_language` y vuelve a la página de origen. Django solo acepta una página del propio sitio. |
| **Sin campo `next` en el formulario de las banderas** | La URL de algunas páginas lleva tokens (verificación de email, recuperación de contraseña). Con `next` acabarían escritos en el HTML. La vuelta se hace por la cabecera `Referer` (`SECURE_REFERRER_POLICY = "same-origin"`), que Django valida. |
| **Emails y SMS en el idioma del sitio** (`apps.core.i18n.site_language`) | Se renderizan siempre con `translation.override(LANGUAGE_CODE)`, también los que se envían al momento desde una petición en castellano. |
| **Textos guardados en el idioma del sitio** (`apps.core.i18n.site_text`) | Motivos de los movimientos de puntos («Canxe cancelado», «Puntos caducados», regalo de aniversario), nombre por defecto de la promoción de cumpleaños, y fecha (`when`) y aviso (`alert`) del contexto de las notificaciones de reservas. No dependen de la bandera de quien hizo la operación. |
| **Interpolación perezosa** (`apps.core.i18n.lazy_format`) | `_("… %(x)s") % {...}` fuera de una función (ayudas de formularios) se evaluaba al importar y quedaba fija en un idioma. |
| **Ciudad de la marca escrita en la frase** | «Agardámoste na Coruña» necesita la contracción del gallego. La ciudad no es editable (`content.BUSINESS["city"]`), así que va dentro de la cadena traducible en vez de como variable. |
| **Banderas sin escudo** | A tamaño icono (24 × 16 px) el escudo no se distingue. Galicia: banda diagonal azul sobre blanco. España: rojo-amarillo-rojo. |
| **`.mo` sin versionar** | Se generan desde el `.po`: en local (`scripts/i18n.py compile`), en la imagen Docker (etapa `messages`, sin gettext en la imagen final) y en el CI. |
| **La suite general sigue en castellano** | `config/settings/test.py` fija `LANGUAGE_CODE = "es"`. Así los tests existentes, que comprueban textos en castellano, siguen validando la lógica sin reescribirse. El gallego lo cubren tests propios (§6) y la comprobación del catálogo. |

## 3. Archivos

| Archivo | Cambio |
|---|---|
| `config/settings/base.py` | `LANGUAGE_CODE`, `LANGUAGES`, `LOCALE_PATHS`, cookie de idioma (1 año, `SameSite=Lax`, `HttpOnly`); middleware de idioma. |
| `config/settings/prod.py` | `LANGUAGE_COOKIE_SECURE = True`. |
| `config/settings/test.py` | `LANGUAGE_CODE = "es"` para la suite general. |
| `config/urls.py` | Ruta `i18n/` (`set_language`); cabecera del admin traducible. |
| `apps/core/middleware.py` | `SiteLanguageMiddleware` y `fixed_language_path()`. |
| `apps/core/i18n.py` | `site_language()`, `site_text()` y `lazy_format()`. |
| `apps/web/context_processors.py` | `language_switch_enabled` (sin banderas en panel, dashboard y admin). |
| `templates/components/language_switch.html` | Las dos banderas (formulario POST con CSRF, `aria-label`, `aria-pressed`). |
| `templates/base.html` | `<html lang>` dinámico; banderas a la derecha del menú, alineadas con los botones de cuenta. |
| `assets/css/input.css`, `static/css/app.css` | Estilos `.flag-btn` / `.flag-btn-active` (borde dorado de la marca); punto de corte `nav` 69rem → 75rem. |
| `static/js/app.js`, `static/js/qr-scanner.js` | Sus textos se leen de atributos `data-*` traducidos en las plantillas. |
| Todas las plantillas (`templates/**`, 111 ficheros) | Textos marcados. Los emails se reescribieron con una frase completa por variante (con o sin evento, quién cancela…). |
| Código Python de `apps/` | Formularios, mensajes, errores de servicios y vistas, `verbose_name` y `choices` de modelos, menús, países (249 nombres). |
| `locale/gl/LC_MESSAGES/django.po` | 1.684 cadenas traducidas al gallego. |
| `locale/es/LC_MESSAGES/django.po` | Catálogo castellano generado (msgstr = msgid). |
| `scripts/i18n.py` | `make` (también genera el catálogo castellano) / `compile` / `check` (ambos catálogos). |
| `Dockerfile`, `.dockerignore`, `.gitignore` | Etapa `messages`; `*.mo` sin versionar. |
| `.github/workflows/ci.yml` | Instala gettext, comprueba el catálogo (`check`) y lo compila antes de los tests. |
| `docs/api/openapi.yaml` | Regenerado (solo cambian descripciones de paginación de DRF; ver §8). |
| `tests/web/test_i18n.py` | 23 tests nuevos. |

Sin migraciones: `makemigrations` y `migrate` se ejecutan sin traducciones activas, así que marcar `verbose_name`/`choices` no cambia el estado de los modelos (comprobado con `makemigrations --check`).

## 4. Uso y operación

### Requisito nuevo en desarrollo: GNU gettext

En Windows (instalado el 2026-10-16 en el equipo de desarrollo):

```powershell
winget install --id mlocati.GetText --exact
```

En Debian/Ubuntu: `sudo apt-get install gettext`. Después de instalarlo, abre una terminal nueva para que el `PATH` lo incluya.

### Órdenes

```powershell
python scripts/i18n.py compile   # necesario tras clonar o actualizar: genera los .mo
python scripts/i18n.py make      # tras añadir o cambiar textos en el código o las plantillas
python scripts/i18n.py check     # lo mismo que comprueba el CI
```

### Añadir o cambiar un texto

1. Escríbelo en castellano y márcalo: `{% translate "…" %}` o `{% blocktranslate %}…{{ variable }}…{% endblocktranslate %}` en plantillas; `_("…")` en Python, con `gettext_lazy` fuera de funciones. Con variables, usa `_("… %(nombre)s …") % {"nombre": valor}` (o `lazy_format` fuera de funciones), nunca f-strings.
2. `python scripts/i18n.py make`.
3. Traduce las entradas nuevas de `locale/gl/LC_MESSAGES/django.po` (`msgstr`). Conserva igual los marcadores (`%(nombre)s`, `%%`); `msgfmt --check` lo verifica.
4. Vuelve a ejecutar `python scripts/i18n.py make` para regenerar el catálogo castellano (`locale/es`), y después `check` y `compile`. El catálogo castellano no se edita a mano.

Si cambias el texto castellano de una cadena ya traducida, gettext marca la traducción como dudosa (`fuzzy`) y no se usa: revísala y quita la marca. `check` falla mientras quede alguna.

### Producción

La imagen compila las traducciones al construirse (etapa `messages`); no hay pasos manuales nuevos en el despliegue.

## 5. Seguridad y privacidad

- **Cookie de idioma** `django_language`: guarda solo `gl` o `es`. Es `HttpOnly`, `SameSite=Lax` y `Secure` en producción. Es una cookie de preferencia que pide el propio usuario al pulsar una bandera, sin datos personales ni seguimiento; conviene mencionarla en la política de cookies del local.
- **CSRF y redirecciones:** el cambio exige POST con token CSRF. Un GET no cambia nada. Django no redirige a otros dominios aunque se le pase un `next` o un `Referer` ajeno (hay tests).
- **Tokens en URL:** el selector no escribe la URL actual en la página (ver §2).
- **Valores no admitidos:** una cookie con otro idioma (p. ej. `fr`) se ignora y se usa el gallego.
- **Textos de terceros:** el marcador `{puntos}` del aviso de cumpleaños sigue sin pasar por el motor de plantillas (Fase 14).
- **Caché:** las respuestas de la web llevan `Vary: Cookie` y las de la API `Vary: Accept-Language`, así que un proxy no sirve una página en el idioma de otro usuario.

## 6. Pruebas

Ejecutadas el 2026-10-16:

| Orden | Resultado |
|---|---|
| `python scripts/i18n.py check` | Traducciones al día y completas (gallego y castellano, `msgfmt --check` sin errores). |
| `python manage.py check` | Sin incidencias. |
| `python manage.py makemigrations --check --dry-run` | Sin cambios. |
| `python manage.py spectacular --validate --fail-on-warn` | Idéntico a `docs/api/openapi.yaml`. |
| `python manage.py test --settings=config.settings.test --parallel 1 --noinput` (PostgreSQL 17) | **953 tests OK** (930 anteriores + 23 nuevos). |
| La misma suite en SQLite | **953 tests OK**; 19 omitidos (los de concurrencia, como siempre en SQLite en memoria). |

Comprobaciones adicionales hechas durante el desarrollo:
- Las 140 combinaciones de plantillas de email y SMS producen en castellano exactamente el mismo texto que antes de marcarlas.
- Recorrido de todas las páginas en gallego (anónimo, cliente, empleado, propietario y admin) con los datos de demostración: lo único en castellano es el contenido de demo escrito por el «propietario», que se muestra tal cual.

Tests nuevos (`tests/web/test_i18n.py`):
- **Idioma por defecto:** gallego aunque el navegador pida castellano; bandera de Galicia marcada.
- **Selector:**
  - la bandera de España cambia la web pública y el área de cliente, y se puede volver;
  - cookie restringida y valores desconocidos ignorados;
  - exige CSRF y POST, y no redirige fuera del sitio;
  - no escribe tokens de la URL en la página.
- **Zonas fijas:** panel, dashboard y admin en gallego con la cookie `es`, sin banderas.
- **API:** gallego por defecto, castellano con `Accept-Language: es`, mismo código de error, `Vary`; ignora la cookie de la web.
- **Envíos y datos:** emails inmediatos y en cola en gallego desde una petición en castellano; fecha de las reservas para los avisos («ás»).
- **Mensajes:** errores de formularios y mensajes flash en gallego.
- **Catálogo:** completo, sin entradas vacías ni `fuzzy`.
- **Castellano sin respaldo al gallego:** con el gallego como idioma del sitio, todas las cadenas salen tal cual en castellano (también con contexto y plurales). Estos tests vacían la caché de catálogos de Django (`override_settings` de `LANGUAGES`): sin eso, el catálogo castellano cargado por el resto de la suite ocultaba el fallo.
- **«Agasallos»:** la sección de recompensas se llama así en gallego, en la web y en el dashboard.

## 7. Criterios de aceptación

| Criterio | Estado |
|---|---|
| Toda la interfaz (web pública, área de cliente, panel, dashboard, admin, notificaciones) en gallego por defecto | Completa |
| Banderas tamaño icono a la derecha del menú, alineadas; la activa con borde de la marca | Completa (pendiente revisión visual) |
| Bandera de España → castellano en web pública y área de cliente; de vuelta al gallego | Completa |
| Panel y dashboard siempre en gallego | Completa |
| Emails y SMS siempre en gallego | Completa |
| API gallego por defecto y castellano a petición | Completa |
| Contenido del propietario sin traducir | Completa |
| Seguridad: CSRF, sin redirecciones abiertas, sin tokens en el HTML | Completa |
| Documentación y tests | Completa |

## 8. Ajustes tras la primera revisión (2026-10-16)

- **La bandera de España no traducía.** Causa: el respaldo de Django al idioma por defecto (ver §2, «Catálogo castellano identidad»). Los tests no lo detectaban porque reutilizaban un catálogo castellano cargado sin respaldo; ahora vacían la caché y lo reproducen (5 tests fallan sin el catálogo `es` y pasan con él).
- **«Recompensas» → «Agasallos» (solo en gallego).** Todas las cadenas de recompensas cambian a «agasallo/agasallos», con la concordancia en masculino («Novo agasallo», «Este agasallo esgotouse», «recollelo»). Los estados de una recompensa usan ahora contexto (`pgettext_lazy("recompensa", …)`: «Activo», «Pausado», «Arquivado», «Esgotado») para no cambiar los de las promociones, que siguen en femenino. En castellano sigue llamándose «Recompensas». Las URL (`/recompensas/`) y los nombres internos no cambian.
- **Mensajes flash sin marcar.** 16 avisos de las vistas (p. ej. «Esta compra ya estaba registrada») se habían quedado en castellano; ahora están traducidos. El aviso «marcado como disponible/agotado» de la carta mezclaba una palabra castellana dentro de la frase gallega: ahora son dos frases completas.

## 9. Limitaciones y pendientes

- **Revisión nativa:** las traducciones las redactó el asistente siguiendo la normativa de la RAG. Revisadlas antes de producción, sobre todo el vocabulario de la casa: «canxe/canxear», «agasallo de aniversario», «billa» (por grifo), «ligazón», «contrasinal».
- **Revisión visual:** el punto de corte de la cabecera en una sola línea se subió a 75rem por estimación (banderas y textos gallegos algo más largos), sin medirlo en el navegador. Comprobad también la cabecera en móvil.
- **Mensajes propios de DRF** (p. ej. «Authentication credentials were not provided.»): DRF no trae traducción al gallego, así que en la API salen en inglés si la app no pide castellano. Los mensajes propios de la API sí están en gallego. Las descripciones de paginación del esquema OpenAPI pasaron, por el mismo motivo, del castellano al inglés.
- **Datos ya guardados:** los motivos de movimientos y los avisos ya encolados antes de esta fase siguen en castellano; los nuevos se guardan en gallego.
- **Orden de la lista de países:** alfabético en castellano también cuando se muestra en gallego.
- **Documentación de la API y mensajes de consola:** siguen en castellano (decisión de alcance).
- **Imagen Docker:** la etapa `messages` no se ha podido construir en local (Docker no está instalado en el equipo de desarrollo); la comprobará el job `docker` del CI.
