# Fase 6 — Fidelización: ledger de puntos, promociones y base de cumpleaños

**Estado:** Completa (pendiente de validar la concurrencia en PostgreSQL; ver §11).
**Fecha:** 2026-10-14.
**Depende de:** [Fase 5](fase-05-qr-compras.md) (compras manuales y QR) y [Fase 2](fase-02-registro-perfil-verificacion.md) (perfil, fecha de nacimiento y consentimientos).

## 1. Objetivo y decisiones previas

Crear un programa de fidelización auditable: cada compra registrada genera puntos en un ledger inmutable, en la misma transacción que la compra, con una conversión configurable y promociones configurables (incluida la base de las de cumpleaños).

Contradicciones detectadas y resueltas por el usuario antes de empezar:

| Cuestión | Decisión |
|---|---|
| El [plan](plan-de-fases.md) situaba las promociones de cumpleaños en la Fase 10 y las estadísticas en la Fase 9; el prompt de la Fase 6 pide la base de promociones y cumpleaños y distinguir compras registradas de facturación | **Seguir el prompt.** Esta fase hace el sistema de promociones, la base de cumpleaños (detección, elegibilidad, anti-duplicados, consentimiento) **sin envíos**, y un servicio mínimo de estadísticas. La Fase 10 queda para los envíos y notificaciones, y la Fase 9 para el dashboard. Plan actualizado. |
| El prompt habla de "fecha de nacimiento **verificada**", pero no existe ningún mecanismo que la verifique (solo se valida y se limita su cambio a uno cada 365 días) | **Validada + anti-abuso.** Se usa la fecha del perfil, se exige que no haya cambiado en los últimos 30 días y se permite como máximo una promoción de cumpleaños por cliente y año (restricción única en BD). Sin campos nuevos en el perfil. |
| Las recompensas y canjes son de la Fase 7: ¿qué da una promoción? | **Puntos al comprar.** Las promociones dan puntos extra (fijos o multiplicador) en el ledger al registrar una compra que cumpla las condiciones. La de cumpleaños se aplica a la primera compra dentro de la ventana del cumpleaños. Sin tareas programadas. |

Decisiones menores (con su motivo):

- **Conversión versionada en BD** (`LoyaltyRule`): el propietario la cambia en el admin sin tocar código; las reglas no se editan ni se borran, se añade otra. Cada movimiento guarda una copia de la tasa aplicada, de modo que un cambio nunca altera puntos ya concedidos. Mientras no haya ninguna regla se aplica `LOYALTY_DEFAULT_POINTS_PER_EURO` (1 punto/€), **pendiente de confirmar por el propietario**.
- **Redondeo hacia abajo** (`ROUND_DOWN`) a puntos enteros: nunca se conceden puntos por céntimos que no se han gastado y el resultado es fácil de explicar al cliente.
- **Saldo derivado del ledger** (suma de movimientos), sin tabla de saldos aparte que pueda desincronizarse. Cada movimiento guarda además `balance_after` para auditarlo.
- **Sin puntos retroactivos:** las compras registradas antes de esta fase no generan puntos. Si el propietario lo quiere, puede hacerse con ajustes manuales (servicio `adjust_points`).
- **Las promociones aplicables se acumulan.** Si el propietario no lo quiere, no debe tener dos activas a la vez.
- **Los usos compensados siguen contando** para los límites de una promoción (no se recupera un uso anulando la compra).
- **Nuevo módulo por responsabilidad** dentro de `apps.loyalty` (`conversion`, `ledger`, `promotions`, `selectors`), sin crear apps nuevas.

## 2. Alcance y exclusiones

**Incluye:** ledger de puntos inmutable con compensaciones, conversión configurable y versionada, generación de puntos en la transacción de la compra, promociones configurables (condiciones, fechas, límites, estado), base de promociones de cumpleaños, ajustes y compensaciones manuales (servicio), vista del cliente "Mis puntos" (saldo, obtenidos, utilizados, historial de movimientos y de compras), puntos generados en el resultado de la compra del personal, admin del propietario, estadísticas mínimas que distinguen compras registradas de facturación, API documentada, tests.

**Excluye:**
- Canjes y recompensas (Fase 7). El tipo `REDEMPTION` existe reservado en el ledger, sin flujo.
- Envío de promociones por email o SMS, registro de notificaciones y tareas programadas (Fase 10). Esta fase solo **selecciona** destinatarios.
- Interfaz de ajustes manuales y estadísticas para el propietario (Fase 9): hoy son servicios.
- Anulación de compras (sigue sin flujo; cuando exista deberá llamar a `ledger.reverse_movement`).
- API REST (Fase 11; ver §8).

## 3. Reglas de fidelización

### 3.1 Puntos por compra
1. Al registrar una compra (`purchases.services.register_purchase`), dentro de la **misma transacción**, `on_purchase_registered` llama a `ledger.award_points_for_purchase`.
2. Puntos = `importe × puntos_por_euro`, **redondeado hacia abajo** a un entero. Importe y tasa son `Decimal`; nunca `float`.
   - 12,50 € × 1 = **12** · 0,99 € × 1 = **0** (no se crea movimiento) · 3,33 € × 1,50 = 4,995 → **4**.
3. La tasa es la de la regla vigente **en el momento de la compra**.
4. Solo compras `COMPLETED` de clientes (`CUSTOMER`). El email verificado ya lo exige el registro de la compra.
5. Los puntos **nunca** llegan del navegador: `register_purchase` no acepta un argumento de puntos (`TypeError`) y la vista ignora campos extra (`points`, `balance`, `points_per_euro`…); hay tests de ambos.

### 3.2 Saldo, obtenidos y utilizados
| Concepto | Definición |
|---|---|
| Saldo | Suma de todos los movimientos del cliente. Nunca negativo (`CHECK` + comprobación en el servicio) |
| Obtenidos | Suma de los movimientos positivos (compras, promociones, ajustes y compensaciones a favor) |
| Utilizados | Puntos gastados en canjes (Fase 7; hoy 0) |
| Corregidos | Resto de movimientos negativos (compensaciones y ajustes en contra) |

Saldo = obtenidos − utilizados − corregidos.

### 3.3 Tipos de movimiento
| Tipo | Signo | Quién lo crea | Restricciones en BD |
|---|---|---|---|
| `EARN_PURCHASE` (Compra) | + | `award_points_for_purchase` | Con compra y sin promoción; **uno por compra** (único parcial) |
| `PROMOTION_BONUS` (Promoción) | + | `award_points_for_purchase` | Con compra y promoción; **uno por promoción y compra**; `birthday_year` único por cliente |
| `ADJUSTMENT` (Ajuste manual) | ± | `adjust_points` (propietario) | Con autor y motivo; `idempotency_key` único |
| `REVERSAL` (Compensación) | − del original | `reverse_movement` (propietario) | `reverses` `OneToOne`: un movimiento se compensa **una sola vez** |
| `REDEMPTION` (Canje) | − | Reservado para la Fase 7 | Negativo |

Además: `points ≠ 0`, `balance_after ≥ 0`, tipos válidos. Los movimientos no se editan ni se borran (admin de solo lectura, `PROTECT` en las claves ajenas).

### 3.4 Promociones
Cada promoción (`Promotion`) tiene:

| Grupo | Campos |
|---|---|
| Identificación | `name`, `description` (pública, sin datos personales), `public_id` |
| Tipo | `PURCHASE` (por compra) o `BIRTHDAY` (cumpleaños) |
| Bonificación | `FIXED_POINTS` (1–10 000 puntos) o `MULTIPLIER` (>1 y ≤10; añade `puntos base × (multiplicador − 1)`, redondeado hacia abajo) |
| Condiciones | `min_purchase_amount`; en cumpleaños, `birthday_window_days` (0–31) |
| Fechas | `starts_at`, `ends_at` (opcional, posterior al inicio). Intervalo `[inicio, fin)` |
| Límites | `max_uses_per_customer`, `max_total_uses` (vacío = sin límite) |
| Estado | `DRAFT`, `ACTIVE`, `PAUSED`, `ENDED`. Solo `ACTIVE` se aplica |

Las coherencias (tipo de bonificación con su valor, fechas, rangos) se validan en `clean()` y con `CHECK` en la BD, incluido `IS NOT NULL` explícito (en SQL un `CHECK` sobre `NULL` se da por cumplido; un test lo detectó durante la fase). El límite total se respeta con compras simultáneas bloqueando las filas de las promociones (`select_for_update`) dentro de la transacción.

### 3.5 Promociones de cumpleaños
- **Detectar el cumpleaños:** fecha de nacimiento del perfil; la compra cuenta si se hace hasta `birthday_window_days` días antes o después (también cruzando el cambio de año).
- **29 de febrero:** en años no bisiestos se celebra el **28 de febrero** (política de la Fase 2, `accounts.birthdays.birthday_in_year`).
- **Una por periodo:** el periodo es el año del cumpleaños. Restricción única `(cliente, birthday_year)` en BD: aunque haya varias promociones de cumpleaños activas o dos compras simultáneas, solo se concede una.
- **Anti-abuso de la fecha de nacimiento** (no se pueden obtener recompensas ilimitadas cambiándola):
  1. El perfil ya solo permite cambiarla una vez cada 365 días (Fase 2).
  2. No se aplica si la fecha cambió hace menos de `LOYALTY_BIRTHDAY_DOB_STABLE_DAYS` (30) días.
  3. Entre dos promociones de cumpleaños deben pasar al menos `LOYALTY_BIRTHDAY_MIN_DAYS_BETWEEN_BONUSES` (300) días, aunque el "año del cumpleaños" sea otro.
- **Preparación de los envíos (Fase 10):** `promotions.birthday_promotion_recipients(channel=EMAIL|SMS, at=...)` devuelve los clientes a los que se podría avisar ese día. **No envía nada.** Filtra: promoción de cumpleaños activa; cumpleaños ese día (29-F incluido); cuenta activa de cliente **con email verificado**; consentimiento vigente del canal (`accounts.services.can_receive_promotional_email/sms`); y que todavía pueda recibir la promoción del año. La Fase 10 deberá registrar cada envío con idempotencia (una notificación por cliente, promoción y año) y volver a comprobar el consentimiento justo antes de enviar.

### 3.6 Ajustes y compensaciones (propietario)
- `ledger.adjust_points(actor, customer, points, reason, idempotency_key)`: entero ≠ 0 de hasta `LOYALTY_MAX_ADJUSTMENT_POINTS` (100 000) en valor absoluto, motivo obligatorio (≤200), no puede dejar el saldo en negativo. Un reintento con la misma referencia devuelve el mismo movimiento; con otros datos da `idempotency_conflict`.
- `ledger.reverse_movement(actor, movement, reason)`: crea el movimiento de signo contrario; idempotente; no se compensa una compensación.
- Ambos dejan un `AuditEvent` (`POINTS_ADJUSTED`, `POINTS_REVERSED`) **sin el texto del motivo** (puede contener datos personales).
- Hoy no tienen interfaz: se usan desde código o `manage.py shell`. La interfaz llegará con el dashboard (Fase 9).

### 3.7 Estadísticas: compras registradas ≠ facturación
`purchases.selectors.registered_purchases_stats(actor, start, end)` (solo propietario) devuelve número de compras, clientes, importe registrado y media, con la etiqueta **"Compras registradas en el programa de fidelización"** y la nota "No es la facturación total del local". `business_revenue` es siempre `None`: el sistema no conoce la facturación (no hay caja ni TPV integrados) y nunca la estima. Las compras anuladas no cuentan. `loyalty.selectors.points_stats` da los puntos emitidos, utilizados, corregidos y el saldo pendiente total. El dashboard de la Fase 9 los mostrará.

## 4. Concurrencia, duplicados e integridad

| Riesgo | Medida |
|---|---|
| Compra y puntos inconsistentes | Misma transacción; cualquier fallo en el ledger deshace la compra (tests con fallo antes y después del `INSERT`) |
| Doble envío o reintento de la compra | La idempotencia de la compra (Fase 5) no vuelve a llamar al ledger; además `award_points_for_purchase` es idempotente y hay un único parcial por compra |
| Dos operaciones simultáneas del mismo cliente | Bloqueo de la fila del cliente (`select_for_update`) y recálculo del saldo dentro de la transacción |
| Saldo negativo | Comprobación en el servicio (`InsufficientPoints`) y `CHECK balance_after >= 0` |
| Límite total de una promoción con compras simultáneas | Bloqueo de las filas de las promociones activas |
| Dos cumpleaños el mismo año | Único `(cliente, birthday_year)` |
| Ajuste duplicado | `idempotency_key` único; la carrera se resuelve con el `IntegrityError` y se devuelve el existente |
| Compensación duplicada | `reverses` `OneToOne` |

Orden de bloqueo: cliente → promociones, siempre igual (evita interbloqueos).

## 5. Cómo probarlo (desarrollo)

```powershell
python manage.py migrate
python manage.py runserver
```

1. Sigue la [guía de la Fase 5](fase-05-qr-compras.md#5-cómo-probar-el-flujo-de-compra) para tener un empleado y un cliente verificado con datos ficticios.
2. **Conversión (opcional):** como propietario, admin → *Fidelización* → *Reglas de conversión de puntos* → *Añadir* (p. ej. 1,00 puntos por euro, en vigor desde ahora). Sin reglas se usa 1 punto/€.
3. **Promoción (opcional):** admin → *Promociones* → *Añadir*: "Puntos dobles", tipo *Por compra*, bonificación *Multiplicador* 2,00, estado *Activa*, empieza ahora.
4. Registra una compra de `12,50` desde `/panel/compras/`. El resultado muestra **Puntos generados: 12** (o 24 con la promoción).
5. Con la sesión del cliente, abre *Mi perfil* → **Mis puntos** (`/cuenta/puntos/`): saldo, obtenidos, utilizados, movimientos y compras.
6. **Cumpleaños:** crea una promoción *Cumpleaños* de 50 puntos fijos, activa, con 7 días de margen. Un cliente cuya fecha de nacimiento (sin cambios en los últimos 30 días) caiga a ±7 días recibe +50 en su primera compra; en la segunda, no.
7. **Movimientos:** admin → *Movimientos de puntos* (solo lectura).

## 6. Seguridad y privacidad

- **Servidor como única fuente:** puntos, tasa, bonificaciones y saldo se calculan en el servidor a partir de datos de la BD.
- **Autorización:** la vista "Mis puntos" exige sesión, email verificado y rol de cliente, y siempre usa `request.user` (no acepta identificadores: no hay IDOR posible; test con parámetros inventados). Empleados y propietarios reciben 403. Conversión, promociones, ajustes, compensaciones y estadísticas: solo propietario (en el servicio, no solo en la interfaz); tests de denegación para anónimo, cliente y empleado.
- **Admin:** solo propietarios. Las reglas no se editan ni se borran, las promociones no se borran y los movimientos son de solo lectura. El QR sigue fuera del admin.
- **Sin caché** en "Mis puntos" (`never_cache`).
- **Logs** solo con identificadores públicos de la compra, número de movimientos y puntos; sin email, nombre ni token (test con `assertLogs`).
- **Auditoría** de conversión, promociones, ajustes y compensaciones, sin el texto libre del motivo.
- **Promociones:** ninguna se envía en esta fase. La selección exige email verificado y consentimiento del canal.
- **Datos personales:** la fecha de nacimiento solo se usa en el servidor para la elegibilidad; no aparece en ninguna respuesta ni log nuevo.

## 7. Configuración

- **Migraciones:** `loyalty/0002_points_ledger_promotions` (tres tablas nuevas con sus restricciones) y `core/0005_audit_actions_phase6` (cuatro acciones nuevas en los `choices`; no toca datos). Son aditivas y reversibles (probado: aplicar → revertir → aplicar sobre una copia de la BD de desarrollo). Ejecuta `python manage.py migrate`.
- **Settings nuevos** en `base.py` (no son variables de entorno): `LOYALTY_DEFAULT_POINTS_PER_EURO` (1.00), `LOYALTY_BIRTHDAY_DOB_STABLE_DAYS` (30), `LOYALTY_BIRTHDAY_MIN_DAYS_BETWEEN_BONUSES` (300), `LOYALTY_MAX_ADJUSTMENT_POINTS` (100 000).
- **Rutas:** nueva `/cuenta/puntos/`. Las del QR (`/cuenta/mi-qr/`, `/cuenta/mi-qr/renovar/`) no cambian: ahora `apps.loyalty.urls` se monta en `/cuenta/` antes que las de cuentas.
- **Sin dependencias nuevas.**

## 8. Preparación para la app y la API (Fase 11)

La lógica está en servicios que no dependen de la petición ni de las plantillas:

| Módulo | Uso |
|---|---|
| `loyalty.conversion` | Tasa vigente, cálculo y redondeo, `create_rule` |
| `loyalty.ledger` | Única vía de escritura: `award_points_for_purchase`, `adjust_points`, `reverse_movement`, `balance` |
| `loyalty.promotions` | Aplicación de promociones, elegibilidad de cumpleaños, `save_promotion`, `birthday_promotion_recipients` |
| `loyalty.selectors` | Lectura: `points_summary`, `points_history`, `points_for_purchase`, `points_stats` |
| `purchases.selectors` | Lectura: `customer_purchases`, `registered_purchases_stats` |

Endpoints propuestos (solo lectura para el cliente):

| Endpoint | Quién | Servicio | Respuesta |
|---|---|---|---|
| `GET /api/v1/me/points/` | Cliente verificado | `loyalty.selectors.points_summary(request.user)` | `{"balance": 17, "earned": 17, "used": 0, "corrected": 0}` |
| `GET /api/v1/me/points/movements/?page=N` | Cliente verificado | `points_history(request.user)` paginado | `public_id`, `kind`, `points`, `balance_after`, `created_at`, `promotion` (`{"public_id", "name"}` o `null`), `purchase` (`public_id` o `null`) |
| `GET /api/v1/me/purchases/?page=N` | Cliente verificado | `purchases.selectors.customer_purchases(request.user)` | `public_id`, `amount` (cadena `"12.50"`), `created_at`, `status`, `points` |
| `GET /api/v1/promotions/` (opcional) | Cliente | `promotions.active_promotions()` | `public_id`, `name`, `description`, `kind`, `ends_at` (sin límites ni usos) |

Pautas:
- Siempre `request.user`: **no** habrá endpoints `/customers/{id}/points/` para clientes. Si el dashboard (Fase 9) los necesita, solo para el propietario y por `public_id`.
- Todos los campos de solo lectura. Nunca exponer `id`, `reason`, `created_by`, `rule`, `birthday_year`, `idempotency_key` ni la fecha de nacimiento.
- Importes como cadena decimal y puntos como enteros.
- Paginación por páginas (o cursor por `created_at`, `id`), con el mismo orden que la web (más reciente primero).
- Errores: `PermissionDenied` → 403; `InsufficientPoints` y demás `ValidationError` → 400 con `code`; `idempotency_conflict` → 409.

## 9. Archivos creados o modificados

- **`apps/loyalty/`:** `models.py` (`LoyaltyRule`, `Promotion`, `PointsTransaction`), nuevos `conversion.py`, `ledger.py`, `promotions.py`, `selectors.py`, `admin.py`; `views.py` (`my_points`), `urls.py`; `migrations/0002_points_ledger_promotions.py`.
- **`apps/purchases/`:** `services.py` (`on_purchase_registered` llama al ledger), nuevo `selectors.py` (historial del cliente y estadísticas), `views.py` (puntos en el resultado).
- **`apps/core/`:** `models.py` (acciones `LOYALTY_RULE_CREATED`, `PROMOTION_SAVED`, `POINTS_ADJUSTED`, `POINTS_REVERSED`) y `migrations/0005_audit_actions_phase6.py`.
- **Configuración:** `config/settings/base.py`, `config/urls.py`.
- **Plantillas:** nueva `templates/loyalty/my_points.html`; `templates/accounts/profile.html` (enlace "Mis puntos"); `templates/purchases/detail.html` (puntos generados). `static/css/app.css` recompilado.
- **Tests:** nuevos `tests/loyalty/test_points.py`, `test_promotions.py`, `test_points_views.py`, `tests/purchases/test_stats.py`; `tests/loyalty/factories.py` (`buy`, `make_promotion`); `tests/purchases/test_views.py` (ver §10).
- **Documentación:** este documento, `README.md`, `plan-de-fases.md`, `arquitectura.md`.

## 10. Tests y resultados reales

Nuevos (92):
- **Ledger** (`test_points.py`, 41): redondeo (casos límite), rechazo de `float`/NaN/negativos, tasa por defecto; reglas (propietario, auditoría, permisos, valores no válidos, no retroactiva, futura no aplicada, `CHECK`); movimiento de compra con todos sus campos, compra sin puntos, cadena de `balance_after`, saldos por cliente, puntos enviados por el cliente rechazados, reintentos sin duplicar, idempotencia del ledger, único por compra en BD, `CHECK` de saldo negativo y de puntos cero, compra anulada, fallos transaccionales antes y después del `INSERT` sin compra ni movimiento residual, bloqueo del cliente, logs sin datos personales; ajustes (auditoría sin motivo, permisos, validación, signo, saldo insuficiente, solo clientes, reintento, conflicto, carrera simulada); compensaciones (sin editar el original, idempotencia, `OneToOne` en BD, no compensar compensaciones, saldo insuficiente, permisos); resumen.
- **Promociones** (`test_promotions.py`, 30): puntos fijos, multiplicador con redondeo, sin puntos base, estado y fechas, importe mínimo, límite por cliente y total, reintento sin duplicar, único en BD; validación del modelo y `CHECK` en BD; `save_promotion` (permisos, auditoría, validación); cumpleaños: 29-F, cambio de año, bordes de la ventana, una sola vez, una aunque haya varias promociones, fuera de ventana o sin fecha, fecha cambiada hace poco, cambio de fecha para obtener otra, único por año en BD, 29-F con compra real el 28-F de un año no bisiesto; destinatarios: solo verificados con consentimiento y cumpleaños hoy, inactivos fuera, SMS, ya recibida, sin promoción activa, 29-F, canal desconocido, no envía emails.
- **Vistas y admin** (`test_points_views.py`, 15): login, 403 para no verificados, empleados y propietarios, saldo e historial propios, sin datos de otros clientes con parámetros inventados, paginación, `POST` no cambia puntos, enlace en el perfil, rutas del QR sin cambios, campos de puntos en el `POST` del personal ignorados, puntos en el resultado; admin: regla vía servicio no editable ni borrable, promoción auditada no borrable, errores de formulario, movimientos de solo lectura, sin acceso para empleados.
- **Estadísticas** (`test_stats.py`, 6): compras registradas ≠ facturación (`business_revenue` `None`, anuladas excluidas, media redondeada), periodo vacío, filtro por fechas, solo propietario, estadísticas de puntos, historial de compras con puntos.

Modificado: `tests/purchases/test_views.py::test_qr_tokens_are_not_in_admin` comprobaba que la app `loyalty` no aparecía en el admin. Ahora aparece (puntos y promociones), así que comprueba lo que protegía: que el modelo del QR no está en el admin y que el token no aparece en el índice ni en las listas de compras y movimientos.

| Comando o prueba (SQLite, Python 3.14.2, Django 5.2.18) | Resultado |
|---|---|
| `python manage.py check` | Sin incidencias |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| `python manage.py test --settings=config.settings.test` | **466 tests, OK** (374 anteriores + 92 nuevos) |
| `migrate` → revertir (`loyalty 0001`, `core 0004`) → `migrate` sobre una copia temporal de la BD de desarrollo | OK |
| `check --deploy --settings=config.settings.prod` (variables ficticias) | Solo `W021` (HSTS preload, intencionado, ya existente) |
| `python scripts/tailwind.py build` | OK |

**No probado:** la concurrencia real con bloqueos de fila. En SQLite `select_for_update` no bloquea; las carreras se probaron con las restricciones únicas y simulando el `IntegrityError`. Tampoco se hizo una revisión visual manual de `/cuenta/puntos/` en el navegador (la página se renderiza en los tests).

## 11. Limitaciones, riesgos y pendientes

- **Concurrencia en PostgreSQL** pendiente de verificar (Fase 12), igual que en la Fase 5. Las restricciones únicas y el `CHECK` del saldo garantizan la integridad aunque falle un bloqueo; lo que falta verificar es el comportamiento de los bloqueos.
- **Fecha de nacimiento no verificada documentalmente:** un cliente puede declarar una fecha falsa al registrarse. El daño está acotado a una promoción de cumpleaños al año y por cuenta. Si se quiere más, la opción descartada en esta fase era que el personal la verificara con un documento (campo nuevo en el perfil).
- **Conversión por defecto** (1 punto/€) pendiente de confirmar por el propietario.
- **Sin interfaz para ajustes, compensaciones y estadísticas** hasta la Fase 9.
- **Rendimiento:** el saldo se calcula sumando movimientos. Con el volumen de una cervecería es inmediato (hay índice `(customer, created_at)`). Si algún día creciera mucho, se podría usar el `balance_after` del último movimiento o una tabla de saldos.
- **Caducidad de puntos:** no se ha definido; los puntos no caducan.
- **Anulación de compras** aún sin flujo: cuando exista deberá compensar los movimientos de la compra con `reverse_movement`, no borrarlos.
- **Textos legales** de las promociones y del programa (bases, condiciones) los aporta el propietario.

## 12. Estado de los criterios de aceptación

| Criterio | Estado |
|---|---|
| Cada cliente tiene saldo, historial de movimientos, historial de compras, puntos obtenidos y utilizados | Completo (utilizados = 0 hasta la Fase 7) |
| Ledger que registra cada movimiento | Completo (inmutable, con compensaciones) |
| Puntos calculados solo en el backend; no se aceptan del frontend | Completo (con tests) |
| Conversión configurable | Completo (`LoyaltyRule` en el admin, versionada) |
| `Decimal` y redondeo definido | Completo (`ROUND_DOWN` a enteros) |
| Compras y puntos consistentes mediante transacciones | Completo (con tests de fallo) |
| Sin duplicados ni problemas de concurrencia | Completo (restricciones únicas + bloqueos; concurrencia real pendiente de PostgreSQL) |
| Promociones configurables con condiciones, fechas, límites y estado | Completo |
| Base de cumpleaños: detectar, comprobar el periodo, evitar duplicados, preferencias, 29-F | Completo (sin envíos, como pide la fase) |
| Sin recompensas ilimitadas cambiando la fecha de nacimiento | Completo (único por año + 30 días de estabilidad + 300 días entre promociones + 1 cambio/año) |
| No enviar a emails sin verificar ni sin consentimiento | Completo en la selección; no hay envíos en esta fase |
| Distinguir compras registradas de facturación | Completo (servicio; la interfaz llega en la Fase 9) |
| Servicios independientes de las vistas y API documentada | Completo (§8) |
| Pruebas de puntos, saldo, redondeo, duplicados, concurrencia, promociones y permisos | Completo (92 tests) |
| Reglas de fidelización documentadas | Completo (§3) |

## 13. Dependencias para la fase siguiente (Fase 7 — Recompensas y canjes)

> Resuelto en la [Fase 7](fase-07-recompensas-canjes.md): `ledger.spend_points`/`refund_spent_points`; además, "Utilizados" pasó a ser neto de las devoluciones de canjes (y "Obtenidos" ya no las incluye).

- Escribir los canjes como movimientos `REDEMPTION` desde un servicio nuevo de `ledger` que bloquee al cliente y use `_append` (comprueba el saldo dentro de la transacción).
- "Utilizados" ya suma los `REDEMPTION`; la vista "Mis puntos" no necesita cambios.
- Un canje cancelado o caducado debe compensarse con `reverse_movement`, no borrarse.
