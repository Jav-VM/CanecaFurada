# Fase 16 — Registro con código postal, localidad por CP y sexo

**Estado:** Completa (revisión visual en el navegador pendiente; ver §9).
**Fecha:** 2026-10-17.
**Depende de:** [Fase 2](fase-02-registro-perfil-verificacion.md) (registro y perfil), [Fase 9](fase-09-dashboard-propietario.md) (zonas), [Fase 11](fase-11-api-auditoria.md) (API) y [Fase 15](fase-15-idioma-gallego.md) (traducciones).

## 1. Objetivo y decisiones

Un registro más corto: de la dirección solo es obligatorio el **código postal**. Se añaden un campo **sexo** y el aviso «Para rexistrarte tes que ser maior de idade.» para los menores.

Decisiones tomadas con el usuario:

| Decisión | Motivo |
|---|---|
| **Las columnas de dirección no se borran.** Calle, línea 2 y provincia salen del registro; calle y línea 2 quedan como opcionales en el perfil. | Borrarlas perdería las direcciones guardadas, rompería la API de la app y dejaría el dashboard sin provincias ni localidades. |
| **Provincia deducida del CP** (España). | En España los dos primeros dígitos del CP son la provincia. Es una tabla fija de 52 entradas con los nombres del INE (`apps/accounts/postal.py`). |
| **Localidad elegida entre las del CP**, obligatoria solo si el CP tiene datos. | Se mantienen las estadísticas por localidad sin que el cliente teclee nada si su CP solo tiene una. |
| **Fuente: GeoNames, España** (CC BY 4.0). | No hay una lista oficial y abierta de CP → localidad (la de Correos es de pago). Hay que citar la fuente; se hace bajo el campo y aquí. |
| **Localidad = municipio** (columna «municipio» de GeoNames), no el «lugar». | El «lugar» baja a parroquias y calles («Suso (Arteixo)», «Castro De Elviña (Carretera)»): demasiado detalle para elegir y para agrupar zonas. Con municipios, 10 682 de 10 683 CP tienen uno solo y se marca solo. |
| **Sexo:** Hombre / Mujer / Prefiero no decirlo, obligatorio en el registro. | La tercera opción evita forzar el dato a quien no quiera darlo. |
| **Aviso de edad al instante (JS) y al enviar (servidor).** | El JS solo informa; decide el servidor. |

## 2. Alcance y exclusiones

- **Incluye:** registro web y API, perfil web y API, endpoint de localidades (web y API), ficha del cliente en el dashboard, datos de demostración, traducciones y tests.
- **No incluye:** datos de localidades fuera de España (el resto de países usan texto libre), estadísticas por sexo en el dashboard y migración de los datos de los clientes existentes (siguen como estaban; ver §8).

## 3. Datos de localidades

- `scripts/postal_codes.py build` descarga `https://download.geonames.org/export/zip/ES.zip` (solo biblioteca estándar) y genera `apps/accounts/data/postal_codes_es.json` (≈260 KB, versionado): `{"15001": ["A Coruña"], …}`, con la fecha y el SHA-256 del zip en los metadatos.
- GeoNames no publica checksums y el fichero cambia con el tiempo, así que no se fija un hash: los cambios del JSON se revisan en el diff. La aplicación **nunca descarga nada**; el script solo se ejecuta para actualizar los datos.
- 467 CP de GeoNames no traen municipio (apartados de correos, organismos: p. ej. 04070). Quedan fuera y su localidad es texto libre opcional.
- `postal.localities_for()` carga el JSON una sola vez por proceso (`lru_cache`).

## 4. Reglas (validadas en el servidor)

Viven en el modelo (`CustomerProfile.clean`), así que se aplican igual en la web, la API y el admin:

- **Obligatorios** (`CustomerProfile.REQUIRED_FIELDS`): código postal, país, fecha de nacimiento y sexo. Nombre y apellidos se validan aparte, en el usuario.
- **Provincia:** si el país es España y el CP es válido, se sobrescribe con la del prefijo, aunque llegue otra. Fuera de España se guarda lo que se envíe (opcional).
- **Localidad:** si el CP tiene localidades, es obligatoria («Elige tu localidad.») y debe ser una de ellas, sin distinguir mayúsculas; se guarda con el nombre canónico. Si no («Elige una localidad de la lista para este código postal.»), es texto libre opcional.
- **Sexo:** `MALE`, `FEMALE` o `UNDISCLOSED`. Además hay una restricción `CHECK` en la base de datos (`accounts_profile_sex_valid`).
- **Edad mínima:** el mismo validador de siempre (`ACCOUNTS_MIN_CUSTOMER_AGE`, 18); solo cambia el texto: «Para registrarte tienes que ser mayor de edad.» / gl «Para rexistrarte tes que ser maior de idade.». El texto habla de mayoría de edad: si se cambia la edad mínima, hay que revisarlo.

## 5. Interfaz

- **Registro:** Datos personales (nombre, apellidos, fecha de nacimiento, **sexo**, teléfono) · **Dónde vives** (país, código postal, localidad) · Acceso · Preferencias.
- **Perfil:** lo mismo, más calle y línea 2 opcionales. La provincia no se muestra: se deduce.
- **Sexo:** botones de opción dentro de un `fieldset` con `legend`; el error se enlaza con `aria-describedby`.
- **Localidad** (`static/js/app.js`, mejora progresiva): al teclear un CP español de 5 dígitos se consulta la lista. Con una localidad, se marca sola; con varias, aparece un desplegable; sin datos, queda el texto libre. Sin JS, el servidor valida igual y, tras un envío con errores, pinta ya el desplegable (`RegistrationForm.locality_options`).
- **Aviso de edad:** al elegir la fecha aparece el mensaje en una zona `aria-live`. No bloquea el envío.
- **Dashboard:** la ficha del cliente muestra el sexo y la dirección aunque no tenga calle.

El test de la Fase 3 que prohibía cualquier `fetch` en `app.js` se ha acotado: sigue prohibiendo validaciones (`setCustomValidity`), `XMLHttpRequest` y reglas de puntos y contraseñas, y solo admite **una** consulta GET a la URL de localidades.

## 6. Endpoints

| Ruta | Acceso | Respuesta |
|---|---|---|
| `GET /cuenta/localidades/?cp=15179` | Público, 120 consultas/hora por IP (`POSTAL_LOOKUP_MAX_PER_IP_PER_HOUR`) | `{"localities": ["Oleiros"]}`; `Cache-Control: public, max-age=86400`; 400 si el CP no es válido; 429 al superar el límite |
| `GET /api/v1/postal-codes/{cp}/localities/` | Público, límite anónimo general de la API | Igual; 400 con el formato de error de la API |

Cambios en la API (`docs/api/openapi.yaml` regenerado):

- `POST /auth/register/`: `sex` obligatorio; `address_line_1`, `address_line_2`, `city` y `province` opcionales.
- `GET/PATCH /me/profile/`: devuelve y acepta `sex`; la dirección admite vacío.

Ejemplos para la app: [guia-app-flutter.md](guia-app-flutter.md#3-registro-y-verificación-del-email).

## 7. Archivos

- **Nuevos:** `apps/accounts/postal.py`, `apps/accounts/data/postal_codes_es.json`, `scripts/postal_codes.py`, `apps/api/views/postal.py`, `apps/accounts/migrations/0008_customerprofile_sex.py`, `tests/accounts/test_postal.py`.
- **Modificados:** `apps/accounts/models.py`, `services.py` (`register_customer`, `PROFILE_FIELDS`), `forms.py`, `validators.py`, `views.py`, `urls.py`; `apps/api/serializers/auth.py`, `accounts.py`, `apps/api/urls.py`; `config/settings/base.py`; `templates/accounts/_field.html`, `templates/dashboard/customer_detail.html`; `static/js/app.js`; `assets/css/input.css` y `static/css/app.css`; `locale/gl` y `locale/es`; `apps/demo/builder.py`; tests de cuentas, API y web.

**Migración `0008_customerprofile_sex`:** añade la columna `sex` (vacía para los clientes existentes) y la restricción `CHECK`. No toca ni borra datos y es reversible.

**Configuración nueva:** `POSTAL_LOOKUP_MAX_PER_IP_PER_HOUR = 120` (en `base.py`, sin variable de entorno). No hay secretos nuevos.

## 8. Seguridad y privacidad

- **Minimización:** el sexo solo lo ven el propio cliente y el propietario (ficha del cliente, consulta auditada). Los empleados no lo ven, igual que el resto del perfil. «Prefiero no decirlo» permite no darlo.
- **Lista blanca:** `sex` entra por `PROFILE_FIELDS`; ningún campo nuevo permite cambiar rol, verificación ni puntos.
- **Endpoint público:** solo devuelve datos públicos de GeoNames, no consulta la base de datos de clientes, no repite el valor recibido en los errores y está limitado por IP.
- **Clientes existentes:** su dirección no cambia hasta que editen el perfil. Al guardar, la provincia se recalcula y, si su CP tiene datos, tienen que elegir una localidad de la lista. Los que no tengan sexo verán el aviso de datos pendientes del perfil (`missing_fields`); no se les bloquea nada.

## 9. Tests y resultados reales

27 tests nuevos (registro, perfil, módulo `postal`, endpoint web, API, restricción de BD, interfaz) y ajuste de los que esperaban calle, localidad y provincia obligatorias.

| Comando | Resultado |
|---|---|
| `python manage.py test --settings=config.settings.test --parallel 1 --noinput` (PostgreSQL 17.11, `DATABASE_URL` del `.env`) | **980 tests OK** |
| Mismo comando con `DATABASE_URL` apuntando a SQLite | **980 tests OK** (19 omitidos: concurrencia, solo PostgreSQL) |
| `python manage.py sqlmigrate accounts 0008` y `python manage.py migrate` (BD de desarrollo en PostgreSQL) | `ADD COLUMN sex … DEFAULT ''` + `CHECK`, en una transacción; `Applying accounts.0008_customerprofile_sex... OK` |
| `python manage.py check` | Sin problemas |
| `python manage.py makemigrations --check --dry-run` | Sin cambios pendientes |
| `python scripts/i18n.py check` | «Traducciones al día y completas.» |
| `python scripts/tailwind.py build` | OK |
| Página de registro en gallego (cliente de pruebas con `config.settings.dev`) | Textos nuevos en gallego; sin campos de calle ni provincia; `/cuenta/localidades/?cp=15179` → `["Oleiros"]` |

**Pendiente:** la revisión visual en el navegador (desplegable de localidad con y sin JS, aviso de edad, botones de sexo en móvil) y aplicar la migración en el VPS al desplegar.

## 10. Limitaciones, riesgos y pendientes

- **GeoNames no es oficial:** puede faltar algún CP o haber cambios de municipio. En ese caso la localidad pasa a texto libre opcional. Conviene regenerar el JSON de vez en cuando (`python scripts/postal_codes.py build`) y revisar el diff.
- **Nombres bilingües:** GeoNames usa formas como «Gasteiz / Vitoria» o «Donostia / San Sebastián», y las provincias siguen el INE («Araba/Álava»). Las estadísticas agrupan por esos nombres.
- **Solo España:** otros países usan texto libre; Portugal se podría añadir con el mismo script.
- **Texto de edad:** asume 18 años.
- **Clientes anteriores:** no tienen sexo y pueden tener una localidad escrita a mano que no coincide con la lista. Se corrige cuando editan su perfil.

## 11. Estado de los criterios de aceptación

| Criterio | Estado |
|---|---|
| Registro con solo el código postal obligatorio de la dirección | Completo |
| Provincia deducida y localidad por CP (desplegable, autorrellena si hay una) | Completo |
| Sexo con tres opciones, obligatorio | Completo |
| Aviso de mayoría de edad al instante y al enviar | Completo |
| Validación en el servidor en web y API | Completo |
| Migración no destructiva | Completo |
| Catálogo gallego completo | Completo |
| Suite en PostgreSQL | Completo (980 OK) |
| Revisión visual en el navegador | Pendiente |
