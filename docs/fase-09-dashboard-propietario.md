# Fase 9 — Dashboard del propietario y estadísticas

> **Nota (2026-10-15):** el propietario ya no tiene el botón «Dashboard» en la cabecera: entra con «Mi cuenta», que lo redirige al dashboard. Ver [fase-03 §14](fase-03-sistema-diseno-web-publica.md#14-ajuste-de-la-cabecera-2026-10-15).

> **Nota (Fase 10, 2026-10-14):** las secciones Eventos y Reservas, las cifras del resumen y la sección Comunicaciones ya son reales; el contenido editable añade los textos del inicio. Ver [fase-10-eventos-reservas-notificaciones.md](fase-10-eventos-reservas-notificaciones.md).

**Estado:** Completa (pendiente de revisión visual en navegador y de validar en PostgreSQL; ver §11).
**Fecha:** 2026-10-14.
**Depende de:** Fases 2–8. La gestión de eventos y reservas se añadirá al dashboard en la [Fase 10](plan-de-fases.md).

## 1. Objetivo y decisiones

Dar al propietario un dashboard profesional en `/dashboard/` para administrar el negocio: resumen con estadísticas reales, clientes (búsqueda, filtros, ficha y estadísticas geográficas), empleados, compras, puntos, recompensas, carta, cervezas, promociones, contenido del local y configuración. Sin datos inventados y con la lógica de negocio fuera del dashboard.

Decisiones tomadas por el usuario al empezar la fase (2026-10-14):

| Cuestión | Decisión |
|---|---|
| ¿Cuánta gestión tiene el dashboard? | **Híbrido:** listados, filtros, estadísticas y acciones rápidas sobre servicios existentes (publicar/archivar, agotado, activar/pausar, ajustar y compensar puntos, alta/baja/rol de empleados, conversión de puntos). La creación y edición de fichas completas (con imágenes y muchos campos) enlaza al admin. |
| Sección «Contenido» | **Editable:** nuevo modelo `web.BusinessInfo` (dirección, horario, email, teléfono, redes y presentación) que usa la web pública. |
| Eventos y Reservas | **Visibles como «Disponible en la Fase 10»**, sin cifras (nunca un 0 falso). |

Otras decisiones (menores, adoptadas y documentadas aquí):

| Cuestión | Decisión | Motivo |
|---|---|---|
| ¿Quién tiene «los permisos» de gestión de clientes? | Solo el rol **OWNER** activo. No hay permisos más finos. | Es lo que define el modelo de roles; un permiso granular futuro puede añadirse en los selectores sin tocar las plantillas. |
| ¿Adónde va el propietario al entrar? | `/cuenta/` lo lleva a `/dashboard/` (antes al admin). Cabecera: «Dashboard» y «Panel». | El dashboard es su herramienta principal; el admin sigue disponible. |
| Búsqueda de clientes | Se envía por **POST** y se guarda en la sesión; los filtros no identificativos (país, provincia, localidad, CP, verificación, periodo) van en la URL. | Política del proyecto: no exponer datos personales (nombre, email) en URLs ni en logs. |
| ¿Se audita la consulta de una ficha? | Sí: `AuditEvent CUSTOMER_DATA_VIEWED` (quién, cuándo, `public_id` del cliente; sin datos). | Trazabilidad del acceso a datos personales. |
| Base de las estadísticas geográficas | Clientes **activos**; «Clientes dados de alta» en el periodo o «Clientes con compras» en el periodo. Agrupación sin distinguir mayúsculas y siempre junto al país. | Evita contar cuentas dadas de baja y mezclar zonas homónimas de otro país. |
| Compensar movimientos de canje | **Bloqueado en el dominio** (`ledger.reverse_movement`). | Ver §6: devolvía los puntos dejando el canje pendiente o usado. |

## 2. Alcance y exclusiones

**Incluye:** app `apps.dashboard` (solo presentación), selectores de solo-propietario en `accounts`, `purchases`, `loyalty`, `rewards` y `catalog`; servicios de cambio de estado de recompensas y promociones; modelo y servicios de contenido del local; dos acciones de auditoría nuevas; componentes CSS del dashboard; tests y documentación.

**Excluye:**
- Formularios propios de alta/edición de productos, cervezas, recompensas y promociones (siguen en el admin, enlazado desde cada sección).
- Eventos y reservas (Fase 10).
- Exportaciones (CSV/Excel), gráficos de evolución temporal y envío de promociones.
- Anulación de compras (el estado `VOIDED` sigue reservado).
- Permisos más finos que el rol de propietario.

## 3. Secciones

Barra de secciones lateral en escritorio y deslizable en móvil. Todas las listas paginan de 25 en 25 y aceptan el filtro de **periodo**: Hoy, 7 días, 30 días (por defecto), 90 días, 12 meses, Todo o Personalizado (desde–hasta, ambos días incluidos, máximo 10 años; un rango incorrecto avisa y aplica el periodo por defecto).

| Sección | Ruta | Qué muestra | Acciones |
|---|---|---|---|
| **Resumen** | `/dashboard/` | Clientes registrados (activos y altas del periodo), compras registradas, importe de compras registradas (y media), puntos emitidos, puntos canjeados, recompensas utilizadas, Reservas y Eventos «Disponible en la Fase 10», top 5 de localidades | — |
| **Clientes** | `/dashboard/clientes/` | Listado: nombre, email, verificación, fecha de alta, estado. Búsqueda por nombre/apellidos/email; filtros: alta en el periodo, verificado, activo, acepta emails promocionales, país, provincia, localidad, CP | Abrir ficha |
| Ficha del cliente | `/dashboard/clientes/<public_id>/` | Nombre, apellidos, email y verificación, dirección postal, teléfono, fecha de nacimiento, fecha de registro, estado, preferencias de comunicación con su historial, actividad de fidelización (saldo, obtenidos, utilizados, corregidos; últimas 10 compras y canjes; últimos 20 movimientos) | Ajuste manual de puntos (motivo obligatorio, idempotente), compensar un movimiento |
| Estadísticas geográficas | `/dashboard/clientes/zonas/` | Clientes por país, provincia, localidad o código postal: recuento, % y barra; «Otras zonas» y «Sin dato en el perfil». Cada zona enlaza al listado filtrado | — |
| **Empleados** | `/dashboard/empleados/` | Personal (nombre, email, rol, estado) con compras, importe y canjes validados en el periodo | Alta de empleado, dar de baja/reactivar, cambiar rol Empleado↔Propietario (con confirmación). No sobre uno mismo |
| **Compras** | `/dashboard/compras/` | Totales del periodo y listado global (fecha, cliente, importe, puntos, empleado, estado); filtros por empleado y estado | — |
| **Puntos** | `/dashboard/puntos/` | Emitidos, canjeados, corregidos y saldo pendiente total; conversión vigente; movimientos de todos los clientes con filtro por tipo | (Ajustes y compensaciones desde la ficha del cliente) |
| **Recompensas** | `/dashboard/recompensas/` | Catálogo con coste, estado, unidades, utilizadas y pendientes; canjes del periodo (solicitados, utilizados, cancelados/caducados, pendientes ahora) con filtro por estado. **Sin códigos** | Activar, pausar, archivar; «Nueva» y «Editar» en el admin |
| **Carta** | `/dashboard/carta/` | Productos fijos con categoría, precio, publicación y disponibilidad; filtros por publicación y categoría | Publicar, borrador, archivar, agotado/disponible; crear y editar en el admin |
| **Cervezas** | `/dashboard/cervezas/` | Igual que Carta para cervezas propias, invitadas y rotativas (tipo, estilo, graduación) y estado de la carta de grifos | Igual que Carta |
| **Eventos** / **Reservas** | `/dashboard/eventos/`, `/dashboard/reservas/` | «Disponible en la Fase 10» | — |
| **Promociones** | `/dashboard/promociones/` | Tipo, bonificación, vigencia, estado y usos | Activar, pausar, finalizar; crear y editar en el admin |
| **Contenido** | `/dashboard/contenido/` | Formulario del contenido público del local | Guardar (validado y auditado) |
| **Configuración** | `/dashboard/configuracion/` | Conversión de puntos vigente e historial; valores fijados en los ajustes del servidor (solo lectura) | Nueva conversión (no altera los puntos ya concedidos) |

> **Ajuste posterior (2026-10-17):** las listas de **Carta** y **Cervezas** usan, como la de Eventos, el modificador `.data-table-fit` (`assets/css/input.css`) para que no haya que desplazarse a los lados. Desde `xl` (1280 px) se muestra una tabla compacta: cabeceras en dos líneas y botones de disponibilidad y de acciones apilados. Por debajo, cada producto es una tarjeta con la etiqueta de cada celda (`data-label`). En Cervezas, tipo, estilo y graduación van en una sola columna («Propia · IPA · 6,5 %») para que la tabla quepa. Solo cambia el aspecto: formularios, CSRF y permisos son los mismos. Test: `tests/dashboard/test_customers_and_actions.py::test_beers_and_menu_sections_split_products`.

### Estadísticas: definiciones

- **Clientes registrados:** cuentas de cliente activas (las desactivadas no cuentan). «+N en el periodo»: altas activas del periodo.
- **Compras registradas / importe:** solo compras vigentes (no anuladas) anotadas por el personal con el QR del cliente. **No es la facturación total del local**: el dashboard lo indica junto a la cifra y nunca muestra ni estima una facturación (`business_revenue` es siempre `None`).
- **Puntos emitidos / canjeados:** definiciones de la [Fase 6](fase-06-fidelizacion.md) (`points_stats`): emitidos = movimientos positivos salvo devoluciones de canjes; canjeados = canjes menos sus devoluciones.
- **Recompensas utilizadas:** canjes validados en barra (`USED`) en el periodo, por fecha de validación.
- **Estadísticas geográficas:** proceden **solo de las direcciones postales declaradas por los propios clientes** (la página lo indica). No se usa geolocalización por IP ni se infieren domicilios. Los gráficos solo muestran la zona (país, provincia, localidad o CP), nunca la dirección completa. Porcentaje = clientes de la zona / total de la base filtrada, con un decimal; la barra es proporcional a la zona con más clientes y el valor siempre aparece en texto.

## 4. Archivos creados o modificados

| Archivo | Cambio |
|---|---|
| `apps/dashboard/` (`apps.py`, `urls.py`, `views.py`, `forms.py`) | Nueva app: 24 rutas, filtros de periodo y formularios de acción |
| `apps/accounts/selectors.py` | **Nuevo:** `search_customers`, `customer_for_owner`, `preference_history`, `customer_counts`, `geographic_distribution`, `staff_members`, `staff_member` |
| `apps/accounts/services.py` | `record_customer_data_access` (auditoría de la ficha) |
| `apps/accounts/views.py` | El propietario va a `dashboard:home` al entrar |
| `apps/purchases/selectors.py` | `all_purchases`, `purchases_by_staff`, `customer_ids_with_purchases` |
| `apps/loyalty/selectors.py` | `all_movements`, `reversible_ids`, `promotions_overview` |
| `apps/loyalty/promotions.py` | `set_promotion_status`, `MANAGEABLE_STATUSES` |
| `apps/loyalty/conversion.py` | `rule_history` |
| `apps/loyalty/ledger.py` | `reverse_movement` rechaza movimientos de canje (§6) |
| `apps/rewards/selectors.py` | `redemption_stats`, `all_redemptions`, `rewards_overview`, `validations_by_staff` |
| `apps/rewards/services.py` | `set_reward_status`, `MANAGEABLE_REWARD_STATUSES` |
| `apps/catalog/selectors.py` | `products_for_management` |
| `apps/web/models.py`, `apps/web/services.py` | **Nuevos:** `BusinessInfo` (fila única) y `business_info` / `update_business_info` |
| `apps/web/context_processors.py`, `apps/web/content.py` | Las plantillas reciben `business` desde `services.business_info()` |
| `apps/core/models.py` | Acciones `CUSTOMER_DATA_VIEWED` y `SITE_CONTENT_UPDATED` |
| `config/settings/base.py`, `config/urls.py` | `apps.dashboard` instalada en `/dashboard/` |
| `templates/dashboard/` | Layout, parciales (periodo, paginación) y una plantilla por sección |
| `templates/base.html` | Botón «Dashboard» para propietarios |
| `assets/css/input.css`, `static/css/app.css` | Componentes `dash-nav`, `filters`, `data-table`, `bar-track`/`bar-fill`, `btn-sm`, `textarea` |
| `tests/dashboard/` | Nuevos tests (§9) |
| `tests/accounts/test_auth_views.py` | El propietario va al dashboard |

### Migraciones (revisadas)

- `core/0007_audit_actions_phase9`: solo cambia las `choices` de `AuditEvent.action` (sin cambio de esquema real).
- `web/0001_business_info`: crea la tabla `web_businessinfo` con `CHECK (id = 1)` (fila única). Sin datos iniciales: mientras esté vacía, la web se comporta exactamente como antes.

Ambas son reversibles y no tocan el modelo de usuario. `makemigrations --check`: sin cambios pendientes. Sin dependencias ni variables de entorno nuevas.

## 5. Separación de responsabilidades y preparación para la app

El dashboard **solo presenta**: no contiene reglas de negocio ni consultas propias sobre datos sensibles. Cada lectura pasa por un selector de dominio que **vuelve a comprobar que el actor es propietario** (`PermissionDenied` en otro caso, con tests directos sobre los selectores), y cada escritura por un servicio existente con su transacción, validación y auditoría. La futura API (Fase 11) podrá exponer lo mismo sin duplicar lógica:

| Operación | Selector / servicio | Endpoint previsto (Fase 11) |
|---|---|---|
| Resumen | `customer_counts`, `registered_purchases_stats`, `points_stats`, `redemption_stats` | `GET /api/v1/owner/stats?from=&to=` |
| Clientes | `accounts.selectors.search_customers` | `GET /api/v1/owner/customers?…` (búsqueda en el cuerpo o parámetro no registrado en logs) |
| Ficha | `customer_for_owner` + `record_customer_data_access` | `GET /api/v1/owner/customers/{public_id}` |
| Zonas | `geographic_distribution` (+ `customer_ids_with_purchases`) | `GET /api/v1/owner/stats/geo?level=&base=` |
| Ajuste / compensación | `ledger.adjust_points` / `ledger.reverse_movement` | `POST /api/v1/owner/customers/{id}/points/adjustments` / `…/reversals` |
| Empleados | `staff_members`, `create_employee`, `set_user_active`, `change_role` | `GET/POST /api/v1/owner/staff`, `PATCH …/{id}` |
| Compras, puntos, canjes | `all_purchases`, `all_movements`, `all_redemptions` | `GET /api/v1/owner/purchases`, `…/movements`, `…/redemptions` |
| Estados | `set_reward_status`, `set_promotion_status`, `set_product_status`, `set_product_availability` | `PATCH` sobre cada recurso |
| Contenido / conversión | `update_business_info` / `conversion.create_rule` | `PUT /api/v1/owner/content`, `POST /api/v1/owner/loyalty-rules` |

## 6. Seguridad y privacidad

- **Autorización en servidor:** todas las vistas usan `role_required(OWNER)`: sin sesión → login; empleado o cliente → 403; propietario desactivado → pierde la sesión. Los selectores y servicios lo vuelven a comprobar. Tests de acceso denegado y de escalada (un empleado no puede ajustar puntos, crear empleados, cambiar roles o estados, editar contenido ni la conversión, ni siquiera conociendo las URLs).
- **Empleados y datos personales:** los empleados **no** acceden a la dirección postal ni a la fecha de nacimiento (ni al dashboard). Su panel (Fase 8) sigue mostrando solo el nombre abreviado.
- **Exposición mínima:** el listado de clientes muestra nombre, email, verificación, alta y estado; la dirección, el teléfono y la fecha de nacimiento solo aparecen en la ficha (tests). Las estadísticas geográficas nunca muestran direcciones completas. Los códigos de canje no aparecen en ninguna página del dashboard.
- **URLs y logs:** la búsqueda por nombre o email no viaja en la URL (POST + sesión). Los objetos se identifican por `public_id`. Los enlaces «Editar» al admin usan la clave interna, como ya hacía el admin (solo propietarios).
- **Auditoría:** consulta de fichas (`CUSTOMER_DATA_VIEWED`), contenido (`SITE_CONTENT_UPDATED`, solo nombres de campos) y las acciones ya auditadas de los servicios reutilizados (ajustes, compensaciones, roles, altas, estados, conversión). Sin datos personales en los metadatos.
- **IDOR:** compensar exige que el movimiento sea del cliente de la URL (otro → 404); la ficha responde 404 a empleados, propietarios o identificadores inexistentes; el cambio de rol solo admite personal y solo los roles Empleado/Propietario.
- **CSRF / métodos:** todas las acciones son POST con token CSRF; las rutas de acción rechazan GET (405). Respuestas `never_cache`.
- **XSS e inyección:** filtros contra listas cerradas o texto acotado; ORM parametrizado; las plantillas escapan la salida; las redes sociales solo admiten `https://` (se rechaza `javascript:`), con test.
- **Operaciones duplicadas:** el ajuste de puntos lleva una referencia de idempotencia generada al mostrar el formulario; un doble envío no duplica (test). Compensar dos veces no duplica (restricción `OneToOne`).
- **Auto-bloqueo:** el propietario no puede darse de baja ni cambiarse el rol desde el dashboard; los servicios ya impedían quedarse sin propietario activo.
- **Problema encontrado y corregido:** `ledger.reverse_movement` permitía compensar un movimiento `REDEMPTION`, lo que devolvía los puntos al cliente con el canje todavía pendiente o ya usado (doble beneficio). No estaba expuesto en ninguna interfaz; ahora el servicio lo rechaza (`code="redemption_reversal"`) y el dashboard no ofrece el botón. Las devoluciones legítimas siguen por `cancel_redemption`/caducidad.
- **Aviso:** este código aplica medidas técnicas de minimización y trazabilidad, pero no garantiza por sí solo el cumplimiento del RGPD (base jurídica, información a los clientes, plazos de conservación siguen pendientes de decisión del propietario).

## 7. Contenido del local

- `BusinessInfo` guarda dirección pública del local, horario («Días | horario» por línea), email, teléfono, redes («Nombre | https://…» por línea, solo https) y la presentación. El nombre y la ciudad siguen fijos en `content.BUSINESS`.
- Lo que está vacío se muestra como «Pendiente de publicar», igual que antes: no se inventa nada.
- `business_info()` se guarda en la caché 5 minutos y la edición la invalida al confirmar la transacción. Con la caché por defecto (memoria local), otros procesos del servidor pueden tardar hasta 5 minutos en ver el cambio; en producción conviene una caché compartida (`CACHE_URL`, ya configurable).

## 8. Cómo usarlo

1. `python manage.py migrate` (aplica `core.0007` y `web.0001`).
2. Entra con la cuenta de propietario (`python manage.py create_owner` si aún no existe): llegas a `/dashboard/`.
3. Para probar con datos ficticios: crea un empleado en *Empleados*, registra clientes desde la web pública y compras desde el panel (`/panel/compras/`).

## 9. Tests y resultados reales

`tests/dashboard/` (59 tests):
- `test_access.py` — anónimo → login; empleado y cliente → 403 en las 15 páginas; propietario → 200 con `no-store`; propietario desactivado → login; redirección y enlace «Dashboard»; acciones con GET → 405; **escalada**: el empleado no puede ajustar puntos, crear empleados, cambiar roles o estados, recompensas, promociones, contenido ni conversión, y su intento no audita fichas; los 14 selectores de solo-propietario y 3 servicios rechazan a empleados y clientes.
- `test_stats.py` — cifras reales del resumen (compras anuladas excluidas, importe, puntos emitidos y canjeados, recompensas utilizadas); aviso «no es la facturación total» y `business_revenue = None`; eventos y reservas sin cifras; filtros de periodo (preset, rango inclusivo, rango inválido, valor desconocido o `<script>`); filtros de compras por empleado y estado; estadísticas por empleado; puntos y canjes por tipo/estado; los códigos de canje no aparecen; **geografía**: agrupación por localidad sin distinguir mayúsculas, país, provincia (con su país) y CP, porcentajes, «sin dato», exclusión de cuentas desactivadas, filtro por país y límite con «otras zonas», base por altas o por compras del periodo, aviso de la fuente y sin direcciones ni emails.
- `test_customers_and_actions.py` — listado sin dirección, CP, teléfono ni fecha de nacimiento; búsqueda por POST fuera de la URL, por varios términos y borrado; filtros; el personal no aparece como cliente; ficha con los datos autorizados y la actividad, auditada sin datos; 404 para personal o ids inexistentes; cliente sin perfil; ajuste idempotente, sin saldo negativo ni motivo vacío; compensación única, IDOR de movimientos ajenos → 404; canjes no compensables; alta de empleado y errores; baja/reactivación; sin auto-baja ni auto-cambio de rol; cambio de rol con confirmación y nunca a cliente; estados de recompensas, promociones y productos con auditoría y redirección a su sección; separación Carta/Cervezas; contenido publicado en la web y auditado, vacío = pendiente, enlaces inseguros rechazados, salida escapada; nueva conversión y valores no válidos.

Comandos ejecutados (2026-10-14, SQLite de desarrollo, Python 3.14):

```text
python manage.py check                                     → System check identified no issues (0 silenced).
python manage.py makemigrations --check --dry-run          → No changes detected
python manage.py test tests.dashboard --settings=config.settings.test → Ran 59 tests … OK
python manage.py test --settings=config.settings.test      → Ran 639 tests … OK (skipped=3)
python manage.py migrate                                   → Applying core.0007_audit_actions_phase9… OK; Applying web.0001_business_info… OK
python scripts/tailwind.py build                           → CSS recompilado
```

Los 3 tests omitidos son los de concurrencia de fases anteriores, que solo se ejecutan contra PostgreSQL.

## 10. Estado de los criterios de aceptación

| Criterio | Estado |
|---|---|
| Secciones Resumen, Clientes, Empleados, Compras, Puntos, Recompensas, Carta, Cervezas, Promociones, Contenido, Configuración | **Completa** |
| Secciones Eventos y Reservas | **Pendiente (Fase 10)**: visibles como «Disponible en la Fase 10», sin cifras inventadas |
| Perfiles de clientes con los datos pedidos, búsqueda y filtros | **Completa** |
| Listados con campos mínimos; ficha con los datos autorizados | **Completa** (con tests) |
| Estadísticas geográficas por país, provincia, localidad y CP, con periodo, recuentos y % | **Completa** |
| Sin direcciones completas en gráficos, sin geolocalización por IP, fuente indicada | **Completa** (con tests) |
| Estadísticas de negocio reales; compras registradas ≠ facturación | **Completa** (reservas y eventos: Fase 10) |
| Solo el propietario accede; empleados sin dirección ni fecha de nacimiento | **Completa** (con tests de escalada) |
| Lógica de negocio independiente del dashboard | **Completa** (selectores y servicios con su propio control de permisos) |
| Pruebas de permisos, estadísticas, filtros y privacidad | **Completa** |

## 11. Limitaciones, riesgos y pendientes

- **Sin revisión visual en navegador ni en dispositivos:** las páginas se han comprobado con los tests (todas responden y muestran los datos esperados); falta revisarlas a mano en escritorio, tablet y móvil. No hay herramientas de navegador automatizadas en el proyecto.
- **Sin validar en PostgreSQL:** la agrupación sin mayúsculas (`UPPER`) y los agregados son SQL estándar, pero los tests se han ejecutado en SQLite. En SQLite `UPPER` no convierte letras no ASCII (`ñ`, tildes): «a coruña» y «A CORUÑA» podrían quedar en grupos distintos; en PostgreSQL sí se agrupan.
- **Grupos pequeños:** una zona o código postal con 1–2 clientes puede identificar a personas concretas. Solo lo ve el propietario, que ya tiene acceso a las fichas; si en el futuro se comparten estadísticas con terceros habría que ocultar los grupos pequeños.
- **Caché del contenido** con memoria local: hasta 5 minutos de retraso entre procesos (§7).
- **Edición completa en el admin:** productos, recompensas, promociones, categorías, estilos y carta de grifos se crean y editan allí.
- La búsqueda guardada en la sesión se mantiene hasta que se borra o se cierra la sesión.
- Pendientes de decisión del propietario heredados: conversión por defecto (1 punto/€), plazo de recogida de canjes, contenidos del local (ahora editables), política de conservación de datos.

## 12. Dependencias para la fase siguiente

- **Fase 10 (eventos y reservas):** sustituir `pending_phase.html` en `dashboard:events` y `dashboard:reservations` por la gestión real, y añadir las cifras de reservas y eventos al resumen (`data-stat="reservations"` / `"events"`) desde selectores de `apps.events`, con la misma comprobación de propietario.
- **Fase 11 (API):** endpoints del propietario en §5, sobre los mismos selectores y servicios.
