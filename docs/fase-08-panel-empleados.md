# Fase 8 — Panel de empleados

**Estado:** Completa (pendiente de probar en móviles y tablets físicos; ver §10).
**Fecha:** 2026-10-14.
**Depende de:** [Fase 5](fase-05-qr-compras.md) (QR, registro de compras y lector) y [Fase 7](fase-07-recompensas-canjes.md) (validación de canjes).

## 1. Objetivo y decisiones

Reunir en un panel web rápido y responsive todo lo que un empleado hace en la barra: ver su perfil, escanear QR, registrar compras, confirmar operaciones, validar canjes y consultar sus resultados. Solo con operaciones autorizadas y sin datos personales del cliente.

**Contradicción detectada y resuelta (2026-10-14, decisión del usuario):** el [plan](plan-de-fases.md) situaba en la Fase 8 "Eventos y reservas" y no tenía una fase para el panel (las Fases 5 y 7 habían creado sus pantallas). Nueva numeración: **8** Panel de empleados, **9** Dashboard del propietario, **10** Eventos y reservas, **11** API, auditoría, seguridad y preparación final para la app móvil. Ver la nota en el plan sobre las fases que quedan sin número.

| Cuestión no especificada | Decisión | Motivo |
|---|---|---|
| ¿Dónde vive el panel? | Nueva app **`apps.staff`**, solo presentación y sin modelos, en `/panel/` (decisión del usuario) | Las operaciones siguen en `apps.purchases` y `apps.rewards`; el panel solo las reúne |
| ¿Se reescriben las pantallas de compras y canjes? | **No**: se mantienen sus rutas, vistas y servicios (`/panel/compras/`, `/panel/canjes/`) y pasan a usar el layout del panel | Ya cumplían los requisitos de seguridad y estaban probadas; reescribirlas solo añadía riesgo |
| "Consulta de resultados" | Lista de **las operaciones propias** (compras registradas o canjes validados) por periodo (hoy, 7 o 30 días), con resumen y paginación | Es lo que necesita un empleado para comprobar su trabajo, sin ver el de los demás |
| ¿Y el propietario en el panel? | Puede usarlo para operar y ve también **solo lo suyo** | La vista global (todas las compras, estadísticas) es del dashboard (Fase 9) |
| "Perfil del empleado" | Solo lectura: nombre, email de acceso con su estado y rol, más enlaces a cambiar email y contraseña y a cerrar sesión | El nombre y el rol los cambia el propietario; un empleado no puede modificarlos |
| ¿Adónde va el empleado al entrar? | `/cuenta/` lo redirige a `/panel/` | Sustituye la antigua tarjeta "Mi cuenta" (`accounts/staff_home.html`, eliminada) |
| Confirmaciones visibles | Banner verde con icono "Compra registrada" / "Canje validado: entrega la recompensa" en el detalle, además del mensaje | Se ve de un vistazo en una pantalla pequeña |

## 2. Alcance y exclusiones

**Incluye:** app `apps.staff` (inicio, perfil, resultados), selectores de lectura en los módulos de dominio, layout y navegación común del panel, botones grandes, importe con letra grande, confirmaciones visibles, enlace "Panel" en la cabecera para el personal, tests y documentación.

**Excluye:**
- App separada para empleados (el panel es web responsive; ver §8).
- Ver operaciones de otros empleados, estadísticas globales o gestión de clientes, empleados, puntos o configuración (Fase 9).
- Anular compras (el estado `VOIDED` sigue reservado).
- Cualquier dato personal del cliente (§6).

## 3. Flujo del empleado

```text
Entrar (/cuenta/entrar/) ──► /cuenta/ ──► /panel/  (Inicio)
                                           │  «Hoy, por ti»: compras, importe registrado y canjes de hoy
     ┌──────────────────┬──────────────────┼──────────────────┬──────────────────┐
     ▼                  ▼                  ▼                  ▼                  
 Registrar compra   Validar canje     Mis resultados      Mi perfil
 /panel/compras/    /panel/canjes/    /panel/resultados/  /panel/perfil/
```

1. **Inicio.** Cuatro botones grandes y el resumen del día. Una barra fija de secciones (Inicio · Compra · Canje · Resultados · Perfil) aparece en todas las pantallas del panel y marca la sección actual.
2. **Registrar compra** (Fase 5):
   1. *Escanear:* "Abrir la cámara" lee el QR del cliente (cámara nativa o jsQR local; solo en `localhost` o HTTPS). Si la cámara no funciona, se teclea el código que aparece bajo el QR.
   2. *Confirmar:* se muestra solo el nombre abreviado («Lúa F.»). El empleado pregunta el nombre al cliente, introduce el importe (campo grande, teclado decimal) y pulsa "Registrar compra".
   3. *Resultado:* banner "Compra registrada", importe, puntos generados, fecha, estado y "Registrar otra compra". Un doble envío no duplica la compra ("Esta compra ya estaba registrada").
3. **Validar canje** (Fase 7):
   1. *Escanear* el código del canje del cliente (o teclearlo).
   2. *Comprobar:* recompensa, nombre abreviado del cliente, estado y caducidad. Si el código está usado, caducado o cancelado, aviso rojo "no entregues la recompensa" y no hay botón de validar.
   3. *Validar y entregar:* banner "Canje validado: entrega la recompensa". El código no vuelve a servir.
4. **Mis resultados:** pestañas Compras / Canjes y periodo Hoy / 7 días / 30 días. Cada fila enlaza al detalle de la operación. Muestra el resumen del periodo y pagina de 20 en 20.
5. **Mi perfil:** datos de acceso, cambio de email o contraseña y cierre de sesión.

**Errores:** QR o código no válido, cliente sin email verificado, importe incorrecto, código ya usado o caducado y demasiados intentos fallidos (bloqueo temporal) muestran un aviso rojo con `role="alert"` y el foco en el mensaje, sin registrar nada. Los mensajes son los de los servicios de las Fases 5 y 7.

## 4. Archivos creados o modificados

| Archivo | Cambio |
|---|---|
| `apps/staff/` (`apps.py`, `urls.py`, `views.py`, `forms.py`) | Nueva app: vistas `home`, `profile`, `results` (GET, `never_cache`, solo personal) y filtro de resultados |
| `apps/purchases/selectors.py` | `purchases_registered_by(staff, since=)` (con puntos, sin N+1) y `staff_purchases_summary(staff, since=)` (excluye anuladas) |
| `apps/rewards/selectors.py` | `validations_by(staff, since=)` |
| `apps/purchases/forms.py` | Importe con letra grande |
| `apps/accounts/views.py` | `home`: el empleado va a `staff:home` |
| `config/settings/base.py`, `config/urls.py` | `apps.staff` en `INSTALLED_APPS` y montada en `/panel/` |
| `templates/staff/` | `_layout.html` (barra de secciones), `home.html`, `profile.html`, `results.html`, `_summary.html`, `_done.html` |
| `templates/purchases/*.html`, `templates/rewards/staff_*.html` | Usan el layout del panel, botones `btn-lg`, banner de confirmación y "Volver al panel" |
| `templates/base.html` | Botón "Panel" para empleados y propietarios; el empleado ya no ve "Mi cuenta" (lleva al mismo sitio) |
| `templates/accounts/staff_home.html` | Eliminada (sustituida por `/panel/`) |
| `assets/css/input.css`, `static/css/app.css` | Componentes `btn-lg`, `panel-nav`, `panel-tile`, `stat`, `segmented`, `result-row`, `done-banner` |
| `tests/staff/test_panel.py` | Nuevos tests (§9) |
| `tests/accounts/test_admin.py`, `test_auth_views.py`, `test_profile.py`, `tests/purchases/test_views.py`, `tests/rewards/test_views.py` | Ajustados a la redirección de `/cuenta/` al panel |

Sin modelos ni migraciones nuevas (`makemigrations --check`: sin cambios). Sin dependencias ni variables de entorno nuevas.

## 5. Rutas

| Ruta | Nombre | Método | Quién |
|---|---|---|---|
| `/panel/` | `staff:home` | GET | Empleado y propietario |
| `/panel/perfil/` | `staff:profile` | GET | Empleado y propietario |
| `/panel/resultados/?tipo=compras\|canjes&periodo=hoy\|7d\|30d&page=N` | `staff:results` | GET | Empleado y propietario |
| `/panel/compras/…`, `/panel/canjes/…` | (Fases 5 y 7) | sin cambios | Empleado y propietario |

Un `tipo` o `periodo` desconocido se sustituye por el valor por defecto (compras, hoy); un número de página incorrecto muestra la página válida más cercana.

## 6. Seguridad y privacidad

- **Autorización en servidor:** todas las vistas usan `role_required(OWNER, EMPLOYEE)` (`apps.accounts.permissions`): sin sesión → login; cliente → 403; cuenta desactivada → pierde la sesión. Ocultar botones en la cabecera es solo comodidad.
- **Solo lectura:** las tres vistas nuevas aceptan solo GET (POST → 405). No hay formularios que cambien rol, nombre, puntos, saldos ni configuración; las únicas escrituras del panel son las de las Fases 5 y 7 (`register_purchase`, `validate_redemption`), que vuelven a comprobar el rol, el cliente y el estado dentro de su transacción.
- **Sin escalada:** el empleado no entra en el admin (solo propietarios) y los servicios de gestión (`ledger.adjust_points`, `reverse_movement`, `save_reward`, `change_role`, `set_user_active`) rechazan a quien no sea propietario. Hay tests de ambos casos.
- **IDOR:** los resultados se filtran por `registered_by` / `validated_by = request.user`, nunca por un parámetro. Los detalles siguen respondiendo 404 a operaciones de otros empleados (`visible_purchases`, `visible_redemptions_for_staff`).
- **Datos del cliente:** solo el nombre abreviado («Lúa F.»). **No se muestran** dirección, fecha de nacimiento, teléfono, email, saldo, historial del cliente ni el token de su QR. Los códigos de canje no aparecen en los resultados. Si una función futura necesitara un dato personal, deberá justificarse y protegerse con un permiso específico, no con el rol de empleado.
- **Datos del empleado:** el perfil muestra solo los suyos.
- **Caché y URLs:** respuestas `never_cache`. Los filtros de la URL no llevan datos personales; los códigos siguen viajando solo en el cuerpo de las peticiones POST.
- **XSS:** los parámetros se validan contra una lista cerrada y las plantillas escapan la salida (test con `tipo=<script>`).

## 7. Diseño móvil y tablet

- Objetivos táctiles de al menos 44 px; los botones principales (`btn-lg`) y la barra de secciones llegan a 48–56 px.
- Inicio con baldosas grandes (una columna en móvil, dos en tablet); la acción principal, "Registrar compra", en dorado.
- La barra de secciones se desplaza horizontalmente si no cabe, sin romper el diseño.
- Importe con letra grande y `inputmode="decimal"` (teclado numérico en el móvil).
- Confirmaciones con banner verde e icono; errores en rojo con `role="alert"`.
- Contraste de la paleta de la [Fase 3](fase-03-sistema-diseno-web-publica.md) (AA). El verde de confirmación (`ok`) y el rojo de error (`danger`) ya estaban validados sobre negro.

## 8. Preparación para la app

El panel es una interfaz web responsive; no se ha creado una app de empleados. Las pantallas solo llaman a servicios y selectores de dominio que la API de la Fase 11 podrá exponer sin duplicar lógica:

| Operación | Servicio / selector | Endpoint previsto (Fase 11) |
|---|---|---|
| Identificar cliente por QR | `purchases.services.identify_for_purchase` | `POST /api/v1/staff/purchases/identify` |
| Registrar compra | `purchases.services.register_purchase` | `POST /api/v1/staff/purchases` |
| Comprobar / validar canje | `rewards.services.lookup_redemption` / `validate_redemption` | `POST /api/v1/staff/redemptions/lookup` / `validate` |
| Mis compras | `purchases.selectors.purchases_registered_by` | `GET /api/v1/staff/me/purchases?since=` |
| Mis canjes validados | `rewards.selectors.validations_by` | `GET /api/v1/staff/me/redemptions?since=` |
| Resumen | `purchases.selectors.staff_purchases_summary` + `validations_by().count()` | `GET /api/v1/staff/me/summary?since=` |
| Mi perfil | `request.user` (campos explícitos: nombre, email, rol) | `GET /api/v1/me` |

## 9. Tests y resultados reales

`tests/staff/test_panel.py` (31 tests):
- **Acceso:** anónimo → login; cliente → 403; empleado y propietario → 200; empleado desactivado → login; POST → 405 y el rol no cambia; `Cache-Control: no-store`; `/cuenta/` lleva al panel.
- **Escalada:** el empleado no abre el admin (índice, lista y ficha de usuarios), no puede ajustar puntos (`PermissionDenied`, saldo intacto) y el panel no ofrece campos de rol ni de puntos.
- **Inicio:** acciones y navegación; el resumen del día cuenta solo las operaciones propias de hoy; enlace "Panel" solo para el personal.
- **Perfil:** datos propios y enlaces de cuenta, sin datos de otros.
- **Resultados:** por defecto compras de hoy; solo las propias (también para el propietario); detalle ajeno → 404; filtros por periodo con límites de 5, 20 y 40 días; medianoche local; canjes validados (sin el código y sin los pendientes); filtros desconocidos y `<script>`; paginación y página fuera de rango; estados vacíos; número de consultas constante.
- **Privacidad:** ninguna página del panel contiene email, nombre completo, dirección, código postal, teléfono, año de nacimiento, token QR ni saldo del cliente.
- **Flujos completos por las vistas:** escaneo → confirmación → compra registrada con banner → aparece en resultados y en el resumen; QR no válido → error y nada registrado; canje escaneado → validado con banner → aparece en resultados; código ya usado → error y una sola validación.
- **Selector:** el resumen excluye compras anuladas.

Comandos ejecutados (2026-10-14, SQLite de desarrollo, Python 3.14):

```text
python manage.py check                                  → System check identified no issues (0 silenced).
python manage.py makemigrations --check --dry-run       → No changes detected
python manage.py test tests.staff --settings=config.settings.test → Ran 31 tests … OK
python manage.py test --settings=config.settings.test   → Ran 580 tests … OK (skipped=3)
python scripts/tailwind.py build                        → CSS recompilado
```

Los 3 tests omitidos son los de concurrencia de fases anteriores, que solo se ejecutan contra PostgreSQL.

## 10. Limitaciones, riesgos y pendientes

- **Sin prueba en dispositivos físicos:** el diseño se ha comprobado con los tests y revisando las clases; falta probarlo en un móvil y una tablet reales, incluido el escaneo con cámara (pendiente ya desde la Fase 5). La cámara necesita HTTPS fuera de `localhost`.
- **Sin prueba visual automatizada** (no hay herramientas de navegador configuradas en el proyecto).
- El propietario ve en el panel solo sus propias operaciones; la vista global llega con el dashboard (Fase 9).
- El resumen cuenta compras registradas en el programa, no la caja del local (se indica en pantalla).
- Fases sin número tras la reordenación (notificaciones completas y despliegue): ver el [plan](plan-de-fases.md).

## 11. Estado de los criterios de aceptación

| Criterio | Estado |
|---|---|
| Perfil del empleado | **Completa** (`/panel/perfil/`, solo lectura) |
| Escaneo QR | **Completa** (Fase 5, integrado en el panel; pendiente de prueba en dispositivos) |
| Registro de compras | **Completa** (Fase 5, integrado) |
| Confirmación de operaciones | **Completa** (paso de confirmación y banner de resultado) |
| Validación de canjes | **Completa** (Fase 7, integrado) |
| Consulta de resultados | **Completa** (`/panel/resultados/`) |
| Optimizado para móvil y tablet, botones grandes, mensajes claros | **Completa** (pendiente de prueba en dispositivos físicos) |
| Solo operaciones autorizadas; sin modificar roles, saldos ni configuración | **Completa** (con tests de escalada) |
| Sin dirección, fecha de nacimiento, teléfono ni historial privado | **Completa** (con tests) |
| Sin app separada; operaciones sobre servicios internos | **Completa** |
| Tests de escaneo, compras, canjes, errores y permisos | **Completa** |

## 12. Dependencias para las fases siguientes

- **Fase 9 (dashboard):** puede reutilizar `staff_purchases_summary` y `validations_by` para estadísticas por empleado, y los componentes `stat` y `segmented`.
- **Fase 11 (API):** endpoints del personal en §8, sobre los mismos servicios y selectores.
