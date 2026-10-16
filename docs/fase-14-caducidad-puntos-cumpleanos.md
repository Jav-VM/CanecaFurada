# Fase 14 — Caducidad de puntos y regalo de cumpleaños configurables

**Estado:** Completa (2026-10-16). Migraciones aplicadas en la base de desarrollo; pendientes la revisión visual en navegador y el despliegue en producción.
**Depende de:** Fases 6 (ledger y promociones), 7 (canjes), 9 (dashboard) y 10 (cumpleaños y notificaciones).

## 1. Objetivo, alcance y exclusiones

**Objetivo:** que el propietario gestione desde **Dashboard → Configuración**:
1. la **caducidad de los puntos**: activarla, cambiar el plazo o quitarla;
2. el **regalo de cumpleaños**: activarlo o desactivarlo, cambiar los puntos y editar el texto del aviso (asunto y cuerpo del email, y SMS).

**Decisiones del usuario (2026-10-16):**

| Pregunta | Decisión |
|---|---|
| ¿Cómo caducan los puntos? | **Por antigüedad de cada punto** (FIFO): se gastan primero los más antiguos. |
| ¿Qué pasa con los puntos existentes al activar o acortar? | **Sin retroactividad**: el plazo nuevo empieza a contar desde ese momento. |
| ¿Qué es la "recompensa de cumpleaños"? | **Puntos regalados** (sistema actual), más un **texto editable** del aviso. |
| ¿Se avisa antes de caducar? | **Sí**: fecha visible en «Mis puntos» y un **email de aviso** previo. |

**Exclusiones:**
- El regalo de cumpleaños sigue siendo solo de puntos: no se regalan recompensas del catálogo.
- No hay aviso de «tus puntos han caducado» después del vencimiento, solo antes.
- La API no expone todavía la próxima fecha de caducidad; solo el total `expired` y el tipo de movimiento nuevo.
- Los datos de demostración (`seed_demo_data`) no configuran caducidad.
- El cambio de idioma (gallego) queda para una fase posterior.

## 2. Reglas de la caducidad

**Política versionada** (`PointsExpiryPolicy`, igual que `LoyaltyRule`): no se edita ni se borra. Cada cambio añade una versión y la vigente es la última. Sin política, o con `months` vacío, los puntos no caducan.

| Campo | Significado |
|---|---|
| `months` | Meses de validez (1–60) o vacío = sin caducidad. «Quitar la caducidad» crea una versión con `months` vacío. |
| `warn_days` | Días de antelación del email de aviso (1–60, por defecto 15). |
| `counts_from` | Desde cuándo empieza a contar el plazo. **Lo calcula el servicio, nunca el formulario.** |

**Fecha de caducidad de cada crédito:** `max(fecha en que se ganó, counts_from) + months`. La suma de meses recorta el día al fin de mes (31/01 + 1 mes = 28/02 o 29/02).

**Cálculo de `counts_from`** (`expiry.set_policy`):

| Cambio | `counts_from` | Efecto |
|---|---|---|
| Activar (antes no caducaban) | ahora | Nadie pierde puntos de golpe: lo antiguo vence `months` meses después de activar. |
| Acortar el plazo | ahora | Igual: el plazo nuevo cuenta desde el cambio. |
| Alargar el plazo o cambiar solo `warn_days` | se conserva el anterior | Las fechas solo pueden retrasarse. |
| Quitar la caducidad | vacío | Ya no caduca nada. Volver a activarla cuenta desde ese momento. |
| Mismos valores | — | No se crea otra versión. |

**FIFO sin tablas de lotes** (`apps/loyalty/expiry.py`, funciones puras):
- **Créditos:** movimientos positivos (compra, promoción, cumpleaños, ajuste a favor).
- **Débitos:** canjes, ajustes en contra, compensaciones y caducidades. Se consumen de los créditos más antiguos primero.
- Un movimiento y su compensación (`REVERSAL`) se anulan y no cuentan. Una compra compensada no deja puntos, y un **canje cancelado devuelve los puntos con su fecha de caducidad original**.
- **Puntos que caducan en el instante t** = créditos vencidos en t − débitos totales, si el resultado es positivo.
  - Lo ya caducado es un débito más, así que repetir el cálculo da 0: **la caducidad es idempotente**.
  - El resultado nunca supera el saldo, de modo que el `CHECK balance_after >= 0` se respeta.

**Movimiento nuevo `EXPIRATION`** («Puntos caducados»):
- Siempre negativo, sin compra ni promoción; restricción `loyalty_points_expiration_shape` en la base de datos.
- Lo crea `ledger.expire_points` con el cliente bloqueado (`select_for_update`), igual que el resto de escrituras del ledger. Una compra o un canje simultáneos se serializan con la caducidad.
- **No se puede compensar** (`reverse_movement` → `expiration_reversal`, y el botón no aparece en el dashboard). La compensación dejaría esos puntos «sin consumir» y volverían a caducar en la siguiente ejecución. Para devolver puntos caducados, el propietario hace un **ajuste a favor**, que cuenta como puntos nuevos con su propia fecha.

**Cuándo se descuentan:** el comando diario `expire_points` (cron a las 04:40) descuenta lo vencido hasta ese momento. Unos puntos que vencen el día D se pueden usar durante todo el día D y se descuentan en la ejecución de la madrugada siguiente.

## 3. Aviso previo (email)

- Tipo nuevo `Notification.Kind.POINTS_EXPIRING`, **transaccional**.
  - **Motivo de clasificarlo así:** informa del estado de la cuenta de puntos del cliente y no contiene publicidad.
  - Por eso no exige consentimiento promocional, pero sí **cliente activo y email verificado**.
  - Encaja en el `CHECK` de categoría existente sin modificarlo.
- Se envía cuando el próximo vencimiento cae dentro de `warn_days` **días naturales**: hasta el final de ese día, en hora local.
- Un único aviso por vencimiento: `dedup_key = points_expiring:{public_id}:{fecha}`.
- El contexto guarda solo `points` y `expires_on`. El saludo usa el nombre de pila, que se lee al enviar y no se guarda, como en el resto de avisos transaccionales.
- Plantillas: `templates/notifications/points_expiring_{subject,body}.txt`.

## 4. Regalo y aviso de cumpleaños

- **Puntos y activación:** se guardan en la `Promotion` de tipo `BIRTHDAY` que ya usaba `run_birthday_promotions` (`birthday_settings.update_birthday_gift`).
  - Se edita la promoción vigente; si no hay, la activa más antigua; si tampoco, la última modificada sin finalizar. Si no existe ninguna, se crea «Regalo de cumpleaños».
  - **Activar:** estado `ACTIVE`. Si la promoción había terminado, se quita su fecha de fin; si estaba programada para más adelante, empieza ahora.
  - **Desactivar:** pausa **todas** las promociones de cumpleaños activas, también las programadas.
  - Los regalos ya concedidos no cambian (el ledger guarda sus puntos).
- **Textos** (`BirthdayMessage`, fila única con `CHECK id = 1`): asunto (120), email (2000) y SMS (200). Vacío = texto por defecto.
  - **Único marcador: `{puntos}`.** Se sustituye con `str.replace`, **nunca con el motor de plantillas**: lo que escriba el propietario no se interpreta como plantilla, así que no hay riesgo de inyección (SSTI).
  - El servicio además rechaza cualquier otra llave (`{{ }}`, `{% %}`, `{nombre}`), exige una sola línea en el asunto y el SMS, y limita longitudes.
  - Sin nombre del cliente, por privacidad, como ya ocurría en los avisos promocionales.
  - Los textos se **resuelven al encolar** el aviso y se guardan en su contexto: editarlos después no cambia los avisos que ya están en cola.
  - El **pie con el enlace de baja lo añade siempre la plantilla**. El SMS va siempre precedido de «Caneca Furada:» y seguido del enlace de baja.
- El consentimiento promocional y el resto del flujo de cumpleaños (Fase 10) no cambian.

## 5. Archivos

| Archivo | Cambio |
|---|---|
| `apps/loyalty/models.py` | `PointsExpiryPolicy`, `BirthdayMessage`, tipo `EXPIRATION` y sus `CHECK`. |
| `apps/loyalty/expiry.py` | **Nuevo.** Política (`set_policy`, `current_policy`, `active_policy`) y cálculo FIFO (`remaining_lots`, `expirable_points`, `next_expiry`). |
| `apps/loyalty/expirations.py` | **Nuevo.** Ejecución diaria: avisos y caducidades, con auditoría `POINTS_EXPIRY_RUN`. |
| `apps/loyalty/birthday_settings.py` | **Nuevo.** Servicio del regalo de cumpleaños y sustitución de `{puntos}`. |
| `apps/loyalty/ledger.py` | `expire_points`; `reverse_movement` rechaza compensar caducidades. |
| `apps/loyalty/birthdays.py` | El aviso lleva los textos personalizados ya resueltos. |
| `apps/loyalty/selectors.py` | Total `expired` en el resumen del cliente y en las estadísticas; las caducidades no son compensables. |
| `apps/loyalty/views.py`, `templates/loyalty/my_points.html` | Próximo vencimiento y total «Caducados». |
| `apps/loyalty/admin.py` | Historial de la caducidad, solo lectura. |
| `apps/loyalty/management/commands/expire_points.py` | **Nuevo.** Comando diario; `--at` solo con `DEBUG`. |
| `apps/dashboard/forms.py`, `views.py`, `urls.py` | `PointsExpiryForm`, `BirthdayGiftForm`; vistas POST `settings_expiry` y `settings_birthday`. |
| `templates/dashboard/settings.html` | Secciones «Caducidad de los puntos» y «Regalo de cumpleaños». |
| `templates/dashboard/points.html`, `customer_detail.html`, `promotions.html` | Total «Caducados»; enlace a Configuración. |
| `templates/notifications/birthday_*.txt` | Texto personalizado o el de por defecto; pie de baja siempre. |
| `templates/notifications/points_expiring_*.txt` | **Nuevas.** Aviso de caducidad. |
| `apps/notifications/models.py`, `apps/core/models.py` | Tipo `POINTS_EXPIRING`; acciones de auditoría `POINTS_EXPIRY_POLICY_CREATED`, `POINTS_EXPIRY_RUN` y `BIRTHDAY_SETTINGS_UPDATED`. |
| `apps/api/serializers/loyalty.py`, `owner.py`, `docs/api/openapi.yaml` | Campo `expired` y valor `EXPIRATION` en el enum de tipos. |
| `deploy/cron/crontab` | `expire_points && process_notifications` a las 04:40. |
| `static/css/app.css` | Recompilado (clases de rejilla nuevas). |

**Rutas nuevas** (solo propietario, solo POST): `/dashboard/configuracion/caducidad/` y `/dashboard/configuracion/cumpleanos/`.

## 6. Migraciones

| Migración | Contenido | Riesgo |
|---|---|---|
| `loyalty/0004_points_expiry_birthday_message` | Crea `PointsExpiryPolicy` y `BirthdayMessage`; amplía el `CHECK` `loyalty_points_kind_valid` con `EXPIRATION` y añade `loyalty_points_expiration_shape`. | Bajo: solo añade. El `CHECK` ampliado acepta todas las filas existentes. No toca el modelo de usuario ni datos. |
| `notifications/0002_points_expiring_kind` | Choices de `kind`. | Ninguno: no cambia la base de datos. |
| `core/0010_audit_actions_phase14` | Choices de `action`. | Ninguno: no cambia la base de datos. |

Reversibles con `migrate loyalty 0003`, `migrate notifications 0001` y `migrate core 0009`. Para revertir `loyalty` no puede haber movimientos `EXPIRATION`: el `CHECK` anterior los rechazaría.

## 7. Configuración y operación

- **Sin variables de entorno nuevas.**
- **Aplicar las migraciones** en cada entorno: `python manage.py migrate`.
  - **Base de desarrollo `caneca_furada` (PostgreSQL 17 local): aplicadas el 2026-10-16.** Antes se comprobó que no había movimientos con tipos fuera de la lista nueva, ni tablas o restricciones con los mismos nombres, y se revisó el SQL (`sqlmigrate`, todo en una transacción). Se hizo una copia con `pg_dump -Fc`. Después: `migrate --check` sin pendientes, `check` sin incidencias, `expire_points` sin efecto (no hay caducidad configurada) y Configuración, Puntos y Promociones cargan con 200.
  - **Producción:** las aplica el servicio `migrate` durante el despliegue (`deploy/scripts/deploy.sh`).
  - **Otras bases** (`db.sqlite3`, `demo.sqlite3`, bases de `pruebas_dev/`): se migran al usarlas, con su `DATABASE_URL`.
- **Tarea programada:** `expire_points` y después `process_notifications`, a diario. En Docker Compose ya lo programa el servicio `scheduler`. Va después de `expire_redemptions` para que los puntos devueltos por un canje caducado recuperen su fecha antes de calcular.
- Sin caducidad configurada, el comando no hace nada y lo indica.
- **Probar en desarrollo:** `python manage.py expire_points --at AAAA-MM-DD` simula otra fecha (solo con `DEBUG=True`). Ver [pruebas_dev/pruebas.md](../pruebas_dev/pruebas.md).

## 8. Seguridad y privacidad

- **Autorización en el servidor:** los servicios exigen el rol de propietario (`PermissionDenied`). Las vistas usan además `owner_required`, `require_POST` y `never_cache`; un empleado o un cliente recibe 403 y un anónimo va al login.
- **Sin asignación masiva:** `counts_from`, `valid_from` y `created_by` los fija el servidor. Un `counts_from` enviado en el POST se ignora (hay test).
- **Validación** en el formulario y de nuevo en el servicio (tipos, rangos, longitudes, marcadores), con `CHECK` en la base de datos para rangos, coherencia de la política, forma del movimiento y fila única.
- **Plantillas:** el texto del propietario nunca pasa por el motor de plantillas. Los emails son texto plano.
- **Auditoría sin texto libre:** la de la política registra meses, días y fechas (no el motivo); la del regalo registra activo, puntos y qué textos cambiaron (no los textos); la de la ejecución solo recuentos.
- **Avisos:** el contexto guardado no incluye datos personales. Los logs solo registran `public_id` y puntos.
- **Concurrencia e idempotencia:** bloqueo de fila del cliente, cálculo dentro de la transacción y `dedup_key` única en los avisos.

## 9. Tests

| Archivo | Tests | Qué cubre |
|---|---|---|
| `tests/loyalty/test_expiry.py` | 35 | Suma de meses y fin de mes; FIFO (consumo parcial, compra compensada, canje devuelto con su fecha original, `counts_from`, agrupación por día); idempotencia; política (permisos, validación, `counts_from` en cada caso, sin versión si no hay cambios, auditoría sin texto, `CHECK` en la base de datos); caducidad sin retroactividad; auditoría de la ejecución; no se compensa una caducidad; `CHECK` del movimiento; resumen y estadísticas; avisos (ventana por días, uno por vencimiento, nunca a cuentas inactivas o sin verificar, contenido del email); comando (`--at` solo con `DEBUG`); «Mis puntos»; **concurrencia real** de caducidad y canjes simultáneos (PostgreSQL). |
| `tests/loyalty/test_birthday_settings.py` | 16 | Creación de la promoción; puntos nuevos solo para los regalos siguientes; desactivar pausa todas, también las programadas; reactivar una terminada; sin cambios no se audita; permisos; validación de puntos y textos (llaves, una línea, longitudes, normalización); auditoría sin textos; email personalizado con `{puntos}` y pie de baja; texto por defecto; **la sintaxis de plantilla guardada no se interpreta**; los avisos en cola conservan su texto; SMS con marca y enlace de baja. |
| `tests/dashboard/test_settings_phase14.py` | 12 | La página muestra las secciones; solo POST; 403 a empleado y cliente, login para anónimos; activar y quitar la caducidad; `counts_from` del cliente ignorado; datos no válidos → 400; sin versión nueva si no hay cambios; guardar el regalo; sintaxis de plantilla → 400; puntos no válidos → 400; desmarcar pausa el regalo. |

**Tests existentes adaptados:**
- `tests/api/test_customer.py`: el resumen de la API incluye `expired`.
- `tests/demo/test_seed_demo_data.py`: la demo no genera `EXPIRATION`, porque no configura caducidad.

**Comandos ejecutados y resultados (2026-10-16, Windows, PostgreSQL 17 local):**

```text
python manage.py check --settings=config.settings.test                        → sin incidencias
python manage.py makemigrations --check --dry-run --settings=config.settings.test → No changes detected
python manage.py spectacular --validate --fail-on-warn --file docs/api/openapi.yaml → sin avisos
python manage.py test --settings=config.settings.test --parallel 1 --noinput  → 930 tests OK (867 previos + 63 nuevos), sin omitidos
```

Prueba de humo del comando sobre una base SQLite temporal:
1. Sin política: «no caducan».
2. Política de 12 meses con 100 puntos: a +350 días, nada.
3. A +370 días: 100 puntos caducados.
4. A +371 días: 0, es decir, idempotente.

**No ejecutado:** la suite en SQLite y la revisión visual en navegador.

## 10. Criterios de aceptación

| Criterio | Estado |
|---|---|
| El propietario activa, modifica y quita la caducidad desde Configuración | **Completa** |
| Caducidad por antigüedad (FIFO) y sin retroactividad | **Completa** |
| Descuento diario idempotente, atómico y seguro frente a concurrencia | **Completa** |
| Fecha de caducidad en «Mis puntos» y email de aviso previo | **Completa** |
| El propietario edita los puntos, la activación y el texto del aviso de cumpleaños | **Completa** |
| Validación y autorización en el servidor, con tests de accesos denegados | **Completa** |
| Migraciones pequeñas y revisadas | **Completa** |
| Documentación en `docs/` y `README.md` | **Completa** |
| Revisión visual en navegador | **Pendiente** |

## 11. Limitaciones, riesgos y pendientes

- **Comunicar el cambio a los clientes:** activar la caducidad cambia las condiciones del programa de puntos. Conviene informar a los clientes y reflejarlo en las condiciones o en el aviso legal. El código no garantiza el cumplimiento legal.
- **El email de aviso es transaccional:** si el propietario prefiere tratarlo como comunicación comercial, basta con añadir `POINTS_EXPIRING` a `PROMOTIONAL_KINDS` y ajustar el `CHECK` de categoría con una migración.
- **Coste del comando:** preselecciona clientes en SQL y calcula cliente a cliente leyendo sus movimientos. Es suficiente para el volumen de un local; con muchos miles de clientes convendría procesar por lotes.
- **Varias promociones de cumpleaños:** la pantalla edita una sola (§4). Si se crean más en el admin, pueden convivir; desactivar las pausa todas.
- **Pendiente para la app Flutter:** exponer `next_expiry` en la API.
- **Pendiente:** revisión visual de Configuración y «Mis puntos» en navegador.
