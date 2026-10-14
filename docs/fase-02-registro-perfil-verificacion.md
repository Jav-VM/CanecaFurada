# Fase 2 — Autenticación, registro, perfiles, verificación de email y permisos

**Estado:** Completa (validación en PostgreSQL y SMTP real pendientes; ver §10).
**Fecha:** 2026-10-14.
**Depende de:** [Fase 0](fase-00-fundacion.md) y [Fase 1](fase-01-proyecto-base.md).

## 1. Objetivo, contexto y decisiones previas

Completar la autenticación: registro público de clientes con datos estructurados, verificación del email, perfil editable, preferencias de comunicación auditables, cambio seguro de email y permisos por rol.

Decisiones tomadas con el usuario antes de empezar:

| Cuestión | Decisión |
|---|---|
| El prompt de la "Fase 2" correspondía a la Fase 3 del plan, y la Fase 2 del plan (sistema de diseño) no estaba hecha | **Reordenar el plan**: este trabajo es la Fase 2 y el sistema de diseño pasa a la Fase 3 ([plan](plan-de-fases.md)). Las plantillas de esta fase son HTML sencillo y accesible. |
| Validación del teléfono | Librería mantenida **`phonenumbers`** (nueva dependencia), normalización E.164. |
| Alcance de "completar la autenticación" | Incluye **login/logout propios y recuperación de contraseña** (y cambio de contraseña). |

Decisiones menores adoptadas (motivo entre paréntesis):

- **Edad mínima 18 años**, configurable con `ACCOUNTS_MIN_CUSTOMER_AGE` (cervecería y promociones de bebidas alcohólicas; además evita tratar datos de menores). **Debe confirmarla el propietario.**
- **País como código ISO 3166-1 alfa-2** (estable, independiente del idioma, útil para estadísticas). La lista se valida en el modelo, no como `choices`, para que actualizarla no genere migraciones.
- **Código postal**: formato estricto para España (01–52 + 3 dígitos) y Portugal (`1234-567`); genérico (2–12 caracteres alfanuméricos, espacio o guion) para el resto.
- **Solo móviles**: se rechazan fijos (el campo es "teléfono móvil"); se aceptan los números que `phonenumbers` clasifica como `MOBILE` o `FIXED_LINE_OR_MOBILE` (países que no distinguen, como EE. UU.).
- **Fecha de nacimiento editable una vez cada 365 días** (`ACCOUNTS_DATE_OF_BIRTH_CHANGE_COOLDOWN_DAYS`): permite corregir errores y evita abusar de las promociones de cumpleaños. El primer valor (registro o perfil antiguo vacío) no cuenta como cambio.
- **Anti-enumeración en el registro**: si el email ya existe, la web responde igual que un registro correcto y envía al titular un aviso con enlace a la recuperación de contraseña (como mucho uno al día).
- **Sin inicio de sesión automático tras registrarse**: la respuesta es idéntica exista o no el email.

## 2. Alcance y exclusiones

**Incluye:** registro público (solo `CUSTOMER`), login/logout, recuperación y cambio de contraseña, verificación de email con token de un solo uso y caducidad, reenvío limitado, cambio de email con nueva verificación, página de perfil, preferencias promocionales con historial, activación/desactivación auditada de cuentas por el propietario, decorador y servicio para exigir email verificado, utilidades de cumpleaños (29 de febrero), configuración de correo por variables de entorno y límites de intentos.

**Excluye:** sistema de diseño (Fase 3), envío de promociones y SMS (Fase 10; no se integra ningún proveedor de SMS), verificación del teléfono, API REST (Fase 11), panel de empleado (Fase 6), borrado de cuenta o exportación de datos (pendiente de decisión), política de privacidad y textos legales (los aporta el propietario).

## 3. Campos del registro

Formulario `/cuenta/registro/` en cuatro secciones. Los obligatorios se marcan con `*` (y "obligatorio" para lectores de pantalla); el teléfono y la segunda línea de dirección, con "(opcional)".

| Sección | Campo | Obligatorio | Validación |
|---|---|---|---|
| A. Datos personales | Nombre, Apellidos | Sí | ≤150, espacios normalizados |
| | Fecha de nacimiento | Sí | Fecha real, no futura, edad 18–120 |
| | Teléfono móvil | **No** | Móvil válido, normalizado a E.164 |
| B. Dirección postal | Dirección | Sí | ≤200 |
| | Dirección (línea 2) | No | ≤200 |
| | Código postal | Sí | Según país (ver §1) |
| | Localidad, Provincia | Sí | ≤100 |
| | País | Sí | Código ISO de la lista (por defecto ES) |
| C. Acceso a la cuenta | Email | Sí | Formato, ≤254, minúsculas, único sin distinguir mayúsculas |
| | Contraseña y confirmación | Sí | Coinciden; validadores de Django (≥10, no común, no numérica, no parecida a los datos) |
| D. Preferencias de comunicación | Email promocional, SMS promocional | No | Desactivadas por defecto; el SMS exige teléfono |

No existe ningún campo de rol, estado o verificación: el formulario es un `forms.Form` con campos explícitos y el servicio `register_customer` no acepta esos argumentos (un `TypeError` lo impide).

## 4. Modelo de datos

### `accounts.User` (un campo nuevo)
| Campo | Tipo | Notas |
|---|---|---|
| `email_verified_at` | DateTime, nullable | Vacío = pendiente. Solo lo fija `services.confirm_email_token`. |

**Invariante:** si cambia el email por cualquier `save()` (incluido el admin) sin fijar a la vez una nueva fecha de verificación, `User.save()` anula la verificación. `QuerySet.update()` no pasa por `save()` y no debe usarse para cambiar emails.

### `accounts.CustomerProfile` (campos nuevos)
| Campo | Tipo | Notas |
|---|---|---|
| `address_line_1`, `address_line_2` | Char(200) | |
| `postal_code` | Char(12) | Mayúsculas, espacios normalizados |
| `city`, `province` | Char(100) | `province` admite estado o región |
| `country` | Char(2) | ISO 3166-1 alfa-2, por defecto `ES` |
| `date_of_birth` | Date, nullable | `DateField` |
| `date_of_birth_changed_at` | DateTime, nullable | Para el límite de cambios |
| `phone_number` | Char(16) | E.164 o vacío; **no hay campo de "verificado"** |
| `promo_email_opt_in`, `promo_sms_opt_in` | Bool, `False` | Consentimiento vigente |

En BD los campos personales admiten vacío porque los clientes anteriores a esta fase y quienes pasan a cliente desde otro rol no los tienen. El registro y la edición del perfil exigen los obligatorios (`CustomerProfile.REQUIRED_FIELDS`); la página de perfil avisa si faltan. Restricción `CHECK`: `promo_sms_opt_in` solo con teléfono.

### `accounts.EmailVerificationToken` (nuevo)
`user`, `purpose` (`VERIFY` / `CHANGE`), `email` (dirección que se confirma), `token_hash` (SHA-256, único), `created_at`, `expires_at`, `used_at`, `revoked_at`. **El token en claro no se guarda**: solo viaja en el email.

### `accounts.CommunicationPreferenceChange` (nuevo, solo inserción)
`user`, `channel` (`EMAIL` / `SMS`), `opted_in`, `source` (`REGISTRATION` / `PROFILE` / `SYSTEM`), `created_at`. Solo lectura en el admin.

### `core.AuditEvent` (acciones nuevas)
`ACCOUNT_ACTIVATED`, `ACCOUNT_DEACTIVATED`, `EMAIL_VERIFIED`, `EMAIL_CHANGE_REQUESTED`, `EMAIL_CHANGED`, `PROFILE_UPDATED` (con `metadata.fields`: **solo los nombres** de los campos cambiados, nunca los valores).

### Migraciones (revisadas, pequeñas y reversibles)
| Migración | Contenido |
|---|---|
| `accounts/0004_user_email_verified_at` | Única modificación de la tabla de usuarios: `ADD COLUMN email_verified_at NULL` (revisado con `sqlmigrate`). No toca datos: las cuentas existentes quedan pendientes de verificación (no se presume verificado un email que nadie confirmó). |
| `accounts/0005_customer_profile_personal_data` | Columnas nuevas del perfil, todas con vacío o valor por defecto, y el `CHECK` del SMS. |
| `accounts/0006_email_tokens_and_preference_history` | Dos tablas nuevas. |
| `core/0002_audit_actions_phase2` | Solo cambia las `choices` de `action` (sin efecto en SQL). |

Probadas hacia delante, hacia atrás (`accounts 0003`, `core 0001`) y otra vez hacia delante sobre una SQLite temporal, y aplicadas a la `db.sqlite3` local.

## 5. Flujo de verificación del email

1. **Registro** (`services.register_customer`, transacción única): valida todo en servidor → crea `User` `CUSTOMER` con `email_verified_at = NULL` → completa el perfil → registra el estado inicial de los dos consentimientos → emite un token (`secrets.token_urlsafe(32)`, 256 bits) y guarda su hash → **al confirmar la transacción** (`on_commit`) envía el email con el enlace `SITE_BASE_URL/cuenta/verificar-email/<token>/`.
2. **Confirmación:** el `GET` del enlace solo muestra un botón; el **`POST`** consume el token (así los analizadores de enlaces del correo no lo gastan). `services.confirm_email_token` comprueba que existe, no está usado, revocado ni caducado, que la cuenta está activa y que el email no ha cambiado desde que se emitió; lo marca usado con un `UPDATE … WHERE used_at IS NULL` (solo una petición concurrente puede ganar) y fija `email_verified_at`. Queda un `AuditEvent` `EMAIL_VERIFIED`.
3. **Errores:** inválido, caducado, ya usado, sustituido por otro más reciente. Se muestran con estado 200 (no 404) para que el token no aparezca en los logs de peticiones fallidas; las páginas usan `Cache-Control: no-cache`.
4. **Caducidad:** `EMAIL_VERIFICATION_TOKEN_TTL_HOURS` (24 h por defecto).
5. **Reenvío:** desde el perfil (`POST`, sesión iniciada) o desde `/cuenta/verificar-email/reenviar/` (público, por email). Cada envío revoca los tokens pendientes anteriores. Límites por cuenta, calculados en BD: **1 envío por minuto y finalidad** y **5 al día** en total. El reenvío público responde siempre lo mismo (exista o no la cuenta, esté o no verificada o limitada) y además limita por IP (20 por hora).
6. **Cambio de email** (`services.request_email_change`): exige la contraseña actual; envía un token `CHANGE` a la **nueva** dirección; **el email de acceso no cambia hasta confirmar**. Al confirmar, el email cambia y queda verificado (se acaba de demostrar su control), se revocan los demás tokens, se audita `EMAIL_CHANGED` y se avisa a la dirección anterior. Si la nueva dirección ya pertenece a otra cuenta no se envía nada ni se informa (anti-enumeración); si alguien la ocupa entre la solicitud y la confirmación, la confirmación falla.

### Qué puede hacer una cuenta pendiente de verificación
| Puede | No puede |
|---|---|
| Iniciar y cerrar sesión, ver y editar su perfil, cambiar preferencias (se guardan pero no se envían promociones), reenviar la verificación, cambiar email y contraseña, recuperar la contraseña | Recibir comunicaciones promocionales (`can_receive_promotional_email` exige email verificado) ni usar operaciones que lo exijan: acumular o canjear puntos, mostrar el QR, reservas (fases 5–8). Esas vistas deben usar `@verified_email_required` y sus servicios `services.require_verified_email(user)`. |

## 6. Configuración del correo y variables de entorno

| Variable | Uso | Por defecto |
|---|---|---|
| `EMAIL_BACKEND` | Backend de Django | Base/prod: SMTP · dev: consola · tests: memoria |
| `EMAIL_HOST`, `EMAIL_PORT` | Servidor SMTP | vacío, `587` |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Credenciales SMTP (**solo en `.env` o en el entorno**) | vacío |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `EMAIL_TIMEOUT` | Conexión | `True`, `False`, `10` |
| `DEFAULT_FROM_EMAIL` | Remitente | `no-reply@example.com` |
| `SITE_BASE_URL` | Base de los enlaces de los emails (no se usa la cabecera `Host`) | `http://localhost:8000` |
| `EMAIL_VERIFICATION_TOKEN_TTL_HOURS` | Caducidad del enlace de verificación | `24` |
| `ACCOUNTS_MIN_CUSTOMER_AGE` | Edad mínima de registro | `18` |
| `CACHE_URL` | Caché para limitar intentos de login | caché en memoria |

- **Desarrollo:** los emails se imprimen en la consola de `runserver`, con el enlace de verificación (solo en local). Para probar con un SMTP local (por ejemplo Mailpit), define `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT` y `EMAIL_USE_TLS=False` en `.env`. **En Windows**, si la consola falla al imprimir acentos (`UnicodeEncodeError` en el log), arranca con `PYTHONUTF8=1` (PowerShell: `$env:PYTHONUTF8=1`).
- **Producción (`config.settings.prod`)**: no arranca si `EMAIL_BACKEND` es consola, memoria, fichero o nulo, si falta `EMAIL_HOST` con SMTP, o si `SITE_BASE_URL` no empieza por `https://`. No se simula ningún envío.
- **Fallos del SMTP:** no deshacen el registro; se registran como `ERROR` con el tipo de excepción, **sin destinatario, token ni enlace**. El usuario puede pedir un reenvío.
- Configuración no expuesta como variable (en `config/settings/base.py`): intervalo y máximo de reenvíos, días entre cambios de fecha de nacimiento, región por defecto del teléfono (`ES`), límites de login (5 fallos por email y 30 por IP cada 15 min) y de formularios públicos por IP (20/h), caducidad de la recuperación de contraseña (2 h).

## 7. Preferencias de comunicación

- Dos consentimientos independientes en el perfil, **desactivados por defecto**. Introducir email o teléfono, o verificar el email, **no** los activa.
- Solo cambian con `services.set_communication_preferences` (página de perfil) o al registrarse. Cada cambio real crea una fila en `CommunicationPreferenceChange` (canal, nuevo valor, origen y fecha). En el registro se guarda el estado inicial de ambos canales.
- No se puede aceptar SMS sin teléfono (servicio, modelo y `CHECK` en BD). Si el cliente borra su teléfono, el consentimiento de SMS se retira automáticamente con origen `SYSTEM`.

**Cómo se comprobarán antes de enviar promociones (Fase 10):** todo envío promocional debe llamar, justo antes de enviar cada mensaje, a:
- `services.can_receive_promotional_email(user)`: cuenta activa, rol `CUSTOMER`, **email verificado** y `promo_email_opt_in` vigente.
- `services.can_receive_promotional_sms(user)`: cuenta activa, rol `CUSTOMER`, teléfono indicado y `promo_sms_opt_in` vigente. Como el teléfono no está verificado, la Fase 10 debe decidir si exige verificarlo antes del primer SMS.

Los emails de esta fase (verificación, cambio de email, aviso de cuenta existente, recuperación de contraseña) son **transaccionales** y no contienen publicidad.

Para las promociones de cumpleaños, `apps/accounts/birthdays.py` ofrece `birthday_in_year` y `profiles_with_birthday_on`. **Política del 29 de febrero:** en años no bisiestos el cumpleaños promocional es el **28 de febrero**. El cálculo de edad para el registro considera cumplidos los años el 1 de marzo.

## 8. Preparación para la app móvil

Toda la lógica está en `apps/accounts/services.py` y no depende de `request` ni de la sesión. La futura API (Fase 11) necesitará estas operaciones, que solo deben llamar a los servicios:

| Operación | Servicio |
|---|---|
| Registro | `register_customer(...)`; ante `EmailAlreadyRegistered`, responder igual que un registro correcto y llamar a `notify_existing_account(email)` |
| Confirmar email (desde un enlace universal o deep link) | `confirm_email_token(token)` |
| Reenviar verificación | `resend_verification_email(user)` / `request_verification_resend(email)` |
| Ver o editar perfil (`/me/profile`) | lectura del perfil de `request.user`; `update_customer_profile(user=..., ...)` |
| Preferencias | `set_communication_preferences(user=..., ...)` |
| Cambiar email | `request_email_change(user=..., new_email=..., password=...)` |
| Recuperar contraseña | `PasswordResetForm` de Django o un servicio equivalente |
| Comprobar requisitos | `require_verified_email(user)` |

Errores: `ValidationError` → 400 con `message_dict`, `PermissionDenied` → 403, `RateLimited` → 429. Pendiente para la Fase 11: autenticación por token, límites de intentos de login para la API y enlaces de los emails que abran la app.

## 9. Roles y permisos

- **Registro público → siempre `CUSTOMER`.** Ni el formulario ni el servicio aceptan rol, `is_staff`, `is_superuser` o `email_verified_at` (con tests).
- **OWNER:** admin técnico. Desde él puede dar de alta empleados, cambiar roles (`change_role`) y **autorizar o desactivar cuentas** con las acciones "Activar (autorizar)" y "Desactivar" o con la casilla *activo*. Ambas vías usan `services.set_user_active`, que exige propietario activo, protege al último propietario y audita. Una cuenta desactivada pierde la sesión y no puede entrar.
- **EMPLOYEE:** de momento solo "Mi cuenta" (cambiar email y contraseña); el panel de empleado llega en la Fase 6. No accede al admin ni al perfil de cliente (403).
- **CUSTOMER:** solo **su** perfil. Las URLs de perfil no llevan identificadores (`/cuenta/perfil/`) y las vistas actúan sobre `request.user`: los IDs, `public_id` o emails enviados en el formulario se ignoran (tests de IDOR).
- Todas las operaciones sensibles son `POST` con CSRF (logout, preferencias, reenvío, confirmación del token). El cambio de email y el de contraseña exigen la contraseña actual.

## 10. Limitaciones, riesgos y pendientes

- **PostgreSQL:** los tests se ejecutan en SQLite. Los `select_for_update` solo bloquean en PostgreSQL. El consumo del token es atómico en ambos (UPDATE condicionado). Hay que repetir los tests en PostgreSQL.
- **SMTP real:** no se ha probado con un proveedor real; el flujo se verificó con el backend en memoria (tests) y el de consola (prueba manual con `runserver`).
- **Límites de intentos en caché local:** la caché en memoria es por proceso. Con varios procesos en producción hay que definir `CACHE_URL` (Redis requiere instalar el paquete `redis`; `dbcache` requiere `createcachetable`). Detrás de un proxy, `REMOTE_ADDR` es la IP del proxy: se revisará en la Fase 12.
- **Diferencias de tiempo de respuesta:** el registro con un email existente responde algo más rápido (no calcula el hash de la contraseña), lo que permitiría enumerar emails midiendo tiempos. El riesgo es bajo; se revisará en la Fase 12.
- **Tokens:** las filas de tokens usados o caducados conservan la dirección de email. Falta una tarea de purga periódica (pendiente; Fase 10/12).
- **Datos personales y legal:** falta la política de privacidad y el texto de consentimiento definitivo (los aporta el propietario), el plazo de conservación, el borrado o anonimización de cuentas y la exportación de datos. Al pasar de cliente a empleado se conserva el perfil. Este código no garantiza por sí mismo el cumplimiento del RGPD/LOPDGDD.
- **Edad mínima 18** pendiente de confirmar por el propietario.
- **Teléfono no verificado:** no se usa para recuperar la cuenta ni se marca como verificado.
- **Consentimiento:** el historial no guarda IP ni el texto exacto aceptado (minimización). Si el asesor legal lo exige, se añadirá una versión del texto de consentimiento.
- **Cuentas existentes** (propietario creado en la Fase 0): quedan pendientes de verificación. Pueden verificarse desde `/cuenta/verificar-email/reenviar/` (el propietario va directo al admin y no ve "Mi cuenta"; los empleados y clientes tienen además el botón en su página).
- **Plantillas provisionales:** HTML sencillo; la Fase 3 las integrará en el sistema de diseño. No existe aún la página de inicio (`/` responde 404).
- **El admin** no muestra el perfil del cliente (dirección, fecha de nacimiento): no hace falta y se minimiza la exposición. Gestión de clientes en la Fase 9.

## 11. Seguridad y privacidad

- Validación completa en servidor, en servicios reutilizables. Los formularios solo adelantan los mismos validadores para mostrar todos los errores de una vez.
- Sin asignación masiva: formularios con campos explícitos; `update_customer_profile` rechaza campos fuera de su lista blanca.
- Tokens con `secrets`; solo se guarda su hash SHA-256; un solo uso, caducidad y revocación; confirmación por `POST`; sin 404 con el token en la URL; enlaces construidos con `SITE_BASE_URL` (evita la inyección de la cabecera `Host`).
- Anti-enumeración en registro, reenvío público, recuperación de contraseña, cambio de email y login (mensaje genérico).
- Límites: login (por email y por IP), formularios públicos por IP, reenvíos por cuenta (en BD), aviso de cuenta existente (1 al día).
- `next` del login validado por Django (sin redirecciones abiertas). Logout solo por `POST`.
- Auditoría sin datos personales: perfil (solo nombres de campos), cambios de email (sin direcciones) y activaciones de cuentas.
- Logs: los errores de email no incluyen destinatarios ni enlaces.
- La fecha de nacimiento completa solo aparece en el formulario del propio cliente.
- Tests con datos ficticios (`example.com`, móviles `600 000 00x`).

## 12. Tests y resultados reales

Nuevos o ampliados en `tests/accounts/`:
- `test_registration.py`: registro válido, campos obligatorios, dirección incompleta, dirección internacional, país y código postal inválidos, email inválido y duplicado (también sin distinguir mayúsculas y sin revelarlo), contraseñas débiles o distintas, fecha futura, imposible, inverosímil o de un menor, 29 de febrero, teléfono opcional, internacional e inválido, preferencias por defecto y su historial, SMS sin teléfono, registro solo como cliente (rol, flags y verificación ignorados), CSRF, secciones y marcas del formulario.
- `test_email_verification.py`: token válido, inválido, caducado, usado y revocado; TTL; carrera de consumo simultáneo; token de un email ya cambiado; cuenta inactiva; límites de reenvío (intervalo, diario, ventana); reenvío público anti-enumeración y desde la sesión; GET que no consume; restricciones de cuentas pendientes; fallo de SMTP sin datos personales en el log.
- `test_profile.py`: edición, lista blanca, obligatorios, teléfono (cambiar o borrar, con retirada del SMS), límite de cambios de fecha de nacimiento, perfiles antiguos, preferencias auditadas, verificación ≠ consentimiento, condiciones para promociones, flujo completo de cambio de email (contraseña, email igual o inválido, ocupado, ocupado antes de confirmar, aviso al email anterior), invariante del email verificado, acceso a perfiles ajenos (IDOR, escalada de rol), empleados y propietarios sin acceso al perfil de cliente.
- `test_auth_views.py`: login sin distinguir mayúsculas, redirección por rol, mensaje genérico, cuenta inactiva, bloqueo por intentos, redirección abierta bloqueada, logout por POST, recuperación de contraseña (anti-enumeración, enlace con `SITE_BASE_URL`, un solo uso), cambio de contraseña.
- `test_validators.py`: teléfono, códigos postales, límites de la fecha de nacimiento, edad con 29 de febrero, utilidades de cumpleaños.
- `test_admin.py` (ampliado): activar y desactivar con auditoría, desactivación desde el formulario, pérdida de acceso, último propietario, edición de email en el admin que anula la verificación, historial de solo lectura.
- `tests/core/test_audit_and_settings.py` (ampliado): producción exige `EMAIL_HOST`, rechaza backends simulados y exige `SITE_BASE_URL` https.

| Comando (SQLite, Python 3.14.2, Django 5.2.18, phonenumbers 9.0.41) | Resultado |
|---|---|
| `python manage.py check` | Sin incidencias |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| `python manage.py test --settings=config.settings.test` | **203 tests, OK** |
| `migrate` → `migrate accounts 0003` + `migrate core 0001` → `migrate` (SQLite temporal) | OK |
| `python manage.py migrate` (`db.sqlite3` local) | 4 migraciones aplicadas |
| `check --deploy --settings=config.settings.prod` (variables ficticias) | `W009` (por la clave ficticia de la prueba) y `W021` (HSTS preload, intencionado) |
| Prueba manual con `runserver` y `curl`: registro → email en consola → GET (no consume) → POST (confirmado) → segundo POST ("ya se ha utilizado") | OK con `PYTHONUTF8=1` (sin él, la consola de Windows falló al imprimir el email; ver §6) |

## 13. Archivos creados o modificados

- **Modelos y migraciones:** `apps/accounts/models.py`, `apps/accounts/migrations/0004–0006`, `apps/core/models.py`, `apps/core/migrations/0002`.
- **Dominio:** `apps/accounts/services.py` (registro, tokens, perfil, preferencias, `set_user_active`, comprobaciones de promociones), `validators.py`, `countries.py`, `birthdays.py`, `emails.py`, `permissions.py` (`verified_email_required`), `apps/core/throttling.py`.
- **Web:** `apps/accounts/forms.py`, `views.py`, `urls.py`, `admin.py`; `config/urls.py` (`/cuenta/`).
- **Plantillas:** `templates/base.html`, `templates/accounts/*.html`, `templates/emails/*.txt`; `static/css/base.css`.
- **Configuración:** `config/settings/base.py`, `dev.py`, `prod.py`, `.env.example`, `requirements/base.txt` (`phonenumbers`).
- **Tests:** ver §12.
- **Documentación:** este documento, `plan-de-fases.md` (reordenación), `arquitectura.md`, `README.md`.

### Rutas (`/cuenta/…`)
`registro/`, `registro/enviado/`, `verificar-email/<token>/`, `verificar-email/reenviar/`, `verificar-email/reenviar-mio/` (POST), `entrar/`, `salir/` (POST), `perfil/`, `perfil/preferencias/` (POST), `perfil/email/`, `perfil/contrasena/`, `contrasena/recuperar/`, `contrasena/recuperar/enviado/`, `contrasena/restablecer/<uidb64>/<token>/`, `contrasena/restablecida/`, y `""` (redirección según el rol).

## 14. Estado de los criterios de aceptación

| Criterio | Estado |
|---|---|
| Registro con todos los campos obligatorios, en secciones A–D, con obligatorios y teléfono opcional marcados | Completo |
| Datos estructurados, direcciones internacionales, email normalizado, sin usar el email como identificador | Completo |
| Verificación: cuenta pendiente, token seguro con caducidad y un solo uso, reenvío limitado, verificación solo en servidor | Completo |
| Cuentas pendientes sin operaciones que exigen verificación (documentado y con decorador y servicio) | Completo (lo aplicarán las fases 5–8) |
| Correo por variables de entorno; consola en desarrollo; sin simulación en producción | Completo (SMTP real no probado) |
| Fecha de nacimiento validada, `DateField`, 29 de febrero, no expuesta fuera del perfil | Completo |
| Teléfono opcional validado, normalizado, internacional, editable, no verificado | Completo |
| Preferencias separadas, desactivadas por defecto, auditables y editables | Completo |
| Roles: registro solo `CUSTOMER`; el propietario autoriza o desactiva empleados | Completo |
| Perfil editable; cambio de email con nueva verificación | Completo |
| Servicios reutilizables por la futura API; operaciones documentadas | Completo |
| Tests pedidos ejecutados | Completo (SQLite) |
| Validación en PostgreSQL | Pendiente |

## 15. Dependencias para la fase siguiente

Fase 3 (sistema de diseño y web pública): CLI standalone de Tailwind, textos reales del negocio y política de privacidad aportados por el propietario, recursos de `static/img/brand/`, y migrar `templates/base.html` y `templates/accounts/` al sistema de diseño. Antes de producción conviene confirmar la edad mínima y decidir la política de conservación de datos.
