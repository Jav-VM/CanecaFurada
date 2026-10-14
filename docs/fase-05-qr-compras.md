# Fase 5 — QR personal y registro de compras manuales

**Estado:** Completa (pendiente de validar la concurrencia en PostgreSQL y el escaneo en dispositivos físicos; ver §11).
**Fecha:** 2026-10-14.
**Depende de:** [Fase 2](fase-02-registro-perfil-verificacion.md) (clientes, verificación de email, permisos) y [Fase 3](fase-03-sistema-diseno-web-publica.md) (sistema de diseño).

## 1. Objetivo y decisiones previas

Dar a cada cliente un QR personal que lo identifica sin contener datos personales, y permitir que el personal lo escanee desde el navegador y registre manualmente el importe de una compra con todas las validaciones en el servidor.

Contradicción detectada y resuelta por el usuario antes de empezar:

| Cuestión | Decisión |
|---|---|
| El prompt de la fase pide **QR + registro de compras** y no menciona los puntos; el [plan](plan-de-fases.md) situaba en la Fase 5 el **ledger de puntos + QR** y en la Fase 6 el **registro de compras** | **Seguir el prompt.** Esta fase hace QR, escaneo y compras sin puntos. El ledger de puntos pasa a la Fase 6 y la compra deja preparado el punto de extensión (`on_purchase_registered`) donde se generarán los puntos en la misma transacción. Plan reordenado. |
| Lector de QR en el navegador | **Lector nativo + jsQR local.** `BarcodeDetector` si el navegador lo trae (Chrome/Edge en Android y escritorio); si no (Safari/iPhone, Firefox), jsQR 1.4.0 servido desde el propio sitio con checksum fijado. Siempre se puede teclear el código. |
| Quién registra compras | **Empleados y propietarios.** Los clientes nunca. |

Decisiones menores (con su motivo):

- **Dependencias:** `segno` (Python puro, sin dependencias, BSD) para dibujar el QR en el servidor como SVG, sin servicios de terceros. jsQR (Apache-2.0) se guarda en `static/vendor/jsqr/` con su licencia: se descargó de npm, se verificó su hash de integridad SHA-512 publicado por npm y se fija su SHA-256 en un test. No llama a la red ni usa `eval`.
- **Apps según el mapa de módulos:** `apps.loyalty` (QR) y `apps.purchases` (compras y panel del personal).
- **Se exige email verificado** al cliente para mostrar su QR y para sumarle compras, como se acordó en la Fase 2 ("mostrar el QR" y "acumular" requieren verificación).
- **Rotación del QR** (estaba en el plan): el cliente puede renovarlo si cree que alguien lo ha copiado; máximo 5 al día.
- **Importe máximo** por compra: 1000 €, configurable (`PURCHASES_MAX_AMOUNT`). Evita errores de tecleo como "1250" en lugar de "12,50".
- **El token se guarda en claro** (no como hash) porque hay que poder volver a dibujar el QR. Como solo identifica y no autoriza nada, el riesgo es bajo; se compensa con no escribirlo nunca en logs, auditoría ni URLs y con la rotación.

## 2. Alcance y exclusiones

**Incluye:** token QR aleatorio y opaco, vista "Mi código QR" del cliente con renovación, panel del personal (`/panel/compras/`) con escaneo por cámara o código tecleado, confirmación con datos mínimos, registro transaccional e idempotente de la compra, resultado y últimos registros propios, consulta de compras en el admin (solo lectura, propietario), límites de intentos, tests y documentación.

**Excluye:** puntos, saldo y ledger (Fase 6 tras la reordenación); anulación de compras (el estado `VOIDED` existe, pero no hay flujo); integración real con TPV (solo preparada, §8); API REST (Fase 11, §9); estadísticas (Fase 9).

## 3. Modelo de datos

### `loyalty.CustomerQRCode`

| Campo | Notas |
|---|---|
| `user` | `OneToOne` con el cliente |
| `token` | 32 caracteres base32 (`A-Z2-7`) = 160 bits de `secrets.token_bytes`. Único. `CHECK` de formato en BD |
| `rotated_at` | Última renovación |

Contenido del QR: `CF1:<token>`. El prefijo indica la versión del formato y permite descartar QR ajenos sin consultar la BD. **No contiene** nombre, apellidos, email, dirección, teléfono, fecha de nacimiento, saldo ni identificadores internos (hay tests que lo comprueban). `__str__` no muestra el token y el modelo no está en el admin.

### `purchases.Purchase`

| Campo pedido | Campo | Notas |
|---|---|---|
| Identificador único | `public_id` | UUID; el `id` interno no sale del backend |
| Cliente | `customer` | `PROTECT` |
| Empleado | `registered_by` | `PROTECT`; empleado o propietario |
| Importe | `amount` | `DecimalField(8, 2)`; `CHECK amount >= 0.01` |
| Fecha y hora | `created_at` | La fija el servidor |
| Origen | `source` | `MANUAL` (panel) o `POS` (reservado, deshabilitado) |
| Estado | `status` | `COMPLETED` (registrada) o `VOIDED` (reservado para anulaciones) |
| Referencia de idempotencia | `idempotency_key` | UUID **único** en BD |
| — | `external_reference` | Reservado para el ticket del TPV; único por origen cuando no está vacío |

Otras restricciones en BD: origen y estado válidos y `customer ≠ registered_by`. Las compras no se editan ni se borran (admin de solo lectura).

## 4. Flujo y validaciones

```
Cliente: /cuenta/mi-qr/  →  muestra el QR (y el código en texto)
Personal: /panel/compras/  →  escanea o teclea  →  POST /identificar/
          → confirmación: «Lúa F.» + importe  →  POST /registrar/
          → redirección a /panel/compras/<public_id>/ (resultado)
```

`apps/purchases/services.py`:

1. **`identify_for_purchase(staff, qr_code)`** comprueba el personal, el límite de intentos y el QR, y devuelve **solo** el nombre y la inicial del apellido ("Lúa F."). Nunca devuelve el email, la dirección, el teléfono ni la fecha de nacimiento.
2. **`register_purchase(staff, qr_code, amount, idempotency_key, source="MANUAL")`** valida, en este orden:
   - **Personal autenticado, activo y con permiso** (`OWNER` o `EMPLOYEE`); si no, `PermissionDenied`.
   - **Origen habilitado** (`PURCHASES_ENABLED_SOURCES`; el TPV no lo está).
   - **Importe:** número finito, con un máximo de 2 decimales, entre 0,01 € y `PURCHASES_MAX_AMOUNT`. Acepta "12,50" y "12.50", y nunca hace cálculos con `float`.
   - **Referencia de idempotencia:** un UUID válido.
   - **Límite de códigos no válidos** por miembro del personal: 20 en 15 minutos.
   - **Dentro de una transacción:**
     - Si la referencia ya existe (fila bloqueada), se trata como **reintento**. Devuelve la misma compra si coinciden personal, cliente, importe y origen y la compra sigue `COMPLETED`. Si los datos son otros, da error `idempotency_conflict`; si la compra ya no está vigente, `operation_not_completed`.
     - Se **vuelve a comprobar el QR y el estado del cliente** con su fila bloqueada: cliente activo, rol `CUSTOMER` y email verificado.
     - Se crea la compra. Si otra petición con la misma referencia gana la carrera, la restricción única da `IntegrityError`, se recupera la compra existente y se aplica la misma comprobación de reintento.
     - `on_purchase_registered(purchase)` es hoy un punto de extensión vacío. Cualquier fallo en él deshace la compra (hay un test).

La referencia de idempotencia **la genera el servidor** al mostrar la confirmación (un UUID nuevo cada vez) y viaja en un campo oculto. Un doble clic, recargar la página o reenviar el formulario no crea otra compra; la web avisa con "Esta compra ya estaba registrada. No se ha duplicado". Además, en el navegador el botón se desactiva al enviar (Fase 3).

Mensajes de error, siempre sin datos personales:

| Caso | Mensaje |
|---|---|
| Código inexistente, mal formado, de un no cliente o de una cuenta inactiva | "El código no es válido o la cuenta no está activa." (el mismo mensaje en todos los casos) |
| Email del cliente sin verificar | "El cliente tiene que verificar su email antes de poder sumar compras." |
| Demasiados códigos no válidos | "Demasiados códigos no válidos seguidos. Espera unos minutos…" (HTTP 429) |
| Importe | "Introduce un importe válido…", "…como máximo dos decimales", "…mayor que cero", "…supera el máximo permitido (1000.00 €)" |

## 5. Cómo probar el flujo de compra

### Preparación (desarrollo)

```powershell
pip install -r requirements/dev.txt
python manage.py migrate
python manage.py create_owner        # si aún no hay propietario
python manage.py runserver
```

1. **Crea un empleado:** como propietario, en el admin → Usuarios → Añadir (rol Empleado, datos ficticios).
2. **Crea un cliente:** regístrate en `/cuenta/registro/` con datos ficticios (p. ej. `cliente@example.com`). El enlace de verificación aparece en la consola de `runserver`; ábrelo para verificar el email. En Windows, si da `UnicodeEncodeError`, arranca con `$env:PYTHONUTF8=1`.
3. **QR del cliente:** con la sesión del cliente, entra en Mi perfil → *Mi código QR* (`/cuenta/mi-qr/`). Verás el QR y el código en grupos de 4 caracteres.
4. **Registrar la compra:** en otra ventana (privada u otro navegador), entra como empleado. *Mi cuenta* → *Registrar compra* (`/panel/compras/`):
   - **Con cámara:** "Abrir la cámara" y apunta al QR que se ve en la pantalla del cliente (o en el móvil). La cámara solo funciona en `localhost` o con HTTPS.
   - **Sin cámara:** copia en *Código del cliente* el código que aparece bajo el QR (con o sin espacios).
   - Comprueba que aparece "Lúa F." (o el nombre ficticio que pusieras), escribe el importe (`12,50`) y pulsa *Registrar compra*.
5. **Resultado:** verás el importe, la fecha y hora, el origen, el estado y el identificador. En la página del escáner aparece en *Tus últimos registros*. El propietario la ve en el admin → Compras (solo lectura).

### Casos para comprobar a mano

| Prueba | Resultado esperado |
|---|---|
| Recargar la página de confirmación después de registrar (reenviar el formulario) | No se duplica: "Esta compra ya estaba registrada" |
| Importe `0`, `-3`, `1,234` o `5000` | Error en el importe; no se registra |
| Código inventado (`AAAA…`) | Error genérico sin datos del cliente |
| El cliente pulsa *Renovar mi código* y se reutiliza el código anterior | Error genérico |
| El propietario desactiva al cliente entre la identificación y el registro | Error genérico; no se registra |
| Un cliente abre `/panel/compras/` | 403 |
| Otro empleado abre la URL del resultado | 404 |

## 6. Seguridad y privacidad

- **El QR identifica, no autoriza:** registrar una compra exige una sesión de personal y todas las comprobaciones de §4. Con el código de un cliente, alguien sin cuenta de personal no puede hacer nada, y un cliente no puede sumarse compras a sí mismo.
- **Token no predecible:** 160 bits de `secrets`. Enumerarlo es inviable y además está limitado por intentos y por personal.
- **Sin el token en logs:** los logs solo registran el `public_id` de la compra y del personal (comprobado con `assertLogs` y en la prueba manual). El token tampoco va en `AuditEvent`, en `__str__` ni en el admin.
- **Nunca en la URL:** el código viaja por `POST` (lo que lee la cámara también); la redirección tras registrar usa el `public_id` de la compra. Así no queda en los logs de acceso del servidor ni en el historial del navegador.
- **Sin caché:** el QR del cliente y las páginas del panel se sirven con `Cache-Control: no-cache, no-store` (`never_cache`).
- **Datos mínimos en el flujo:** el personal solo ve "Nombre I.". No se muestran la dirección, la fecha de nacimiento, el teléfono ni el email (hay tests en la confirmación, el resultado y los errores).
- **Autorización por objeto (IDOR):** un empleado solo ve sus compras; las de otros dan 404 para no revelar si existen. El propietario las ve todas.
- **Asignación masiva:** cliente, personal, origen, estado y fecha los fija el servidor; los campos añadidos al `POST` se ignoran (hay un test).
- **CSRF** en todos los formularios; `GET` en las acciones da 405.
- **Cámara:** `getUserMedia` solo funciona en contexto seguro (HTTPS o `localhost`) y con permiso del usuario. La imagen se procesa en el navegador; ni el vídeo ni los fotogramas se envían al servidor. Solo se envía el texto leído.
- **jsQR** se sirve desde el propio dominio (sin CDN), con versión y checksum fijados.

## 7. Configuración

- **Dependencias nuevas:** `segno>=1.6,<2`; jsQR 1.4.0 incluido en `static/vendor/jsqr/` (no se instala nada con npm).
- **Migraciones:** `loyalty/0001_initial`, `purchases/0001_initial` (tablas nuevas) y `core/0004_audit_actions_phase5` (añade la acción `QR_ROTATED` a los `choices`; no toca datos). Son aditivas y reversibles. Ejecuta `python manage.py migrate`.
- **Settings nuevos** en `base.py` (no son variables de entorno): `LOYALTY_QR_MAX_ROTATIONS_PER_DAY` (5), `PURCHASES_MAX_AMOUNT` (1000.00), `PURCHASES_ENABLED_SOURCES` (`("MANUAL",)`), `PURCHASES_MAX_QR_FAILURES` (20) y `PURCHASES_QR_FAILURE_WINDOW_SECONDS` (900).
- **Rutas nuevas:** `/cuenta/mi-qr/` y `/cuenta/mi-qr/renovar/` (cliente); `/panel/compras/`, `/panel/compras/identificar/`, `/panel/compras/registrar/` y `/panel/compras/<public_id>/` (personal).
- Los límites de intentos usan la caché: en producción con varios procesos hace falta una caché compartida (`CACHE_URL`), como ya se indicó en la Fase 2.
- En producción la cámara exige **HTTPS**.

## 8. Preparación para el TPV (sin simularlo)

Ya existe:
- El origen `POS` en el modelo, **deshabilitado**: `register_purchase(source="POS")` da error `source_disabled` mientras no esté en `PURCHASES_ENABLED_SOURCES`.
- `external_reference` con restricción única por origen, para el número de ticket del TPV.
- La idempotencia por UUID único, que el TPV podrá usar para reintentar sin duplicar.

Cuando haya un TPV real habrá que:
1. Autenticar el dispositivo o la integración, no a una persona: por ejemplo, un usuario técnico con permiso específico o un token de dispositivo revocable. Esto lo decidirá la fase correspondiente.
2. Añadir `"POS"` a `PURCHASES_ENABLED_SOURCES` y que el servicio acepte `external_reference` (el identificador del ticket) cuando el origen sea `POS`.
3. Elegir cómo se asocia el cliente: escaneando el QR en el propio TPV o con el flujo actual.
4. Usar la referencia del ticket o un UUID estable como `idempotency_key`.

## 9. Preparación para la app y la API (Fase 11)

Toda la lógica está en servicios que no dependen de la petición ni de las plantillas; la API debe limitarse a llamarlos.

| Endpoint propuesto | Quién | Servicio | Respuesta |
|---|---|---|---|
| `GET /api/v1/me/qr/` | Cliente verificado | `loyalty.get_customer_qr` | `{"payload": "CF1:…", "code": "XXXX XXXX …"}`; la app dibuja el QR |
| `POST /api/v1/me/qr/rotate/` | Cliente verificado | `loyalty.rotate_customer_qr` | Igual; 429 si `RotationRateLimited` |
| `POST /api/v1/staff/purchases/identify/` | Personal | `purchases.identify_for_purchase` | `{"display_name": "Lúa F."}` |
| `POST /api/v1/staff/purchases/` | Personal | `purchases.register_purchase` | 201 al crear y 200 en un reintento idempotente, con `public_id`, `amount` (cadena "12.50"), `created_at`, `source`, `status` |
| `GET /api/v1/staff/purchases/{public_id}/` | Personal | `purchases.visible_purchases` | 404 si no es suya (salvo propietario) |

Pautas:
- La **referencia de idempotencia** en la API llega en la cabecera `Idempotency-Key` (un UUID generado por la app por cada intento de compra, reutilizado en los reintentos), en lugar del campo oculto de la web.
- El código QR va en el cuerpo del `POST`, nunca en la URL ni en parámetros `GET`.
- Traducción de errores: `PermissionDenied` → 403; `InvalidQRCode`/`CustomerNotEligible` y demás `ValidationError` → 400 con `code` (`invalid_qr`, `email_not_verified`, `amount_*`, `idempotency_conflict`…); `idempotency_conflict` puede devolverse como 409; `TooManyFailedAttempts` → 429.
- Serializadores con campos explícitos; nunca exponer `customer.email` ni otros datos personales en el flujo del personal. El `token` solo lo ve su dueño.
- Throttling de DRF además del límite propio del servicio.

## 10. Archivos creados o modificados

- **`apps/loyalty/` (nueva):** `apps.py`, `models.py`, `services.py`, `views.py`, `urls.py`, `migrations/0001_initial.py`.
- **`apps/purchases/` (nueva):** `apps.py`, `models.py`, `services.py`, `forms.py`, `views.py`, `urls.py`, `admin.py`, `migrations/0001_initial.py`.
- **Core:** `apps/core/models.py` (`QR_ROTATED`) y `migrations/0004_audit_actions_phase5.py`.
- **Configuración:** `config/settings/base.py` (apps y límites), `config/urls.py` (rutas), `requirements/base.txt` (segno).
- **Plantillas:** `templates/loyalty/my_qr.html`, `templates/purchases/scan.html`, `confirm.html` y `detail.html`; `templates/base.html` (bloque `extra_scripts`); `templates/accounts/profile.html` (enlace "Mi código QR") y `templates/accounts/staff_home.html` (botón "Registrar compra").
- **Estáticos:** `static/js/qr-scanner.js`, `static/vendor/jsqr/jsQR.js` y `LICENSE`, `static/css/app.css` recompilado.
- **Tests:** `tests/loyalty/` (`factories.py`, `test_qr.py`) y `tests/purchases/` (`test_services.py`, `test_views.py`).
- **Documentación:** este documento, `README.md`, `plan-de-fases.md`, `arquitectura.md`.

## 11. Tests y resultados reales

Nuevos (72):
- **QR** (`tests/loyalty/test_qr.py`, 22): token aleatorio con formato base32; el contenido del QR no tiene datos personales, saldo ni identificadores; normalización de lo leído o tecleado y rechazo de códigos mal formados; máscara; `__str__` sin token; creación única; solo clientes activos verificados; la renovación invalida el código anterior y se audita sin el token; límite de renovaciones; código válido, inválido, inactivo y de un no cliente con el mismo error genérico; email sin verificar; errores sin datos personales; nombre mínimo; vista con login, 403 para cliente sin verificar y para personal, QR construido solo con el token, sin caché; renovación solo por `POST` y con CSRF.
- **Servicio de compras** (`tests/purchases/test_services.py`, 25): registro de todos los campos pedidos; el propietario también registra; código leído o tecleado; identificación con datos mínimos; permisos (anónimo, `None`, cliente, empleado inactivo); TPV deshabilitado; QR inválido, rotado, de un cliente inactivo o sin verificar; límite de fallos por miembro del personal; logs sin token ni datos personales; importes no válidos (0, negativo, texto, vacío, `None`, NaN, infinito, 3 decimales, por encima del máximo) y normalización; `CHECK` de importe y de autorregistro en BD; doble envío; referencia reutilizada con otros datos (importe, personal, cliente); reintento de una operación anulada; referencia no válida; carrera simulada con la restricción única; fallos transaccionales (después del `INSERT` y durante él) sin compra residual; reintento tras un fallo; visibilidad por rol.
- **Vistas** (`tests/purchases/test_views.py`, 25): acceso de anónimos, clientes, empleados y propietarios; `POST` y CSRF obligatorios; confirmación con "Lúa F." y sin email, dirección, teléfono ni fecha de nacimiento; referencia nueva en cada confirmación; errores genéricos; flujo completo con redirección por `public_id` (sin el token en la URL); doble envío; importe no válido; referencia manipulada; asignación masiva ignorada; cliente desactivado entre pasos; últimos registros solo propios; detalle con 404 para otro empleado, acceso del propietario y 403 para el cliente; admin de solo lectura; QR fuera del admin; checksum de jsQR; el script del lector no hace peticiones de red.

| Comando o prueba (SQLite, Python 3.14.2, Django 5.2.18, segno 1.6.6) | Resultado |
|---|---|
| `python manage.py check` | Sin incidencias |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| `python manage.py test --settings=config.settings.test` | **374 tests, OK** (302 anteriores + 72 nuevos) |
| `check --deploy --settings=config.settings.prod` (variables ficticias) | Solo `W021` (HSTS preload, intencionado, ya existente) |
| `python scripts/tailwind.py build` | OK |
| Descarga de jsQR 1.4.0 desde npm | El hash SHA-512 coincide con el `integrity` publicado |
| Decodificación del QR generado por segno con el jsQR incluido (Edge headless) | Leído exactamente: `CF1:<token>` |
| Flujo real con una BD temporal (fuera del repositorio): QR del cliente → identificar → registrar → resultado → código no válido; capturas a 500 px | Correcto. Los logs muestran solo los `public_id` de la compra y del personal |

**No probado:** la cámara real (`getUserMedia` necesita un dispositivo y un permiso que el modo headless no tiene), el lector nativo en Android, jsQR en Safari/iPhone y la concurrencia real con bloqueos de fila (en SQLite `select_for_update` no bloquea; la carrera se probó simulando el `IntegrityError`).

## 12. Limitaciones, riesgos y pendientes

- **Escaneo en dispositivos reales** sin probar. Conviene probarlo en el móvil del personal (Android/Chrome y iPhone/Safari) en un entorno con HTTPS antes de usarlo en el local.
- **Concurrencia en PostgreSQL** sin probar (Fase 12): la restricción única garantiza que no haya duplicados, pero el comportamiento de los bloqueos se debe verificar allí.
- **El QR en una captura de pantalla** se puede compartir. Como solo identifica, el riesgo es que alguien sume compras a otra persona con la complicidad del personal; se mitiga con la confirmación del nombre en barra y con la renovación.
- **Límites de intentos en caché por proceso** hasta configurar una caché compartida.
- **Sin anulaciones:** si el personal se equivoca de importe, todavía no hay flujo para anular (estado `VOIDED` reservado). Pendiente de decidir en qué fase.
- **No es facturación:** las compras son lo que el personal anota, no la caja del local (como indica el plan para la Fase 9).
- **Pantalla del cliente:** el brillo y el tamaño del móvil afectan a la lectura. El código en texto es la alternativa.

## 13. Estado de los criterios de aceptación

| Criterio | Estado |
|---|---|
| Token aleatorio, opaco y no predecible por cliente | Completo |
| El QR no contiene nombre, apellidos, email, dirección, teléfono, fecha de nacimiento ni saldo | Completo (con tests) |
| El QR identifica pero no autoriza por sí solo | Completo |
| El personal autenticado escanea desde el navegador | Completo (cámara: nativo + jsQR; sin probar en dispositivos físicos) |
| Solo los datos necesarios para confirmar la identidad, sin dirección, fecha de nacimiento ni teléfono | Completo (con tests) |
| Importe introducido manualmente | Completo |
| El backend valida personal, permisos, cliente activo, QR, importe, idempotencia y estado | Completo |
| Se registran cliente, empleado, importe, fecha y hora, identificador, origen, estado y referencia de idempotencia | Completo |
| Transacciones y sin duplicados | Completo (restricción única + transacción; concurrencia real pendiente de PostgreSQL) |
| TPV preparado sin simularlo | Completo (§8) |
| Token fuera de los logs y errores sin datos personales | Completo (con tests) |
| Lógica en servicios y API documentada | Completo (§9) |
| Pruebas de QR válido e inválido, permisos, importe, duplicados, cliente inactivo y fallos transaccionales | Completo (72 tests) |

## 14. Dependencias para la fase siguiente (Fase 6 — Ledger de puntos)

- Generar los puntos en `apps.purchases.services.on_purchase_registered`, dentro de la misma transacción que la compra, con un movimiento por compra (restricción única sobre la compra) para heredar la idempotencia.
- Mostrar el saldo y el historial en la vista del cliente, nunca en el QR.
- Las anulaciones de compras (si se aprueban) deberán generar movimientos compensatorios en lugar de borrar.
