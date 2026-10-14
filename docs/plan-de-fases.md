# Plan de fases — Caneca Furada

El prompt maestro es la fuente de verdad de los requisitos. Este documento divide el trabajo en fases acotadas. **Solo se implementa la fase que se solicite explícitamente**; el plan puede ajustarse antes de comenzar cada fase.

| Fase | Nombre | Estado |
|------|--------|--------|
| 0 | Fundación del proyecto | **Completa** ([detalle](fase-00-fundacion.md)) |
| 1 | Sistema de diseño y web pública | Pendiente |
| 2 | Registro, perfil de cliente y verificación de email | Pendiente |
| 3 | Carta y cervezas | Pendiente |
| 4 | Fidelización: ledger de puntos y QR personal | Pendiente |
| 5 | Panel de empleado y registro de compras | Pendiente |
| 6 | Recompensas y canjes | Pendiente |
| 7 | Eventos y reservas | Pendiente |
| 8 | Dashboard del propietario y estadísticas | Pendiente |
| 9 | Notificaciones completas y promociones de cumpleaños | Pendiente |
| 10 | API REST v1 | Pendiente |
| 11 | Endurecimiento y despliegue | Pendiente |
| Futuro | App móvil (Flutter) | Fuera del alcance actual |

---

## Fase 0 — Fundación del proyecto
- **Objetivo:** base técnica sobre la que construir sin rehacer migraciones de usuarios.
- **Incluye:** monolito modular Django, settings por entorno, `DATABASE_URL` (PostgreSQL objetivo), usuario personalizado con roles `OWNER/EMPLOYEE/CUSTOMER` antes de la primera migración, servicios de cuentas y roles, permisos reutilizables, auditoría mínima, comando `create_owner`, tests, documentación.
- **Criterios de aceptación:** `check` y `test` pasan; ningún flujo permite elegir rol al registrarse; el primer propietario se crea con un procedimiento seguro y auditado; documentación en `docs/` y `README.md`.

## Fase 1 — Sistema de diseño y web pública
- **Depende de:** Fase 0.
- **Incluye:** Tailwind CSS mediante la CLI standalone (sin Node), plantilla base accesible y responsive con la paleta oficial y los recursos de `static/img/brand/`, navegación, páginas Inicio, La cervecería y Contacto, páginas de error. Alpine.js/HTMX solo si aportan algo concreto.
- **Exclusiones:** Carta, Recompensas, Eventos, Registro y Perfil (se enlazan cuando existan).
- **Criterios:** sin horarios, precios ni datos inventados (los textos del negocio se marcan como pendientes de aportar por el propietario); contraste AA; responsive móvil/tablet/escritorio; tests de vistas públicas.

## Fase 2 — Registro, perfil de cliente y verificación de email
- **Depende de:** Fases 0 y 1.
- **Incluye:** `CustomerProfile` 1:1 con dirección estructurada (`address_line_1`, `address_line_2`, `postal_code`, `city`, `province`, `country`), fecha de nacimiento (`DateField`, sin fechas futuras, límites documentados), teléfono opcional normalizado E.164; registro público solo CUSTOMER (usa `services.create_customer`); login/logout; recuperación de contraseña; verificación de email con token seguro, caducidad, uso único, reenvío limitado y mensajes anti-enumeración; preferencias de comunicación (email/SMS promocional) desactivadas por defecto y con historial de cambios; edición del perfil; servicio base de notificaciones por email configurado por variables de entorno; acciones permitidas con cuenta pendiente de verificación documentadas.
- **Criterios:** todos los tests de registro, validación, verificación, tokens caducados/usados, reenvío, fecha de nacimiento, teléfono, dirección, preferencias y permisos del perfil del §25 del prompt maestro; política de datos personales documentada.

## Fase 3 — Carta y cervezas
- **Depende de:** Fases 0–1.
- **Incluye:** categorías, productos fijos, cervezas propias/invitadas/rotativas, 14 grifos, estilos, graduación, precios `DecimalField` (2 decimales), imágenes validadas, disponibilidad, publicación y archivo sin borrar historial; gestión por el propietario sin tocar código; página pública Carta.
- **Criterios:** validación de precios e imágenes; solo OWNER gestiona; productos archivados no se borran.

## Fase 4 — Fidelización: ledger de puntos y QR personal
- **Depende de:** Fase 2.
- **Incluye:** ledger auditable de movimientos (saldo derivado), configuración de conversión importe→puntos, token QR opaco y aleatorio (sin datos personales), rotación del token, vista del cliente con saldo, historial y QR.
- **Criterios:** puntos solo calculados en backend; movimientos inmutables con compensaciones; tests de concurrencia e idempotencia.

## Fase 5 — Panel de empleado y registro de compras
- **Depende de:** Fase 4.
- **Incluye:** panel de empleado (perfil, escaneo de QR, registro manual de importe, resultados de sus operaciones), servicio transaccional e idempotente de compras que genera puntos, preparación para TPV futuro.
- **Criterios:** validación de empleado, cliente activo, token, importe e idempotencia; datos personales mínimos visibles; tests de doble envío y permisos.

## Fase 6 — Recompensas y canjes
- **Depende de:** Fases 4–5.
- **Incluye:** catálogo de recompensas gestionado por el propietario, solicitud de canje por el cliente, código de un solo uso, validación por empleado, movimientos de puntos y auditoría.
- **Criterios:** protección frente a doble consumo y concurrencia; tests de saldo insuficiente, código usado/caducado.

## Fase 7 — Eventos y reservas
- **Depende de:** Fases 1–2.
- **Incluye:** eventos gestionables, solicitudes de reserva con estados `PENDING/CONFIRMED/REJECTED/CANCELLED/COMPLETED` y transiciones válidas, confirmación manual, notificaciones transaccionales de reserva.
- **Criterios:** transiciones validadas en servidor; datos de reservas protegidos; tests.

## Fase 8 — Dashboard del propietario y estadísticas
- **Depende de:** Fases 2–7.
- **Incluye:** gestión de clientes, empleados (alta/baja/rol vía servicios existentes), compras, puntos, recompensas, carta, eventos, reservas, contenido editable y configuración de fidelización; estadísticas reales y geográficas (país, provincia, localidad, código postal) con filtros por periodo, sin direcciones completas.
- **Criterios:** acceso solo OWNER; las compras registradas no se presentan como facturación total; tests de permisos.

## Fase 9 — Notificaciones completas y promociones de cumpleaños
- **Depende de:** Fases 2, 4, 6.
- **Incluye:** registro de notificaciones con estados (pendiente/enviada/fallida) e idempotencia, distinción transaccional/promocional, SMS opcional por variables de entorno, tareas programadas, promociones de cumpleaños configurables (29 de febrero, una por cliente y periodo, bloqueo de cambios abusivos de fecha, solo emails verificados y con consentimiento).
- **Criterios:** sin envíos simulados; tests de reintentos, duplicados y consentimiento.

## Fase 10 — API REST v1
- **Depende de:** fases funcionales previas.
- **Incluye:** Django REST Framework bajo `/api/v1/`, autenticación por token apropiada para móviles, permisos DRF basados en `apps.accounts.permissions`, serializadores explícitos con campos mínimos, paginación, errores coherentes, CORS restrictivo, documentación de endpoints.
- **Criterios:** sin duplicar lógica (solo llama a servicios); tests de API, permisos e IDOR.

## Fase 11 — Endurecimiento y despliegue
- **Incluye:** servidor WSGI, almacenamiento de estáticos/medios, copias de seguridad, rate limiting, revisión de seguridad, guía de despliegue, ejecución de tests contra PostgreSQL.

## Futuro — App móvil
Flutter para iOS y Android consumiendo la API v1. No se desarrolla en estas fases.
