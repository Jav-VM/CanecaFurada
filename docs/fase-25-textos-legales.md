# Fase 25 — Textos legales, aceptación en el registro y minimización de datos

**Estado:** En curso (2026-10-17). Código, traducciones y tests hechos; faltan la revisión en el navegador y, sobre todo, la **revisión legal** de los textos y de la documentación interna (§8).

> El código da la estructura y los mecanismos. Los textos definitivos, los plazos y los documentos firmados son del titular y de su asesor: todo lo generado aquí está marcado como **borrador pendiente de revisión legal**. El código no garantiza por sí mismo el cumplimiento del RGPD, la LOPDGDD ni la LSSI-CE.

## 1. Objetivo y alcance

Cubrir los puntos de cumplimiento que faltaban (conversación del 2026-10-17):

1. **Textos legales:** aviso legal (LSSI-CE art. 10), política de privacidad (RGPD arts. 13–14), política de cookies (LSSI-CE art. 22.2) y condiciones del programa de puntos, enlazados en el pie y en el registro.
2. **Datos del titular** para el aviso legal, editables en el dashboard.
3. **Aceptación informada en el registro**, con prueba (fecha y versiones), también en la API.
4. **Minimización:** el sexo pasa a opcional.
5. **Documentación interna** (plantillas para el asesor): registro de actividades, encargados, brechas y plazos de conservación.

**Fase 26 (siguiente):** exportar y suprimir la cuenta y la purga con plazos (ver `docs/legal/conservacion.md`).

**Decisiones del usuario:**
- dos fases;
- textos **editables en el dashboard** a partir de un borrador base sin datos inventados;
- supresión desde el perfil del cliente (Fase 26);
- **sexo opcional** y fecha de nacimiento obligatoria (mayoría de edad para el alcohol y regalo de cumpleaños).

## 2. Criterios de aceptación

| Criterio | Estado |
|---|---|
| Cuatro páginas legales públicas (`/legal/<documento>/`), enlazadas en el pie de todas las páginas | Completa (tests) |
| Sin texto publicado: borrador base marcado «pendiente de revisión legal», con los valores reales de la web y sin datos del negocio inventados | Completa (tests) |
| Datos del titular editables (NIF/CIF con formato validado) y usados en los textos | Completa (tests) |
| Dashboard → Contenido → «Textos legales»: editar y publicar; la versión sube solo si el texto cambia; auditado sin el texto; solo el propietario | Completa (tests) |
| Registro web y API: aceptación obligatoria, con fecha y versiones guardadas | Completa (tests) |
| Sexo opcional en el registro, el perfil y la API | Completa (tests) |
| Documentación interna en `docs/legal/` | Completa (borradores) |
| Revisión en el navegador | Pendiente |
| Revisión legal de los textos y de `docs/legal/` | **Pendiente (asesor)** |

## 3. Decisiones técnicas

| Decisión | Motivo |
|---|---|
| Modelo `LegalDocument` (uno por tipo, `version` entera) y servicio `apps/web/legal.py` | El propietario publica los textos que le dé su asesor. Cada cambio sube la versión, y el perfil guarda qué versión aceptó cada cliente (art. 7.1 RGPD: poder demostrar el consentimiento). |
| Borrador base generado (`apps/web/legal_defaults.py`) | Sin texto publicado, la web no queda sin información legal. El borrador describe lo que la web hace de verdad: datos, finalidades, bases legales, solo cookies técnicas (`sessionid`, `csrftoken`, `django_language`), puntos por euro vigentes, caducidad, validez de los canjes y edad mínima. Lo que solo sabe el negocio (titular, proveedores, plazos) aparece como «[pendiente…]». Versión 0 = borrador. |
| Solo cookies técnicas: sin banner | No hay analítica, publicidad ni recursos de terceros (comprobado). Según la guía de la AEPD, las cookies técnicas y de preferencia no necesitan consentimiento, pero sí información, que da la política de cookies. |
| La aceptación se exige en el **servicio** `register_customer` | La web y la API no pueden saltársela. Guarda `terms_accepted_at`, `privacy_version` y `terms_version`. |
| Titular en `BusinessInfo` | Mismo patrón que el resto del contenido: vacío = «pendiente de publicar», nunca valores inventados. El NIF/CIF se normaliza (sin espacios, puntos ni guiones) y se valida el formato. |
| Sexo opcional | Minimización (art. 5.1.c RGPD): solo se usaba para estadísticas agregadas. Sale de `CustomerProfile.REQUIRED_FIELDS` y es opcional en el formulario y en la API. |
| Borrador solo en castellano | Lo que publica el propietario no se traduce (Fase 15). Los textos de la interfaz sí están en gallego. |

## 4. Archivos

- **Modelos y migraciones:**
  - `apps/web/models.py` (titular y `LegalDocument`) → `web.0009_legal_texts`;
  - `apps/accounts/models.py` (aceptación en el perfil y `REQUIRED_FIELDS` sin sexo) → `accounts.0009_terms_acceptance`.
  - Solo añaden campos y una tabla; no tocan datos.
- **Dominio:** `apps/web/legal.py`, `apps/web/legal_defaults.py`, `apps/web/services.py` (titular en `EDITABLE_FIELDS`), `apps/accounts/services.py` (`register_customer(accept_terms=…, sex="")`).
- **Web:** `apps/web/views.py` (`LegalView`), `apps/web/urls.py` (`legal/<kind>/`), `templates/web/legal.html`, pie (`templates/components/footer.html`), Recompensas (`templates/web/rewards/_como.html`); `static/css/app.css` recompilado (`python scripts/tailwind.py build`) por la rejilla de la página legal.
- **Registro:** `apps/accounts/forms.py` (`accept_terms`, sexo opcional), `templates/accounts/register.html`.
- **API:** `apps/api/serializers/auth.py` (`accept_terms` obligatorio, `sex` opcional) → `docs/api/openapi.yaml` regenerado. **Cambio para la app:** el registro debe enviar `accept_terms: true`.
- **Dashboard:** `apps/dashboard/forms.py` (titular y `LegalDocumentForm`), `apps/dashboard/views.py` (`legal_edit`), `apps/dashboard/urls.py`, `templates/dashboard/content.html` («Textos legales»).
- **Demo:** `apps/demo/builder.py` (los clientes ficticios aceptan los textos).
- **Documentación interna:** `docs/legal/registro-actividades.md`, `encargados.md`, `brechas.md`, `conservacion.md`.
- **Traducciones:** `locale/gl`, `locale/es` (49 entradas nuevas).
- **Tests:** nuevo `tests/web/test_legal.py`; adaptados los que exigían el sexo (`tests/accounts/test_registration.py`, `test_profile.py`, `test_postal.py`, `tests/api/test_auth.py`, `tests/web/test_account_forms_ui.py`) y la factoría (`accept_terms`).

Sin variables de entorno nuevas.

## 5. Uso

1. Dashboard → Contenido: rellena el **titular** (nombre o razón social, NIF/CIF, domicilio, email legal y, si los hay, datos registrales).
2. Dashboard → Contenido → **Textos legales** → «Editar» en cada documento. Se abre con el borrador base: revísalo con tu asesor, completa lo marcado «[pendiente…]», quita la primera línea («BORRADOR…») y guarda. Cada cambio se publica como versión nueva.
3. Revisa y completa `docs/legal/` con tu asesor.

Antes de usarlo en una base existente: `python manage.py migrate` (`web.0009` y `accounts.0009`).

## 6. Seguridad y privacidad

- Solo el propietario edita los textos y el titular, con el permiso comprobado en la vista y en el servicio. Queda auditado sin el contenido.
- Los textos se pintan con autoescape: no se puede inyectar HTML.
- La aceptación se guarda con fecha y versión; las cuentas anteriores a esta fase quedan sin ella (ver §8).
- No se añaden cookies ni servicios de terceros.

## 7. Pruebas y resultados

| Comando | Resultado (2026-10-17) |
|---|---|
| `python manage.py makemigrations --check --dry-run --settings=config.settings.test` | Sin cambios pendientes |
| `python manage.py test --settings=config.settings.test --noinput` | **1168 tests OK** |
| `python scripts/i18n.py check` | Al día y completas |
| `python manage.py spectacular --validate --fail-on-warn` | Válido; `docs/api/openapi.yaml` regenerado con `accept_terms` y `sex` opcional |
| `node --check` del JavaScript propio | Sin errores (sin cambios) |

`tests/web/test_legal.py` (17 tests):
- las cuatro páginas con el borrador;
- titular vacío como «pendiente»; titular rellenado, NIF normalizado y NIF no válido;
- condiciones con los valores reales y cookies solo técnicas;
- texto publicado escapado y versionado;
- enlaces en el pie y en Recompensas;
- versiones que solo suben si el texto cambia, auditoría sin texto, solo el propietario;
- edición en el dashboard (borrador como punto de partida, 400 vacío, 404, 403);
- aceptación obligatoria en el servicio, la web y la API, con las versiones guardadas;
- enlaces en el registro y sexo opcional.

## 8. Limitaciones y pendientes

- **Revisión legal (imprescindible antes de abrir al público):** textos definitivos, proveedores (encargados), plazos y documentación de `docs/legal/`.
- **Clientes anteriores a esta fase:** no tienen aceptación guardada. Pedírsela en su siguiente acceso sería una mejora aparte.
- **Fase 26:** exportación y supresión de la cuenta (el borrador de las condiciones indica de momento que la baja se pide por email) y la purga con plazos.
- Revisión en el navegador: las cuatro páginas legales, el pie, el registro (con y sin aceptar) y el perfil sin sexo.
