# Guía para el desarrollador de la app Flutter

Cómo consumir la API v1 de Caneca Furada desde la futura app móvil (iOS y Android). La app **no** se ha desarrollado todavía; esta guía fija el contrato y las buenas prácticas.

- Referencia completa de endpoints, esquemas y parámetros: [docs/api/openapi.yaml](api/openapi.yaml) (puede generarse un cliente Dart con `openapi-generator`), o `/api/v1/docs/` en el servidor (en desarrollo sin sesión; en producción solo el propietario).
- Decisiones de diseño y seguridad: [fase-11-api-auditoria.md](fase-11-api-auditoria.md).
- Todos los ejemplos usan datos ficticios.

## 1. Conceptos básicos

| Tema | Regla |
|---|---|
| URL base | `https://<dominio>/api/v1/` (en desarrollo, `http://10.0.2.2:8000/api/v1/` desde el emulador de Android). Configúrala por *flavor* (dev/prod); nunca la incrustes con credenciales. |
| Formato | Solo JSON: `Content-Type: application/json`. Otros formatos → 415. |
| Autenticación | `Authorization: Bearer <access>`. No uses cookies. |
| Identificadores | `public_id` (UUID). No existen IDs numéricos. |
| Fechas | ISO 8601 con zona: `2026-11-20T21:00:00+01:00`. Envía siempre la zona (una hora sin zona se interpreta en Europe/Madrid). Las fechas sin hora: `AAAA-MM-DD`. |
| Importes | Texto con dos decimales: `"12.50"`. Nunca `double` para dinero (usa `Decimal` del paquete `decimal`). |
| Puntos | Enteros. Los calcula siempre el servidor. |
| Idioma | Los mensajes `detail` vienen en español y se pueden mostrar al usuario. |

## 2. Secretos y almacenamiento

- **La app no contiene ningún secreto del servidor** (ni `SECRET_KEY`, ni claves de firma, ni credenciales SMTP o de SMS). Todo lo que va en el binario se puede extraer.
- Guarda `access` y `refresh` en `flutter_secure_storage` (Keychain / Keystore). Nunca en `SharedPreferences`, ficheros o logs.
- No registres en logs, Crashlytics ni analítica: tokens, contraseñas, el contenido del QR, códigos de canje, email, teléfono, dirección ni fecha de nacimiento.
- Solo HTTPS en producción (ATS en iOS y `usesCleartextTraffic=false` en Android).

## 3. Registro y verificación del email

```http
POST /api/v1/auth/register/
{
  "email": "lua@example.com", "password": "Contrasena-Ficticia-2026",
  "first_name": "Lúa", "last_name": "Ficticia Exemplo", "date_of_birth": "1996-06-15",
  "sex": "UNDISCLOSED", "phone_number": "",
  "country": "ES", "postal_code": "15001", "city": "A Coruña",
  "promo_email_opt_in": false, "promo_sms_opt_in": false
}
→ 202 {"detail": "Si los datos son correctos, te hemos enviado un email…"}
```

- **Dirección (Fase 16):** de la dirección solo es obligatorio `postal_code`. `address_line_1`, `address_line_2` y `province` son opcionales; en España la provincia se deduce del CP y lo que envíes se ignora.
- **Localidad:** pide las del CP con `GET /api/v1/postal-codes/{cp}/localities/` → `{"localities": ["Oleiros"]}`. Con una, márcala sin preguntar; con varias, muestra un desplegable; con lista vacía (o fuera de España), deja un campo de texto **opcional**. Si la lista no está vacía, `city` es obligatoria y debe ser una de ellas (si no, 400 en `city`). Datos: GeoNames (CC BY 4.0); cítalo en la pantalla o en «Acerca de».
- **Sexo:** `sex` obligatorio, uno de `MALE`, `FEMALE` o `UNDISCLOSED` («Prefiero no decirlo»).
- **Edad:** si el usuario es menor de 18, `date_of_birth` devuelve «Para rexistrarte tes que ser maior de idade.» (o el texto en castellano, según `Accept-Language`). Puedes avisar antes en la app, pero decide el servidor.

- Responde **siempre 202 igual** aunque el email ya exista (no revela cuentas). Errores de datos → 400 con `fields`.
- Los consentimientos promocionales van **desmarcados por defecto**; muéstralos como casillas opcionales y separadas.
- El usuario recibe un enlace `https://<dominio>/cuenta/verificar-email/<token>/`. Opciones:
  1. Abrirlo en el navegador (funciona sin la app).
  2. Con enlaces universales (iOS) / App Links (Android) para `/cuenta/verificar-email/*`, extraer `<token>` y llamar a `POST /api/v1/auth/email/verify/` con `{"token": "<token>"}`. Requiere publicar `apple-app-site-association` y `assetlinks.json` en el dominio (pendiente).
- Reenviar: `POST /auth/email/resend/` (sin sesión, 202 siempre igual) o `POST /me/email/resend-verification/` (con sesión; 429 si se pide demasiado).
- Mientras el email no esté verificado el usuario **puede entrar**, pero puntos, QR, canjes y reservas devuelven 403 `email_not_verified`. Usa `user.email_verified` para mostrar el aviso.

## 4. Inicio de sesión, renovación y cierre

```http
POST /api/v1/auth/login/
{"email": "lua@example.com", "password": "Contrasena-Ficticia-2026"}
→ 200 {
  "access": "eyJ…", "refresh": "eyJ…", "token_type": "Bearer",
  "access_expires_in": 900, "refresh_expires_in": 2592000,
  "user": {"public_id": "…", "email": "lua@example.com", "first_name": "Lúa", "last_name": "Ficticia Exemplo",
           "role": "CUSTOMER", "email_verified": true, "profile_complete": true}
}
```

- 401 `invalid_credentials` (mismo mensaje exista o no la cuenta); 429 `login_throttled` tras varios fallos.
- `role` decide qué pantallas mostrar (`CUSTOMER`, `EMPLOYEE`, `OWNER`), pero **el servidor vuelve a comprobarlo siempre**: ocultar un botón no es seguridad.

**Renovación** (el access dura 15 min):

```http
POST /api/v1/auth/token/refresh/
{"refresh": "eyJ…"}
→ 200 {"access": "…", "refresh": "…", …}
```

- La rotación es obligatoria: **guarda siempre el refresh nuevo** y descarta el anterior (ya no vale).
- Implementa un interceptor (p. ej. en `dio`): ante un 401 de una petición autenticada, renueva **una sola vez** (usa un candado para que varias peticiones simultáneas no renueven a la vez: la segunda renovación con el mismo refresh fallaría) y repite la petición.
- Si la renovación responde 401 `token_not_valid`, borra los tokens y lleva al usuario al login. Pasa cuando el refresh caducó, se cerró la sesión, **la contraseña cambió** o la cuenta se desactivó.
- Un 401 `token_revoked` en cualquier petición significa lo mismo: sesión invalidada.

**Cierre de sesión:**
- Este dispositivo: `POST /auth/logout/` con `{"refresh": "…"}` → 204. Borra después ambos tokens localmente (el access seguiría valiendo ≤ 15 min).
- Todos los dispositivos: `POST /auth/logout-all/` → 204.

## 5. Contraseña y recuperación de la cuenta

- Cambio: `POST /auth/password/change/` con `{"current_password", "new_password"}` → 200 con un **par nuevo**. Guárdalo: todos los tokens anteriores (también de otros dispositivos) quedan invalidados.
- Recuperación: `POST /auth/password/reset/` con `{"email"}` → 202 siempre igual. El email trae `https://<dominio>/cuenta/contrasena/restablecer/<uid>/<token>/`:
  - sin enlaces universales, el usuario termina en la web;
  - con enlaces universales, la app extrae `uid` y `token` y llama a `POST /auth/password/reset/confirm/` con `{"uid", "token", "new_password"}`. Error 400 `invalid_token` si caducó o ya se usó.

## 6. Perfil, preferencias y email

| Operación | Llamada |
|---|---|
| Datos básicos | `GET /me/` (sin dirección, fecha de nacimiento, teléfono ni preferencias) |
| Perfil completo (solo clientes) | `GET /me/profile/` |
| Editar perfil | `PATCH /me/profile/` con **solo** los campos cambiados. `missing_fields` indica obligatorios pendientes. La fecha de nacimiento se cambia como mucho una vez al año. Para borrar el teléfono envía `""` (retira el consentimiento de SMS). |
| Preferencias | `GET`/`PATCH /me/preferences/` con `promo_email_opt_in` y/o `promo_sms_opt_in` (el SMS exige teléfono). |
| Cambiar email | `POST /me/email/change/` con `{"new_email", "password"}` → 202. El email no cambia hasta confirmar el enlace enviado a la nueva dirección (mismo flujo que §3). |

No cachees el perfil completo más allá de la pantalla que lo usa.

## 7. Errores

```json
{"code": "duplicate_pending", "detail": "Ya tienes un código pendiente…", "fields": {"campo": ["mensaje"]}}
```

Decide con `code` (estable), muestra `detail`. Desde la Fase 15, `detail` y las etiquetas de estado (`*_display`) vienen en gallego por defecto. Envía `Accept-Language: es` para recibirlos en castellano; los `code` y los valores de los campos no cambian con el idioma. Algunos mensajes genéricos de DRF (p. ej. falta de credenciales) salen en inglés si se piden en gallego, porque DRF no tiene traducción al gallego. Ver [fase-15-idioma-gallego.md](fase-15-idioma-gallego.md).

Códigos principales:

| HTTP | `code` | Significado |
|---|---|---|
| 400 | `invalid` | Validación del formulario; mira `fields` (`non_field_errors` para los generales). |
| 400 | `idempotency_invalid` | Falta la cabecera `Idempotency-Key` o no es un UUID. |
| 400 | `insufficient_points`, `reward_unavailable`, `out_of_stock` | Canjes. |
| 400 | `event_not_bookable`, `event_not_found`, `too_many_active`, `in_the_past`, `too_early` | Reservas. |
| 400 | `invalid_qr`, `email_not_verified`, `amount_invalid`, `amount_min`, `amount_max`, `amount_decimals` | Personal: compras. |
| 400 | `invalid_code`, `code_expired` | Personal: canjes. |
| 400 | `invalid`, `expired`, `used`, `revoked`, `email_taken`, `invalid_token` | Verificación del email / recuperación. |
| 401 | `not_authenticated`, `token_not_valid`, `token_revoked`, `invalid_credentials` | Sesión. |
| 403 | `permission_denied`, `email_not_verified` | Rol no permitido o email sin verificar. |
| 404 | `not_found` | No existe **o no es tuyo** (no se distingue a propósito). |
| 409 | `idempotency_conflict`, `duplicate_pending`, `code_used`, `code_not_pending`, `already_reserved`, `event_full`, `invalid_transition` | Choca con el estado actual. |
| 415 | `unsupported_media_type` | El cuerpo no es JSON. |
| 429 | `throttled`, `rate_limited`, `login_throttled` | Demasiadas peticiones; respeta `Retry-After` si viene. |

## 8. Paginación

Los listados devuelven `{"count", "next", "previous", "results"}`. Usa `?page=N` (desde 1) y opcionalmente `?page_size=M` (máx. 50). Una página fuera de rango da 404. Para scroll infinito, sigue `next` hasta que sea `null`.

## 9. Idempotencia (operaciones que crean algo)

Canjear (`POST /rewards/{id}/redeem/`), reservar (`POST /me/reservations/`) y registrar una compra (`POST /staff/purchases/`) exigen la cabecera:

```http
Idempotency-Key: 8f14e45f-ceea-467a-9f4e-1a2b3c4d5e6f
```

- Genera un UUID v4 (`uuid` de pub.dev) **cuando el usuario confirma la acción** y guárdalo hasta recibir respuesta.
- Si hay un error de red o un *timeout*, **reintenta con la misma clave**: no se duplica nada y la respuesta será 200 con el mismo objeto (201 la primera vez).
- Para una operación nueva, genera una clave nueva. Reutilizar una clave con otros datos → 409 `idempotency_conflict`.

## 10. Pantallas del cliente

| Pantalla | Llamadas |
|---|---|
| Saldo | `GET /me/points/` → `balance`, `earned`, `used`, `corrected` |
| Movimientos | `GET /me/points/movements/` (paginado) |
| Compras | `GET /me/purchases/` (paginado; `amount` como texto) |
| Mi QR | `GET /me/qr/` → dibuja `payload` (p. ej. con `qr_flutter`, corrección de errores M) y muestra `code` debajo. Sube el brillo de la pantalla al mostrarlo. No lo guardes en caché persistente. `POST /me/qr/rotate/` lo renueva (máx. 5/día). |
| Recompensas | `GET /rewards/` (público), `GET /rewards/{id}/` |
| Canjear | `POST /rewards/{id}/redeem/` + `Idempotency-Key` → canje con `code` y `qr_payload` (`CFR1:…`) |
| Mis canjes | `GET /me/redemptions/` (sin códigos), `GET /me/redemptions/{id}/` (código solo si está pendiente y vigente), `POST /me/redemptions/{id}/cancel/` |
| Eventos | `GET /events/` (público), `GET /events/{id}/` (`bookable`, `seats_left`) |
| Reservar | `POST /me/reservations/` + `Idempotency-Key`: `{"event": "<public_id>", "party_size": 2, "notes": ""}` o `{"requested_for": "2026-11-20T21:00:00+01:00", "party_size": 4}`. Queda `PENDING` hasta que el local la confirme (el cliente recibe un email). |
| Mis reservas | `GET /me/reservations/`, `GET /me/reservations/{id}/` (`can_cancel`), `POST /me/reservations/{id}/cancel/` |

## 11. Funciones del personal (si se hace una app de empleados)

Requieren rol `EMPLOYEE` u `OWNER`. Los códigos van siempre en el cuerpo del `POST`, nunca en la URL.

1. Escanear el QR del cliente → `POST /staff/purchases/identify/` `{"qr_code": "CF1:…"}` → `{"display_name": "Lúa F."}`. Pide al empleado que confirme el nombre.
2. `POST /staff/purchases/` + `Idempotency-Key` `{"qr_code": "CF1:…", "amount": "12.50"}` → compra con los puntos calculados.
3. Canjes: `POST /staff/redemptions/lookup/` `{"code": "CFR1:…"}` para ver el estado y `POST /staff/redemptions/validate/` para entregarlo (solo una validación tiene éxito; la segunda da 409 `code_used`).

Demasiados códigos no válidos seguidos → 429 durante unos minutos. Del cliente solo se recibe el nombre corto.

El propietario dispone además de `GET /owner/stats/?date_from=&date_to=` y de la gestión de reservas (`GET /owner/reservations/`, `POST /owner/reservations/{id}/{confirm|reject|cancel|complete}/`). El resto de la gestión se hace en el dashboard web.

## 12. Lista de comprobación antes de publicar la app

- [ ] Ningún secreto del servidor en el código ni en los recursos.
- [ ] Tokens en almacenamiento seguro; borrado al cerrar sesión y ante `token_not_valid`/`token_revoked`.
- [ ] Interceptor de renovación con candado y rotación del refresh.
- [ ] `Idempotency-Key` reutilizada en los reintentos.
- [ ] Sin datos personales, tokens, QR ni códigos en logs, analítica o informes de errores.
- [ ] Solo HTTPS en producción.
- [ ] Enlaces universales / App Links publicados para verificación y recuperación (si se usan).
- [ ] Textos legales (privacidad, condiciones del programa) aportados por el propietario.
- [ ] Probado contra un servidor con PostgreSQL y SMTP reales.
