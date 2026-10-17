# Plan de fases — Caneca Furada

El prompt maestro es la fuente de verdad de los requisitos. Este documento divide el trabajo en fases acotadas. **Solo se implementa la fase que se solicite explícitamente**; el plan puede ajustarse antes de comenzar cada fase.

| Fase | Nombre | Estado |
|------|--------|--------|
| 0 | Fundación del proyecto | **Completa** ([detalle](fase-00-fundacion.md)) |
| 1 | Proyecto base: perfil de cliente, módulos y preparación para la app | **Completa** ([detalle](fase-01-proyecto-base.md)) |
| 2 | Autenticación, registro, perfiles, verificación de email y permisos | **Completa** ([detalle](fase-02-registro-perfil-verificacion.md)) |
| 3 | Sistema de diseño y web pública | **Completa** ([detalle](fase-03-sistema-diseno-web-publica.md)) |
| 4 | Carta y cervezas | **Completa** ([detalle](fase-04-carta.md)) |
| 5 | QR personal y registro de compras manuales | **Completa** ([detalle](fase-05-qr-compras.md)) |
| 6 | Fidelización: ledger de puntos, promociones y base de cumpleaños | **Completa** ([detalle](fase-06-fidelizacion.md)) |
| 7 | Recompensas y canjes | **Completa** ([detalle](fase-07-recompensas-canjes.md)) |
| 8 | Panel de empleados | **Completa** ([detalle](fase-08-panel-empleados.md)) |
| 9 | Dashboard del propietario y estadísticas | **Completa** ([detalle](fase-09-dashboard-propietario.md)) |
| 10 | Eventos, reservas, contenido y notificaciones | **Completa** ([detalle](fase-10-eventos-reservas-notificaciones.md)) |
| 11 | API, auditoría, seguridad y preparación final para la app móvil | **Completa** ([detalle](fase-11-api-auditoria.md)) |
| 12 | Despliegue y endurecimiento | **Completa en local** ([detalle](fase-12-despliegue.md)); CI en verde; pendiente el VPS |
| 13 | Datos de demostración | **Completa** ([detalle](fase-13-datos-demo.md)) |
| 14 | Caducidad de puntos y regalo de cumpleaños configurables | **Completa** ([detalle](fase-14-caducidad-puntos-cumpleanos.md)); pendiente revisión visual |
| 15 | Web en gallego con selector gallego/castellano | **Completa** ([detalle](fase-15-idioma-gallego.md)); pendientes la revisión nativa de las traducciones y la visual |
| 17 | Interruptor de reservas online | **Completa** ([detalle](fase-17-reservas-online.md)); pendiente revisión visual |
| 18 | Ordenar los listados del dashboard por columnas | **Completa** ([detalle](fase-18-ordenacion-listados.md)); pendiente revisión visual |
| 19 | Filtro «sin gasto», selección de clientes y campañas con imagen y puntos | **Completa** ([detalle](fase-19-campanas-seleccion.md)); pendientes revisión visual y prueba con SMTP real |
| Futuro | App móvil (Flutter) | Fuera del alcance actual |

---

## Fase 0 — Fundación del proyecto
- **Objetivo:** base técnica sobre la que construir sin rehacer migraciones de usuarios.
- **Incluye:** monolito modular Django, settings por entorno, `DATABASE_URL` (PostgreSQL objetivo), usuario personalizado con roles `OWNER/EMPLOYEE/CUSTOMER` antes de la primera migración, servicios de cuentas y roles, permisos reutilizables, auditoría mínima, comando `create_owner`, tests, documentación.
- **Criterios de aceptación:** `check` y `test` pasan; ningún flujo permite elegir rol al registrarse; el primer propietario se crea con un procedimiento seguro y auditado; documentación en `docs/` y `README.md`.

## Fase 1 — Proyecto base: perfil de cliente, módulos y preparación para la app
- **Depende de:** Fase 0.
- **Incluye:** revisión del prompt de la Fase 1 frente a lo construido en la Fase 0; `CustomerProfile` 1:1 mínimo (sin datos personales) creado en la misma transacción que el alta del cliente o el paso al rol CUSTOMER; migración de datos para clientes existentes; mapa de módulos; identificadores estables y guía para incorporar DRF ([arquitectura.md](arquitectura.md)).
- **Exclusiones:** campos personales del perfil y registro (Fase 2 tras la reordenación); apps de dominio vacías; DRF (Fase 11).
- **Criterios:** todo cliente creado por los servicios tiene exactamente un perfil; la creación es transaccional; migraciones revisadas y reversibles; `check`, `makemigrations --check` y tests superados.

> **Reordenación (2026-10-14):** el prompt de la Fase 2 pidió el registro, los perfiles y la verificación de email, que el plan inicial situaba en la Fase 3. Por decisión del usuario se intercambiaron: el registro pasa a ser la Fase 2 y el sistema de diseño la Fase 3. Las plantillas de cuenta de la Fase 2 son HTML sencillo y accesible que la Fase 3 integrará en el sistema de diseño. Los documentos de las Fases 0 y 1 conservan la numeración antigua.

## Fase 2 — Autenticación, registro, perfiles, verificación de email y permisos
- **Depende de:** Fases 0–1.
- **Incluye:** campos del `CustomerProfile`: dirección estructurada (`address_line_1`, `address_line_2`, `postal_code`, `city`, `province`, `country`), fecha de nacimiento (`DateField`, sin fechas futuras, límites documentados, 29 de febrero), teléfono opcional normalizado E.164; registro público solo CUSTOMER; login/logout; recuperación y cambio de contraseña; verificación de email con token seguro, caducidad, uso único, reenvío limitado y mensajes anti-enumeración; cambio de email con nueva verificación; preferencias de comunicación (email/SMS promocional) desactivadas por defecto y con historial de cambios; edición del perfil; emails transaccionales configurados por variables de entorno; activación/desactivación auditada de cuentas por el propietario; acciones permitidas con cuenta pendiente de verificación documentadas.
- **Criterios:** tests de registro, validación, verificación, tokens caducados/usados, reenvío, cambio de email, fecha de nacimiento, teléfono, dirección, preferencias, registro solo como cliente y acceso a perfiles ajenos; política de datos personales documentada.

## Fase 3 — Sistema de diseño y web pública
- **Depende de:** Fases 0–2.
- **Incluye:** Tailwind CSS mediante la CLI standalone (sin Node), plantilla base accesible y responsive con la paleta oficial y los recursos de `static/img/brand/`, navegación, páginas Inicio, La cervecería y Contacto, páginas de error. Integra las plantillas de cuenta de la Fase 2 (`templates/base.html`, `templates/accounts/`) en el sistema de diseño. Alpine.js/HTMX solo si aportan algo concreto.
- **Exclusiones:** modelos y gestión de Carta, Recompensas y Eventos.
- **Ajuste (2026-10-14, decidido por el usuario):** el prompt de la fase pidió también las páginas Carta, Recompensas y Eventos y las secciones del Inicio "Selección de cervezas" y "Eventos destacados". Se crearon con su diseño final y un estado vacío, sin datos inventados; las Fases 4, 7 y 8 rellenarán su contexto. Los datos del local quedan pendientes en `apps/web/content.py`.
- **Criterios:** sin horarios, precios ni datos inventados (los textos del negocio se marcan como pendientes de aportar por el propietario); contraste AA; responsive móvil/tablet/escritorio; tests de vistas públicas.

## Fase 4 — Carta y cervezas
- **Depende de:** Fases 0–1 y 3 (sistema de diseño).
- **Incluye:** categorías, productos fijos, cervezas propias/invitadas/rotativas, 14 grifos, estilos, graduación, precios `DecimalField` (2 decimales), imágenes validadas, disponibilidad, publicación y archivo sin borrar historial; gestión por el propietario sin tocar código; página pública Carta.
- **Criterios:** validación de precios e imágenes; solo OWNER gestiona; productos archivados no se borran.
- **Ajuste (2026-10-14, decidido por el usuario):** en lugar de modelar 14 grifos, el propietario sube una imagen de la carta de grifos (`TapMenu`) y la Carta reserva su hueco hasta entonces. Un único precio por producto; las cervezas agotadas se muestran como "Agotada"; la gestión se hace en el admin de Django.

> **Reordenación (2026-10-14, decidida por el usuario):** el prompt de la Fase 5 pidió el QR personal y el registro de compras manuales, sin puntos. Las compras (antes Fase 6) pasan a la Fase 5 y el ledger de puntos (antes en la Fase 5) pasa a la Fase 6.

## Fase 5 — QR personal y registro de compras manuales
- **Depende de:** Fases 2–3.
- **Incluye:** token QR opaco y aleatorio (sin datos personales) con rotación, vista del cliente con su QR, panel del personal (empleados y propietarios) con escaneo desde el navegador (nativo + jsQR local) o código tecleado, servicio transaccional e idempotente de compras manuales, resultados de sus operaciones, preparación para TPV futuro sin simularlo.
- **Criterios:** validación de personal, permisos, cliente activo, token, importe, idempotencia y estado; datos personales mínimos visibles; token fuera de logs; tests de QR, permisos, importe, duplicados, cliente inactivo y fallos transaccionales.

> **Ajuste de alcance (2026-10-14, decidido por el usuario):** el prompt de la Fase 6 pidió, además del ledger, un sistema de promociones, la base de las promociones de cumpleaños y distinguir compras registradas de facturación. Se adelantan a la Fase 6 sin envíos ni interfaz: la Fase 10 conserva el envío de notificaciones y la Fase 9 el dashboard. La "fecha de nacimiento verificada" se interpreta como la fecha validada del perfil más reglas anti-abuso, y las promociones dan puntos extra al registrar una compra.

## Fase 6 — Fidelización: ledger de puntos, promociones y base de cumpleaños
- **Depende de:** Fase 5.
- **Incluye:** ledger auditable e inmutable (saldo derivado, compensaciones), conversión importe→puntos configurable y versionada (`Decimal`, redondeo hacia abajo), generación de puntos en `purchases.services.on_purchase_registered` (misma transacción que la compra), promociones configurables (condiciones, fechas, límites, estado) que dan puntos extra, base de cumpleaños (detección, 29 de febrero, una por cliente y año, anti-abuso de la fecha, selección de destinatarios con consentimiento y email verificado, sin envíos), ajustes y compensaciones del propietario (servicio), vista del cliente con saldo e historiales, estadísticas mínimas (compras registradas ≠ facturación).
- **Criterios:** puntos solo calculados en backend; movimientos inmutables con compensaciones; tests de redondeo, duplicados, concurrencia, promociones e idempotencia.

## Fase 7 — Recompensas y canjes
- **Depende de:** Fases 5–6 (compras y ledger).
- **Incluye:** catálogo de recompensas gestionado por el propietario, solicitud de canje por el cliente, código de un solo uso, validación por empleado, movimientos de puntos y auditoría.
- **Criterios:** protección frente a doble consumo y concurrencia; tests de saldo insuficiente, código usado/caducado.
- **Implementado (2026-10-14):** los puntos se descuentan al solicitar el canje (movimiento `REDEMPTION`) y se devuelven con una compensación si el cliente cancela o el código caduca (30 días, configurable); un solo código pendiente por cliente y recompensa; validación por el personal en `/panel/canjes/`; comando `expire_redemptions` (su programación queda para la Fase 10).

> **Reordenación (2026-10-14, decidida por el usuario):** el prompt de la Fase 8 pidió el panel de empleados, que el plan no tenía como fase propia (las Fases 5 y 7 crearon sus pantallas). Nueva numeración: 8 Panel de empleados, 9 Dashboard del propietario, 10 Eventos y reservas (antes 8), 11 API, auditoría, seguridad y preparación final para la app móvil (antes 11 "API REST v1"). Las antiguas Fases 10 (notificaciones) y 12 (endurecimiento y despliegue) se conservan **sin número asignado** hasta que el usuario decida dónde van; su contenido no se ha descartado. Los documentos de fases anteriores conservan la numeración antigua en sus referencias.

## Fase 8 — Panel de empleados
- **Depende de:** Fases 5 y 7.
- **Incluye:** app `apps.staff` (solo presentación) en `/panel/` con inicio, perfil del empleado (solo lectura) y consulta de sus resultados (compras registradas y canjes validados por periodo); integración de las pantallas de escaneo, registro de compras y validación de canjes en un layout común responsive con botones grandes y confirmaciones visibles; selectores de lectura en `purchases` y `rewards`.
- **Exclusiones:** app separada de empleados, vista global de operaciones y gestión (Fase 9), anulación de compras, datos personales del cliente.
- **Criterios:** solo personal (servidor); sin modificar roles, saldos ni configuración; sin dirección, fecha de nacimiento, teléfono ni historial privado; tests de escaneo, compras, canjes, errores y permisos.
- **Implementado (2026-10-14):** ver [fase-08-panel-empleados.md](fase-08-panel-empleados.md).

## Fase 9 — Dashboard del propietario y estadísticas
- **Depende de:** Fases 2–8 (la gestión de eventos y reservas se añadirá al dashboard en la Fase 10).
- **Incluye:** gestión de clientes, empleados (alta/baja/rol vía servicios existentes), compras, puntos (interfaz para `ledger.adjust_points`/`reverse_movement`), recompensas y canjes (sobre `rewards.services.save_reward` y los selectores), carta, contenido editable y configuración de fidelización; estadísticas reales (sobre `purchases.selectors.registered_purchases_stats` y `loyalty.selectors.points_stats`) y geográficas (país, provincia, localidad, código postal) con filtros por periodo, sin direcciones completas.
- **Criterios:** acceso solo OWNER; las compras registradas no se presentan como facturación total; tests de permisos.
- **Implementado (2026-10-14):** app `apps.dashboard` en `/dashboard/` con modelo híbrido (acciones rápidas en el dashboard, fichas completas en el admin), contenido del local editable (`web.BusinessInfo`) y Eventos/Reservas visibles como «Fase 10» sin cifras (decisiones del usuario). Ver [fase-09-dashboard-propietario.md](fase-09-dashboard-propietario.md).

## Fase 10 — Eventos, reservas, contenido y notificaciones (antes Fase 8)
- **Depende de:** Fases 2–3, 6–7 y 9.
- **Incluye:** eventos gestionables (también desde el dashboard), solicitudes de reserva con estados `PENDING/CONFIRMED/REJECTED/CANCELLED/COMPLETED` y transiciones válidas, confirmación manual, notificaciones transaccionales de reserva.
- **Criterios:** transiciones validadas en servidor; datos de reservas protegidos; tests.
- **Ajuste de alcance (2026-10-14, decidido por el usuario):** el prompt de la fase incluyó la antigua fase «Notificaciones completas y promociones de cumpleaños» y la edición de los contenidos principales, que se implementan aquí. Decisiones: reservas de mesa o de evento solo para clientes verificados; el beneficio de cumpleaños pasa a ser un **regalo de puntos el mismo día** (sustituye la bonificación en compra de la Fase 6); tareas con comandos y el programador del sistema (sin Celery); campañas promocionales por email y textos del inicio editables. Ver [fase-10-eventos-reservas-notificaciones.md](fase-10-eventos-reservas-notificaciones.md).

## Fase 11 — API, auditoría, seguridad y preparación final para la app móvil
- **Depende de:** fases funcionales previas.
- **Incluye:** Django REST Framework bajo `/api/v1/`, autenticación por token apropiada para móviles, permisos DRF basados en `apps.accounts.permissions`, serializadores explícitos con campos mínimos, paginación, errores coherentes, CORS restrictivo, documentación de endpoints.
- **Incluye además (2026-10-14):** revisión de auditoría y de seguridad y preparación final para la app móvil; los endpoints del personal previstos están en [Fase 8, §8](fase-08-panel-empleados.md#8-preparación-para-la-app).
- **Criterios:** sin duplicar lógica (solo llama a servicios); tests de API, permisos e IDOR.
- **Implementado (2026-10-14):** auditoría con 6 correcciones (enumeración de emails en el registro, tiempos, IP real tras proxies, auditoría de contraseñas, purga de tokens de email, texto de la portada); `apps.api` con DRF, JWT (simplejwt: access 15 min, refresh rotatorio con lista negra, revocación al cambiar la contraseña), OpenAPI (drf-spectacular), endpoints de cliente y solo las operaciones de personal y propietario justificadas. Guías: [Flutter](guia-app-flutter.md) y [despliegue](despliegue.md). Ver [fase-11-api-auditoria.md](fase-11-api-auditoria.md).


## Fase 12 — Despliegue y endurecimiento
- **Numeración:** antes «Sin número — Endurecimiento y despliegue». Pasó a ser la Fase 12 por decisión del usuario el 2026-10-15.
- **Decisiones:**
  - VPS Ubuntu LTS con Docker Compose y multimedia en un volumen servido por Nginx;
  - CI en GitHub Actions con PostgreSQL real;
  - PostgreSQL 17, Python 3.14 y copias con restic.
- **Resultado (2026-10-15):**
  - imagen multietapa no root;
  - Compose de producción (Nginx con TLS, Gunicorn, PostgreSQL 17 con un rol sin privilegios, Redis, scheduler con supercronic, certbot) y pila local con Mailpit;
  - `/healthz` y estáticos con hash;
  - scripts de despliegue, rollback, copia cifrada y restauración, probados en local desde cero;
  - CI;
  - tests de concurrencia de tokens y reservas, y de `UPPER` no ASCII en PostgreSQL.
  - **833 tests OK** en PostgreSQL (local y en contenedor) y en SQLite.
- **Pendiente:** acciones manuales en el VPS (DNS, certificado, SMTP real, destino de copias) (el CI ya pasa en GitHub). Ver [fase-12-despliegue.md](fase-12-despliegue.md).

**Historial de la fase antes de numerarla:**
- **Incluye:** servidor WSGI, almacenamiento de estáticos/medios, copias de seguridad, ejecución de tests contra PostgreSQL, caché compartida, proveedor SMTP real y programación de `process_notifications`, `run_birthday_promotions`, `expire_redemptions`, `purge_email_tokens` y `flushexpiredtokens`. La revisión de seguridad, el rate limiting de la API y la guía de despliegue se hicieron en la Fase 11 ([despliegue.md](despliegue.md)).
- **Migración a PostgreSQL (2026-10-15):** completa en desarrollo ([migracion-postgresql.md](migracion-postgresql.md)).
- **Auditoría previa (2026-10-15, completa):** destino VPS Linux con Docker Compose, PostgreSQL, Redis, Gunicorn y Nginx. Corregidos el límite del login del admin, la caché compartida obligatoria en producción, un bloqueo de canjes y las versiones de las dependencias; añadidos tests de concurrencia. 817 tests OK en PostgreSQL 17. Ver [auditoria-pre-fase-12.md](auditoria-pre-fase-12.md).

## Refactorización final controlada
- **Objetivo:** mejorar la mantenibilidad, la consistencia y la eficiencia sin cambiar el comportamiento, antes de congelar la versión de la memoria técnica.
- **Resultado (2026-10-15):**
  - tests de caracterización previos;
  - `apps.core.querysets.period_q`, que sustituye unas 9 copias del filtro de periodo;
  - estadísticas de canjes y reservas con agregados condicionales (resumen del dashboard de 17 a 12 consultas, API de estadísticas de 12 a 7);
  - bloqueo de la regla del último propietario en un único helper.
  - Sin cambios en migraciones, permisos ni contratos.
  - Corregido, con aprobación del usuario, el interbloqueo previo R-1: orden de bloqueo único y nueva comprobación del actor con los bloqueos tomados.
  - **849 tests OK** en PostgreSQL (local y en contenedor) y en SQLite.
- **Pendiente:** actualizar las cifras de la documentación de la defensa. Ver [refactorizacion-final.md](refactorizacion-final.md).

## Fase 13 — Datos de demostración
- **Numeración:** fase añadida por el usuario el 2026-10-16.
- **Incluye:**
  - comando `seed_demo_data` en la app solo de desarrollo `apps.demo`, que crea datos ficticios coherentes de todas las áreas por los servicios reales, con un reloj simulado;
  - `--reset` y `--clean`, esta última solo sobre datos identificables como demo;
  - tests de guardas, coherencia, idempotencia, limpieza y escenarios negativos.
- **Decisiones del usuario:**
  - reloj simulado;
  - base de datos sin datos ajenos;
  - solo `config.settings.dev` (con `DEBUG=True`) y `config.settings.test`;
  - `BusinessInfo` sin rellenar.
- **Criterios:**
  - no se ejecuta en producción;
  - saldos iguales al ledger;
  - sin datos personales ni secretos en la salida;
  - tests en SQLite y PostgreSQL.
- **Resultado (2026-10-16):**
  - 18 tests nuevos;
  - **867 tests OK** en PostgreSQL 17 y en SQLite.
- Ver [fase-13-datos-demo.md](fase-13-datos-demo.md).

## Fase 14 — Caducidad de puntos y regalo de cumpleaños configurables
- **Numeración:** fase añadida por el usuario el 2026-10-16.
- **Incluye:**
  - en Dashboard → Configuración, la caducidad de los puntos (activar, cambiar el plazo, quitar), versionada;
  - cálculo FIFO sin retroactividad, movimiento `EXPIRATION`, comando diario `expire_points` y email transaccional de aviso previo;
  - regalo de cumpleaños editable (activación, puntos y textos del aviso con el marcador `{puntos}`).
- **Decisiones del usuario:** caducidad por antigüedad de cada punto; sin retroactividad; regalo en puntos con texto editable; fecha en «Mis puntos» y email previo.
- **Criterios:**
  - autorización y validación en el servidor;
  - caducidad atómica, idempotente y segura frente a concurrencia;
  - los textos del propietario nunca pasan por el motor de plantillas;
  - migraciones pequeñas;
  - tests de permisos, límites, idempotencia y concurrencia.
- **Resultado (2026-10-16):**
  - 63 tests nuevos;
  - **930 tests OK** en PostgreSQL 17.
- Ver [fase-14-caducidad-puntos-cumpleanos.md](fase-14-caducidad-puntos-cumpleanos.md).

## Fase 15 — Web en gallego con selector gallego/castellano
- **Numeración:** fase añadida por el usuario el 2026-10-16.
- **Incluye:**
  - toda la interfaz en gallego por defecto (i18n de Django, castellano como idioma fuente, `locale/gl`);
  - banderas de Galicia y España en la cabecera: la de España pasa a castellano la web pública y el área de cliente;
  - panel, dashboard, admin, emails y SMS siempre en gallego; API según `Accept-Language`;
  - `scripts/i18n.py` y comprobación del catálogo en el CI; compilación en la imagen Docker.
- **Decisiones del usuario:** contenido del propietario sin traducir; panel y dashboard sin selector; emails siempre en gallego; API en gallego por defecto; gettext instalado con winget.
- **Criterios:**
  - cambio de idioma por POST con CSRF y sin redirecciones abiertas;
  - catálogo completo y al día;
  - sin migraciones;
  - suite existente intacta.
- **Resultado (2026-10-16):**
  - 23 tests nuevos (5 tras la primera revisión: catálogo castellano y «Agasallos»);
  - **953 tests OK** en PostgreSQL 17 y en SQLite.
- Ver [fase-15-idioma-gallego.md](fase-15-idioma-gallego.md).

## Fase 16 — Registro con código postal, localidad por CP y sexo
- **Numeración:** fase añadida por el usuario el 2026-10-17.
- **Incluye:**
  - registro sin calle ni provincia: de la dirección solo es obligatorio el código postal;
  - provincia deducida del CP (España) y localidad elegida entre las del CP (GeoNames, CC BY 4.0), obligatoria solo si el CP tiene datos;
  - campo sexo (Hombre, Mujer, Prefiero no decirlo), obligatorio en el registro;
  - aviso «Para rexistrarte tes que ser maior de idade.» al elegir la fecha y al enviar;
  - endpoint de localidades en la web y en la API.
- **Decisiones del usuario:** columnas de dirección conservadas (sin borrar datos); calle opcional en el perfil; dataset GeoNames de España; sexo con «Prefiero no decirlo»; aviso inmediato además del servidor.
- **Criterios:**
  - migración no destructiva;
  - validación en el servidor (web y API);
  - catálogo gallego completo;
  - suite existente intacta.
- **Resultado (2026-10-17):**
  - 27 tests nuevos;
  - **980 tests OK** en PostgreSQL 17 y en SQLite;
  - migración `0008` aplicada en la BD de desarrollo (PostgreSQL).
- Ver [fase-16-registro-cp-sexo.md](fase-16-registro-cp-sexo.md).

## Fase 17 — Interruptor de reservas online
- **Numeración:** fase añadida por el usuario el 2026-10-17.
- **Incluye:** opción en Dashboard → Configuración para activar o desactivar las reservas online; desactivadas, los enlaces de reserva llevan a Contacto, que pide reservar por teléfono; bloqueo en vistas, servicio y API (`reservations_disabled`, 409; `bookable = false`).
- **Criterios:** solo el propietario lo cambia (servidor); por defecto activadas; reservas existentes intactas; migración no destructiva; catálogo gallego completo; suite existente intacta.
- **Resultado (2026-10-17):** 16 tests nuevos; **996 tests OK**.
- Ver [fase-17-reservas-online.md](fase-17-reservas-online.md).

## Fase 18 — Ordenar los listados del dashboard por columnas
- **Numeración:** fases 18 y 19 añadidas por el usuario el 2026-10-17 (una petición dividida en dos fases).
- **Incluye:** flechas ↑/↓ en cada columna ordenable de todos los listados del dashboard, con lista blanca de columnas, filtros conservados y sin JavaScript.
- **Criterios:** ningún dato de la petición llega a `order_by`; valores desconocidos sin error; solo propietario; suite existente intacta.
- **Resultado (2026-10-17):** 13 tests nuevos; **1009 tests OK**.
- Ver [fase-18-ordenacion-listados.md](fase-18-ordenacion-listados.md).

## Fase 19 — Filtro «sin gasto», selección de clientes y campañas con imagen y puntos
- **Incluye:** filtro de clientes sin compras; casillas «Envío» y selección general en Clientes; botón a Comunicaciones; formulario único de campaña con destinatarios (todos con consentimiento o seleccionados), imagen y puntos de regalo con o sin caducidad; «Crear y enviar».
- **Decisiones del usuario:** formulario único (sin apartado nuevo); los seleccionados sin consentimiento no reciben el mensaje pero sí los puntos; «con caducidad» sigue la política general y «sin caducidad» no caduca nunca.
- **Criterios:** consentimiento comprobado en servidor; puntos idempotentes; selección recalculada en servidor; migraciones aditivas; catálogo gallego completo; suite existente intacta.
- **Resultado (2026-10-17):** 22 tests nuevos; **1031 tests OK**; migraciones aplicadas en PostgreSQL y en la demo.
- Ver [fase-19-campanas-seleccion.md](fase-19-campanas-seleccion.md).

## Futuro — App móvil
Flutter para iOS y Android consumiendo la API v1. No se desarrolla en estas fases.
