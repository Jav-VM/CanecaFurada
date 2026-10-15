# Caneca Furada — Guion de la defensa oral (cap. 17)

> Material para que el autor presente y defienda el proyecto. **Ninguna demostración se ha realizado durante la preparación de este documento**: el orden de demostración es una propuesta que el autor debe ensayar en su equipo. Las cifras citadas están verificadas el 15-10-2026 (802 tests, OK, 3 omitidos).

## 1. Resumen de 30 segundos

> «Caneca Furada es la web de una cervecería artesanal de A Coruña con un programa de fidelización completo: cada cliente tiene un QR personal; en la barra el empleado lo escanea, registra el importe y el sistema suma puntos que el cliente canjea por recompensas con un código de un solo uso. El propietario tiene un dashboard con estadísticas y gestión. Está hecho en Django como un monolito modular, con la lógica en servicios, transacciones y restricciones en la base de datos para que nadie pueda duplicar puntos ni canjes, y tiene una API REST preparada para una app móvil y 802 tests automáticos».

## 2. Presentación de unos 2 minutos

1. **El problema (20 s).** Un local pequeño quiere fidelizar sin tarjetas de cartón y conocer a su clientela sin invadir su privacidad.
2. **La solución (40 s).** Web pública + fidelización (registro verificado, QR, compras, puntos, recompensas) + panel para el personal + dashboard para el propietario + eventos y reservas + API.
3. **Cómo está construido (40 s).** Django 5.2; doce apps; las vistas solo traducen HTTP y la lógica vive en servicios que comprueban permisos, validan y abren transacciones; la base de datos protege las reglas críticas con restricciones; tres roles controlados en el servidor.
4. **Garantías (20 s).** Puntos calculados solo en el servidor con `Decimal`; ledger inmutable; idempotencia; códigos de un solo uso con UPDATE condicionado; datos personales mínimos y consultas auditadas; 802 tests.

## 3. Guion de 10 minutos

| Min. | Bloque | Mensaje clave | Qué enseñar |
|---|---|---|---|
| 0:00-1:00 | Presentación | Resumen del apartado 1 | Portada de la web (`/`) |
| 1:00-2:30 | Usuarios y roles | Tres roles, autorización en el servidor, registro siempre como cliente | Tabla de roles (memoria, cap. 2.2); diagrama `11_roles_permisos.mmd` |
| 2:30-4:00 | Arquitectura | Monolito modular; vistas → servicios → modelos; la API reutiliza los servicios | `diagramas/01_arquitectura_general.mmd`; `apps/purchases/views.py` frente a `services.py` |
| 4:00-6:30 | **Demostración** del circuito de fidelización | QR → compra → puntos → canje → validación | Orden de demostración del apartado 5 (pasos 1-6) |
| 6:30-8:00 | Integridad | Transacción compra + puntos; idempotencia; UPDATE condicionado; restricciones únicas | C8.7, C8.10 y C8.12 |
| 8:00-9:00 | Privacidad y seguridad | El empleado solo ve «Lúa F.»; ficha auditada; búsqueda por POST; anti-enumeración | Panel frente a dashboard; cap. 7.4 |
| 9:00-10:00 | Calidad, límites y cierre | 802 tests; pendientes: PostgreSQL, SMTP, despliegue | Salida de `manage.py test`; `05_limitaciones_y_pendientes.md` |

## 4. Guion ampliado de 15 minutos

Igual que el de 10 minutos, más:

| Min. | Bloque añadido | Contenido |
|---|---|---|
| +1:30 | Modelo de datos | Diagrama ER (`04_entidad_relacion.mmd`): `PointsTransaction` como ledger, `Redemption` con dos movimientos OneToOne, `Reservation` con `TRANSITIONS` |
| +1:30 | Dashboard y estadísticas | Periodos, compras registradas ≠ facturación, distribución geográfica solo con direcciones declaradas |
| +1:00 | Eventos, reservas y notificaciones | Máquina de estados; notificaciones con estado real y consentimiento comprobado al enviar |
| +1:00 | API y app móvil | JWT con refresh rotatorio y revocación por `pwv`; OpenAPI idéntico al código |

## 5. Orden recomendado de la demostración práctica

**Preparación (antes de la defensa, con datos ficticios):**
1. `python manage.py migrate` y `python manage.py create_owner` (p. ej. `propietario@example.com`).
2. Desde el dashboard (`/dashboard/empleados/`), crear un empleado (`empleado@example.com`).
3. Registrar un cliente en `/cuenta/registro/` (`cliente@example.com`) y verificar su email con el enlace que aparece en la consola de `runserver` (en Windows, arrancar con `$env:PYTHONUTF8=1`).
4. En el admin: crear una categoría, un estilo y una cerveza y publicarla; crear una recompensa ACTIVA de 10 puntos.
5. Usar **dos navegadores o una ventana privada** (cliente y empleado a la vez).

**Secuencia (≈ 3 minutos):**

| Paso | Rol | Acción | Qué remarcar |
|---|---|---|---|
| 1 | Visitante | `/carta/` | Solo se ve lo publicado; los agotados aparecen al final |
| 2 | Cliente | `/cuenta/mi-qr/` | El QR no contiene datos personales; código tecleable debajo |
| 3 | Empleado | `/panel/compras/` → teclear el código → «Lúa F.» → importe 12,50 | Solo ve el nombre abreviado |
| 4 | Empleado | Pulsar «Registrar» (con doble clic rápido si se quiere) | `app.js` bloquea el doble envío en el navegador, pero **la garantía real está en el servidor**: enseñar el test C8.20 (misma clave → la misma compra). *Aviso:* no se debe demostrar «volviendo atrás» en el navegador, porque eso reenvía el paso de identificación, que genera **una clave nueva** y registraría otra compra legítima |
| 5 | Cliente | `/cuenta/puntos/` | 12 puntos (ROUND_DOWN) y el movimiento con su compra |
| 6 | Cliente | `/recompensas/` → canjear | Código de un solo uso y saldo descontado al momento |
| 7 | Empleado | `/panel/canjes/` → validar el código → **validarlo otra vez** | «Este código ya se utilizó el…» |
| 8 | Empleado | Teclear `/dashboard/` | 403: autorización en el servidor |
| 9 | Propietario | `/dashboard/` → Resumen → Clientes → ficha | Cifras reales; la ficha queda auditada |
| 10 | (Opcional) | Terminal: `python manage.py test --settings=config.settings.test` | 802 tests (unos 16 s) |

**Plan B** si falla la cámara o el entorno: teclear el código (el flujo es idéntico) o mostrar los tests y los diagramas de secuencia.

## 6. Módulos que conviene mostrar en pantalla (código)

1. `apps/purchases/services.py:158-194` — compra idempotente y transaccional (C8.7).
2. `apps/loyalty/ledger.py:58-72` — saldo derivado y `InsufficientPoints` (C8.8).
3. `apps/loyalty/models.py:404-419` — restricciones únicas del ledger (C8.10).
4. `apps/rewards/services.py:378-393` — validación con UPDATE condicionado (C8.12).
5. `apps/accounts/permissions.py:17-52` — `role_required` (C8.2).
6. `apps/accounts/services.py:421-430` — anti-enumeración (C8.3).
7. `tests/purchases/test_services.py:169-177` — test de doble envío (C8.20).

## 7. Explicación sencilla de la arquitectura

> «Imaginad tres capas. Arriba, las pantallas y la API, que solo reciben peticiones y muestran resultados. En medio, los servicios, que son los que deciden: comprueban quién eres, validan los datos y hacen el cambio dentro de una transacción. Abajo, la base de datos, que además tiene sus propias reglas, como que un saldo nunca pueda ser negativo. La web y la API llaman a los mismos servicios, así que las reglas están escritas una sola vez».

## 8. Explicación técnica de los elementos más complejos

- **Idempotencia de la compra:** UUID por operación + `UNIQUE` en la BD + `select_for_update` + `_replay`, que compara los datos; si gana otra petición, el `IntegrityError` se captura en un savepoint.
- **Ledger:** solo inserciones; saldo = `SUM(points)` con la fila del cliente bloqueada; CHECK `balance_after >= 0`; compensaciones con OneToOne `reverses`.
- **Canje sin doble consumo:** orden de bloqueo cliente → recompensa → canje; stock con `F("stock") - 1` condicionado; validación con `UPDATE ... WHERE status='PENDING'`; devolución con detección de un cambio concurrente que deshace la transacción.
- **JWT revocable:** la reclamación `pwv` = HMAC del hash de la contraseña; al cambiarla, todos los tokens dejan de valer sin esperar a que caduquen.
- **Notificaciones:** se reclaman con un UPDATE condicionado (varios procesos sin duplicar) y se vuelve a comprobar el consentimiento justo antes de enviar.

## 9. Decisiones más defendibles

1. Ledger inmutable (auditoría y corrección sin borrar).
2. Reglas críticas también en la BD (no solo en Python).
3. Mismos servicios para la web y la API (sin lógica duplicada).
4. Minimización de datos y consultas auditadas.
5. Usuario personalizado con roles desde la primera migración.
6. `Decimal` y `ROUND_DOWN` para los puntos.

## 10. Aspectos que conviene reconocer como limitaciones (con honestidad)

- **No está desplegado** y **no se ha probado con PostgreSQL**; los 3 tests de concurrencia se omiten con SQLite en memoria (pasan con SQLite en fichero, pero eso no ejercita los bloqueos de fila).
- El **envío real de emails** no se ha verificado; el **SMS no existe**; las **tareas programadas no están programadas**.
- No hay **exportación ni supresión** de datos personales a petición.
- No hay **CI** ni medición de **cobertura**; el JS y la accesibilidad no tienen tests automáticos.
- **Anulación de compras** y **TPV**: reservados en el modelo, sin flujo.

> Frase útil: «He preferido que lo que está hecho sea correcto y esté probado antes que aparentar funcionalidades; lo pendiente está identificado y documentado».
