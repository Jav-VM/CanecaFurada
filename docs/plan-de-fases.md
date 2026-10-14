# Plan de fases — Caneca Furada

El prompt maestro es la fuente de verdad de los requisitos. Este documento divide el trabajo en fases acotadas. **Solo se implementa la fase que se solicite explícitamente**; el plan puede ajustarse antes de comenzar cada fase.

| Fase | Nombre | Estado |
|------|--------|--------|
| 0 | Fundación del proyecto | **Completa** ([detalle](fase-00-fundacion.md)) |
| 1 | Proyecto base: perfil de cliente, módulos y preparación para la app | **Completa** ([detalle](fase-01-proyecto-base.md)) |
| 2 | Sistema de diseño y web pública | Pendiente |
| 3 | Registro, perfil de cliente y verificación de email | Pendiente |
| 4 | Carta y cervezas | Pendiente |
| 5 | Fidelización: ledger de puntos y QR personal | Pendiente |
| 6 | Panel de empleado y registro de compras | Pendiente |
| 7 | Recompensas y canjes | Pendiente |
| 8 | Eventos y reservas | Pendiente |
| 9 | Dashboard del propietario y estadísticas | Pendiente |
| 10 | Notificaciones completas y promociones de cumpleaños | Pendiente |
| 11 | API REST v1 | Pendiente |
| 12 | Endurecimiento y despliegue | Pendiente |
| Futuro | App móvil (Flutter) | Fuera del alcance actual |

---

## Fase 0 — Fundación del proyecto
- **Objetivo:** base técnica sobre la que construir sin rehacer migraciones de usuarios.
- **Incluye:** monolito modular Django, settings por entorno, `DATABASE_URL` (PostgreSQL objetivo), usuario personalizado con roles `OWNER/EMPLOYEE/CUSTOMER` antes de la primera migración, servicios de cuentas y roles, permisos reutilizables, auditoría mínima, comando `create_owner`, tests, documentación.
- **Criterios de aceptación:** `check` y `test` pasan; ningún flujo permite elegir rol al registrarse; el primer propietario se crea con un procedimiento seguro y auditado; documentación en `docs/` y `README.md`.

## Fase 1 — Proyecto base: perfil de cliente, módulos y preparación para la app
- **Depende de:** Fase 0.
- **Incluye:** revisión del prompt de la Fase 1 frente a lo construido en la Fase 0; `CustomerProfile` 1:1 mínimo (sin datos personales) creado en la misma transacción que el alta del cliente o el paso al rol CUSTOMER; migración de datos para clientes existentes; mapa de módulos; identificadores estables y guía para incorporar DRF ([arquitectura.md](arquitectura.md)).
- **Exclusiones:** campos personales del perfil y registro (Fase 3); apps de dominio vacías; DRF (Fase 11).
- **Criterios:** todo cliente creado por los servicios tiene exactamente un perfil; la creación es transaccional; migraciones revisadas y reversibles; `check`, `makemigrations --check` y tests superados.

## Fase 2 — Sistema de diseño y web pública
- **Depende de:** Fases 0–1.
- **Incluye:** Tailwind CSS mediante la CLI standalone (sin Node), plantilla base accesible y responsive con la paleta oficial y los recursos de `static/img/brand/`, navegación, páginas Inicio, La cervecería y Contacto, páginas de error. Alpine.js/HTMX solo si aportan algo concreto.
- **Exclusiones:** Carta, Recompensas, Eventos, Registro y Perfil (se enlazan cuando existan).
- **Criterios:** sin horarios, precios ni datos inventados (los textos del negocio se marcan como pendientes de aportar por el propietario); contraste AA; responsive móvil/tablet/escritorio; tests de vistas públicas.

## Fase 3 — Registro, perfil de cliente y verificación de email
- **Depende de:** Fases 0–2.
- **Incluye:** campos del `CustomerProfile` existente: dirección estructurada (`address_line_1`, `address_line_2`, `postal_code`, `city`, `province`, `country`), fecha de nacimiento (`DateField`, sin fechas futuras, límites documentados), teléfono opcional normalizado E.164; registro público solo CUSTOMER (usa `services.create_customer`); login/logout; recuperación de contraseña; verificación de email con token seguro, caducidad, uso único, reenvío limitado y mensajes anti-enumeración; preferencias de comunicación (email/SMS promocional) desactivadas por defecto y con historial de cambios; edición del perfil; servicio base de notificaciones por email configurado por variables de entorno; acciones permitidas con cuenta pendiente de verificación documentadas.
- **Criterios:** todos los tests de registro, validación, verificación, tokens caducados/usados, reenvío, fecha de nacimiento, teléfono, dirección, preferencias y permisos del perfil del §25 del prompt maestro; política de datos personales documentada.

## Fase 4 — Carta y cervezas
- **Depende de:** Fases 0–2.
- **Incluye:** categorías, productos fijos, cervezas propias/invitadas/rotativas, 14 grifos, estilos, graduación, precios `DecimalField` (2 decimales), imágenes validadas, disponibilidad, publicación y archivo sin borrar historial; gestión por el propietario sin tocar código; página pública Carta.
- **Criterios:** validación de precios e imágenes; solo OWNER gestiona; productos archivados no se borran.

## Fase 5 — Fidelización: ledger de puntos y QR personal
- **Depende de:** Fase 3.
- **Incluye:** ledger auditable de movimientos (saldo derivado), configuración de conversión importe→puntos, token QR opaco y aleatorio (sin datos personales), rotación del token, vista del cliente con saldo, historial y QR.
- **Criterios:** puntos solo calculados en backend; movimientos inmutables con compensaciones; tests de concurrencia e idempotencia.

## Fase 6 — Panel de empleado y registro de compras
- **Depende de:** Fase 5.
- **Incluye:** panel de empleado (perfil, escaneo de QR, registro manual de importe, resultados de sus operaciones), servicio transaccional e idempotente de compras que genera puntos, preparación para TPV futuro.
- **Criterios:** validación de empleado, cliente activo, token, importe e idempotencia; datos personales mínimos visibles; tests de doble envío y permisos.

## Fase 7 — Recompensas y canjes
- **Depende de:** Fases 5–6.
- **Incluye:** catálogo de recompensas gestionado por el propietario, solicitud de canje por el cliente, código de un solo uso, validación por empleado, movimientos de puntos y auditoría.
- **Criterios:** protección frente a doble consumo y concurrencia; tests de saldo insuficiente, código usado/caducado.

## Fase 8 — Eventos y reservas
- **Depende de:** Fases 2–3.
- **Incluye:** eventos gestionables, solicitudes de reserva con estados `PENDING/CONFIRMED/REJECTED/CANCELLED/COMPLETED` y transiciones válidas, confirmación manual, notificaciones transaccionales de reserva.
- **Criterios:** transiciones validadas en servidor; datos de reservas protegidos; tests.

## Fase 9 — Dashboard del propietario y estadísticas
- **Depende de:** Fases 3–8.
- **Incluye:** gestión de clientes, empleados (alta/baja/rol vía servicios existentes), compras, puntos, recompensas, carta, eventos, reservas, contenido editable y configuración de fidelización; estadísticas reales y geográficas (país, provincia, localidad, código postal) con filtros por periodo, sin direcciones completas.
- **Criterios:** acceso solo OWNER; las compras registradas no se presentan como facturación total; tests de permisos.

## Fase 10 — Notificaciones completas y promociones de cumpleaños
- **Depende de:** Fases 3, 5, 7.
- **Incluye:** registro de notificaciones con estados (pendiente/enviada/fallida) e idempotencia, distinción transaccional/promocional, SMS opcional por variables de entorno, tareas programadas, promociones de cumpleaños configurables (29 de febrero, una por cliente y periodo, bloqueo de cambios abusivos de fecha, solo emails verificados y con consentimiento).
- **Criterios:** sin envíos simulados; tests de reintentos, duplicados y consentimiento.

## Fase 11 — API REST v1
- **Depende de:** fases funcionales previas.
- **Incluye:** Django REST Framework bajo `/api/v1/`, autenticación por token apropiada para móviles, permisos DRF basados en `apps.accounts.permissions`, serializadores explícitos con campos mínimos, paginación, errores coherentes, CORS restrictivo, documentación de endpoints.
- **Criterios:** sin duplicar lógica (solo llama a servicios); tests de API, permisos e IDOR.

## Fase 12 — Endurecimiento y despliegue
- **Incluye:** servidor WSGI, almacenamiento de estáticos/medios, copias de seguridad, rate limiting, revisión de seguridad, guía de despliegue, ejecución de tests contra PostgreSQL.

## Futuro — App móvil
Flutter para iOS y Android consumiendo la API v1. No se desarrolla en estas fases.
