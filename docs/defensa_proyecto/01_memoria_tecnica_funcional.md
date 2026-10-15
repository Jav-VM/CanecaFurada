# Caneca Furada — Memoria técnica y funcional

> **Versión documentada:** la versión congelada para la defensa (commit `d0bac7c`, 15-10-2026, refactorización final, etiqueta `v1.0-defensa`) más los ajustes posteriores de interfaz del mismo día ([fase-03 §14](../fase-03-sistema-diseno-web-publica.md#14-ajuste-de-la-cabecera-2026-10-15)): cabecera en una sola línea (el propietario ve «Mi cuenta», «Panel» y «Salir»), logo del pie enlazado al inicio y columnas del pie juntas y equidistantes. Esos ajustes solo cambian las plantillas `base.html` y `footer.html` y el CSS, así que el resto de líneas citadas no varía.
> **Historia de este documento:** se redactó el 15-10-2026 sobre el código de la Fase 11 (commit `ac5903a` del historial anterior; hoy `eec6abc`, porque el historial se reescribió en la auditoría, P2-6). Ese mismo día se actualizó con la [migración a PostgreSQL](../migracion-postgresql.md), la [auditoría previa a la Fase 12](../auditoria-pre-fase-12.md), la [Fase 12 de despliegue](../fase-12-despliegue.md) y la [refactorización final](../refactorizacion-final.md). Las referencias `archivo:línea` se recalcularon con el diff entre ambas versiones y los bloques de código real se volvieron a comparar con el código.
> **Fuente de verdad:** el código del repositorio. La documentación previa (`docs/`) se ha contrastado con el código y, cuando no coinciden, se indica.
> **Comprobaciones reales ejecutadas sobre la versión congelada** (detalle en [`refactorizacion-final.md` §6](../refactorizacion-final.md)): `manage.py check` sin incidencias, `makemigrations --check` sin cambios, **849 tests OK en PostgreSQL 17 sin omitidos** (en local y dentro del contenedor de producción), 849 OK en SQLite (18 omitidos: los de concurrencia y uno exclusivo de PostgreSQL), esquema OpenAPI regenerado idéntico al versionado y `check --deploy` con variables ficticias (solo el aviso `security.W021`). El CI de GitHub Actions pasó en verde en GitHub con la versión congelada (2026-10-15, [ejecución](https://github.com/Jav-VM/CanecaFurada/actions/runs/38776430860), commit `decff8f`): suite en PostgreSQL 17 sin omitidos, `check --deploy`, OpenAPI, build, pila Compose, prueba de humo por HTTPS y copia con restauración.

## Etiquetas de estado usadas en todo el documento

| Etiqueta | Significado |
|---|---|
| **Implementado y verificado** | Hay código y algún test que lo ejercita se ha **ejecutado y aprobado** en esta revisión. |
| **Implementado, pendiente de verificación** | Hay código, pero su funcionamiento depende de algo no comprobado aquí (SMTP real, PostgreSQL, dispositivo físico, revisión visual, tarea programada). |
| **Parcialmente implementado** | Solo una parte del comportamiento está cubierta. |
| **Planificado** | Aparece en requisitos, en documentación o como valor reservado en un modelo, pero no tiene flujo. |
| **No identificado** | No se ha encontrado evidencia. |

## Índice

1. [Presentación del proyecto](#1-presentación-del-proyecto)
2. [Requisitos y análisis funcional](#2-requisitos-y-análisis-funcional)
3. [Arquitectura general](#3-arquitectura-general)
4. [Tecnologías y justificación técnica](#4-tecnologías-y-justificación-técnica)
5. [Estructura del repositorio](#5-estructura-del-repositorio)
6. [Modelo de datos y base de datos](#6-modelo-de-datos-y-base-de-datos)
7. [Explicación detallada de cada funcionalidad](#7-explicación-detallada-de-cada-funcionalidad)
8. [Explicación del código fuente](#8-explicación-del-código-fuente)
9. [Flujos completos de extremo a extremo](#9-flujos-completos-de-extremo-a-extremo)
10. [Seguridad, privacidad e integridad](#10-seguridad-privacidad-e-integridad)
11. [Pruebas y calidad del software](#11-pruebas-y-calidad-del-software)
12. [Instalación, configuración y ejecución](#12-instalación-configuración-y-ejecución)
13. [Despliegue y mantenimiento](#13-despliegue-y-mantenimiento)
14. [Evolución del proyecto por fases](#14-evolución-del-proyecto-por-fases)
15. [Decisiones de diseño y alternativas](#15-decisiones-de-diseño-y-alternativas)
16. [Limitaciones y mejoras futuras](#16-limitaciones-y-mejoras-futuras)
17. Preparación de la defensa oral → [02_guion_defensa_oral.md](02_guion_defensa_oral.md)
18. Banco de preguntas del tribunal → [03_preguntas_y_respuestas_tribunal.md](03_preguntas_y_respuestas_tribunal.md)
19. [Glosario técnico](#19-glosario-técnico)
20. [Conclusiones y valoración técnica](#20-conclusiones-y-valoración-técnica)

---

## 1. Presentación del proyecto

### 1.1 Versión breve (para la introducción oral, ~1 minuto)

> Caneca Furada es la plataforma web de una cervecería artesanal de A Coruña. Además de la web pública con la carta y los eventos, incluye un **programa de fidelización**: cada cliente registrado tiene un **código QR personal**; cuando consume, el empleado lo escanea en la barra, registra el importe y el sistema le suma **puntos** que puede canjear por **recompensas** con un código de un solo uso. Hay tres roles con permisos diferentes: **cliente**, **empleado** y **propietario**. El propietario tiene un **dashboard** con estadísticas, gestión de clientes, empleados, carta, eventos, reservas y campañas. Todo está construido como un **monolito modular en Django**, con la lógica de negocio en servicios, transacciones y restricciones en la base de datos para que no se puedan duplicar puntos ni canjes, y con una **API REST** preparada para una futura app móvil. El proyecto tiene **849 tests automáticos** que pasan en PostgreSQL, y la pila de producción (Docker Compose con Nginx, Gunicorn, PostgreSQL y Redis) está preparada y probada en local.

### 1.2 Versión extensa

**Qué es.** Una aplicación web de servidor (Django 5.2) para la cervecería artesanal *Caneca Furada* («A cervexería 100% artesá da Coruña», lema en `apps/web/content.py`). Combina tres cosas:

1. **Web pública:** inicio, la cervecería, carta, recompensas, eventos y contacto (`apps/web/`).
2. **Programa de fidelización:** registro de clientes con verificación de email, QR personal, compras registradas por el personal, ledger de puntos, promociones, regalo de cumpleaños, recompensas y canjes (`apps/accounts`, `loyalty`, `purchases` y `rewards`).
3. **Herramientas internas:** panel del personal en barra (`apps/staff`), dashboard del propietario (`apps/dashboard`), eventos y reservas (`apps/events`), notificaciones y campañas (`apps/notifications`), admin técnico de Django y una API REST v1 (`apps/api`).

**Qué problema resuelve.** Un local pequeño que quiere fidelizar clientes sin tarjetas de cartón ni hojas de cálculo necesita: identificar al cliente de forma rápida y segura en la barra, acumular puntos sin que nadie pueda manipularlos, canjearlos sin que un código sirva dos veces y conocer su clientela (cuántos, de dónde, qué consumen en el programa) **sin invadir su privacidad**. La web pública da además un escaparate con carta y eventos que el propietario actualiza sin tocar código.

**Usuarios (roles reales, `apps/accounts/models.py:34-37`).**

| Rol | Valor en BD | Qué hace |
|---|---|---|
| Visitante anónimo | — | Navega por la web pública, se registra, recupera la contraseña, verifica el email y se da de baja de las comunicaciones. |
| Cliente | `CUSTOMER` | Edita su perfil y sus preferencias. Con el email verificado: muestra su QR, consulta sus puntos y compras, canjea recompensas y reserva mesa o plaza en eventos. |
| Empleado | `EMPLOYEE` | Panel `/panel/`: identifica clientes por QR, registra compras, valida canjes y consulta sus propios resultados. |
| Propietario | `OWNER` | Todo lo del empleado más el dashboard `/dashboard/`, el admin técnico y los endpoints `owner/` de la API. |

**Objetivos** (a partir de `docs/plan-de-fases.md` y del código): fidelizar con puntos calculados solo en el servidor; impedir duplicados y abusos (idempotencia, transacciones, restricciones en BD); proteger los datos personales (mínima exposición, auditoría de accesos, consentimiento explícito); dar al propietario cifras reales sin confundirlas con la facturación; y preparar una API para una app móvil.

**Alcance funcional implementado (resumen; detalle en el cap. 2):** cuentas, perfiles y verificación; carta; QR y compras; ledger de puntos y promociones; cumpleaños; recompensas y canjes; panel del personal; dashboard y estadísticas (también geográficas); eventos y reservas; notificaciones por email y campañas; API REST v1 con JWT; auditoría.

**Fuera del alcance o no implementado (verificado):**
- **Despliegue en el VPS real** (contratar el servidor, dominio, certificado de Let's Encrypt, SMTP real y destino externo de las copias): la pila completa está en el repositorio y se ha probado en local y en el CI (Fase 12), pero no se ha desplegado en un servidor. *Pendiente de acciones manuales.*
- **SMS:** el canal existe, pero no hay proveedor integrado (`apps/notifications/sms.py:4-10`). *Planificado.*
- **Anulación de compras e integración con TPV:** valores reservados `VOIDED` y `POS` sin flujo. *Planificado.*
- **App móvil Flutter:** fuera de alcance; solo hay API y guía. *Planificado.*
- **Facturación o caja:** el sistema **no** gestiona ventas ni pagos; registra compras para fidelización (`apps/purchases/selectors.py:1-9`).
- **Exportación o borrado de datos a petición del interesado:** no hay ninguna funcionalidad. Decisión tomada en la auditoría (P2-9): al suprimir una cuenta se conservarán las compras y los movimientos de puntos. *Planificado (fase propia antes de abrir al público).*
- **Monitorización y alertas:** no existen; es el siguiente paso tras la Fase 12. *Planificado.*

**Valor frente a una web informativa.** Una web informativa solo muestra contenido. Aquí hay **estado de negocio con reglas** (saldo de puntos, canjes de un solo uso, reservas con aforo), **tres roles** con autorización en el servidor, **integridad transaccional** y **trazabilidad** (auditoría sin datos personales), además de una API reutilizable.

---

## 2. Requisitos y análisis funcional

### 2.1 Origen de los requisitos

- **Requisitos del plan** (`docs/plan-de-fases.md`): lo que pedía cada fase.
- **Decisiones de implementación** documentadas en el mismo plan como «Ajuste» o «Reordenación», decididas por el autor durante el desarrollo (p. ej. sustituir los 14 grifos por una imagen de la carta de grifos, o regalar los puntos de cumpleaños el mismo día).
- **Requisitos del prompt de documentación** (`docs/prompt_funcionamiento.md`, cap. 7): lista de comprobación; algunos puntos (exportación de datos) no tienen implementación.

### 2.2 Qué puede hacer cada tipo de usuario

| Acción | Anónimo | Cliente sin verificar | Cliente verificado | Empleado | Propietario | Dónde se controla |
|---|:-:|:-:|:-:|:-:|:-:|---|
| Ver la web pública, la carta, las recompensas y los eventos | ✔ | ✔ | ✔ | ✔ | ✔ | Vistas públicas sin decorador |
| Registrarse (siempre como cliente) | ✔ | — | — | — | — | `accounts.views.register` (redirige si hay sesión) |
| Editar el perfil y las preferencias | — | ✔ | ✔ | — | — | `role_required(CUSTOMER)` |
| Ver el QR y los puntos, canjear y reservar | — | ✘ 403 | ✔ | ✘ 403 | ✘ 403 | `verified_email_required` + `_require_customer` |
| Registrar compras y validar canjes | — | ✘ | ✘ | ✔ | ✔ | `role_required(OWNER, EMPLOYEE)` + servicio |
| Ver las operaciones propias en el panel | — | ✘ | ✘ | ✔ | ✔ | `staff.views` |
| Dashboard, admin y API `owner/` | — | ✘ | ✘ | ✘ 403 | ✔ | `role_required(OWNER)`, `is_staff` derivado del rol, `IsOwner` |
| Ajustar puntos, gestionar empleados, carta, eventos y campañas | — | ✘ | ✘ | ✘ | ✔ | Servicios con `is_owner` / `_ensure_active_owner` |

### 2.3 Restricciones, datos, validaciones y casos límite principales

| Proceso | Datos de entrada | Validaciones del servidor (archivo) | Errores posibles | Casos límite tratados |
|---|---|---|---|---|
| Registro | Nombre, apellidos, fecha de nacimiento, móvil opcional, dirección estructurada, país, email, contraseña ×2 y consentimientos | `validators.py`: CP por país (ES `01-52xxx`, PT `1234-567`), móvil E.164, edad ≥ 18 y ≤ 120, no futura; contraseña ≥ 10 caracteres, no común ni solo numérica (`base.py:109-117`) | Errores por campo; 20 intentos por IP y hora | Email duplicado sin revelarlo; 29 de febrero; mayúsculas en el email |
| Verificación de email | Token del enlace | Hash SHA-256, sin usar, sin revocar, sin caducar (24 h), usuario activo, email coincidente | `invalid`, `expired`, `used`, `revoked`, `email_taken` | Doble clic simultáneo: UPDATE condicionado |
| Compra | Código QR o tecleado, importe y clave de idempotencia | Personal activo, origen MANUAL, importe Decimal de 0,01 a 1000 € con 2 decimales, cliente activo y verificado | `invalid_qr`, `email_not_verified`, `amount_*`, `idempotency_conflict`, 429 | Doble envío, reintento, cliente desactivado entre pasos, nadie se registra compras a sí mismo |
| Canje | Recompensa y clave de idempotencia | Cliente verificado, recompensa activa en fechas, stock, saldo y un pendiente por recompensa | `reward_unavailable`, `out_of_stock`, `insufficient_points`, `duplicate_pending` | Peticiones simultáneas, stock que llega a 0 |
| Validación de canje | Código | Personal, código existente, cliente activo, no propio, PENDING y no caducado | `invalid_code`, `code_used`, `code_expired`, `code_not_pending` | Dos empleados a la vez: solo uno |
| Reserva | Fecha y hora (mesa) o evento, personas, notas y clave | Verificado, antelación de 2 h a 90 días, de 1 a 20 personas, aforo, una por evento, como máximo 3 activas, 10 por hora | `event_full`, `already_reserved`, `too_many_active`, `rate_limited`, `invalid_transition` | Cambio de hora del evento, confirmación concurrente |

### 2.4 Tabla de requisitos con evidencia y estado

La matriz completa, con 55 entradas, está en [`_trabajo/matriz_evidencia.md`](_trabajo/matriz_evidencia.md). Resumen agrupado:

| ID | Requisito | Origen | Evidencia en el código | Tests | Estado |
|---|---|---|---|---|---|
| RF-01 | Roles OWNER/EMPLOYEE/CUSTOMER con restricciones en BD; registro siempre como cliente | Plan F0/F2 | `apps/accounts/models.py:34-85`; `forms.py:1-9` | `tests/accounts/*` (209) | Implementado y verificado |
| RF-02 | Perfil de cliente 1:1 transaccional con dirección, fecha de nacimiento y móvil validados | Plan F1/F2 | `services.ensure_customer_profile`, `validators.py` | `test_customer_profile.py`, `test_profile.py` | Implementado y verificado |
| RF-03 | Verificación de email, recuperación y cambio de email con tokens seguros | Plan F2 | `services.py:485-641` | `test_email_verification.py` (23) | Implementado y verificado; **envío SMTP real pendiente** |
| RF-04 | Preferencias promocionales con historial y baja por enlace firmado | Plan F2/F10 | `CommunicationPreferenceChange`; `notifications/unsubscribe.py` | `test_profile.py`, `test_notifications.py` | Implementado y verificado |
| RF-05 | Web pública con sistema de diseño | Plan F3 | `templates/`, `assets/css/input.css` | `tests/web/*` (40) | Implementado y verificado; **revisión visual y contraste pendientes** |
| RF-06 | Carta con publicación, archivo y disponibilidad; imágenes validadas | Plan F4 | `apps/catalog/*` | `tests/catalog/*` (59) | Implementado y verificado |
| RF-07 | QR personal y registro manual de compras idempotente | Plan F5 | `loyalty/services.py`, `purchases/services.py` | `test_qr.py` (22), `tests/purchases/*` (58) | Implementado y verificado; **escaneo con cámara en dispositivos pendiente** |
| RF-08 | Ledger de puntos inmutable, conversión versionada y promociones | Plan F6 | `loyalty/ledger.py`, `conversion.py`, `promotions.py` | `test_points.py` (41), `test_promotions.py` (18) | Implementado y verificado |
| RF-09 | Regalo de cumpleaños con anti-abuso | Plan F6 + decisión F10 | `loyalty/birthdays.py`, `ledger.grant_birthday_gift` | `test_birthdays.py` (21) | Implementado y verificado; programado a diario en el servicio `scheduler` (Fase 12) |
| RF-10 | Recompensas y canjes de un solo uso sin doble consumo | Plan F7 | `rewards/services.py` | `tests/rewards/*` (84) | Implementado y verificado, también la concurrencia en PostgreSQL |
| RF-11 | Panel del personal con datos mínimos del cliente | Plan F8 | `apps/staff/` | `test_panel.py` (31) | Implementado y verificado |
| RF-12 | Dashboard del propietario y estadísticas reales y geográficas | Plan F9 | `apps/dashboard/`, selectores | `tests/dashboard/*` (67) | Implementado y verificado |
| RF-13 | Eventos y reservas con transiciones y aforo | Plan F10 | `apps/events/` | `tests/events/*` (46) | Implementado y verificado |
| RF-14 | Notificaciones con estado real, reintentos y campañas con consentimiento | Plan F10 | `apps/notifications/` | `test_notifications.py` (30) | Implementado y verificado con un backend en memoria; **SMTP real pendiente** |
| RF-15 | SMS | Plan F10 (opcional) | `sms.py`: sin proveedor | — | Planificado |
| RF-16 | API REST v1 con JWT, permisos, errores coherentes y OpenAPI | Plan F11 | `apps/api/` | `tests/api/*` (73) | Implementado y verificado |
| RF-17 | Auditoría de operaciones sensibles sin datos personales | Plan F0-F11 | `apps/core/` | `tests/core/*` (33) | Implementado y verificado |
| RNF-01 | Atomicidad e idempotencia en puntos, compras, canjes y reservas | CLAUDE.md §4 | `transaction.atomic`, `select_for_update`, UNIQUE | Idempotencia probada; 17 tests de concurrencia con hilos que pasan en PostgreSQL (local, contenedor y CI) | Implementado y verificado |
| RNF-02 | Seguridad (CSRF, XSS, IDOR, asignación masiva, abuso) | CLAUDE.md §3 | cap. 10 | Tests de IDOR, roles y API | Implementado y verificado (ver los riesgos del cap. 16) |
| RNF-03 | Configuración de producción endurecida | Plan F11 | `config/settings/prod.py` | `tests/core/test_audit_and_settings.py:58-91` (7 tests de requisitos de `prod.py`) + `check --deploy` (solo W021) | Implementado y verificado en la pila local; **sin despliegue en el VPS** |
| RNF-04 | Despliegue, backups y tareas programadas | Plan F12 | `Dockerfile`, `compose.yaml`, `deploy/`, `.github/workflows/ci.yml` | `tests/core/test_health.py` (8) + procedimientos probados en local (despliegue, rollback, copia y restauración) | Implementado y verificado en local y en el CI; **VPS pendiente** |

### 2.5 Requisitos originales frente a decisiones de implementación

| Requisito original (plan) | Lo que se implementó | Quién lo decidió |
|---|---|---|
| Modelar 14 grifos | Imagen de la carta de grifos (`TapMenu`) | El usuario (ajuste de la Fase 4) |
| Bonificación de cumpleaños en la compra (Fase 6) | Regalo de puntos el mismo día, sin compra (`BIRTHDAY_GIFT`) | El usuario (ajuste de la Fase 10) |
| Tareas con Celery u otra cola | Comandos de gestión y programador del sistema | El usuario (ajuste de la Fase 10) |
| «CORS restrictivo» | Sin cabeceras CORS (una app nativa no las necesita) | Decisión de la Fase 11 documentada en `docs/fase-11-api-auditoria.md:155` |
| Fase de notificaciones propia y Fase 12 de despliegue | Notificaciones dentro de la Fase 10; el despliegue quedó «sin número» y se numeró como Fase 12 el 15-10-2026 | El usuario (reordenación tras la Fase 7 y numeración final) |

---

## 3. Arquitectura general

### 3.1 Patrón arquitectónico

**Monolito modular Django con capa de servicios.** Un único proyecto (`config/`) y doce apps locales (`config/settings/base.py:40-53`), cada una con una responsabilidad de dominio. Dentro de cada app se separan:

| Capa | Archivos típicos | Responsabilidad | Ejemplo real |
|---|---|---|---|
| Presentación | `views.py`, `forms.py`, `urls.py`, `templates/`, `apps/api/views/`, `serializers/` | Traducir HTTP ↔ Python: leer la entrada, llamar al servicio y traducir los errores a mensajes o códigos HTTP | `purchases/views.py:87-117` |
| Dominio (escritura) | `services.py`, `ledger.py`, `promotions.py`, `campaigns.py` | Permisos, validación, transacción y auditoría | `purchases/services.py:158-194` |
| Dominio (lectura) | `selectors.py` | Consultas con permisos (p. ej. solo el propietario) y campos mínimos | `accounts/selectors.py:57-93` |
| Datos | `models.py`, `migrations/` | Esquema e invariantes en BD (CHECK, UNIQUE, PROTECT) | `loyalty/models.py:360-420` |

La regla se cumple en el código: los docstrings de las vistas lo declaran (p. ej. `apps/dashboard/views.py:1-15`: «Solo presentación») y la API reutiliza los mismos servicios que la web (`apps/api/views/staff.py:1-6`). Los formularios y serializadores **solo convierten la entrada** (`apps/accounts/forms.py:1-9`) y el servicio vuelve a validar.

### 3.2 Diagrama de arquitectura (componentes verificados)

Archivo independiente: [`diagramas/01_arquitectura_general.mmd`](diagramas/01_arquitectura_general.mmd).

```mermaid
flowchart TB
    subgraph Clientes["Clientes"]
        NAV["Navegador web<br/>(cliente, empleado, propietario)"]
        APP["Futura app móvil Flutter<br/>(no desarrollada)"]
    end

    subgraph Django["Monolito modular Django 5.2 (config/)"]
        URLS["config/urls.py<br/>enrutado por prefijos"]
        MW["Middleware<br/>Security, Session, Locale, Common,<br/>CSRF, Auth, Messages, XFrame"]

        subgraph Presentacion["Capa de presentación"]
            WEB["Vistas web + Django Templates<br/>web, accounts, loyalty, purchases,<br/>rewards, events, notifications"]
            PANEL["Panel del personal<br/>apps.staff (/panel/)"]
            DASH["Dashboard del propietario<br/>apps.dashboard (/dashboard/)"]
            API["API REST v1 (DRF + JWT)<br/>apps.api (/api/v1/)"]
            ADMIN["Admin técnico<br/>(solo propietario)"]
        end

        subgraph Dominio["Capa de dominio: servicios y selectores"]
            SVC["services.py / ledger.py / campaigns.py<br/>escrituras: permisos, validación,<br/>transacción y auditoría"]
            SEL["selectors.py<br/>lecturas con permisos"]
            PERM["accounts.permissions<br/>has_role, role_required"]
        end

        ORM["Modelos + ORM<br/>21 modelos, restricciones CHECK y UNIQUE"]
        CACHE["Caché de Django<br/>(locmem en desarrollo, Redis en producción)<br/>límites de intentos, contenido"]
    end

    subgraph Datos["Persistencia"]
        DB[("PostgreSQL 17<br/>(SQLite opcional en desarrollo)")]
        MEDIA[("media/<br/>imágenes subidas")]
        STATIC[("static/<br/>CSS Tailwind compilado, JS, jsQR")]
    end

    subgraph Externos["Servicios externos y tareas"]
        SMTP["Proveedor SMTP<br/>(configurable, no verificado)"]
        SMS["Proveedor SMS<br/>(no integrado)"]
        CRON["scheduler (supercronic, Fase 12)<br/>process_notifications, run_birthday_promotions,<br/>expire_redemptions, purgas diarias"]
    end

    NAV --> URLS
    APP -.-> URLS
    URLS --> MW --> WEB & PANEL & DASH & API & ADMIN
    WEB & PANEL & DASH & API & ADMIN --> SVC & SEL
    SVC --> PERM
    SEL --> PERM
    SVC & SEL --> ORM --> DB
    SVC --> CACHE
    ORM -.-> MEDIA
    NAV -.-> STATIC
    SVC -->|"notifications.services"| SMTP
    SVC -.->|"SMS_BACKEND vacío"| SMS
    CRON -.->|"comandos de gestión"| SVC
```

> Desde la Fase 12, las tareas las programa el servicio `scheduler` de Docker Compose (`deploy/cron/crontab`, cap. 13). Las copias de seguridad no van ahí: se programan en el host.

### 3.3 Organización de módulos y dependencias

Las dependencias entre apps se han calculado a partir de los `import` reales ([`diagramas/02_modulos_dependencias.mmd`](diagramas/02_modulos_dependencias.mmd)):

```mermaid
flowchart LR
    core["core<br/>AuditEvent, throttling, client_ip"]
    accounts["accounts<br/>User, perfil, permisos"]
    catalog["catalog<br/>carta"]
    loyalty["loyalty<br/>QR, ledger, promociones"]
    purchases["purchases<br/>compras"]
    rewards["rewards<br/>recompensas, canjes"]
    events["events<br/>eventos, reservas"]
    notifications["notifications<br/>envíos, campañas"]
    web["web<br/>páginas públicas"]
    staff["staff<br/>panel del personal"]
    dashboard["dashboard<br/>propietario"]
    api["api<br/>REST v1"]

    accounts --> core
    accounts -.->|"emails"| notifications
    notifications --> accounts
    notifications --> core
    catalog --> accounts
    catalog --> core
    loyalty --> accounts
    loyalty --> core
    loyalty --> notifications
    loyalty -.->|"vista my_points"| purchases
    purchases --> loyalty
    purchases --> accounts
    purchases --> core
    rewards --> loyalty
    rewards --> accounts
    rewards --> catalog
    rewards --> core
    events --> accounts
    events --> notifications
    events --> catalog
    events --> core
    web --> catalog
    web --> events
    web --> rewards
    web --> accounts
    web --> core
    staff --> purchases
    staff --> rewards
    staff --> loyalty
    staff --> accounts
    dashboard --> accounts & catalog & events & loyalty & notifications & purchases & rewards & web
    api --> accounts & core & events & loyalty & purchases & rewards
```

Observaciones verificadas:
- `core` no depende de nadie: es la base (auditoría y límites).
- `staff`, `dashboard` y `api` son **solo presentación**: dependen de los dominios, pero ningún dominio depende de ellos.
- Hay **dos dependencias mutuas**: `accounts ↔ notifications` (los emails de cuentas salen por el servicio de notificaciones, y este consulta el consentimiento en `accounts`; se resuelve con una **importación diferida** en `apps/notifications/services.py:208-209`) y `loyalty ↔ purchases` (el ledger referencia `purchases.Purchase` por cadena en `apps/loyalty/models.py:306-307` y la vista `my_points` usa un selector de compras). Funcionan, pero son un punto de acoplamiento a vigilar.

### 3.4 Flujo de una petición HTTP

Ejemplo real: registrar una compra ([`diagramas/03_ciclo_peticion.mmd`](diagramas/03_ciclo_peticion.mmd)).

```mermaid
sequenceDiagram
    autonumber
    actor E as Empleado (navegador)
    participant MW as Middleware de Django
    participant U as URLconf (config/urls.py)
    participant V as purchases.views.register
    participant F as PurchaseForm
    participant S as purchases.services
    participant L as loyalty.ledger
    participant DB as Base de datos
    participant T as Plantilla / redirección

    E->>MW: POST /panel/compras/registrar/ (cookie de sesión + csrfmiddlewaretoken)
    MW->>MW: SessionMiddleware carga la sesión, CsrfViewMiddleware valida el token, AuthenticationMiddleware pone request.user
    MW->>U: resolve("panel/compras/registrar/")
    U->>V: purchases:register
    V->>V: never_cache, require_POST, role_required(OWNER, EMPLOYEE)
    alt sin sesión
        V-->>E: 302 al login
    else rol no permitido
        V-->>E: 403
    end
    V->>F: PurchaseForm(request.POST).is_valid()
    F->>S: parse_amount(importe) (Decimal, 2 decimales, 0,01 a 1000)
    V->>S: register_purchase(staff, qr_code, amount, idempotency_key)
    S->>S: ensure_can_register_purchases, origen habilitado, clave UUID, límite de fallos
    S->>DB: BEGIN (transaction.atomic)
    S->>DB: SELECT ... FOR UPDATE de Purchase por idempotency_key
    alt la clave ya existe
        S->>S: _replay: mismos datos o idempotency_conflict
    else nueva
        S->>DB: SELECT ... FOR UPDATE del cliente por token QR
        S->>DB: INSERT Purchase
        S->>L: on_purchase_registered llama a award_points_for_purchase
        L->>DB: SELECT FOR UPDATE del cliente, SUM(points), INSERT PointsTransaction(s)
    end
    S->>DB: COMMIT (o ROLLBACK de todo si algo falla)
    S-->>V: RegistrationResult(purchase, created)
    V->>T: messages + redirect a purchases:detail
    T-->>E: 302 y luego 200 con la plantilla purchases/detail.html
```

Paso a paso, con referencias:
1. **Middleware** (`config/settings/base.py:57-68`): seguridad, sesión, idioma, CSRF, autenticación, mensajes y anti-clickjacking (`X_FRAME_OPTIONS = "DENY"`, `:297`).
2. **Enrutado** (`config/urls.py:13-26`): por prefijos; `panel/compras/` → `apps/purchases/urls.py`.
3. **Vista** (`apps/purchases/views.py:84-117`): los decoradores aplican la caché, el método y el rol.
4. **Validación**: el formulario convierte el importe (`forms.py:35-36` → `services.parse_amount`) y el servicio vuelve a validar todo.
5. **Lógica de negocio y BD**: transacción explícita (`ATOMIC_REQUESTS = False`, `base.py:98`; las transacciones están en los servicios).
6. **Respuesta**: patrón POST-redirect-GET con un mensaje (`views.py:113-117`).

### 3.5 Validación, autenticación, renderizado, acceso a datos y errores

- **Validación en tres niveles:** formulario o serializador (formato) → servicio (reglas de negocio con el estado actual, dentro de la transacción) → BD (CHECK y UNIQUE). Ejemplo: el importe se valida en `parse_amount` y además `CHECK amount >= 0.01` (`apps/purchases/models.py:83`).
- **Autenticación:** web por sesión (`LoginView` con `ThrottledAuthenticationForm`); API por JWT (`apps/api/authentication.py`). **Autorización** por rol leído siempre de la BD (`apps/accounts/permissions.py:17-23`).
- **Renderizado:** Django Templates en `templates/` (109 plantillas), plantilla base con el CSS compilado de Tailwind y un JS de mejora progresiva. La API devuelve solo JSON (`base.py:231-232`).
- **Acceso a datos:** ORM. Los selectores usan `select_related`, `only()` y `defer()` para cargar los campos mínimos (p. ej. `.defer("code")` en `rewards/selectors.py:105`: el propietario no ve los códigos de canje).
- **Errores:** web → mensajes (`django.contrib.messages`) y plantillas 400/403/404/500 (`templates/`); API → formato único `{code, detail, fields}` (`apps/api/exceptions.py`); los errores inesperados devuelven un 500 genérico sin trazas.
- **Integraciones externas:** SMTP (configurable), SMS (no integrado) y CDN de Swagger UI solo en `/api/v1/docs/` (cap. 16).

---

## 4. Tecnologías y justificación técnica

Solo se analizan las tecnologías **confirmadas** en `requirements/*.txt`, `config/settings/base.py`, `scripts/` y `static/`. Versiones instaladas en el entorno de análisis (`pip freeze`).

| Tecnología | Versión (fijada en `requirements/`) | Uso en el proyecto | Alternativas | Por qué encaja | Limitaciones |
|---|---|---|---|---|---|
| **Python** | 3.12+ (README) / 3.14.2 | Lenguaje de todo el backend | Node.js, Java | Ecosistema Django y `Decimal` para el dinero | Rendimiento por petición inferior a lenguajes compilados, irrelevante a esta escala |
| **Django** | 5.2.18 | Framework: ORM, migraciones, autenticación, sesiones, CSRF, admin, plantillas, formularios y señales de seguridad | Flask, FastAPI | «Baterías incluidas»: seguridad nativa y admin gratis para el propietario; versión LTS | Monolito: escalar por partes requiere más trabajo |
| **PostgreSQL 17** / **SQLite** (desarrollo opcional) | psycopg 3.3.6 | BD. `DATABASE_URL` decide; sin ella, SQLite. Producción exige PostgreSQL | MySQL | PostgreSQL soporta `SELECT ... FOR UPDATE` real, índices parciales y CHECK | SQLite no ejercita los bloqueos de fila: la concurrencia se verifica en PostgreSQL (local, contenedor y CI) |
| **django-environ** | 0.12.1 | Configuración por variables de entorno (`.env` opcional) | python-decouple | Secretos fuera del código | — |
| **Django REST Framework** | 3.16.1 | API v1: vistas, serializadores, permisos, throttling y paginación | Django Ninja | Estándar de facto e integración con drf-spectacular | Curva de aprendizaje |
| **djangorestframework-simplejwt** | 5.5.1 | JWT para la app: access, refresh rotatorio y lista negra | Tokens de DRF, OAuth2 | Apto para móviles (sin cookies), revocable con la lista negra | Un access ya emitido vale hasta caducar; se mitiga con 15 min y la reclamación `pwv` |
| **drf-spectacular** | 0.28.0 | Esquema OpenAPI y Swagger UI | drf-yasg | OpenAPI 3 actual | Swagger UI carga recursos de un CDN por defecto |
| **Pillow** | 12.3.0 | Validar las imágenes por su contenido real | — | Requisito de `ImageField` | — |
| **segno** | 1.6.6 | Generar el QR como SVG en el servidor | qrcode | Sin dependencias y SVG como data URI, sin servicios externos | — |
| **phonenumbers** | 9.0.41 | Validar y normalizar móviles a E.164 | Expresiones regulares | Reglas reales por país | — |
| **Tailwind CSS** | v4.3.3, CLI standalone (`scripts/tailwind.py:19`) | Sistema de diseño; CSS compilado y versionado en `static/css/app.css` | Bootstrap, CSS propio | Sin Node: el script descarga el binario y **verifica su SHA-256** | Hay que recompilar al cambiar clases |
| **HTML + Django Templates** | — | Todas las páginas | SPA (React) | Renderizado en el servidor: menos superficie y SEO | Interactividad limitada |
| **JavaScript (vanilla)** | `static/js/app.js` (65 líneas), `qr-scanner.js` (136) | Menú plegable, evitar el doble envío y lector de QR | HTMX, Alpine | **Mejora progresiva**: sin JS todo funciona | — |
| **jsQR** | `static/vendor/jsqr/` (con LICENSE) | Lectura de QR cuando el navegador no tiene `BarcodeDetector` | — | Servido localmente, sin CDN | Versión no indicada en el repositorio |
| **Gunicorn** | 25.3.0 (`requirements/prod.txt`) | Servidor WSGI en el contenedor `web` (3 workers síncronos) | uWSGI, Waitress | Estándar para Django en Linux | No funciona en Windows (solo en el contenedor o el VPS) |
| **Nginx** | imagen oficial | Proxy inverso con TLS, estáticos con hash, `/media` solo imágenes y límite de peticiones en el login | Caddy, Traefik | Probado y configurable; segunda capa de límites | Configuración propia que mantener |
| **Redis** | cliente 7.4.1 | Caché compartida obligatoria en producción (límites de intentos y contenido del local) | Caché en la BD | Con varios workers, los contadores deben ser comunes | Sin persistencia ni contraseña: solo en la red interna |
| **Docker + Docker Compose** | Docker Engine 29 / Compose 2.40 (probado) | Imagen multietapa no root y pila completa: web, db, redis, nginx, scheduler, certbot | Instalación directa en el VPS | Reproducible y con rollback por etiquetas | Un solo servidor, sin alta disponibilidad |
| **supercronic** | 0.2.48 (SHA1 verificado) | Tareas programadas en el servicio `scheduler` | cron del sistema, Celery beat | Sin root, sin solapar ejecuciones, logs a stdout | Granularidad de minutos |
| **restic** | 0.18.1 (contenedor) | Copias cifradas de la BD y de `media/` con retención | `pg_dump` + rsync | Cifrado en el cliente, deduplicación y varios destinos | Requiere un destino externo (pendiente en el VPS) |
| **GitHub Actions** | `.github/workflows/ci.yml` | CI: suite en PostgreSQL 17 sin omitidos, `check --deploy`, OpenAPI, build, pila Compose, prueba de humo y copia/restauración | GitLab CI | Integrado con el repositorio | Acciones fijadas por versión principal, no por SHA |

**Tecnologías NO presentes** (pese a que el prompt las mencione): **HTMX y Alpine.js** (grep sin resultados; el plan las permitía «solo si aportan algo»), **Celery** (las tareas son comandos de gestión programados con supercronic; Redis se usa solo como caché), **Kubernetes** y **herramientas de monitorización** (fuera del alcance de la Fase 12).

---

## 5. Estructura del repositorio

### 5.1 Árbol representativo

```text
webcaneca/
├── manage.py                    # settings por defecto: config.settings.dev
├── requirements/                # base.txt (común), dev.txt, prod.txt (= base)
├── .env.example                 # variables de entorno con valores ficticios
├── config/
│   ├── settings/                # base.py (común), dev.py, test.py, prod.py (endurecido)
│   ├── urls.py                  # montaje de las apps por prefijo
│   └── wsgi.py / asgi.py        # settings por defecto: config.settings.prod
├── apps/
│   ├── core/                    # AuditEvent, TimeStampedModel, throttling, client_ip
│   ├── accounts/                # User, CustomerProfile, tokens de email, permisos, registro, perfil
│   ├── catalog/                 # Category, BeerStyle, Product, TapMenu
│   ├── loyalty/                 # CustomerQRCode, LoyaltyRule, Promotion, PointsTransaction (ledger)
│   ├── purchases/               # Purchase y registro de compras
│   ├── rewards/                 # Reward, Redemption, códigos de canje
│   ├── events/                  # Event, Reservation
│   ├── notifications/           # Notification, Campaign, baja, SMS (sin proveedor)
│   ├── staff/                   # panel del personal (solo presentación)
│   ├── dashboard/               # dashboard del propietario (solo presentación)
│   ├── api/                     # API REST v1 (solo presentación + JWT)
│   └── web/                     # páginas públicas, BusinessInfo, context processor
├── templates/                   # base.html, components/, una carpeta por app, emails/, páginas de error
├── assets/css/input.css         # fuente de Tailwind (tokens de la paleta)
├── static/                      # css/app.css (compilado), js/, vendor/jsqr/, img/brand/
├── scripts/tailwind.py          # descarga verificada y compilación del CSS
├── tests/                       # una carpeta por app y base de concurrencia (849 tests)
├── deploy/                      # Gunicorn, Nginx, crontab, rol de PostgreSQL y scripts de despliegue, copia y restauración
├── Dockerfile, compose*.yaml    # imagen multietapa y pilas de producción y local (Fase 12)
├── .github/workflows/ci.yml     # integración continua (GitHub Actions)
└── docs/                        # plan de fases, un documento por fase, arquitectura, despliegue, auditoría, refactorización, guía Flutter, OpenAPI
```

### 5.2 Archivos con responsabilidad relevante

| Ruta | Qué contiene | Quién lo usa | Consecuencia de modificarlo |
|---|---|---|---|
| `config/settings/base.py` | Toda la configuración común y **todos los parámetros de negocio** (límites, plazos, conversión) | Todo el proyecto | Cambiar un límite cambia una regla de negocio; se documenta en el cap. 12 |
| `config/settings/prod.py` | Endurecimiento: rechaza configuraciones inseguras al arrancar | `wsgi.py`, `asgi.py` | Relajarlo puede exponer el sitio (p. ej. un SMTP simulado) |
| `config/urls.py` | Montaje por prefijo; **el orden importa** (`cuenta/` agrupa tres apps) | Django | Reordenar puede sombrear rutas |
| `apps/accounts/permissions.py` | `has_role`, `role_required`, `verified_email_required` | Todas las vistas y la API | Es el corazón de la autorización |
| `apps/accounts/services.py` | Altas, roles, registro, verificación, perfil y consentimientos (894 líneas) | Vistas, admin, comandos y API | Toda alta de usuario debe pasar por aquí |
| `apps/loyalty/ledger.py` | **Única vía** para escribir movimientos de puntos | `purchases`, `rewards`, `dashboard`, `birthdays` | Es la integridad del saldo |
| `apps/purchases/services.py` | Registro de compras transaccional e idempotente | Panel web y API | — |
| `apps/rewards/services.py` | Canje, validación, cancelación y caducidad | Web, panel, API y comando | — |
| `apps/events/services.py` | Eventos y máquina de estados de las reservas | Web, dashboard y API | — |
| `apps/notifications/services.py` | Envío inmediato, cola, reintentos y consentimiento | `accounts`, `events`, `loyalty`, `campaigns` | Todo email sale por aquí |
| `apps/api/tokens.py` | Emisión, rotación y revocación de JWT | Vistas de autenticación de la API | — |
| `apps/core/services.py` | `record_audit_event` | Casi todos los servicios | — |
| `templates/base.html` | Esqueleto HTML, CSS, JS y formulario de logout con CSRF | Todas las páginas | — |
| `scripts/tailwind.py` | Descarga del binario v4.3.3 con verificación SHA-256 | Desarrollador | — |

### 5.3 Mapa de navegación rápida

El índice completo de funcionalidad → URL → vista → servicio → modelo → plantilla → test está en [04_mapa_codigo_y_funcionalidades.md](04_mapa_codigo_y_funcionalidades.md).

---

## 6. Modelo de datos y base de datos

### 6.1 Visión general

**21 modelos concretos** en 10 apps (volcado de `_meta` en [`_trabajo/volcado_modelos.md`](_trabajo/volcado_modelos.md)) más un modelo abstracto (`core.TimeStampedModel`). Principios comunes verificados:
- **Clave primaria interna `id` (BigAutoField)** que nunca sale del backend, más un **`public_id` UUID** único para URLs, API y auditoría (p. ej. `apps/accounts/models.py:39-41`). Así se evita enumerar objetos por id secuencial.
- **No se borra historial:** las relaciones de negocio usan `on_delete=PROTECT` (compras, movimientos, canjes, reservas) y los admins quitan el permiso de borrado.
- **Invariantes en la BD**, además de en Python: `CheckConstraint` y `UniqueConstraint` (también condicionales). El código lo explica, p. ej. el comentario sobre `NULL` en los CHECK de `apps/loyalty/models.py:206-207`.

### 6.2 Diagrama entidad-relación

Archivo independiente: [`diagramas/04_entidad_relacion.mmd`](diagramas/04_entidad_relacion.mmd) (se muestran los campos clave).

```mermaid
erDiagram
    USER ||--o| CUSTOMER_PROFILE : "tiene (solo clientes)"
    USER ||--o{ EMAIL_VERIFICATION_TOKEN : "recibe"
    USER ||--o{ COMMUNICATION_PREFERENCE_CHANGE : "historial de consentimiento"
    USER |o--o{ AUDIT_EVENT : "actor"
    CATEGORY ||--o{ PRODUCT : "agrupa (PROTECT)"
    BEER_STYLE |o--o{ PRODUCT : "estilo (PROTECT)"
    USER ||--o| CUSTOMER_QR_CODE : "QR personal"
    USER |o--o{ LOYALTY_RULE : "creada por"
    USER ||--o{ POINTS_TRANSACTION : "movimientos (PROTECT)"
    PURCHASE |o--o{ POINTS_TRANSACTION : "genera"
    PROMOTION |o--o{ POINTS_TRANSACTION : "bonifica"
    LOYALTY_RULE |o--o{ POINTS_TRANSACTION : "tasa aplicada"
    POINTS_TRANSACTION |o--o| POINTS_TRANSACTION : "compensa (1:1)"
    USER ||--o{ PURCHASE : "cliente"
    USER ||--o{ PURCHASE : "registrada por"
    USER ||--o{ REDEMPTION : "cliente"
    REWARD ||--o{ REDEMPTION : "se canjea en (PROTECT)"
    POINTS_TRANSACTION ||--o| REDEMPTION : "movimiento del canje"
    POINTS_TRANSACTION |o--o| REDEMPTION : "devolución"
    USER |o--o{ REDEMPTION : "validado por"
    USER ||--o{ RESERVATION : "cliente"
    EVENT |o--o{ RESERVATION : "para el evento"
    USER ||--o{ CAMPAIGN : "creada por"
    CAMPAIGN |o--o{ NOTIFICATION : "reparte"
    USER ||--o{ NOTIFICATION : "destinatario (CASCADE)"
```

> Esta versión incrustada solo muestra las relaciones. La versión con los atributos clave (PK, FK, UK y comentarios) está en el archivo `.mmd`. `TAP_MENU` y `BUSINESS_INFO` no tienen relaciones.

### 6.3 Ficha de cada modelo

> Formato: **negocio** · **campos clave** · **relaciones** · **restricciones e índices** · **métodos** · **uso** · **riesgos de integridad controlados**.

#### `core.AuditEvent` — `apps/core/models.py:15`
- **Negocio:** registro de operaciones sensibles (quién, qué y sobre qué).
- **Campos:** `actor` (FK a User, `SET_NULL`, nulo si lo ejecuta un comando), `action` (30 acciones en `Action`, de `OWNER_CREATED` a `API_SESSIONS_REVOKED`), `target_public_id` (UUID, nunca el id interno), `metadata` (JSON **sin datos personales**), `created_at` (indexado).
- **Índices:** `(action, created_at)`. Orden: los más recientes primero.
- **Uso:** `record_audit_event` (`apps/core/services.py:4-16`), llamado desde casi todos los servicios.
- **Riesgo controlado:** la manipulación del rastro. El admin es de solo lectura (`apps/core/admin.py:14-21`). *Limitación:* nada impide en la BD un `UPDATE` directo; la inmutabilidad es por convención y permisos de la aplicación, no por triggers.

#### `accounts.User` — `apps/accounts/models.py:21`
- **Negocio:** cualquier persona con cuenta (cliente, empleado o propietario).
- **Campos:** `public_id` (UUID único), `email` (único, credencial de acceso), `first_name`, `last_name`, `role` (`OWNER`/`EMPLOYEE`/`CUSTOMER`, indexado, por defecto `CUSTOMER`), `is_active`, `email_verified_at` (nulo = sin verificar), `is_staff` (acceso al admin), `date_joined`. Hereda `password` (hash) y `last_login` de `AbstractBaseUser` e `is_superuser` de `PermissionsMixin`.
- **Restricciones** (`:71-85`): email único **sin distinguir mayúsculas** (`UniqueConstraint(Lower("email"))`); rol válido; `is_staff` solo si es OWNER; `is_superuser` solo si es OWNER.
- **Métodos:** `save()` normaliza el email y **anula la verificación si el email cambia** (`_reset_verification_if_email_changed`, `:113-132`); propiedades `is_email_verified`, `is_owner`, `is_employee` e `is_customer`.
- **Gestor:** `UserManager` (`managers.py`): login sin distinguir mayúsculas (`get_by_natural_key`); `create_superuser` fuerza OWNER.
- **Riesgos controlados:** escalada de privilegios (las banderas se derivan del rol en `services._apply_role_flags` y la BD las restringe), cuentas duplicadas por mayúsculas y un email nuevo que heredaría la verificación del anterior.

#### `accounts.CustomerProfile` — `apps/accounts/models.py:157`
- **Negocio:** datos personales del cliente (fuera de `User` para que empleados y propietarios no los tengan).
- **Campos:** `user` (OneToOne, `CASCADE`), dirección estructurada (`address_line_1/2`, `postal_code`, `city`, `province` y `country` ISO-2), `date_of_birth`, `date_of_birth_changed_at`, `phone_number` (validador E.164), `promo_email_opt_in` y `promo_sms_opt_in` (**False por defecto**).
- **Restricción:** el opt-in de SMS exige teléfono (`:220-223`).
- **Métodos:** `clean()` normaliza y valida (`:229-253`), `missing_required_fields()`.
- **Uso:** registro, perfil, estadísticas geográficas, cumpleaños y destinatarios de campañas.
- **Riesgo controlado:** un cliente sin perfil (se crea en la misma transacción, `services.ensure_customer_profile`, y una migración de datos crea los que faltaban: `0003_backfill_customer_profiles.py`).

#### `accounts.EmailVerificationToken` — `apps/accounts/models.py:262`
- **Campos:** `user` (FK `CASCADE`), `purpose` (`VERIFY`/`CHANGE`), `email` (al que se envió), `token_hash` (SHA-256, único), `created_at`, `expires_at`, `used_at`, `revoked_at`.
- **Índice:** `(user, created_at)`. CHECK de `purpose`.
- **Método:** `hash_token()` (estático).
- **Riesgo controlado:** robo de la BD → solo hay hashes; reutilización → `used_at` con UPDATE condicionado. Se purgan con `purge_email_tokens`.

#### `accounts.CommunicationPreferenceChange` — `apps/accounts/models.py:308`
- **Negocio:** prueba de cuándo y cómo se dio o retiró cada consentimiento.
- **Campos:** `user`, `channel` (`EMAIL`/`SMS`), `opted_in`, `source` (`REGISTRATION`/`PROFILE`/`SYSTEM`/`UNSUBSCRIBE`), `created_at`.
- **Riesgo controlado:** pérdida de la prueba de consentimiento; el admin es de solo lectura.

#### `catalog.Category` y `catalog.BeerStyle` — `apps/catalog/models.py:40` y `:72`
- `Category`: `name` (único sin distinguir mayúsculas), `slug` (único, sirve de ancla en `/carta/#slug`), `description`, `position`, `is_published` (si se despublica, desaparecen todos sus productos).
- `BeerStyle`: `name` (único sin distinguir mayúsculas).

#### `catalog.Product` — `apps/catalog/models.py:89`
- **Campos:** `public_id`, `category` (FK `PROTECT`), `kind` (`FIXED`/`HOUSE_BEER`/`GUEST_BEER`/`ROTATING_BEER`), `name`, `description`, `style` (FK `PROTECT`, nulo en los fijos), `abv` (Decimal(4,1), de 0 a 100), `brewery`, `price` (Decimal(6,2) ≥ 0,01), `serving`, `image` (validada, nombre aleatorio), `position`, `is_featured`, `status` (`DRAFT`/`PUBLISHED`/`ARCHIVED`), `published_at`, `archived_at`, `is_available`, `availability_changed_at`.
- **Restricciones (6 CHECK):** precio positivo, rango de graduación, tipo y estado válidos, **las cervezas exigen estilo y graduación y los fijos no tienen estilo**, y coherencia entre `archived_at` y el estado. Índice `(status, category)`.
- **Métodos:** `clean()` (solo se destacan cervezas), `is_beer`, `is_publicly_visible`, `is_currently_available`.
- **Riesgo controlado:** perder el historial (nunca se borra) y mostrar productos incoherentes.

#### `catalog.TapMenu` — `apps/catalog/models.py:259`
- Imagen de la carta de grifos con `text_alternative` (accesibilidad) e `is_published`. En la web se muestra la publicada más reciente.

#### `loyalty.CustomerQRCode` — `apps/loyalty/models.py:15`
- **Campos:** `user` (OneToOne), `token` (32 caracteres base32, único, no editable), `rotated_at`.
- **Restricción:** CHECK con la expresión regular `^[A-Z2-7]{32}$`.
- **Detalle de privacidad:** `__str__` no muestra el token (`:48-50`).

#### `loyalty.LoyaltyRule` — `apps/loyalty/models.py:56`
- **Campos:** `public_id`, `points_per_euro` (Decimal de 0,01 a 100), `valid_from`, `note`, `created_by` (`PROTECT`).
- **Regla:** versionada; no se edita (el admin la deja en solo lectura, `apps/loyalty/admin.py:43`), y una regla nueva no puede entrar en vigor en el pasado (`clean`, `:104-109`).

#### `loyalty.Promotion` — `apps/loyalty/models.py:112`
- **Campos:** `public_id`, `name`, `description`, `kind` (`PURCHASE`/`BIRTHDAY`), `bonus_type` (`FIXED_POINTS`/`MULTIPLIER`), `fixed_points` (de 1 a 10000), `multiplier` (de 1,01 a 10), `min_purchase_amount`, `starts_at`, `ends_at`, `max_uses_per_customer`, `max_total_uses`, `birthday_window_days` (**sin uso desde la Fase 10**), `status` (`DRAFT`/`ACTIVE`/`PAUSED`/`ENDED`).
- **Restricciones (9 CHECK):** coherencia de la bonificación (fija o multiplicador, nunca ambas), fechas, límites positivos y que las de cumpleaños sean solo de puntos fijos.

#### `loyalty.PointsTransaction` (ledger) — `apps/loyalty/models.py:276`
- **Negocio:** cada movimiento de puntos. **El saldo es la suma de los movimientos.**
- **Campos:** `public_id`, `customer` (`PROTECT`), `kind` (`EARN_PURCHASE`, `PROMOTION_BONUS`, `ADJUSTMENT`, `REVERSAL`, `REDEMPTION`, `BIRTHDAY_GIFT`), `points` (≠ 0), `balance_after` (≥ 0), `purchase`, `promotion` y `rule` (FK `PROTECT`), `reverses` (OneToOne a sí mismo: **un movimiento solo se compensa una vez**), `birthday_year`, `base_amount`, `points_per_euro` (copia de la tasa aplicada), `created_by`, `reason`, `idempotency_key` (único), `created_at`.
- **Restricciones (10 CHECK + 3 UNIQUE condicionales, `:365-420`):** forma de cada tipo de movimiento; saldo resultante no negativo; **una acumulación por compra**; **una bonificación por promoción y compra**; **un cumpleaños por cliente y año**.
- **Índice:** `(customer, created_at)`.
- **Riesgo controlado:** puntos duplicados, saldo negativo y alterar el historial (se corrige con `REVERSAL` o `ADJUSTMENT`).

#### `purchases.Purchase` — `apps/purchases/models.py:21`
- **Campos:** `public_id`, `customer` y `registered_by` (FK `PROTECT`), `amount` (Decimal(8,2)), `created_at`, `source` (`MANUAL`; `POS` reservado), `status` (`COMPLETED`; `VOIDED` reservado), `idempotency_key` (único), `external_reference` (reservado para el TPV).
- **Restricciones:** importe positivo, origen y estado válidos, **`customer` ≠ `registered_by`** (`:88-90`) y referencia externa única por origen.
- **Índices:** `(customer, created_at)` y `(registered_by, created_at)`.
- **Importante:** no es una factura ni la caja (`:4-6`).

#### `rewards.Reward` — `apps/rewards/models.py:36`
- **Campos:** `public_id`, `name`, `description`, `image`, `points_cost` (de 1 a 100000), `status` (`DRAFT`/`ACTIVE`/`PAUSED`/`ARCHIVED`), `valid_from`, `valid_until`, `stock` (nulo = ilimitado), `position`.
- **Restricciones (4 CHECK):** estado, rango de coste, fechas y stock ≥ 0.
- **Métodos:** `is_in_stock`, `is_in_period`, `is_requestable`.

#### `rewards.Redemption` — `apps/rewards/models.py:133`
- **Campos:** `public_id`, `customer`, `reward` (`PROTECT`), `points_cost` (copia), `code` (12 caracteres, único), `status` (`PENDING`/`USED`/`EXPIRED`/`CANCELLED`), `created_at`, `expires_at`, `idempotency_key` (único), `spend_movement` (OneToOne al movimiento de canje), `refund_movement` (OneToOne a la devolución), `validated_by`, `validated_at`, `closed_at`.
- **Restricciones (7 CHECK + 1 UNIQUE condicional, `:194-225`):** formato del código; coherencia `USED` ⇔ quién y cuándo; coherencia cerrado ⇔ devolución; **nadie valida su propio canje**; **un solo `PENDING` por cliente y recompensa**.
- **Índices:** `(customer, created_at)`, `(status, expires_at)` y `(validated_by, validated_at)`.

#### `events.Event` — `apps/events/models.py:42`
- **Campos:** `public_id`, `title`, `summary`, `description`, `starts_at`, `ends_at`, `image`, `status` (`DRAFT`/`PUBLISHED`/`ARCHIVED`), `is_featured`, `accepts_reservations`, `capacity` (de 1 a 1000, nulo = sin límite), `published_at`.
- **Restricciones:** estado, fechas y aforo.

#### `events.Reservation` — `apps/events/models.py:112`
- **Campos:** `public_id`, `customer` (`PROTECT`), `event` (`PROTECT`, **nulo = reserva de mesa**), `requested_for`, `party_size` (de 1 a 50 en la BD; 20 en settings), `notes` (solo para el propietario), `status`, `owner_message`, `status_changed_at`, `status_changed_by`, `idempotency_key`, `created_at`, `updated_at`.
- **Transiciones** (`:121-124`): `PENDING → {CONFIRMED, REJECTED, CANCELLED}`; `CONFIRMED → {CANCELLED, COMPLETED}`.
- **Restricciones:** estado, rango de personas, toda decisión lleva fecha y **una reserva activa por cliente y evento** (UNIQUE condicional, `:179-183`).

#### `notifications.Campaign` — `apps/notifications/models.py:36`
- **Campos:** `public_id`, `name`, `channel`, `subject` (obligatorio en email por CHECK), `body` (2000 caracteres en email y 320 en SMS), `status` (`DRAFT`/`QUEUED`/`DISPATCHED`/`CANCELLED`), `created_by`, `queued_at`, `dispatched_at`, `recipients_count`.

#### `notifications.Notification` — `apps/notifications/models.py:80`
- **Campos:** `public_id`, `recipient` (`CASCADE`), `kind` (12 tipos), `category` (`TRANSACTIONAL`/`PROMOTIONAL`), `channel`, `status` (`PENDING`/`SENDING`/`SENT`/`FAILED`/`SKIPPED`), `context` (JSON sin tokens ni datos personales), `dedup_key` (único), `campaign`, `attempts`, `next_attempt_at`, `last_error` (solo el tipo de error), `sent_at`, `created_at`, `updated_at`.
- **Restricciones:** **la categoría se deriva del tipo** (una campaña nunca pasa como transaccional, `:148-154`) y `sent_at` ⇔ `SENT`.
- **Privacidad:** no guarda ni el destinatario en claro ni el cuerpo del mensaje (`:7-12`).

#### `web.BusinessInfo` — `apps/web/models.py:43`
- **Singleton:** CHECK `id = 1` y `save()` fija `pk = 1`.
- **Campos:** `address`, `opening_hours` («Días | horario»), `email`, `phone`, `social_links` (solo `https`), `about_text`, `hero_text`, `announcement`.

### 6.4 Recorrido de los datos: del formulario a la BD y de vuelta

Ejemplo: **edición del perfil del cliente**.
1. `POST /cuenta/perfil/` → `accounts.views.profile` (`views.py:146`), solo para CUSTOMER.
2. `ProfileForm(request.POST)` convierte los tipos (fecha, texto) y adelanta los errores de formato (`forms.py:64-80`).
3. `services.update_customer_profile(user=request.user, ...)` (`services.py:769`): **rechaza campos desconocidos** (lista blanca `PROFILE_FIELDS`), bloquea las filas de usuario y perfil, normaliza (`_apply_profile_data`), aplica el enfriamiento de 365 días de la fecha de nacimiento, retira el SMS si se borra el teléfono, valida todo (`full_clean`) y guarda.
4. La BD aplica el CHECK «SMS solo con teléfono».
5. `AuditEvent PROFILE_UPDATED` con **solo los nombres** de los campos cambiados.
6. Recuperación: en el siguiente GET, `CustomerProfile.objects.filter(user=user)` → `_profile_initial` → plantilla `accounts/profile.html`.

### 6.5 Evolución del esquema (migraciones)

26 archivos de migración. Commit de origen de cada uno según `git log --diff-filter=A`:

| Fase (commit) | Migraciones añadidas | Qué cambia |
|---|---|---|
| F0 (`4d842da`) | `accounts/0001_initial`, `core/0001_initial` | Usuario propio con roles antes de la primera migración; auditoría |
| F1 (`b2cf7f6`) | `accounts/0002_customer_profile`, `0003_backfill_customer_profiles` (**RunPython**, inversa `noop`) | Perfil 1:1 y creación de los perfiles que faltaban |
| F2 (`d948db7`) | `accounts/0004`, `0005`, `0006`; `core/0002` | Verificación de email, datos personales, tokens e historial de preferencias |
| F4 (`b035ca4`) | `catalog/0001_initial`; `core/0003` | Carta |
| F5 (`d1c1a89`) | `loyalty/0001_initial`, `purchases/0001_initial`; `core/0004` | QR y compras |
| F6 (`99711bc`) | `loyalty/0002_points_ledger_promotions`; `core/0005` | Ledger, reglas y promociones |
| F7 (`c185ff4`) | `rewards/0001_rewards_redemptions`; `core/0006` | Recompensas y canjes |
| F9 (`70fb531`) | `web/0001_business_info`; `core/0007` | Contenido del local |
| F10 (`b91d8bd`) | `events/0001`, `notifications/0001`, `loyalty/0003_birthday_gift` (**RunPython** de comprobación), `accounts/0007`, `web/0002`; `core/0008` | Eventos, reservas, notificaciones y regalo de cumpleaños |
| F11 (`eec6abc`) | `core/0009_audit_actions_phase11` | Nuevas acciones de auditoría |
| PostgreSQL, auditoría, F12 y refactorización | Ninguna | Sin cambios de esquema (`makemigrations --check`) |

Patrón observado: **cada fase añade una migración de `core`** con las nuevas acciones de auditoría (se modifican los `choices` de `AuditEvent.action`). No hay migraciones en F3 ni en F8 (no tocan modelos). `makemigrations --check` confirma que el esquema está sincronizado con los modelos.

---

## 7. Explicación detallada de cada funcionalidad

Cada módulo sigue la estructura **A–O** del prompt: A objetivo · B requisitos · C archivos · D modelos · E flujo · F funciones · G código · H reglas · I seguridad · J interacción · K casos normales y de error · L tests · M ejemplo · N decisiones · O limitaciones. El código comentado línea a línea está en el **cap. 8**; aquí se citan los fragmentos por su identificador (**[C8.x]**).

### 7.1 Web pública

- **A. Objetivo:** escaparate de la cervecería con carta, recompensas y eventos actualizados desde la base de datos, sin inventar datos del negocio.
- **B. Requisitos:** Fase 3 (sistema de diseño, páginas Inicio, La cervecería y Contacto, páginas de error, contraste AA, diseño responsive) y Fases 4, 7 y 10 (rellenar Carta, Recompensas y Eventos).
- **C. Archivos:** `apps/web/views.py`, `urls.py`, `content.py`, `context_processors.py`, `models.py` y `services.py`; `templates/base.html`, `templates/web/*.html`, `templates/components/*.html` (12 componentes: `product_card`, `event_card`, `tap_menu`, `pending`, `page_header`…), `templates/400.html` a `500.html`; `assets/css/input.css`; `static/css/app.css`; `static/js/app.js`.
- **D. Modelos:** `web.BusinessInfo` (singleton) y, en lectura, `catalog.Product`, `TapMenu`, `rewards.Reward` y `events.Event`.
- **E. Flujo:** `GET /` → `HomeView` (`views.py:15`) → `catalog.selectors.featured_beers()` + `events.selectors.featured_events()` → `web/home.html`. El context processor `site` (`context_processors.py:4-10`) inyecta en **todas** las páginas la navegación (`MAIN_NAV`), el lema y `business` (`services.business_info()`, con caché de 300 s).
- **F. Funciones:** `business_info()` (`services.py:55`) mezcla los datos fijos de la marca (`content.BUSINESS`) con lo que el propietario guardó; `update_business_info()` (`:71`) es la única vía de escritura.
- **G. Código:** [C8.15] `BusinessInfo` singleton y validación de enlaces https.
- **H. Reglas:** lo que no se ha aportado vale `None` y se muestra como «pendiente» (`content.py:1-7`); solo se aceptan enlaces sociales `https` (`models.py:38-40`); horario con un máximo de 10 líneas «Días | horario».
- **I. Seguridad:** las vistas públicas solo admiten GET y HEAD (test `test_only_get_and_head_allowed`); el autoescape de las plantillas de Django evita XSS en los textos del propietario; las páginas no exponen datos personales (`test_public_pages_do_not_expose_personal_data`).
- **J. Interacción:** lee de `catalog`, `rewards` y `events` por sus selectores; el dashboard escribe `BusinessInfo` y la caché se invalida en `on_commit` (`services.py:86`).
- **K. Casos:** sin productos publicados, la carta muestra un estado vacío (`components/empty_state.html`); 404 y 403 con plantilla de marca; el 500 se pinta sin contexto de petición.
- **L. Tests:** `tests/web/test_public_pages.py` (17), `test_menu_page.py` (12), `test_account_forms_ui.py` (11). Comprueban el renderizado, la navegación, que no haya datos inventados, las páginas de error, que el CSS compilado contenga la paleta y que `app.js` no contenga reglas de validación.
- **M. Ejemplo:** el propietario escribe «Lunes a jueves | 18:00–00:00» en `/dashboard/contenido/` → en `/contacto/` aparece el horario en lugar de «Pendiente de publicar».
- **N. Decisiones:** renderizado en el servidor con Tailwind compilado (sin Node) y JS de mejora progresiva. Alternativa descartada: una SPA, que exige una API para todo y aumenta la superficie de ataque.
- **O. Limitaciones:** el contraste AA y el diseño responsive están documentados (`docs/fase-03-sistema-diseno-web-publica.md`) pero **no tienen test automático**: *pendiente de verificación visual*. Los datos reales del local dependen de que el propietario los rellene.

**Estado:** Implementado y verificado (funcional); el aspecto visual, pendiente de verificación.

### 7.2 Carta y catálogo de cervezas

- **A. Objetivo:** que el propietario gestione la carta (productos fijos y cervezas propias, invitadas y rotativas) sin tocar código, y que la web muestre solo lo publicado.
- **B. Requisitos:** Fase 4 + ajuste (imagen de la carta de grifos en lugar de 14 grifos; un precio por producto; las agotadas aparecen como «Agotada»; gestión en el admin).
- **C. Archivos:** `apps/catalog/models.py`, `selectors.py`, `services.py`, `validators.py` y `admin.py`; `apps/web/views.py:29-36` (`MenuView`); `templates/web/menu.html`; `components/product_card.html` y `tap_menu.html`; el dashboard (`/dashboard/carta/` y `/dashboard/cervezas/`).
- **D. Modelos:** `Category`, `BeerStyle`, `Product` y `TapMenu` (cap. 6).
- **E. Flujo de lectura:** `GET /carta/` → `MenuView` → `selectors.public_menu()` (`selectors.py:31-39`): categorías publicadas con un `Prefetch` de los productos publicados, **los agotados al final** y sin categorías vacías → `current_tap_menu()`.
- **E'. Flujo de escritura:** el admin (`ProductAdmin.save_model`, `admin.py:154-177`) guarda los datos y aplica el estado y la disponibilidad **a través de los servicios** `set_product_status` y `set_product_availability` (`services.py`, transacción + `select_for_update` + auditoría con `{from, to}`). Desde el dashboard: `product_status` y `product_availability` (`dashboard/views.py:622-646`).
- **F. Funciones:** `public_products()` (la regla de visibilidad en un solo sitio), `featured_beers(limit=6)`, `products_for_management()` (solo el propietario).
- **G. Código:** [C8.14] validación de imágenes con Pillow.
- **H. Reglas:** público = `PUBLISHED` + categoría publicada; para publicar se exige `full_clean()` (`apps/catalog/services.py:41-44`); las cervezas exigen estilo y graduación (CHECK); solo se destacan cervezas; **nada se borra** (se archiva; el admin devuelve `has_delete_permission = False`).
- **I. Seguridad:** `OwnerOnlyAdminMixin` (`admin.py:22-38`) como defensa adicional aunque otro rol llegara al admin; imágenes validadas por su contenido real (no por la extensión), con tamaño y dimensiones limitados y nombre de archivo aleatorio (sin datos del nombre original).
- **J. Interacción:** `web` (carta e inicio) y `dashboard`. La API v1 **no** expone la carta (verificado en `apps/api/urls.py`).
- **K. Casos:** repetir «Publicar» no cambia nada ni duplica la auditoría (idempotente); un SVG renombrado a `.png` se rechaza (`image_invalid`).
- **L. Tests:** `tests/catalog/` (59): modelos, selectores, servicios, validadores y permisos del admin (`test_other_roles_and_anonymous_cannot_access`).
- **M. Ejemplo:** la IPA rotativa se agota → «Marcar como agotado» → sigue en la carta con la etiqueta «Agotada» y pasa al final de su categoría.
- **N. Decisiones:** gestión en el admin de Django (rápida y segura) en lugar de un CRUD propio; imagen de la carta de grifos por simplicidad operativa.
- **O. Limitaciones:** Django solo sirve las imágenes subidas en desarrollo (`config/urls.py:28-31`); en producción las sirve Nginx desde el volumen `media` (Fase 12), que entra en las copias. No hay precios por formato (un precio por producto).

**Estado:** Implementado y verificado.

### 7.3 Autenticación y gestión de clientes

- **A. Objetivo:** alta segura de clientes, acceso, recuperación de la cuenta, verificación del email y edición del perfil.
- **B. Requisitos:** Fases 0 y 2; auditoría de la Fase 11 (anti-enumeración por tiempo, IP real y auditoría de contraseñas).
- **C. Archivos:** `apps/accounts/` (`views.py`, `forms.py`, `services.py`, `validators.py`, `normalization.py`, `emails.py`, `permissions.py`, `managers.py`, `urls.py`); `templates/accounts/*.html` y `templates/emails/*.txt`.
- **D. Modelos:** `User`, `CustomerProfile`, `EmailVerificationToken` y `CommunicationPreferenceChange`.
- **E. Flujos:**
  1. **Registro:** `/cuenta/registro/` → `RegistrationForm` → `services.register_customer` (cap. 9.1) [C8.3].
  2. **Login:** `/cuenta/entrar/` → `LoginView` + `ThrottledAuthenticationForm` (`forms.py:177-203`, límite en `LoginThrottleMixin`): límites de 5 fallos por email y 30 por IP en 15 minutos, con el mismo mensaje exista o no la cuenta. El login del admin técnico comparte los mismos contadores (`ThrottledAdminAuthenticationForm`, `forms.py:206-213`; añadido en la auditoría previa a la Fase 12). Tras entrar, `accounts:home` redirige según el rol (`views.py:126-133`).
  3. **Logout:** `/cuenta/salir/` es un **POST con CSRF** (formulario en `templates/base.html:43-46`; `LogoutView` de Django).
  4. **Recuperación:** `PasswordResetView` (tokens nativos de Django, 2 h, `base.py:124`), límite por IP y enlace construido con `SITE_BASE_URL` (no con la cabecera Host, `views.py:237-240`).
  5. **Verificación:** enlace `/cuenta/verificar-email/<token>/`: GET muestra un botón y POST lo consume (`views.py:71-88`) [C8.4].
  6. **Cambio de email:** `services.request_email_change` exige la contraseña; el email no cambia hasta confirmar; se avisa a la dirección antigua.
  7. **Perfil:** `services.update_customer_profile` (cap. 6.4).
- **F. Funciones:** `_create_user`, `register_customer`, `_issue_email_token`, `confirm_email_token`, `request_email_change`, `change_password`, `reset_password_with_token`, `update_customer_profile` y `set_communication_preferences` (todas en `services.py`).
- **G. Código:** [C8.2] permisos; [C8.3] anti-enumeración en el registro; [C8.4] consumo atómico del token; [C8.5] invariante del email.
- **H. Reglas:** contraseña de al menos 10 caracteres, no común, no solo numérica y no parecida a los datos del usuario (`base.py:109-117`); email normalizado a minúsculas (`normalization.py`); edad mínima de 18 años; 5 emails de verificación al día y 1 por minuto; token de 24 h, de un solo uso y revocado al emitir otro.
- **I. Seguridad:** hash de contraseñas nativo de Django (PBKDF2 por defecto; en los tests se usa MD5 **solo** para acelerarlos, `config/settings/test.py:8-9`); CSRF en todos los formularios; `never_cache` en las páginas sensibles; las vistas nunca reciben un id de usuario (`views.py:1-5`); el token no queda en los logs (errores con 200) y en la BD solo se guarda su hash.
- **J. Interacción:** `notifications` (envío de emails y registro), `core` (auditoría y límites).
- **K. Casos de error:** email ya registrado → la misma respuesta + aviso al titular; token caducado, usado o revocado → mensaje específico; demasiados intentos → mensaje genérico.
- **L. Tests:** `tests/accounts/` (195), entre otros `test_registration.py:277` (`test_duplicate_email_does_not_reveal_existence`), `test_email_verification.py` (23) y `tests/core/test_phase11_audit.py:48-91`.
- **M. Ejemplo:** Ana (datos ficticios, `ana@example.com`) se registra → recibe el enlace → mientras no lo confirma puede entrar y editar su perfil, pero `/cuenta/mi-qr/` le responde 403.
- **N. Decisiones:** reutilizar las vistas nativas de Django (login, logout y recuperación) personalizando el formulario; verificación propia con tokens en BD (revocables y auditables) en lugar de enlaces firmados sin estado.
- **O. Limitaciones:** el **envío real por SMTP no se ha verificado** (sí con Mailpit en la pila local); no hay 2FA. Los contadores de intentos son comunes a todos los workers porque producción exige una caché compartida (auditoría P1-2), y el login del admin tiene el mismo límite (P1-1).

**Estado:** Implementado y verificado (el envío SMTP real, pendiente).

### 7.4 Privacidad y datos personales

- **A. Objetivo:** recoger solo los datos necesarios, limitar quién los ve y dejar constancia de los accesos y consentimientos.
- **B. Requisitos:** CLAUDE.md §3, Fase 2 (política de datos) y Fase 9 (consulta auditada).
- **C. Archivos:** `apps/accounts/models.py` y `selectors.py`, `apps/loyalty/services.py:147-150` (nombre abreviado), `apps/dashboard/views.py:149-225`, `apps/events/selectors.py:104-123`, `apps/notifications/models.py:1-20` y `apps/core/models.py:15-22`.
- **D. Datos recogidos y finalidad:**

| Dato | Dónde | Finalidad (según el código y los docs) | ¿Quién lo ve? |
|---|---|---|---|
| Nombre y apellidos | `User` | Identificación | El propietario completo; el empleado solo «Nombre I.» |
| Email | `User` | Acceso y comunicaciones | El propietario (listado y ficha) |
| Dirección estructurada | `CustomerProfile` | Estadística geográfica agregada | Solo el propietario en la ficha (consulta auditada) |
| Fecha de nacimiento | `CustomerProfile` | Edad mínima y regalo de cumpleaños | Solo el propietario en la ficha |
| Móvil (opcional) | `CustomerProfile` | SMS promocional (sin proveedor) y contacto de reservas | El propietario (ficha y detalle de la reserva, ambos auditados) |
| Consentimientos | `CustomerProfile` + historial | Base legal de las comunicaciones | El propietario |
| Notas de la reserva | `Reservation.notes` | Comentarios para el local | Solo el propietario; **no van en los emails** |

- **E. Flujo de acceso auditado:** `GET /dashboard/clientes/<uuid>/` → `customer_detail` → `accounts.record_customer_data_access` (`AuditEvent CUSTOMER_DATA_VIEWED` con el `public_id` del cliente, **sin los datos**).
- **H. Reglas de minimización verificadas:**
  - Listados del propietario con `.only(LIST_FIELDS)` (sin dirección, teléfono ni fecha de nacimiento) (`accounts/selectors.py:45, 94`).
  - El empleado ve solo «Lúa F.» (`loyalty/services.customer_display_name`).
  - La búsqueda de clientes se envía por **POST y se guarda en la sesión** para que el nombre o el email no queden en la URL ni en los logs (`dashboard/views.py:150-156`).
  - Las estadísticas geográficas solo usan las direcciones declaradas, **sin geolocalización por IP** y sin direcciones completas (`accounts/selectors.py:11-14`).
  - La auditoría guarda los nombres de los campos cambiados, nunca sus valores (`services.py:826-833`).
  - Las notificaciones no guardan ni el destinatario ni el cuerpo; los tokens de los enlaces nunca se persisten (`notifications/models.py:7-12`).
  - Los logs solo llevan `public_id` (p. ej. `purchases/services.py:101, 193`).
  - Las IPs y los emails de los contadores se guardan como hash SHA-256 en la caché (`core/throttling.py:14-16`).
- **Preferencias promocionales:** desactivadas por defecto; **verificar el email no es consentimiento** (`services.py:825`); cada cambio queda en `CommunicationPreferenceChange`; baja con un enlace firmado y POST de confirmación (cap. 7.13); el regalo de cumpleaños **no depende** del consentimiento publicitario (`loyalty/birthdays.py:14-17`).
- **Rectificación:** el cliente edita sus datos en `/cuenta/perfil/` (fecha de nacimiento como máximo una vez al año).
- **Exportación y eliminación:** **no identificadas**. No hay funcionalidad de exportar los datos ni de borrar la cuenta a petición; las cuentas se **desactivan** (el admin no permite borrar, `accounts/admin.py:149-151`), lo que conserva el historial pero no implementa por sí solo el derecho de supresión.
- **L. Tests:** `tests/loyalty/test_points_views.py:57` (`test_never_shows_other_customers_data`), `tests/staff/test_panel.py` (sin datos personales), `tests/dashboard/test_access.py:155`, `tests/web/test_public_pages.py:109`.
- **O. Limitaciones:** el código **no garantiza el cumplimiento del RGPD** por sí mismo (faltan textos legales, exportación y supresión, y una política de conservación más allá de la purga de tokens).

**Estado:** Minimización y auditoría implementadas y verificadas; exportación y supresión, no identificadas.

### 7.5 Código QR del cliente

- **A. Objetivo:** identificar al cliente en la barra sin enseñar ni transmitir datos personales.
- **B. Requisitos:** Fase 5.
- **C. Archivos:** `apps/loyalty/models.py:15-50`, `services.py:29-150`, `views.py:26-39, 66-76`; `templates/loyalty/my_qr.html`; `static/js/qr-scanner.js`; `static/vendor/jsqr/`.
- **D. Modelo:** `CustomerQRCode` (OneToOne con el usuario y token único).
- **E. Generación:** la primera visita a `/cuenta/mi-qr/` llama a `get_customer_qr()`, que lo crea con `generate_token()` = `base64.b32encode(secrets.token_bytes(20))` → **32 caracteres A-Z/2-7 (160 bits)**. Si dos peticiones lo crean a la vez, el `IntegrityError` se resuelve devolviendo el existente (`services.py:97-108`).
- **Contenido:** `CF1:` + token (`qr_payload`). **Ningún dato personal ni el saldo**; el prefijo versiona el formato y permite descartar QR ajenos sin consultar la BD.
- **Representación:** SVG generado en el servidor con `segno` como data URI (`views.py:32-34`), sin servicios externos. Debajo, el código en grupos de 4 para teclearlo a mano.
- **Validación:** `normalize_code()` acepta el QR o el código tecleado (espacios, guiones, minúsculas) y valida la expresión regular; `identify_customer()` busca el token y exige un cliente activo y verificado.
- **Uso en la compra:** cap. 7.6. El QR **solo identifica**: no autoriza nada por sí mismo. Registrar una compra exige un empleado autenticado (`loyalty/models.py:19-22`).
- **Por qué no permite modificar datos:** el token es un identificador opaco; las vistas que lo usan son del personal y solo devuelven el nombre abreviado; no hay ningún endpoint que acepte el token para cambiar nada del cliente.
- **Renovación:** `POST /cuenta/mi-qr/renovar/` → `rotate_customer_qr()`: como máximo 5 al día, auditado (`QR_ROTATED`); el anterior deja de servir.
- **G. Código:** [C8.6].
- **I. Seguridad y abuso:** un QR fotografiado por otra persona permitiría que **se le sumaran puntos al titular** (no robarlos). Se mitiga con la renovación. Límite de 20 códigos no válidos seguidos por empleado (anti-fuerza bruta). El token se guarda en claro porque hay que volver a dibujarlo, pero nunca se escribe en logs ni en la auditoría.
- **L. Tests:** `tests/loyalty/test_qr.py` (22).
- **O. Limitaciones:** escaneo con cámara **no probado en dispositivos físicos** (README); la cámara solo funciona en `localhost` o con HTTPS (requisito del navegador).

**Estado:** Implementado y verificado (escaneo en dispositivo, pendiente).

### 7.6 Registro de compras

- **A. Objetivo:** que el personal anote en la barra el importe consumido por un cliente del programa.
- **B. Requisitos:** Fase 5.
- **C. Archivos:** `apps/purchases/models.py`, `services.py`, `forms.py`, `views.py`, `selectors.py` y `admin.py`; `templates/purchases/scan.html`, `confirm.html` y `detail.html`; API `apps/api/views/staff.py:35-68`.
- **D. Modelo:** `Purchase`.
- **E. Flujo (dos pasos):** `/panel/compras/` (escanear) → `POST identificar/` (`identify_for_purchase` → nombre abreviado + formulario con `code` oculto y una `idempotency_key` UUID nueva) → `POST registrar/` (`register_purchase`) → detalle (cap. 9.5).
- **Quién puede:** empleados y propietarios activos (`is_staff_member`) y **nunca para sí mismos** (CHECK `purchases_not_self_registered`).
- **Datos:** QR o código e importe. Nada más: los puntos los calcula el servidor.
- **H. Validaciones:** importe en `Decimal` (acepta coma o punto; **rechaza `float`**: lo convierte desde `repr`), como máximo 2 decimales, de 0,01 a 1000 €; origen habilitado (`MANUAL`); clave UUID válida; QR de un cliente activo y verificado; **todo se vuelve a comprobar dentro de la transacción** con el cliente bloqueado.
- **Repetición:** misma clave + mismos datos → devuelve la compra existente (`created=False`, mensaje «no se ha duplicado»); misma clave con otros datos → `idempotency_conflict` [C8.7].
- **Historial:** la compra es inmutable (el admin es de solo lectura) y está ligada a sus movimientos de puntos.
- **Compras registradas ≠ facturación:** el sistema no conoce la caja ni el TPV; las estadísticas lo dicen explícitamente (`NOT_REVENUE_NOTE`, `purchases/selectors.py:23-26`) y `business_revenue` siempre es `None`.
- **I. Seguridad:** el código del cliente viaja por POST (nunca en la URL), `never_cache`, 404 para las compras de otro empleado (`views.py:130-132`), límite de 20 fallos y un log sin código ni datos del cliente.
- **L. Tests:** `tests/purchases/test_services.py` (25: importes, cliente inactivo o sin verificar, doble envío, clave reutilizada, autorregistro rechazado por la BD), `test_views.py` (25), `test_stats.py` (6).
- **M. Ejemplo:** un empleado registra 12,50 € → compra creada + movimiento `EARN_PURCHASE` de 12 puntos (conversión por defecto); vuelve a pulsar «Registrar» → «Esta compra ya estaba registrada».
- **N. Decisiones:** dos pasos (identificar y confirmar el nombre) para evitar asignar la compra a otra persona; clave de idempotencia generada por el servidor.
- **O. Limitaciones:** **no hay anulación** (`VOIDED` reservado) ni TPV (`POS` reservado); la clave viaja de ida y vuelta por el navegador y el servidor no comprueba que la emitiera él (lo que protege es el UNIQUE + `_replay`, D9); y si el navegador **reenvía el paso de identificación** (volver atrás), se genera una clave nueva y un segundo «Registrar» crearía otra compra (ver [05_limitaciones_y_pendientes.md](05_limitaciones_y_pendientes.md), §5).

**Estado:** Implementado y verificado.

### 7.7 Sistema de puntos

- **A. Objetivo:** acumular puntos de forma auditable, sin manipulación ni duplicados.
- **B. Requisitos:** Fase 6.
- **C. Archivos:** `apps/loyalty/ledger.py`, `conversion.py`, `promotions.py`, `selectors.py`, `models.py:53-423` y `admin.py`; `templates/loyalty/my_points.html`; dashboard `/dashboard/puntos/`, ajuste y compensación.
- **D. Modelos:** `PointsTransaction`, `LoyaltyRule` y `Promotion`.
- **Reglas de obtención:** puntos base = `importe × puntos_por_euro` **truncado hacia abajo** (`ROUND_DOWN`): 12,50 € × 1,00 = 12; 0,99 € = 0 (`conversion.py:4-11`). Tasa: la última `LoyaltyRule` con `valid_from ≤ fecha de la compra` o, si no hay ninguna, `LOYALTY_DEFAULT_POINTS_PER_EURO = 1.00`. Promociones de compra: puntos fijos o `base × (multiplicador − 1)` truncado, con importe mínimo y límites de uso total y por cliente; se acumulan todas las aplicables.
- **Registro de movimientos:** **única vía**: `ledger.py`. Cada escritura bloquea la fila del cliente (`select_for_update`), recalcula el saldo (`SUM`) y crea el movimiento con `balance_after`; si quedaría negativo, `InsufficientPoints` [C8.8].
- **Saldo y trazabilidad:** saldo = `SUM(points)`; cada movimiento guarda `balance_after`, la regla y la tasa aplicadas, quién y por qué. Resumen para el cliente (`selectors.points_summary`): obtenidos, utilizados (canjes menos devoluciones) y corregidos.
- **Correcciones:** `adjust_points` (solo el propietario, entero distinto de 0 de hasta ±100000, motivo obligatorio, idempotente por clave) y `reverse_movement` (compensa una vez gracias al OneToOne `reverses`; **no se compensan canjes**: se cancelan).
- **Transacciones:** los puntos se crean **dentro de la misma transacción que la compra** (`purchases.services.on_purchase_registered`): o se guardan ambos o ninguno.
- **Concurrencia:** bloqueo de la fila del cliente + bloqueo de las promociones para respetar `max_total_uses` + restricciones únicas como red final.
- **Duplicados y manipulación:** 3 UNIQUE condicionales y `idempotency_key` única; los puntos **nunca llegan del cliente** (ningún formulario ni serializador tiene un campo de puntos, salvo el ajuste del propietario).
- **G. Código:** [C8.8] ledger; [C8.9] conversión; [C8.10] restricciones del ledger.
- **L. Tests:** `tests/loyalty/test_points.py` (41: redondeo, float y negativos rechazados, idempotencia, saldo no negativo en la BD, compensaciones), `test_promotions.py` (18), `test_points_views.py` (15).
- **M. Ejemplo:** Promoción «Doble jueves» (×2,00, mínimo 10 €). Compra de 15,00 € → `EARN_PURCHASE` +15 y `PROMOTION_BONUS` +15.
- **N. Decisiones:** ledger de solo inserción con saldo derivado (como un libro contable) en lugar de un campo `saldo` editable: da trazabilidad y permite reconstruir cualquier saldo.
- **O. Limitaciones:** `balance()` suma todos los movimientos en cada escritura (O(n) por cliente; aceptable a esta escala, mejorable con un saldo materializado); la conversión por defecto está «pendiente de confirmar por el propietario».

**Estado:** Implementado y verificado.

### 7.8 Recompensas y canjes

- **A. Objetivo:** canjear puntos por recompensas con un código de un solo uso que se valida en la barra.
- **B. Requisitos:** Fase 7.
- **C. Archivos:** `apps/rewards/models.py`, `codes.py`, `services.py`, `selectors.py`, `views.py`, `urls.py`, `panel_urls.py`, `admin.py` y `management/commands/expire_redemptions.py`; plantillas `templates/rewards/*`; API `apps/api/views/rewards.py` y `staff.py`.
- **D. Modelos:** `Reward` y `Redemption` (+ `PointsTransaction`).
- **Catálogo:** el propietario crea recompensas en el admin (`save_reward`) y cambia su estado desde el dashboard (`set_reward_status`: ACTIVE, PAUSED o ARCHIVED; nunca se borran). En la web pública (`/recompensas/`) aparecen las activas y en fechas, también las agotadas.
- **Requisitos para canjear:** cliente activo y **verificado**, recompensa activa y en fechas, con unidades, saldo suficiente y sin otro código pendiente de esa recompensa.
- **Flujo de canje** (`_create_redemption`, [C8.11]): transacción → clave de idempotencia → bloqueo del cliente → bloqueo de la recompensa → comprobaciones → **stock con UPDATE condicionado** (`stock >= 1`) → `ledger.spend_points` (movimiento `REDEMPTION` negativo) → `Redemption` `PENDING` con un código de 12 caracteres y caducidad a 30 días.
- **Códigos:** alfabeto de 31 símbolos sin 0, O, 1, I ni L, 12 caracteres con `secrets` (≈ 59 bits); prefijo de QR `CFR1:` distinto del personal (`codes.py`).
- **Estados:** ver el diagrama `diagramas/09_estados_canje.mmd` (PENDING → USED / CANCELLED / EXPIRED).
- **Doble uso imposible:** la validación es `UPDATE ... WHERE status='PENDING' AND expires_at > now` [C8.12]; de dos validaciones simultáneas solo una cambia la fila. Además: CHECK de coherencia de `USED` y prohibición de validar el propio canje.
- **Errores y reversión:** cancelación del cliente o caducidad → `_close()` devuelve los puntos con un `REVERSAL` y devuelve la unidad de stock en una transacción; si alguien lo validó entre medias, `_ConcurrentChange` **deshace la devolución**.
- **I. Seguridad:** 404 para los canjes ajenos; el código no aparece en la URL, los logs ni la auditoría; el propietario ve los listados con `.defer("code")`; límite de 20 códigos no válidos por empleado.
- **L. Tests:** `tests/rewards/test_services.py` (54: saldo insuficiente sin efectos, stock que no baja de 0 aunque la comprobación estuviera desfasada, código usado, caducado con devolución, cancelación ajena o usada), `test_views.py` (26), `test_concurrency.py` (4, con hilos; pasan en PostgreSQL y se omiten en SQLite en memoria).
- **M. Ejemplo:** Lúa (ficticia) tiene 100 puntos y canjea «Pinta de la casa» (40) → saldo 60 y código `ABCD-EFGH-JKMN` → en la barra el empleado lo valida → USED. Si no lo recoge en 30 días, `expire_redemptions` lo caduca y le devuelve 40 puntos.
- **N. Decisiones:** descontar los puntos al **solicitar** (no al recoger) para que el saldo mostrado sea real, con devolución automática si no se usa.
- **O. Limitaciones:** el plazo de 30 días está «pendiente de confirmar»; `expire_redemptions` se ejecuta a diario en el servicio `scheduler` (Fase 12); aunque no se ejecutara, un código vencido nunca se acepta.

**Estado:** Implementado y verificado, también la concurrencia real en PostgreSQL (`tests/rewards/test_concurrency.py`).

### 7.9 Panel del empleado

- **A. Objetivo:** una herramienta de barra rápida para móvil o tablet.
- **B. Requisitos:** Fase 8.
- **C. Archivos:** `apps/staff/views.py`, `forms.py` y `urls.py`; `templates/staff/*`; integra `/panel/compras/` (purchases) y `/panel/canjes/` (rewards).
- **Funciones:** inicio con el resumen de hoy (compras, importe y canjes validados), registrar compra, validar canje, resultados por periodo (hoy, 7 o 30 días) y perfil de solo lectura.
- **Permisos:** `role_required(OWNER, EMPLOYEE)` en todas las vistas.
- **Identificación de clientes:** solo por QR o código (no hay búsqueda por nombre en el panel).
- **Acciones prohibidas (verificadas con tests):** cambiar roles, puntos o configuración; ver la dirección, la fecha de nacimiento, el teléfono, el email, el saldo o el historial del cliente; ver las operaciones de otros empleados (404).
- **L. Tests:** `tests/staff/test_panel.py` (31), `tests/purchases/test_views.py:188` (`test_other_employee_gets_404`), `tests/dashboard/test_access.py:120-160` (el empleado no puede ajustar puntos ni crear empleados).
- **O. Limitaciones:** **pendiente de probar en móviles y tablets físicos** (README).

**Estado:** Implementado y verificado.

### 7.10 Panel del propietario

- **A. Objetivo:** gestionar el negocio y ver cifras reales.
- **B. Requisitos:** Fase 9 (+ eventos, reservas y comunicaciones en la Fase 10).
- **C. Archivos:** `apps/dashboard/views.py` (990 líneas) y `forms.py`; `templates/dashboard/*` (22 plantillas).
- **Secciones (14, `views.py:59-74`):** resumen, clientes (búsqueda, filtros y zonas), empleados (alta, activación y rol), compras, puntos (movimientos, ajuste y compensación), recompensas, carta, cervezas, eventos, reservas, promociones, comunicaciones (campañas y registro de envíos), contenido y configuración (nueva conversión de puntos).
- **Modelo híbrido (decisión de la Fase 9):** acciones rápidas en el dashboard; fichas completas de productos, recompensas y promociones en el admin de Django.
- **Indicadores:** clientes (total, activos, verificados, con opt-in de email y altas del periodo), compras registradas (número, clientes, importe y media), puntos (emitidos, utilizados, corregidos y saldo pendiente global), canjes (solicitados, utilizados, cerrados y pendientes) y reservas.
- **Restricciones de acceso:** `role_required(OWNER)` + cada selector y servicio vuelve a comprobar el rol (`test_owner_only_selectors_reject_employee`); un propietario desactivado pierde el acceso; las acciones solo admiten POST; nadie se desactiva ni cambia su propio rol (`views.py:397-399, 418-420`).
- **Diferencia con el empleado:** el empleado solo opera y ve lo suyo con datos mínimos; el propietario ve a todos los clientes (ficha auditada), gestiona y configura.
- **L. Tests:** `tests/dashboard/test_access.py` (13), `test_customers_and_actions.py` (27), `test_stats.py` (19).
- **O. Limitaciones:** **revisión visual en el navegador pendiente** (README); no hay exportación de informes.

**Estado:** Implementado y verificado.

### 7.11 Eventos y reservas

- **A. Objetivo:** publicar eventos y gestionar solicitudes de reserva con confirmación manual.
- **B. Requisitos:** Fase 10 (+ decisión: reservas de mesa o de evento, solo para clientes verificados).
- **C. Archivos:** `apps/events/models.py`, `services.py`, `selectors.py`, `views.py`, `forms.py` y `urls.py`; `templates/events/*`; dashboard (`events`, `event_form`, `reservations` y `reservation_detail`); API `apps/api/views/events.py` y `owner.py`.
- **D. Modelos:** `Event` y `Reservation` (cap. 6).
- **Publicación:** `save_event` (lista blanca de campos, auditado) y `set_event_status` (DRAFT ↔ PUBLISHED, ARCHIVED; **no se publica un evento que ya ha empezado**). Si cambia la hora, las reservas activas pasan a la nueva hora (sin aviso automático: lo decide el propietario).
- **Solicitudes:** `request_reservation` (validaciones del cap. 2.3) y `_create` con los bloqueos (cap. 9.10).
- **Estados y confirmación:** `Reservation.TRANSITIONS` + `_transition` con la fila bloqueada [C8.13]; confirmar **vuelve a comprobar el aforo con el evento bloqueado**; COMPLETED solo desde el día de la reserva; el cliente puede cancelar antes de la hora.
- **Duplicidades:** una reserva activa por cliente y evento (UNIQUE condicional + comprobación previa); `idempotency_key` única; como máximo 3 activas futuras y 10 solicitudes por hora.
- **Notificaciones:** recibida (cliente + alerta a los propietarios), confirmada, rechazada y cancelada, con `deliver_on_commit` y `dedup_key` `reservation:{id}:{tipo}`.
- **L. Tests:** `tests/events/test_services.py` (25), `test_views.py` (16, incluido `test_cannot_see_or_cancel_others_reservations`).
- **O. Limitaciones:** las reservas de **mesa no tienen aforo** (la confirmación manual lo suple); al solicitar, las pendientes no cuentan para el aforo (D12).

**Estado:** Implementado y verificado.

### 7.12 Estadísticas y geografía

- **Métricas:** cap. 7.10. **Fuentes:** selectores de cada dominio (`accounts`, `purchases`, `loyalty`, `rewards` y `events`), reutilizados por el dashboard y por la API (`owner/stats/`).
- **Agregaciones:** `aggregate` con `Count(..., filter=Q(...))` y `Sum` + `Coalesce` (p. ej. `accounts/selectors.py:121-127`), en una sola consulta por bloque.
- **Periodos:** `[start, end)` en medianoches locales (`dashboard/forms.py:40-60`); los canjes «utilizados» se cuentan por fecha de validación y los solicitados por fecha de creación (`rewards/selectors.py:80-93`).
- **Geografía** (`geographic_distribution`, `accounts/selectors.py:190-235`): niveles país, provincia, localidad y CP (siempre con el país para no mezclar homónimos), agrupación sin distinguir mayúsculas (`Upper` como clave y `Max` como etiqueta), las `limit` primeras zonas + «otros» + «sin dato», porcentaje con un decimal `ROUND_HALF_UP`. Base: altas del periodo **o** clientes con compras en el periodo.
- **Privacidad:** solo direcciones **declaradas**, sin geolocalización por IP y sin direcciones completas.
- **Clientes registrados frente a ventas:** las cifras de compras son **compras registradas en el programa**, no la facturación (cap. 7.6).
- **Limitaciones estadísticas:** las direcciones las declara el cliente y no se verifican; las zonas pequeñas podrían permitir identificar a alguien si se combinan filtros (riesgo bajo, solo para el propietario).
- **Tests:** `tests/dashboard/test_stats.py` (19), `tests/purchases/test_stats.py` (6).

**Estado:** Implementado y verificado.

### 7.13 Notificaciones

- **Canales:** **email** (implementado; envío real pendiente de un SMTP) y **SMS** (sin proveedor: `is_configured()` es False y nunca se da un SMS por enviado). **No hay mensajes internos** dentro de la web (solo `django.contrib.messages` de cada petición).
- **Desencadenantes:**

| Tipo (`Notification.Kind`) | Disparador | Modo |
|---|---|---|
| `EMAIL_VERIFICATION`, `EMAIL_CHANGE`, `PASSWORD_RESET` | Registro, reenvío, cambio de email y recuperación | Inmediato, **sin guardar el contexto** (llevan token) |
| `EMAIL_CHANGED_NOTICE`, `EXISTING_ACCOUNT` | Cambio de email confirmado; intento de registro con un email existente | Inmediato |
| `RESERVATION_*` | Cada cambio de estado de una reserva | Cola + `deliver_on_commit` |
| `CAMPAIGN` | `process_notifications` reparte una campaña `QUEUED` | Cola |
| `BIRTHDAY` | `run_birthday_promotions`, solo con consentimiento | Cola |

- **Tratamiento de fallos:** un fallo inmediato queda como `FAILED` sin romper el flujo (el usuario pide otro enlace); en la cola se reintenta con una espera de 5·2^(n−1) minutos y pasa a `FAILED` tras 5 intentos; `recover_stale` rescata los envíos atascados más de 30 minutos (puede duplicar si el proveedor ya había aceptado, D17).
- **Consentimiento al enviar:** `_skip_reason` vuelve a comprobarlo justo antes de enviar (quien se da de baja entre medias no recibe nada) → `SKIPPED` con su motivo.
- **Baja:** enlace firmado con `django.core.signing` (sal propia, caduca en 365 días, solo `public_id` y canal) + cabecera `List-Unsubscribe`; la página pide confirmar con un POST.
- **G. Código:** [C8.16] `deliver`.
- **Tests:** `tests/notifications/test_notifications.py` (30, incluido `test_dedup_key_prevents_duplicates`).
- **Estado:** Implementado y verificado con backends en memoria y con Mailpit en la pila local; `process_notifications` se ejecuta cada 5 minutos en el `scheduler` (Fase 12); **SMTP real pendiente**; SMS planificado.

### 7.14 API REST v1

- **Endpoints (38 rutas + `schema/` y `docs/`, `apps/api/urls.py`):**

| Grupo | Rutas | Permiso |
|---|---|---|
| Autenticación (10) | `auth/register/`, `auth/email/verify/`, `auth/email/resend/`, `auth/login/`, `auth/token/refresh/`, `auth/logout/`, `auth/logout-all/`, `auth/password/change/`, `auth/password/reset/`, `auth/password/reset/confirm/` | Públicas con `AuthThrottle` por IP (excepto logout y cambio de contraseña) |
| Mi cuenta (5) | `me/`, `me/profile/`, `me/preferences/`, `me/email/change/`, `me/email/resend-verification/` | Autenticado / `IsCustomer` |
| Puntos y QR (5) | `me/points/`, `me/points/movements/`, `me/purchases/`, `me/qr/`, `me/qr/rotate/` | `IsVerifiedCustomer` |
| Recompensas (6) | `rewards/`, `rewards/<uuid>/`, `rewards/<uuid>/redeem/`, `me/redemptions/`, `me/redemptions/<uuid>/`, `me/redemptions/<uuid>/cancel/` | Públicas (lectura) / `IsVerifiedCustomer` |
| Eventos (5) | `events/`, `events/<uuid>/`, `me/reservations/`, `me/reservations/<uuid>/`, `me/reservations/<uuid>/cancel/` | Públicas (lectura) / `IsVerifiedCustomer` |
| Personal (4) | `staff/purchases/identify/`, `staff/purchases/`, `staff/redemptions/lookup/`, `staff/redemptions/validate/` | `IsStaffMember` |
| Propietario (3) | `owner/stats/`, `owner/reservations/`, `owner/reservations/<uuid>/<acción>/` | `IsOwner` |

- **Serializadores:** todos `serializers.Serializer` con campos explícitos (no hay `ModelSerializer` ni `__all__`), lo que impide la asignación masiva.
- **Autenticación:** JWT Bearer; access de 15 min y refresh de 30 días rotatorio con lista negra; reclamación `pwv` que invalida todo al cambiar la contraseña [C8.17].
- **Permisos:** envoltorios de `accounts.permissions` (`apps/api/permissions.py`); el rol se lee de la BD, no del token.
- **Validaciones:** las de los mismos servicios que la web; errores `{code, detail, fields}` con 400/401/403/404/409/415/429.
- **Versionado:** por URL (`/api/v1/`).
- **Diferencias con la web:** sin sesión ni CSRF (cabecera `Authorization`); la idempotencia por cabecera `Idempotency-Key` la **genera la app**; respuestas `Cache-Control: no-store, private`; sin cabeceras CORS; paginación con un máximo de 50; el propietario solo dispone de estadísticas y reservas (el resto, en el dashboard).
- **Documentación:** `docs/api/openapi.yaml`, **idéntico** al esquema regenerado; `docs/guia-app-flutter.md`.
- **Tests:** `tests/api/` (72), incluidos `test_security.py` (9) y `test_auth.py:181` (`test_logout_cannot_revoke_another_users_token`).
- **Estado:** Implementado y verificado. La app que la consumiría no existe.

---

## 8. Explicación del código fuente

**Convenciones.**
- Los bloques marcados como **Código real** se han copiado tal cual del repositorio, con la ruta y las líneas exactas de la versión congelada (`d0bac7c`). El 15-10-2026 se volvieron a comparar automáticamente con el código: coinciden todos; el de C8.13 se actualizó porque la migración a PostgreSQL cambió ese fragmento.
- Los bloques marcados como **Versión didáctica (comentarios añadidos)** **no son el código original**: añaden comentarios `# ◆` para explicar el porqué. No se deben presentar como transcripción.
- Los ejemplos usan datos ficticios.

### C8.1 Enrutado del proyecto — `config/urls.py:13-26`

**Objetivo:** montar cada app bajo su prefijo. **Por qué importa:** el orden decide qué patrón gana cuando varios comparten prefijo (`cuenta/` agrupa tres apps).

**Código real:**
```python
urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/v1/", include("apps.api.urls")),
    path("cuenta/", include("apps.loyalty.urls")),
    path("cuenta/", include("apps.rewards.urls")),
    path("cuenta/", include("apps.accounts.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("panel/", include("apps.staff.urls")),
    path("panel/compras/", include("apps.purchases.urls")),
    path("panel/canjes/", include("apps.rewards.panel_urls")),
    path("comunicaciones/", include("apps.notifications.urls")),
    path("", include("apps.events.urls")),
    path("", include("apps.web.urls")),
]
```

**Explicación:** `settings.ADMIN_URL` sale de una variable de entorno (`DJANGO_ADMIN_URL`) para no exponer el admin en `/admin/` en producción. `include()` delega en el `urls.py` de cada app, que declara su `app_name` (espacio de nombres: `reverse("purchases:register")`). Las rutas usan `<uuid:public_id>`, **nunca el id interno**, de modo que no se pueden recorrer objetos probando 1, 2, 3…

**Explicación oral:** «Cada módulo tiene sus URLs bajo un prefijo; los objetos se identifican siempre por un UUID público, así que no se puede adivinar el siguiente».

---

### C8.2 Autorización por rol — `apps/accounts/permissions.py:17-52`

**Objetivo:** una única definición de «quién puede» que usan las vistas web, el dashboard y (envuelta) la API.

**Código real:**
```python
def has_role(user, *roles):
    return bool(
        user is not None
        and getattr(user, "is_authenticated", False)
        and user.is_active
        and user.role in roles
    )


def is_owner(user):
    return has_role(user, User.Role.OWNER)


def is_staff_member(user):
    """Personal del local: propietario o empleado."""
    return has_role(user, User.Role.OWNER, User.Role.EMPLOYEE)


def role_required(*roles):
    """
    Decorador para vistas de función: redirige al login si no hay sesión y
    responde 403 si el rol no está permitido.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not has_role(request.user, *roles):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
```

**Versión didáctica (comentarios añadidos):**
```python
def has_role(user, *roles):                       # ◆ *roles: acepta 1 o varios roles permitidos
    return bool(
        user is not None
        and getattr(user, "is_authenticated", False)  # ◆ AnonymousUser → False sin excepción
        and user.is_active                        # ◆ una cuenta desactivada pierde el acceso al momento
        and user.role in roles                    # ◆ el rol viene de la BD (request.user), nunca del formulario
    )

def role_required(*roles):                        # ◆ fábrica de decoradores: role_required(OWNER)
    def decorator(view_func):
        @wraps(view_func)                         # ◆ conserva el nombre y el docstring de la vista
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())  # ◆ 302 al login con ?next=
            if not has_role(request.user, *roles):
                raise PermissionDenied            # ◆ Django responde 403 con templates/403.html
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
```

| Elemento | Función | Explicación aplicada al proyecto |
|---|---|---|
| `has_role` | Comprobación pura | La reutilizan `apps/api/permissions.py:15-20` y todos los servicios (`is_owner`, `is_staff_member`) |
| `*roles` | Parámetro variable | `role_required(User.Role.OWNER, User.Role.EMPLOYEE)` para el panel |
| `redirect_to_login` | Respuesta sin sesión | El usuario vuelve a la página tras entrar |
| `PermissionDenied` | Respuesta con rol incorrecto | 403: un empleado que teclea `/dashboard/` no ve nada |

**Relación:** `purchases/views.py:25` define `staff_required = role_required(User.Role.OWNER, User.Role.EMPLOYEE)`; `dashboard/views.py:76`, `owner_required = role_required(User.Role.OWNER)`.
**Seguridad:** mostrar u ocultar los botones de la cabecera según el rol (`templates/base.html:41-42`: «Mi cuenta», que lleva al propietario a su dashboard, y «Panel») es cosmético; el control real es este decorador, **y además** cada servicio vuelve a comprobar el rol (defensa en profundidad).
**Explicación oral:** «Un decorador comprueba en el servidor que el usuario está autenticado, activo y tiene el rol permitido; si no, login o 403. Los servicios vuelven a comprobarlo por si alguien llama a la lógica desde otro sitio».

---

### C8.3 Registro sin revelar si el email existe — `apps/accounts/services.py:437-446`

**Objetivo:** que un atacante no pueda saber si un email tiene cuenta, ni por el mensaje **ni por el tiempo de respuesta**.

**Código real:**
```python
        _validate_registration(profile, email, first_name, last_name, password)

        # Solo con todos los datos válidos se mira si el email existe: así la
        # respuesta a datos no válidos (p. ej. una contraseña débil) no depende
        # de que la cuenta exista.
        if User.objects.filter(email=email).exists():
            # Mismo coste que un alta real (el hash de la contraseña es lo más
            # lento): el tiempo de respuesta tampoco lo revela.
            make_password(password)
            raise EmailAlreadyRegistered()
```

**Flujo:** (1) se valida **todo** primero; si la contraseña es débil, el error es el mismo exista o no el email; (2) si existe, se calcula un hash de todas formas (`make_password`, la operación más lenta de un alta real) para igualar los tiempos; (3) la vista (`views.py:52-55`) responde **igual que un registro correcto** y llama a `notify_existing_account`, que avisa por email **al titular** (como máximo una vez al día).
**Tests:** `tests/accounts/test_registration.py:277` y `tests/core/test_phase11_audit.py:48-57` (la misma respuesta con una contraseña débil; validación antes de mirar el email).
**Explicación oral:** «Si alguien prueba a registrar un email ajeno, ve lo mismo que si fuera nuevo y tarda lo mismo; el dueño real recibe un aviso. Así no sirve para averiguar quién es cliente».

---

### C8.4 Consumo atómico del enlace de verificación — `apps/accounts/services.py:603-621`

**Código real:**
```python
    user = User.objects.select_for_update().get(pk=token.user_id)
    if not user.is_active:
        raise _token_error("invalid")

    claimed = EmailVerificationToken.objects.filter(
        pk=token.pk, used_at__isnull=True, revoked_at__isnull=True
    ).update(used_at=now)
    if claimed != 1:
        raise _token_error("used")

    if token.purpose == TokenPurpose.VERIFY:
        if token.email != user.email:
            # El email cambió después de emitir el enlace.
            raise _token_error("invalid")
        if not user.is_email_verified:
            user.email_verified_at = now
            user.save(update_fields=["email_verified_at"])
            record_audit_event(action=AuditEvent.Action.EMAIL_VERIFIED, actor=user, target=user)
        return user
```

**Versión didáctica (comentarios añadidos):**
```python
    claimed = EmailVerificationToken.objects.filter(
        pk=token.pk, used_at__isnull=True, revoked_at__isnull=True   # ◆ WHERE: solo si nadie lo ha usado
    ).update(used_at=now)                                             # ◆ UPDATE ... devuelve el nº de filas
    if claimed != 1:                                                  # ◆ 0 → otra petición lo consumió antes
        raise _token_error("used")
```

| Elemento | Función | Explicación |
|---|---|---|
| `raw_token` | Entrada | Del enlace del email; en la BD solo está `sha256(raw_token)` |
| `select_for_update()` | Bloqueo | Serializa dos confirmaciones del mismo usuario |
| `.update(...)` condicionado | Consumo atómico | La BD garantiza que solo una petición pasa `used_at` de NULL a ahora |
| `token.email != user.email` | Validación | Un enlace antiguo no verifica un email que ya cambió |
| `record_audit_event` | Trazabilidad | `EMAIL_VERIFIED` sin datos personales |

**Explicación oral:** «El token solo se gasta con un UPDATE condicionado: aunque el usuario pulse dos veces a la vez, la base de datos solo deja que una lo marque como usado».

---

### C8.5 Un email nuevo nunca hereda la verificación — `apps/accounts/models.py:113-132`

**Código real:**
```python
    def _reset_verification_if_email_changed(self, save_kwargs):
        """
        Invariante: un email nuevo nunca hereda la verificación del anterior.

        Si el email cambia y quien guarda no fija a la vez una nueva fecha de
        verificación (solo lo hace `services.confirm_email_token`), la
        verificación se anula. Cubre el admin y cualquier otro `save()`;
        `QuerySet.update()` no pasa por aquí y no debe usarse para cambiar emails.
        """
        loaded_email = getattr(self, "_loaded_email", None)
        if self.pk is None or loaded_email is None or self.email == loaded_email:
            return
        update_fields = save_kwargs.get("update_fields")
        if update_fields is not None and "email" not in update_fields:
            return  # este guardado no persiste el email
        if self.email_verified_at != getattr(self, "_loaded_email_verified_at", None):
            return
        self.email_verified_at = None
        if update_fields is not None:
            save_kwargs["update_fields"] = {*update_fields, "email_verified_at"}
```

**Explicación:** `from_db()` (`:91-95`) recuerda el email cargado de la BD. Al guardar, si el email cambió y nadie fijó a la vez una nueva fecha de verificación (solo lo hace `confirm_email_token`), se anula la verificación. Así, aunque el propietario cambie el email de un cliente desde el admin, el cliente tiene que verificar el nuevo. El propio docstring reconoce la limitación: `QuerySet.update()` no pasa por `save()`.
**Explicación oral:** «Es una invariante en el modelo: si cambia el email, hay que volver a verificarlo, venga el cambio de donde venga».

---

### C8.6 Token del QR personal — `apps/loyalty/services.py:54-83` y `:127-144`

**Código real (generación y normalización):**
```python
def generate_token():
    # 20 bytes aleatorios -> 32 caracteres en base32 (A-Z, 2-7), sin relleno.
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii")


def qr_payload(token):
    return f"{QR_PAYLOAD_PREFIX}{token}"


def format_code(token):
    """Versión legible para teclearlo a mano: grupos de 4 caracteres."""
    return " ".join(token[i : i + 4] for i in range(0, len(token), 4))


def mask_code(token):
    """Para soporte o depuración: nunca se muestra el token completo."""
    return f"{token[:4]}…" if token else "…"


def normalize_code(raw):
    """
    Acepta el contenido del QR (`CF1:XXXX…`) o el código tecleado (con
    espacios, guiones o en minúsculas). Devuelve el token o `None`.
    """
    if not isinstance(raw, str) or len(raw) > 100:
        return None
    value = _SEPARATORS_RE.sub("", raw).upper()
    if value.startswith(QR_PAYLOAD_PREFIX):
        value = value[len(QR_PAYLOAD_PREFIX) :]
    return value if _TOKEN_RE.match(value) else None
```

**Código real (identificación):**
```python
def identify_customer(raw_code, *, for_update=False):
    """
    Cliente activo al que pertenece el código. Lanza `InvalidQRCode` si el
    código no existe, no pertenece a un cliente o la cuenta está inactiva, y
    `CustomerNotEligible` si el email no está verificado.
    """
    token = normalize_code(raw_code)
    if token is None:
        raise InvalidQRCode()
    users = User.objects.all()
    if for_update:
        users = users.select_for_update()
    user = users.filter(qr_code__token=token).first()
    if user is None or not user.is_active or user.role != User.Role.CUSTOMER:
        raise InvalidQRCode()
    if not user.is_email_verified:
        raise CustomerNotEligible()
    return user
```

| Elemento | Función | Explicación |
|---|---|---|
| `secrets.token_bytes(20)` | Aleatoriedad criptográfica | 160 bits: imposible de adivinar (no se usa `random`) |
| `base64.b32encode` | Codificación | Solo A-Z y 2-7: legible y fácil de teclear |
| `len(raw) > 100` | Validación | Corta entradas enormes antes de la expresión regular |
| `InvalidQRCode` (mensaje único) | Privacidad | No distingue «no existe» de «inactivo»: no filtra información |
| `for_update=True` | Concurrencia | Al registrar la compra, bloquea la fila del cliente |

**Ejemplo:** el cliente tiene el token `ABCD2345EFGH6789JKLM2345NOPQ6789` (ficticio); en pantalla ve `ABCD 2345 EFGH …`; el empleado teclea `abcd-2345-efgh…` → `normalize_code` lo acepta.
**Explicación oral:** «El QR es solo un número aleatorio de 160 bits; no lleva nombre, email ni saldo. Si se pierde, el cliente lo renueva y el anterior deja de valer».

---

### C8.7 Registro de compra idempotente y transaccional — `apps/purchases/services.py:158-194`

**Código real:**
```python
def register_purchase(*, staff, qr_code, amount, idempotency_key, source=Purchase.Source.MANUAL):
    ensure_can_register_purchases(staff)
    if source not in settings.PURCHASES_ENABLED_SOURCES:
        raise ValidationError("Este origen de compras no está habilitado.", code="source_disabled")
    amount = parse_amount(amount)
    key = parse_idempotency_key(idempotency_key)
    _check_failures(staff)

    with transaction.atomic():
        existing = (
            Purchase.objects.select_for_update().select_related("customer").filter(idempotency_key=key).first()
        )
        if existing is not None:
            return _replay(existing, staff=staff, qr_code=qr_code, amount=amount, source=source)

        # Se vuelve a comprobar el QR y el estado del cliente dentro de la transacción.
        customer = _identify(staff, qr_code, for_update=True)
        try:
            with transaction.atomic():
                purchase = Purchase.objects.create(
                    customer=customer,
                    registered_by=staff,
                    amount=amount,
                    source=source,
                    idempotency_key=key,
                )
        except IntegrityError:
            # Otra petición con la misma referencia ganó la carrera.
            existing = Purchase.objects.select_related("customer").filter(idempotency_key=key).first()
            if existing is None:
                raise
            return _replay(existing, staff=staff, qr_code=qr_code, amount=amount, source=source)

        on_purchase_registered(purchase)

    logger.info("Compra registrada %s (origen %s, personal %s)", purchase.public_id, source, staff.public_id)
    return RegistrationResult(purchase=purchase, created=True)
```

**Versión didáctica (comentarios añadidos):**
```python
def register_purchase(*, staff, qr_code, amount, idempotency_key, source=Purchase.Source.MANUAL):
    ensure_can_register_purchases(staff)          # ◆ 1. ¿empleado o propietario activo? (BD)
    if source not in settings.PURCHASES_ENABLED_SOURCES:
        raise ValidationError(...)                # ◆ 2. el TPV (POS) aún no está habilitado
    amount = parse_amount(amount)                 # ◆ 3. Decimal, 2 decimales, de 0,01 a 1000 €
    key = parse_idempotency_key(idempotency_key)  # ◆ 4. debe ser un UUID
    _check_failures(staff)                        # ◆ 5. anti-fuerza bruta: 20 QR malos en 15 min

    with transaction.atomic():                    # ◆ todo o nada desde aquí
        existing = (...filter(idempotency_key=key)...)    # ◆ ¿reintento de la misma operación?
        if existing is not None:
            return _replay(...)                   # ◆ mismos datos → la misma compra; otros → conflicto
        customer = _identify(staff, qr_code, for_update=True)  # ◆ se revalida el QR con el cliente BLOQUEADO
        try:
            with transaction.atomic():            # ◆ savepoint: un IntegrityError no rompe la transacción externa
                purchase = Purchase.objects.create(...)  # ◆ la BD aplica el UNIQUE de la clave y los CHECK
        except IntegrityError:                    # ◆ carrera: otra petición con la misma clave ganó
            ...
            return _replay(...)
        on_purchase_registered(purchase)          # ◆ puntos en la MISMA transacción (ledger)
    logger.info(...)                              # ◆ solo public_id: sin código QR ni datos personales
    return RegistrationResult(purchase=purchase, created=True)
```

| Elemento | Función | Explicación aplicada al proyecto |
|---|---|---|
| `register_purchase` | Servicio de dominio | Lo llaman la vista web (`views.py:95-100`) y la API (`api/views/staff.py:51-56`) |
| `staff` | Actor | `request.user`; jamás un id enviado por el navegador |
| `amount` | Importe | Llega como texto; `parse_amount` rechaza `float`, decimales de más y fuera de rango |
| `idempotency_key` | Dato recibido | UUID generado por el servidor al mostrar el formulario (web) o por la app (cabecera) |
| `select_for_update` | Bloqueo | Serializa dos envíos con la misma clave |
| Atomic anidado | Savepoint | Permite capturar `IntegrityError` y seguir dentro de la transacción |
| `on_purchase_registered` | Integración | Si fallan los puntos, se deshace también la compra |
| `RegistrationResult.created` | Retorno | `False` en un reintento → la web dice «no se ha duplicado» y la API responde 200 en lugar de 201 |

**Casos de error:** `PermissionDenied` (no es personal), `ValidationError` con códigos `source_disabled`, `amount_*`, `idempotency_invalid`, `invalid_qr`, `email_not_verified`, `idempotency_conflict` y `operation_not_completed`; `TooManyFailedAttempts` (429).
**Explicación oral:** «Cada compra lleva una referencia única. Si el empleado pulsa dos veces o falla la red, el servidor encuentra la misma referencia y devuelve la compra ya hecha. Además, la compra y sus puntos se guardan en la misma transacción: o todo o nada».

---

### C8.8 Ledger: saldo derivado y escritura protegida — `apps/loyalty/ledger.py:58-72`

**Código real:**
```python
def balance(customer):
    """Saldo actual: suma de todos los movimientos del cliente."""
    return PointsTransaction.objects.filter(customer=customer).aggregate(total=Sum("points"))["total"] or 0


def _lock_customer(customer):
    return User.objects.select_for_update().get(pk=customer.pk)


def _append(customer, **fields):
    """Añade un movimiento con el saldo resultante. El cliente debe estar bloqueado."""
    new_balance = balance(customer) + fields["points"]
    if new_balance < 0:
        raise InsufficientPoints()
    return PointsTransaction.objects.create(customer=customer, balance_after=new_balance, **fields)
```

**Explicación:** el saldo no es un campo editable: se **calcula** sumando los movimientos. Toda escritura pasa por `_append`, que exige tener bloqueada la fila del cliente (`_lock_customer`); así dos operaciones simultáneas del mismo cliente se ejecutan una tras otra y la segunda ve el saldo actualizado. Si el resultado fuera negativo, se lanza `InsufficientPoints`, y además la BD lo rechazaría (`CHECK balance_after >= 0`, `models.py:373`).
**Riesgo conocido:** `balance()` suma todos los movimientos en cada escritura (coste lineal en el número de movimientos del cliente); a esta escala no importa, pero con millones de movimientos convendría un saldo materializado (cap. 16).
**Explicación oral:** «Los puntos funcionan como un libro de contabilidad: no se edita un saldo, se añaden apuntes. Para corregir un error se añade un apunte contrario, nunca se borra».

---

### C8.9 Conversión importe → puntos — `apps/loyalty/conversion.py:36-48`

**Código real:**
```python
def round_points(value):
    """Decimal → puntos enteros, truncando hacia abajo."""
    if not isinstance(value, Decimal) or not value.is_finite():
        raise TypeError("Los puntos se calculan con Decimal finitos.")
    return int(value.to_integral_value(rounding=POINTS_ROUNDING))


def calculate_points(amount, points_per_euro):
    if not isinstance(amount, Decimal) or not isinstance(points_per_euro, Decimal):
        raise TypeError("Importe y tasa deben ser Decimal.")
    if amount < 0 or points_per_euro < 0:
        raise ValueError("Importe y tasa no pueden ser negativos.")
    return round_points(amount * points_per_euro)
```

**Explicación:** se exige `Decimal` (lanza `TypeError` con `float`) para evitar errores de coma flotante como `0.1 + 0.2 ≠ 0.3`. `POINTS_ROUNDING = ROUND_DOWN` (`:27`): siempre se trunca, nunca se regala un punto por redondeo.
**Ejemplos:** `calculate_points(Decimal("12.50"), Decimal("1.00"))` → 12; `calculate_points(Decimal("9.99"), Decimal("1.50"))` → 14 (14,985 truncado).
**Test:** `tests/loyalty/test_points.py:52` (`test_rejects_floats_and_negatives`).

---

### C8.10 Invariantes del ledger en la BD — `apps/loyalty/models.py:404-419`

**Código real:**
```python
            # Una compra genera como máximo un movimiento de puntos base...
            models.UniqueConstraint(
                fields=["purchase"], condition=Q(kind="EARN_PURCHASE"), name="loyalty_points_one_earn_per_purchase"
            ),
            # ...y como máximo una bonificación por promoción.
            models.UniqueConstraint(
                fields=["promotion", "purchase"],
                condition=Q(kind="PROMOTION_BONUS"),
                name="loyalty_points_one_bonus_per_promotion_purchase",
            ),
            # Una sola promoción de cumpleaños por cliente y año.
            models.UniqueConstraint(
                fields=["customer", "birthday_year"],
                condition=Q(birthday_year__isnull=False),
                name="loyalty_points_one_birthday_per_year",
            ),
```

**Explicación:** son **índices únicos parciales** (con condición). Aunque un error de programación llamara dos veces a `award_points_for_purchase`, la BD rechazaría el segundo `EARN_PURCHASE` de la misma compra. Es la «red de seguridad» bajo la idempotencia del código (`ledger.py:87-93`, que devuelve los movimientos existentes).
**Tests:** `tests/loyalty/test_promotions.py:107` (`test_database_rejects_duplicate_bonus_for_same_purchase`) y `test_points.py:152-159`.
**Explicación oral:** «Además de comprobarlo en Python, la base de datos impide físicamente dos acumulaciones para la misma compra o dos regalos de cumpleaños el mismo año».

---

### C8.11 Solicitud de canje — `apps/rewards/services.py:176-210`

**Código real:**
```python
def _create_redemption(customer, reward, key, now):
    with transaction.atomic():
        existing = Redemption.objects.select_for_update().filter(idempotency_key=key).first()
        if existing is not None:
            return _replay(existing, customer, reward)

        # Todo se vuelve a comprobar con las filas bloqueadas.
        customer = ledger.lock_customer(customer)
        ensure_can_redeem(customer)
        reward = Reward.objects.select_for_update().get(pk=reward.pk)
        if not (reward.status == Reward.Status.ACTIVE and reward.is_in_period(now)):
            raise RewardNotAvailable()
        if Redemption.objects.filter(customer=customer, reward=reward, status=Status.PENDING).exists():
            raise PendingRedemptionExists()
        if reward.stock is not None:
            # Resta condicionada: nunca baja de cero aunque fallara el bloqueo.
            if not Reward.objects.filter(pk=reward.pk, stock__gte=1).update(stock=F("stock") - 1):
                raise RewardOutOfStock()

        # Lanza InsufficientPoints si el saldo (recalculado aquí) no alcanza;
        # la excepción deshace también la resta de unidades.
        movement = ledger.spend_points(
            customer=customer, points=reward.points_cost, reason=f"Canje: {reward.name}"[:200]
        )
        redemption = Redemption.objects.create(
            customer=customer,
            reward=reward,
            points_cost=reward.points_cost,
            code=_new_code(),
            created_at=now,
            expires_at=now + datetime.timedelta(days=settings.REWARDS_CODE_VALIDITY_DAYS),
            idempotency_key=key,
            spend_movement=movement,
        )
    return RedemptionResult(redemption=redemption, created=True)
```

| Elemento | Función | Explicación |
|---|---|---|
| Orden de bloqueo cliente → recompensa → canje | Evitar interbloqueos | Documentado en el docstring del módulo (`:21-22`) y aplicado igual en `_close` |
| `F("stock") - 1` con `stock__gte=1` | Resta atómica | La BD hace la resta; nunca baja de 0 aunque dos peticiones la intenten a la vez |
| `ledger.spend_points` | Descuento | Recalcula el saldo **dentro** de la transacción; si no alcanza, la excepción deshace también la resta de stock |
| `points_cost` copiado | Histórico | Cambiar el precio de la recompensa no afecta a los canjes ya hechos |
| `spend_movement` OneToOne | Trazabilidad | Cada canje apunta a su movimiento de puntos |

**Explicación oral:** «Al canjear se bloquean el cliente y la recompensa, se comprueba todo otra vez y se descuentan los puntos y una unidad en la misma transacción. Si falta saldo, se deshace todo, incluida la unidad».

---

### C8.12 Validación de un código sin doble consumo — `apps/rewards/services.py:381-396`

**Código real:**
```python
    with transaction.atomic():
        redemption = _find(staff, code, for_update=True)
        if redemption.customer_id == staff.pk:
            raise PermissionDenied("No puedes validar tu propio canje.")
        expired = redemption.is_expired(now)
        if not expired:
            updated = Redemption.objects.filter(pk=redemption.pk, status=Status.PENDING, expires_at__gt=now).update(
                status=Status.USED, validated_by=staff, validated_at=now
            )
            if updated:
                record_audit_event(
                    action=AuditEvent.Action.REDEMPTION_VALIDATED,
                    actor=staff,
                    target=redemption,
                    metadata={"reward": str(redemption.reward.public_id), "points": redemption.points_cost},
                )
```

**Explicación:** dos defensas superpuestas: (1) el bloqueo de fila (`for_update=True`) hace esperar a la segunda petición; (2) aunque el bloqueo fallara, el `UPDATE ... WHERE status='PENDING' AND expires_at > now` solo afecta a una fila una vez. Si `updated` es 0, el servicio informa de «ya se utilizó el dd/mm/aaaa hh:mm» (`:398-403`).
**Pregunta del tribunal relacionada:** «¿Qué pasa si dos empleados validan a la vez el mismo código?» → solo uno recibe «Canje validado»; el otro, `code_used`. Lo prueba `test_same_code_validated_concurrently_is_used_once`, que pasa en PostgreSQL con bloqueos de fila reales (se omite en SQLite en memoria).

---

### C8.13 Máquina de estados de las reservas — `apps/events/services.py:343-373`

**Código real:**
```python
    with transaction.atomic():
        # `of=("self",)`: solo se bloquea la reserva. PostgreSQL no admite FOR UPDATE
        # sobre el LEFT JOIN de `event` (nulo en las reservas de mesa); el evento se
        # bloquea aparte cuando hace falta.
        locked = (
            Reservation.objects.select_for_update(of=("self",))
            .select_related("event", "customer")
            .get(pk=reservation.pk)
        )
        if by_customer and locked.customer_id != actor.pk:
            raise PermissionDenied
        if locked.status == to_status:
            return ReservationResult(reservation=locked, created=False)
        if not locked.can_transition_to(to_status):
            raise _error(
                f"Una reserva {locked.get_status_display().lower()} no puede pasar a "
                f"{Status(to_status).label.lower()}.",
                "invalid_transition",
            )
        if to_status == Status.CONFIRMED:
            if locked.requested_for <= now:
                raise _error("La fecha de la reserva ya ha pasado.", "in_the_past")
            if locked.event_id:
                event = Event.objects.select_for_update().get(pk=locked.event_id)
                if event.capacity is not None and confirmed_seats(event) + locked.party_size > event.capacity:
                    raise _error("Confirmarla superaría el aforo del evento.", "event_full")
        if to_status == Status.COMPLETED and timezone.localdate(locked.requested_for) > timezone.localdate(now):
            raise _error("Una reserva solo se completa a partir de su día.", "too_early")
        if by_customer and locked.requested_for <= now:
            raise _error("La hora de la reserva ya ha pasado: ya no se puede cancelar.", "in_the_past")

```

**Explicación:** las transiciones permitidas están en un diccionario declarativo (`Reservation.TRANSITIONS`, `models.py:121-124`) y `can_transition_to` lo consulta. Repetir la misma transición es idempotente (`created=False`). Confirmar **vuelve a comprobar el aforo con el evento bloqueado**: dos confirmaciones simultáneas no pueden superar la capacidad. `select_for_update(of=("self",))` bloquea solo la reserva: PostgreSQL no admite `FOR UPDATE` sobre el `LEFT JOIN` del evento (nulo en las reservas de mesa). SQLite ignora `FOR UPDATE` y no lo detectó; apareció al ejecutar la suite en PostgreSQL ([migración, H2](../migracion-postgresql.md)). Un cliente solo actúa sobre sus reservas (`PermissionDenied`). La API traduce `invalid_transition` y `event_full` a **409 Conflict** (`apps/api/exceptions.py:31-42`).

---

### C8.14 Validación real de imágenes — `apps/catalog/validators.py:29-65`

**Código real:**
```python
def validate_image_file(file):
    # Los ficheros ya guardados se validaron al subirlos; no se vuelven a leer
    # del almacenamiento en cada edición.
    if getattr(file, "_committed", False):
        return

    max_bytes = settings.CATALOG_IMAGE_MAX_BYTES
    if file.size is not None and file.size > max_bytes:
        raise ValidationError(
            "La imagen ocupa demasiado. Máximo: %(max)s MB.",
            code="image_too_large",
            params={"max": max_bytes // (1024 * 1024)},
        )

    max_dimension = settings.CATALOG_IMAGE_MAX_DIMENSION
    try:
        file.seek(0)
        with Image.open(file) as image:
            image_format = image.format
            width, height = image.size
            if image_format not in ALLOWED_IMAGE_FORMATS:
                raise ValidationError(
                    "Formato no admitido. Usa JPEG, PNG o WebP.", code="image_format"
                )
            if width > max_dimension or height > max_dimension:
                raise ValidationError(
                    "La imagen es demasiado grande. Máximo: %(max)s px por lado.",
                    code="image_dimensions",
                    params={"max": max_dimension},
                )
            image.verify()
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise ValidationError("El fichero no es una imagen válida.", code="image_invalid")
    finally:
        file.seek(0)
```

**Explicación:** no basta la extensión: Pillow abre el archivo y comprueba el **formato real** (JPEG, PNG o WebP), las dimensiones (≤ 5000 px, lo que también limita las «bombas de descompresión») y la integridad (`verify()`). Se rechazan SVG (que podrían contener scripts), HTML disfrazado y archivos corruptos. El mismo validador se usa en `Product`, `TapMenu`, `Reward` y `Event`. Junto con `_random_image_path` (`:68-74`), el nombre publicado es un UUID.

---

### C8.15 Contenido editable seguro — `apps/web/models.py:38-40` y `:73-75`

**Código real:**
```python
def _is_safe_url(url):
    parts = urlsplit(url)
    return parts.scheme == "https" and bool(parts.netloc) and " " not in url
```
```python
    def save(self, *args, **kwargs):
        self.pk = SINGLETON_ID
        super().save(*args, **kwargs)
```

**Explicación:** solo se aceptan enlaces sociales `https://` con dominio, lo que impide inyectar `javascript:` en un `href`. `save()` fija siempre `pk = 1` y además hay un `CHECK id = 1` en la BD: existe una sola fila de contenido.

---

### C8.16 Entrega de una notificación — `apps/notifications/services.py:264-293`

**Código real:**
```python
def deliver(notification_id):
    """
    Envía una notificación pendiente. Devuelve su estado final, o `None` si
    no estaba pendiente (otro proceso la reclamó o ya se envió).
    """
    now = timezone.now()
    claimed = Notification.objects.filter(pk=notification_id, status=Status.PENDING).exclude(
        kind__in=IMMEDIATE_KINDS
    ).update(status=Status.SENDING, attempts=F("attempts") + 1, updated_at=now)
    if not claimed:
        return None
    notification = Notification.objects.select_related("recipient", "campaign").get(pk=notification_id)
    reason = _skip_reason(notification)
    if reason:
        notification.status = Status.SKIPPED
        notification.last_error = reason
        notification.next_attempt_at = None
        notification.save(update_fields=["status", "last_error", "next_attempt_at", "updated_at"])
        return notification.status
    try:
        _send(notification)
    except Exception as exc:  # noqa: BLE001 - se registra y se reintenta
        _register_failure(notification, exc)
        return notification.status
    notification.status = Status.SENT
    notification.sent_at = timezone.now()
    notification.next_attempt_at = None
    notification.last_error = ""
    notification.save(update_fields=["status", "sent_at", "next_attempt_at", "last_error", "updated_at"])
    return notification.status
```

**Explicación:** «reclamar» con `UPDATE ... WHERE status='PENDING'` permite lanzar `process_notifications` varias veces a la vez sin enviar dos veces lo mismo. `_skip_reason` (`:203-224`) **vuelve a comprobar el consentimiento** justo antes de enviar. `SENT` solo se marca si el proveedor acepta el mensaje, y el error se guarda solo como el tipo de excepción, nunca con el texto del mensaje (`:246`).

---

### C8.17 Revocación de los JWT al cambiar la contraseña — `apps/api/tokens.py:43-49` y `apps/api/authentication.py:16-21`

**Código real:**
```python
def password_version(user):
    return salted_hmac(_SALT, user.password, algorithm="sha256").hexdigest()[:32]


def password_version_matches(user, payload):
    claim = payload.get(PASSWORD_VERSION_CLAIM)
    return isinstance(claim, str) and constant_time_compare(claim, password_version(user))
```
```python
class JWTAuthentication(BaseJWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if not tokens.password_version_matches(user, validated_token):
            raise AuthenticationFailed("La sesión ya no es válida. Vuelve a iniciar sesión.", code="token_revoked")
        return user
```

**Explicación:** cada token lleva la reclamación `pwv`, un HMAC (con `SECRET_KEY` y sal propia) del **hash** de la contraseña. Si la contraseña cambia por cualquier vía (web, API, admin o recuperación), el hash cambia, `pwv` deja de coincidir y **todos** los tokens anteriores se rechazan al momento, sin esperar a que caduquen. `constant_time_compare` evita ataques de tiempo. No se implementa criptografía propia: se usan `salted_hmac` y `constant_time_compare` de Django.

---

### C8.18 IP real tras proxies de confianza — `apps/core/http.py:18-27`

**Código real:**
```python
def client_ip(request):
    remote_addr = request.META.get("REMOTE_ADDR") or "-"
    proxies = getattr(settings, "TRUSTED_PROXY_COUNT", 0)
    if proxies <= 0:
        return remote_addr
    forwarded = [part.strip() for part in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if part.strip()]
    if len(forwarded) < proxies:
        # Cabecera ausente o incompleta: la petición no pasó por todos los proxies.
        return remote_addr
    return forwarded[-proxies]
```

**Explicación:** `X-Forwarded-For` lo puede inventar el cliente. Solo se usa si hay N proxies **de confianza** configurados, y se toma la N-ésima entrada por la derecha (la que añadió el proxy propio). Sin proxies se ignora la cabecera. Esto evita que un atacante eluda el límite de intentos falseando su IP. Tests: `tests/core/test_phase11_audit.py:30-40` y `tests/api/test_security.py:64`.

---

### C8.19 Invariantes de la compra en la BD — `apps/purchases/models.py:82-97`

**Código real:**
```python
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=MIN_AMOUNT), name="purchases_amount_positive"),
            models.CheckConstraint(condition=Q(source__in=["MANUAL", "POS"]), name="purchases_source_valid"),
            models.CheckConstraint(
                condition=Q(status__in=["COMPLETED", "VOIDED"]), name="purchases_status_valid"
            ),
            models.CheckConstraint(
                condition=~Q(customer=models.F("registered_by")), name="purchases_not_self_registered"
            ),
            # Un mismo ticket del TPV no puede registrarse dos veces.
            models.UniqueConstraint(
                fields=["source", "external_reference"],
                condition=~Q(external_reference=""),
                name="purchases_unique_external_reference",
            ),
        ]
```

**Explicación:** `~Q(customer=F("registered_by"))` impide **en la BD** que alguien se registre compras a sí mismo (además, el registrador tiene que ser personal y el cliente, CUSTOMER, y los roles son excluyentes). El test `test_database_rejects_self_registration` (`tests/purchases/test_services.py:163`) fuerza un `UPDATE` directo y comprueba el `IntegrityError`.

---

### C8.20 Un test real comentado — `tests/purchases/test_services.py:169-177`

**Código real:**
```python
class IdempotencyTests(PurchaseTestCase):
    def test_double_submit_returns_the_same_purchase(self):
        key = uuid.uuid4()
        first = self.register(idempotency_key=key)
        second = self.register(idempotency_key=str(key))
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.purchase.pk, second.purchase.pk)
        self.assertEqual(Purchase.objects.count(), 1)
```

**Qué garantiza:** que un doble envío (incluso con la clave como texto en lugar de UUID) devuelve la misma compra y no crea otra. **Qué no garantiza:** el comportamiento con dos peticiones **simultáneas** en procesos distintos; eso lo cubre la combinación de `select_for_update` y el UNIQUE, que solo se puede probar de verdad con PostgreSQL.

---

## 9. Flujos completos de extremo a extremo

Formato de cada flujo: tabla con actor, petición, ruta y vista, validaciones, servicios, BD, cambios de estado, respuesta, errores, seguridad y tests; diagrama de secuencia en los flujos principales (también disponibles como `.mmd` en [`diagramas/`](diagramas/)).

### 9.1 Registro de un cliente y verificación del email

| Aspecto | Detalle |
|---|---|
| Actor | Visitante anónimo |
| Petición | `POST /cuenta/registro/` y después `GET` + `POST /cuenta/verificar-email/<token>/` |
| Ruta y vista | `accounts:register` → `views.register` (`apps/accounts/views.py:42`); `accounts:verify_email` → `views.verify_email` (`:71`) |
| Validaciones | `RegistrationForm` (formato, CP por país, móvil, edad y contraseñas iguales) + `services._validate_registration` (todo a la vez) + límite de 20 por IP y hora |
| Servicios | `register_customer` → `_create_user` → `ensure_customer_profile` → `_record_preference` ×2 → `_issue_email_token` → `_send_token_on_commit`; después `confirm_email_token` |
| BD | INSERT `User`, `CustomerProfile`, 2 `CommunicationPreferenceChange`, `EmailVerificationToken` (hash) y `AuditEvent CUSTOMER_CREATED`; `Notification` (SENDING → SENT/FAILED); al verificar, UPDATE del token (`used_at`) y del usuario (`email_verified_at`) + `AuditEvent EMAIL_VERIFIED` |
| Estado | Usuario `email_verified_at = NULL` → fecha |
| Respuesta | 302 a `/cuenta/registro/enviado/` (también si el email ya existía); 200 «Email verificado» |
| Errores | Errores de formulario; `invalid`, `expired`, `used`, `revoked` (con 200, para que el token no quede en los logs de 4xx) |
| Seguridad | Sin campo de rol; anti-enumeración por mensaje y tiempo; solo se guarda el hash del token; GET no consume el token; `never_cache` |
| Tests | `test_registration.py` (38), `test_email_verification.py` (23), `test_phase11_audit.py` |

```mermaid
sequenceDiagram
    autonumber
    actor C as Visitante
    participant V as views.register (/cuenta/registro/)
    participant F as RegistrationForm
    participant S as accounts.services
    participant DB as Base de datos
    participant N as notifications.send_immediately
    participant M as Proveedor SMTP

    C->>V: POST datos personales, dirección, email, contraseña y consentimientos
    V->>F: is_valid() (formato, CP por país, móvil E.164, edad, contraseñas iguales)
    V->>V: ip_limited(register-ip, 20 por hora)
    V->>S: register_customer(**datos) (sin campo de rol)
    S->>DB: BEGIN
    S->>S: normaliza y valida TODO (perfil, usuario y contraseña) antes de mirar el email
    alt el email ya existe
        S->>S: make_password(password) para igualar el tiempo de respuesta
        S-->>V: EmailAlreadyRegistered
        V->>S: notify_existing_account (como máximo 1 al día y avisa al titular)
        V-->>C: 302 a registro enviado (misma respuesta que un alta correcta)
    else email nuevo
        S->>DB: INSERT User (rol CUSTOMER) y CustomerProfile
        S->>DB: INSERT 2 CommunicationPreferenceChange (REGISTRATION)
        S->>DB: revoca los tokens pendientes e INSERT EmailVerificationToken (solo el hash SHA-256, caduca en 24 h)
        S->>DB: COMMIT
        S->>N: on_commit: envía el enlace SITE_BASE_URL/cuenta/verificar-email/token/
        N->>DB: Notification SENDING (sin contexto ni destinatario)
        N->>M: EmailMessage.send()
        N->>DB: SENT o FAILED (un fallo no rompe el registro)
        V-->>C: 302 a registro enviado
    end
    C->>V: GET /cuenta/verificar-email/token/ (muestra un botón de confirmación)
    C->>V: POST de confirmación (los analizadores de enlaces no gastan el token)
    V->>S: confirm_email_token(token)
    S->>DB: SELECT FOR UPDATE por hash, comprobaciones de usado, revocado y caducado
    S->>DB: UPDATE token SET used_at WHERE used_at IS NULL AND revoked_at IS NULL
    S->>DB: UPDATE user SET email_verified_at y AuditEvent EMAIL_VERIFIED
    V-->>C: 200 Email verificado (los errores también con 200 para no dejar el token en los logs de 4xx)
```

**¿Qué pasa si falla el envío del email?** El email se envía en `transaction.on_commit`: **la cuenta ya está creada** cuando se intenta. `send_immediately` captura la excepción, marca la notificación como `FAILED` (`apps/notifications/services.py:151-156`) y no rompe el flujo. El cliente puede pedir otro enlace (`/cuenta/verificar-email/reenviar/`, con límites). Si fallara la BD **antes** del commit, no se crea nada y no se envía nada.

### 9.2 Inicio de sesión y acceso al perfil

| Aspecto | Detalle |
|---|---|
| Actor | Cliente (o cualquier rol) |
| Petición | `POST /cuenta/entrar/` → `GET /cuenta/` → `GET /cuenta/perfil/` |
| Vistas | `LoginView` (`views.py:222`), `home` (`:126`), `profile` (`:146`) |
| Validaciones | `ThrottledAuthenticationForm`: límites por email y por IP; credenciales; cuenta activa (nativo de Django) |
| BD | Lectura del usuario; sesión; `last_login` (Django) |
| Respuesta | Redirección según el rol: CUSTOMER → `/cuenta/perfil/`, OWNER → `/dashboard/`, EMPLOYEE → `/panel/` |
| Errores | «Email o contraseña incorrectos» (sin revelar si existe); «Demasiados intentos fallidos» |
| Seguridad | Cookie de sesión HttpOnly + SameSite Lax (+ Secure en producción); `redirect_authenticated_user`; logout por POST con CSRF |
| Tests | `tests/accounts/test_auth_views.py` (11) |

Diagrama: [`diagramas/05_autenticacion.mmd`](diagramas/05_autenticacion.mmd) (incluye también el flujo JWT de la API).

### 9.3 Consulta de la carta

| Aspecto | Detalle |
|---|---|
| Actor | Cualquiera |
| Petición | `GET /carta/` |
| Vista | `web.views.MenuView` (`apps/web/views.py:29-36`) |
| Servicios | `catalog.selectors.public_menu()` y `current_tap_menu()` |
| BD | 2 consultas principales: categorías publicadas + `Prefetch` de los productos públicos (con `select_related` de categoría y estilo); carta de grifos |
| Respuesta | `web/menu.html` con las categorías, los productos (agotados al final, con la etiqueta «Agotada») y la imagen de los grifos |
| Seguridad | Solo GET y HEAD; nunca se muestran borradores ni archivados |
| Tests | `tests/web/test_menu_page.py` (12), `tests/catalog/test_selectors.py` (8) |

### 9.4 Identificación del cliente mediante QR

| Aspecto | Detalle |
|---|---|
| Actores | Cliente (enseña el QR) y empleado (lo escanea) |
| Petición | Cliente: `GET /cuenta/mi-qr/`. Empleado: `GET /panel/compras/` → lectura con cámara (`qr-scanner.js`) o tecleo → `POST /panel/compras/identificar/` |
| Vistas | `loyalty.views.my_qr` (`verified_email_required`); `purchases.views.identify` (`staff_required`) |
| Validaciones | `normalize_code` (formato `CF1:` + 32 caracteres base32); cliente activo, CUSTOMER y verificado; límite de 20 fallos por empleado |
| BD | Lectura de `CustomerQRCode` → `User` |
| Respuesta | Pantalla de confirmación con **solo «Nombre I.»** y el formulario de importe con el código oculto y una clave de idempotencia nueva |
| Errores | 400 «El código no es válido o la cuenta no está activa»; 400 «verificar su email»; 429 por demasiados fallos |
| Seguridad | El código viaja por POST (nunca en la URL), `never_cache`, log sin el código |
| Tests | `tests/loyalty/test_qr.py` (22), `tests/purchases/test_views.py` (25) |

### 9.5 Registro de una compra por parte de un empleado

Tabla resumida (detalle del código en C8.7):

| Aspecto | Detalle |
|---|---|
| Petición | `POST /panel/compras/registrar/` (`code`, `idempotency_key` y `amount`) |
| Vista | `purchases.views.register` (`views.py:84-117`) |
| Servicios | `register_purchase` → `_identify(for_update=True)` → `Purchase.objects.create` → `on_purchase_registered` → `ledger.award_points_for_purchase` |
| BD | `SELECT FOR UPDATE` (clave y cliente), INSERT `Purchase`, `SELECT FOR UPDATE` del cliente (ledger), `SUM`, INSERT `PointsTransaction` (base + bonificaciones), `SELECT FOR UPDATE` de las promociones activas |
| Estado | La compra nace `COMPLETED` |
| Respuesta | 302 a `/panel/compras/<uuid>/` con «Compra registrada» o «Esta compra ya estaba registrada» |
| Errores | 400 por importe o QR; 400 por `idempotency_conflict`; 429 |
| Tests | `tests/purchases/test_services.py:133-200`, `test_views.py` |

```mermaid
sequenceDiagram
    autonumber
    actor CL as Cliente
    actor E as Empleado
    participant Q as loyalty (QR)
    participant P as purchases.services
    participant L as loyalty.ledger
    participant CV as loyalty.conversion
    participant PR as loyalty.promotions
    participant DB as Base de datos

    CL->>E: enseña /cuenta/mi-qr/ (QR SVG con CF1:token, o el código tecleable)
    E->>P: POST /panel/compras/identificar/ con code
    P->>P: is_staff_member, límite de 20 fallos en 15 min por empleado
    P->>Q: identify_customer(code): normaliza y busca el token
    alt no existe, inactivo o no es cliente
        Q-->>E: El código no es válido (mensaje genérico)
    else email sin verificar
        Q-->>E: El cliente tiene que verificar su email
    else válido
        P-->>E: solo el nombre corto (Lúa F.) + formulario con code y una idempotency_key nueva
    end
    E->>P: POST /panel/compras/registrar/ con importe
    P->>P: parse_amount (Decimal, 0,01 a 1000 €), clave UUID
    P->>DB: BEGIN y busca Purchase por idempotency_key FOR UPDATE
    P->>Q: identify_customer(code, for_update=True) (vuelve a comprobarlo todo con el cliente bloqueado)
    P->>DB: INSERT Purchase (CHECK customer distinto de registered_by)
    P->>L: on_purchase_registered(purchase) en la MISMA transacción
    L->>DB: SELECT User FOR UPDATE (serializa al cliente)
    L->>CV: current_rate(purchase.created_at)
    CV-->>L: LoyaltyRule vigente o 1,00 punto por euro por defecto
    L->>CV: calculate_points(importe, tasa) con ROUND_DOWN
    L->>DB: INSERT PointsTransaction EARN_PURCHASE (UNIQUE: una por compra)
    L->>PR: bonuses_for_purchase (promociones ACTIVE, FOR UPDATE, límites)
    L->>DB: INSERT PointsTransaction PROMOTION_BONUS (UNIQUE por promoción y compra)
    P->>DB: COMMIT (compra y puntos, o nada)
    P-->>E: 302 al detalle: Compra registrada, o ya estaba registrada si es un reintento
```

**¿Qué pasa si falla a mitad?** Si cualquier paso lanza una excepción (p. ej. un error al crear un movimiento), `transaction.atomic()` hace **ROLLBACK de la compra y de todos sus puntos**. No puede quedar una compra sin puntos ni puntos sin compra. Si se pierde la respuesta pero el COMMIT se hizo, el reintento con la misma clave devuelve la compra existente.

### 9.6 Cálculo y asignación de puntos

| Paso | Código | Detalle |
|---|---|---|
| 1 | `ledger.award_points_for_purchase` (`ledger.py:75`) | Solo compras `COMPLETED` de un CUSTOMER; bloquea al cliente |
| 2 | Idempotencia (`:87-93`) | Si la compra ya tiene movimientos, los devuelve sin crear otros |
| 3 | `conversion.current_rate(purchase.created_at)` | La regla vigente **en el momento de la compra** |
| 4 | `calculate_points` | `Decimal` y `ROUND_DOWN` |
| 5 | `_append(EARN_PURCHASE)` | Con `rule`, `base_amount` y `points_per_euro` copiados (si se cambia la tasa, los puntos antiguos no cambian) |
| 6 | `promotions.bonuses_for_purchase` | Promociones `PURCHASE` activas, bloqueadas, con importe mínimo y límites |
| 7 | `_append(PROMOTION_BONUS)` por cada una | UNIQUE (promoción, compra) |
| 8 | `logger.info` | Solo `public_id`, el número de movimientos y los puntos |

Tests: `tests/loyalty/test_points.py` y `test_promotions.py`.

### 9.7 Consulta del saldo

| Aspecto | Detalle |
|---|---|
| Petición | `GET /cuenta/puntos/` (web) o `GET /api/v1/me/points/` (API) |
| Vista | `loyalty.views.my_points` (`views.py:47-63`); `api.views.loyalty.PointsSummaryView` |
| Servicios | `selectors.points_summary(request.user)`, `points_history`, `purchases.selectors.customer_purchases` |
| BD | 1 agregación (saldo, obtenidos, utilizados y corregidos con `Sum(filter=...)`) + 2 listados paginados de 20 |
| Seguridad | Siempre `request.user`: no hay ningún parámetro de cliente (test `test_never_shows_other_customers_data`) |

### 9.8 Solicitud de una recompensa

| Aspecto | Detalle |
|---|---|
| Petición | `GET /cuenta/recompensas/<uuid>/` → `POST .../canjear/` (con `idempotency_key` oculta) o `POST /api/v1/rewards/<uuid>/redeem/` (cabecera `Idempotency-Key`) |
| Vista | `rewards.views.redeem` (`views.py:79-99`); `api.views.rewards.RedeemView` |
| Servicios | `request_redemption` → `_create_redemption` (C8.11) |
| BD | Bloqueos cliente → recompensa; UPDATE condicionado del stock; INSERT `PointsTransaction REDEMPTION` e INSERT `Redemption PENDING` |
| Respuesta | 302 al detalle con el QR del canje (web); 201 o 200 (API) |
| Errores | `reward_unavailable`, `out_of_stock`, `insufficient_points`, `duplicate_pending` (409 en la API) |
| Tests | `tests/rewards/test_services.py:92-166`, `tests/api/test_customer.py:89` |

### 9.9 Validación y consumo de un canje

```mermaid
sequenceDiagram
    autonumber
    actor CL as Cliente (email verificado)
    actor E as Empleado
    participant R as rewards.services
    participant L as loyalty.ledger
    participant DB as Base de datos

    CL->>R: POST /cuenta/recompensas/id/canjear/ con idempotency_key
    R->>DB: BEGIN y busca Redemption por clave FOR UPDATE (si existe, _replay)
    R->>L: lock_customer (orden de bloqueo: cliente, recompensa, canje)
    R->>DB: SELECT Reward FOR UPDATE: ACTIVE y dentro de sus fechas
    R->>DB: ¿ya hay un PENDING de esta recompensa? (también UNIQUE parcial en BD)
    R->>DB: UPDATE reward SET stock = stock - 1 WHERE stock mayor o igual que 1 (si tiene stock)
    R->>L: spend_points: recalcula el saldo, InsufficientPoints si no alcanza
    L->>DB: INSERT PointsTransaction REDEMPTION (puntos negativos)
    R->>DB: INSERT Redemption PENDING, código de 12 caracteres, caduca en 30 días
    R->>DB: COMMIT
    R-->>CL: detalle con QR (CFR1:código) y código ABCD-EFGH-JKMN

    CL->>E: enseña el código en la barra
    E->>R: POST /panel/canjes/consultar/ (lookup_redemption: vista previa sin datos personales)
    E->>R: POST /panel/canjes/validar/
    R->>DB: BEGIN y SELECT Redemption FOR UPDATE por código
    R->>R: impide validar el propio canje
    alt ha caducado
        R->>R: _close_safely(EXPIRED): devuelve los puntos (REVERSAL) y el stock
        R-->>E: Este código ha caducado
    else vigente
        R->>DB: UPDATE redemption SET status USED WHERE status PENDING AND expires_at posterior a now
        alt 1 fila actualizada
            R->>DB: AuditEvent REDEMPTION_VALIDATED y COMMIT
            R-->>E: Canje validado. Entrega la recompensa
        else 0 filas (otro empleado se adelantó)
            R-->>E: Este código ya se utilizó el día dd/mm/aaaa hh:mm
        end
    end
```

**¿Qué pasa si falla a mitad?** En la solicitud, si falla el descuento (saldo insuficiente) se deshacen también la resta de stock y el canje. En la cancelación o caducidad (`_close`), si al marcar el canje como cerrado resulta que otro proceso ya lo validó (0 filas actualizadas), se lanza `_ConcurrentChange` y **se deshace la devolución de puntos** (`apps/rewards/services.py:259-264`).

### 9.10 Creación y confirmación de una reserva

```mermaid
sequenceDiagram
    autonumber
    actor CL as Cliente verificado
    actor PO as Propietario
    participant ES as events.services
    participant NS as notifications.services
    participant DB as Base de datos
    participant M as SMTP

    CL->>ES: POST /cuenta/reservas/evento/id/ (personas, notas, idempotency_key)
    ES->>ES: ensure_can_reserve, _parse_party_size (1 a 20), _parse_text (300), límite de 10 por hora
    ES->>DB: BEGIN y SELECT FOR UPDATE de la clave, el cliente y el evento
    ES->>ES: evento PUBLISHED, admite reservas y no ha empezado
    ES->>ES: una activa por evento, plazas confirmadas + personas no superan el aforo, como máximo 3 activas
    ES->>DB: INSERT Reservation PENDING
    ES->>NS: enqueue RESERVATION_RECEIVED y RESERVATION_OWNER_ALERT (dedup_key, deliver_on_commit)
    ES->>DB: COMMIT
    NS->>M: deliver() al confirmar la transacción (UPDATE PENDING a SENDING)
    PO->>ES: POST /dashboard/reservas/id/estado/ accion=confirmar
    ES->>DB: SELECT Reservation FOR UPDATE, can_transition_to(CONFIRMED)
    ES->>DB: SELECT Event FOR UPDATE y vuelve a comprobar el aforo
    ES->>DB: UPDATE status CONFIRMED, status_changed_at, by y AuditEvent (sin notas)
    ES->>NS: enqueue RESERVATION_CONFIRMED (deliver_on_commit)
    NS->>M: email al cliente (sin notas, teléfonos ni direcciones)
```

| Aspecto | Detalle |
|---|---|
| Vistas | `events.views.event_reservation_new` (`views.py:102`), `reservation_new` (mesa, `:85`); `dashboard.views.reservation_action` (`:796`); API `me/reservations/` y `owner/reservations/<uuid>/<acción>/` |
| Errores | `event_not_bookable`, `already_reserved`, `event_full` (409), `too_many_active`, `rate_limited` (429), `invalid_transition` (409), `in_the_past`, `too_early` |
| Seguridad | Reserva ajena → 404; listado del propietario sin datos de contacto; detalle con el teléfono **auditado** (`RESERVATION_DATA_VIEWED`) |
| Tests | `tests/events/test_services.py` (25), `test_views.py` (16), `tests/api/test_customer.py:158` |

**Fallo de notificación:** el aviso se crea dentro de la transacción y se envía **después** del commit (`deliver_on_commit`). Si el SMTP falla, la reserva sigue existiendo y la notificación queda `PENDING` para que la reintente `process_notifications` (si está programado).

### 9.11 Consulta de estadísticas por el propietario

| Aspecto | Detalle |
|---|---|
| Petición | `GET /dashboard/?periodo=30d` (o `rango` con `desde` y `hasta`); `GET /dashboard/clientes/zonas/?nivel=provincia&base=compras`; API `GET /api/v1/owner/stats/?date_from=…&date_to=…` |
| Vistas | `dashboard.views.home` (`:122-140`), `customer_zones` (`:283-320`); `api.views.owner.OwnerStatsView` |
| Servicios | `customer_counts`, `registered_purchases_stats`, `points_stats`, `redemption_stats`, `reservation_stats` y `geographic_distribution` |
| BD | Agregaciones (`Count` y `Sum` con `filter`) por bloque; agrupación geográfica con `values().annotate()` |
| Seguridad | `role_required(OWNER)` + `_require_owner` en cada selector; sin datos personales en las estadísticas |
| Tests | `tests/dashboard/test_stats.py` (19), `test_access.py` |

---

## 10. Seguridad, privacidad e integridad

Se distinguen los **mecanismos presentes en el código** (con evidencia) de las **recomendaciones pendientes**. Usar Django no hace segura la aplicación por sí mismo: estos son los controles concretos.

### 10.1 Mecanismos implementados

| Ámbito | Control concreto | Evidencia | Verificación |
|---|---|---|---|
| Autenticación web | Sesión de Django; login con límites por email (5) e IP (30) en 15 min; mensaje genérico | `apps/accounts/forms.py:177-213` (web y admin); `base.py:146-148` | Tests |
| Autenticación API | JWT HS256: access de 15 min y refresh de 30 días rotatorio con lista negra; `pwv` revoca al cambiar la contraseña; `CHECK_USER_IS_ACTIVE` | `apps/api/tokens.py`, `authentication.py`; `base.py:255-266` | `tests/api/test_auth.py` (28) |
| Autorización por roles | `has_role` con el rol leído de la BD; decoradores en las vistas; los servicios y selectores vuelven a comprobarlo | `apps/accounts/permissions.py`; `_ensure_active_owner` (`services.py:77-82`) | `tests/dashboard/test_access.py`, `tests/accounts/test_permissions.py` |
| Escalada de privilegios | Registro sin campo de rol; `is_staff` e `is_superuser` derivados del rol y restringidos en la BD; rol de solo lectura en el admin; nunca se queda el sistema sin propietario activo | `models.py:71-85`; `services.py:70-74, 198-237` | `tests/accounts/test_services.py`, `test_admin.py` |
| IDOR / BOLA | Las vistas usan `request.user`; los objetos se buscan **filtrando por el propietario** (`customer_redemption(customer, public_id)`) → 404 si son ajenos; UUID en las URLs | `rewards/selectors.py:38-40`; `events/selectors.py:77-78`; `dashboard/views.py:265` | `test_cannot_see_or_cancel_others_reservations`, `test_other_employee_gets_404`, `test_cannot_reverse_other_customers_movement_through_url` |
| CSRF | `CsrfViewMiddleware`; `{% csrf_token %}` (también en el logout); la API sin cookies (no hay superficie CSRF); la documentación de la API acepta sesión pero solo GET | `base.py:64`; `templates/base.html:42-45`; `apps/api/urls.py:12-15` | Comportamiento por defecto de Django |
| XSS | Autoescape de las plantillas; QR como data URI SVG generado en el servidor; SVG rechazado en las subidas; enlaces sociales solo `https` | `loyalty/views.py:31-34`; `catalog/validators.py`; `web/models.py:38-40` | Tests de validadores |
| Inyección SQL | Solo ORM con parámetros (no se ha encontrado SQL crudo: `grep` de `raw(` y `cursor` sin resultados en `apps/`) | — | — |
| Asignación masiva | Formularios `forms.Form` y serializadores `Serializer` con campos explícitos; listas blancas `PROFILE_FIELDS`, `EVENT_FIELDS`, `EDITABLE_FIELDS`; `save_event` rechaza campos desconocidos | `accounts/services.py:37-46, 764-766`; `events/services.py:55-65, 98-100` | `test_cannot_modify_other_profile_by_sending_identifiers` (`test_profile.py:287`) |
| Abuso de endpoints | Límites: registro, reenvío y recuperación (20 por IP y hora), QR mal leídos (20 en 15 min por empleado), códigos de canje, rotación de QR (5 al día), reservas (10 por hora), throttling DRF (anon 60/min, user 240/min, auth 10/min); paginación con un máximo de 50 | `base.py`; `apps/api/throttling.py`; `pagination.py` | `tests/api/test_security.py:48-64` |
| Operaciones duplicadas | Claves de idempotencia únicas (compras, canjes, reservas y ajustes), `dedup_key` en las notificaciones y UNIQUE condicionales | Cap. 6 y 8 | Tests de idempotencia (cap. 11) |
| Contraseñas | Hash nativo de Django; validadores (≥ 10, comunes, numéricas, similitud); nunca como argumento de comando (`getpass` o variable de entorno) | `base.py:109-117`; `create_owner.py:1-9` | `test_create_owner_command.py` |
| Gestión de secretos | Todo por entorno (`django-environ`); `.env` en `.gitignore`; `.env.example` con valores ficticios; `prod.py` falla si falta la `SECRET_KEY` o si mide menos de 32 bytes | `base.py:15-21`; `prod.py:9-13` | `check --deploy` |
| Sesiones | HttpOnly, SameSite Lax, 14 días; Secure en producción; cambiar la contraseña invalida las otras sesiones (hash de sesión de Django) | `base.py:293-296`; `prod.py:77-78` | — |
| Tokens de verificación | `secrets.token_urlsafe(32)`, solo el hash en la BD, caducidad, uso único atómico, revocación y purga | `accounts/services.py:485-518, 562-625, 660-671` | Tests |
| Exposición de datos personales | Campos mínimos (`.only`, `.defer`), nombre abreviado para el personal, búsqueda por POST + sesión, auditoría de las consultas de fichas, logs solo con `public_id` | Cap. 7.4 | Tests de privacidad |
| Protección del QR | Token opaco de 160 bits, renovable, sin datos personales, solo identifica | Cap. 7.5 | `test_qr.py` |
| Transacciones | `transaction.atomic` en todas las escrituras de negocio; `ATOMIC_REQUESTS = False` (control explícito) | Servicios | Tests |
| Concurrencia | `select_for_update` con un orden de bloqueo fijo (también en la regla del último propietario, corregida en la refactorización final, R-1); UPDATE condicionados; restricciones únicas como última barrera | Cap. 8 | 17 tests con hilos que pasan en PostgreSQL (local, contenedor y CI); se omiten en SQLite en memoria |
| Auditoría | `AuditEvent` (30 acciones) sin datos personales; admin de solo lectura | `apps/core/` | `tests/core/*` |
| Producción | `DEBUG = False`, `ALLOWED_HOSTS` obligatorio, PostgreSQL y caché compartida obligatorios, SSL redirect, HSTS de 1 año, cookies Secure, backends simulados rechazados, `SITE_BASE_URL` https, admin en una ruta configurable y con límite de intentos, `X-Frame-Options: DENY`, nosniff, Referrer-Policy | `config/settings/prod.py`; `base.py:297-299, 341` | 7 tests (`tests/core/test_audit_and_settings.py:58-91`) + `check --deploy`: solo W021 |
| API | Solo JSON (415 con otros tipos), `no-store`, sin CORS, errores sin trazas | `apps/api/views/base.py`; `exceptions.py` | `tests/api/test_security.py` |

### 10.2 Riesgos y recomendaciones pendientes

| Riesgo | Situación actual | Recomendación |
|---|---|---|
| Contadores de intentos por proceso | **Resuelto** (auditoría P1-2): `prod` exige una caché compartida; Redis en Docker Compose | — |
| Concurrencia en el motor real | **Resuelto**: 17 tests de concurrencia pasan en PostgreSQL; la auditoría corrigió un interbloqueo en la validación de canjes (P2-1) y la refactorización final otro en la regla del último propietario (R-1) | Mantenerlos en el CI |
| Sin monitorización ni alertas | Healthcheck (`/healthz` interno) y logs, sin avisos | Comprobador externo de disponibilidad, aviso si fallan las copias y Sentry para los errores 500 |
| Controles de la auditoría pospuestos | Sin Content-Security-Policy, sin borrar EXIF de las imágenes, sin `List-Unsubscribe-Post` (P3) | Abordarlos antes de abrir al público |
| No hay 2FA para el propietario | — | TOTP para la cuenta OWNER |
| Auditoría inmutable solo por convención | Admin de solo lectura | Permisos de BD o triggers que impidan UPDATE y DELETE |
| QR fotografiado por otra persona | Solo permite que el titular **gane** puntos | La renovación ya existe; se podría añadir caducidad periódica |
| Clave de idempotencia que el navegador devuelve | El UNIQUE + `_replay` impiden los duplicados | Firmar la clave (HMAC) si se quisiera atarla a la sesión |
| Swagger UI desde un CDN | Solo en `/api/v1/docs/` (pública en desarrollo; en producción, solo el propietario) | `drf-spectacular-sidecar` para servirlo localmente |
| Cumplimiento del RGPD | Minimización y consentimiento; sin exportación ni supresión | Funciones de exportación y anonimización; textos legales |
| Dependencias | Versiones exactas en `requirements/*.txt` y transitivas en `constraints.txt` (auditoría P2-4) | Añadir `pip-audit` al CI de GitHub Actions |

---

## 11. Pruebas y calidad del software

### 11.1 Estrategia y herramientas

- **Framework:** `django.test` (`TestCase`, y `TransactionTestCase` para la concurrencia) sobre `unittest`. No se usan pytest ni coverage (no están en `requirements/dev.txt`).
- **Settings de test:** `config/settings/test.py` (hasher MD5 rápido **solo en los tests**, email en memoria, sin SMS y logs de `django.request` silenciados).
- **Estructura:** `tests/<app>/test_*.py`, una carpeta por app; **factories** propias (no factory_boy) en `tests/accounts/factories.py`, `tests/catalog/factories.py`, `tests/loyalty/factories.py`, `tests/rewards/factories.py` y `tests/events/factories.py`; una base para la API en `tests/api/base.py` y otra para la concurrencia con hilos en `tests/concurrency.py`. Datos ficticios (`@example.com`).
- **Motores:** la verificación que cuenta es en **PostgreSQL 17** (`--parallel 1`), donde no se omite ningún test. Con SQLite en memoria se omiten los de concurrencia, que necesitan varias conexiones.
- **CI:** `.github/workflows/ci.yml` ejecuta en cada push la suite en PostgreSQL 17 y falla si hay tests omitidos.

### 11.2 Resultado real (2026-10-15, versión congelada)

```text
python manage.py test --settings=config.settings.test --parallel 1     # DATABASE_URL de PostgreSQL 17
Ran 849 tests in 41.909s
OK
```

| Entorno | Resultado |
|---|---|
| PostgreSQL 17.11 local | **849 OK, 0 omitidos** |
| Dentro del contenedor de producción, contra el PostgreSQL 17 de Docker Compose | **849 OK** |
| SQLite en memoria | 849 OK, 18 omitidos (17 de concurrencia y uno de `UPPER` no ASCII, exclusivo de PostgreSQL) |

| Área | Tests | Qué cubre (ejemplos reales) |
|---|---|---|
| accounts | 209 | Registro (38), perfil (40), servicios (28), verificación (23), vistas de autenticación (16), admin (15), modelos, permisos, comando `create_owner`, validadores y concurrencia del último propietario (3) |
| api | 73 | Autenticación y tokens (28), cliente (15), cuenta (12), seguridad (9), personal o propietario (8) y rotación simultánea del refresh (1) |
| catalog | 59 | Modelos, selectores, servicios, validadores de imagen y permisos del admin |
| core | 33 | Auditoría y settings de producción (15), auditoría de la Fase 11 (10) y healthcheck (8) |
| dashboard | 67 | Acceso por rol (13), clientes y acciones (27), estadísticas (20) y límites de periodo de los selectores (7) |
| events | 46 | Servicios de reserva (25), vistas (16) y concurrencia (5) |
| loyalty | 119 | Puntos (41), QR (22), cumpleaños (21), promociones (18), vistas (15) y concurrencia (2) |
| notifications | 30 | Cola, deduplicación, consentimiento, baja y SMS en memoria |
| purchases | 58 | Servicio (25), vistas (25), estadísticas (6) y concurrencia (2) |
| rewards | 84 | Servicios (54), vistas (26) y concurrencia (4) |
| staff | 31 | Panel del personal |
| web | 40 | Páginas públicas, carta y formularios |

### 11.3 Tipos de prueba y ejemplos

| Tipo | Ejemplo real | Qué garantiza |
|---|---|---|
| Unitaria de regla | `tests/loyalty/test_points.py:52` `test_rejects_floats_and_negatives` | `calculate_points` no acepta `float` |
| Integración servicio + BD | `tests/rewards/test_services.py:92` `test_insufficient_balance_changes_nothing` | Un canje sin saldo no deja rastro (ni stock ni movimiento) |
| Restricción de BD | `tests/purchases/test_services.py:163` `test_database_rejects_self_registration` | El CHECK actúa aunque se salte el servicio |
| Permisos y escalada | `tests/dashboard/test_access.py:69` `test_employee_and_customer_are_forbidden` | 403 para otros roles |
| IDOR | `tests/events/test_views.py:115` `test_cannot_see_or_cancel_others_reservations` | 404 para reservas ajenas |
| Formularios | `tests/accounts/test_registration.py` (38) | Validación por campo y anti-enumeración |
| Idempotencia | `tests/purchases/test_services.py:170` (C8.20) | Doble envío sin duplicado |
| Errores de la API | `tests/api/test_security.py:36` `test_error_format` | Formato `{code, detail}` |
| Configuración | `tests/core/test_audit_and_settings.py:58-91` (`test_prod_requires_secret_key`, `test_prod_rejects_simulated_email_backends`, `test_prod_requires_https_site_url`…) | `prod.py` no arranca con configuraciones inseguras |
| Concurrencia | `tests/*/test_concurrency.py` (17, hilos que arrancan a la vez con `Barrier`) | Sin doble consumo, duplicados ni saldo negativo; aforo respetado; un solo refresh válido; siempre queda un propietario activo y sin interbloqueos |
| Caracterización | `tests/dashboard/test_stats_selectors.py` | Fija los límites `[inicio, fin)` de 17 cálculos antes de refactorizarlos |
| Número de consultas | `assertNumQueries` en `test_stats_selectors.py` | Las estadísticas de canjes (1 consulta) y reservas (2) no vuelven a crecer |

### 11.4 Qué no garantizan los tests

- **El servidor real:** DNS, certificado, SMTP y destino de las copias (la pila se probó en local y en el CI).
- **El envío real** de emails (backend en memoria o Mailpit) y los SMS (no hay proveedor).
- **El JavaScript** (`qr-scanner.js`, `app.js`): no hay tests de navegador (Selenium o Playwright).
- **Accesibilidad y diseño visual**: no hay pruebas automáticas de contraste ni de diseño responsive.
- **Rendimiento con carga**: no hay pruebas de carga; solo se mide el número de consultas.
- **Cobertura de código**: no se mide (no hay coverage instalado); **no se puede afirmar un porcentaje**.

### 11.5 Casos adicionales propuestos

1. Pruebas E2E del lector de QR con Playwright (permiso de cámara simulado).
2. Medición de cobertura (`coverage run manage.py test`) para localizar ramas sin probar.
3. Test de que `process_notifications` lanzado dos veces en paralelo no duplica envíos (supercronic ya evita solaparlo).
4. Pruebas de carga del registro de compras en hora punta.
5. `pip-audit` en el CI.

---

## 12. Instalación, configuración y ejecución

Comandos contrastados con `README.md`, `.env.example`, `manage.py` y `scripts/tailwind.py`.

### 12.1 Requisitos previos
- Python 3.12 o superior (desarrollado con 3.14).
- PostgreSQL 14 o superior (probado con 17), obligatorio en producción. En desarrollo es opcional: sin `DATABASE_URL` se usa SQLite `db.sqlite3`.
- Opcional: Docker (en Windows, Docker Engine dentro de WSL) para levantar la pila completa de producción en local.
- No hacen falta Node ni npm (el CSS compilado está versionado).

### 12.2 Pasos

| Paso | Windows (PowerShell) | Linux / macOS |
|---|---|---|
| Entorno virtual | `python -m venv .venv` · `.venv\Scripts\activate` | `python3 -m venv .venv` · `source .venv/bin/activate` |
| Dependencias | `pip install -r requirements/dev.txt` | ídem |
| Variables | `copy .env.example .env` (y ajusta los valores) | `cp .env.example .env` |
| Migraciones | `python manage.py migrate` | ídem |
| Primer propietario | `python manage.py create_owner` (interactivo, contraseña oculta) | ídem |
| Ejecutar | `python manage.py runserver` → http://localhost:8000 | ídem |
| Tests | `python manage.py check` · `python manage.py test --settings=config.settings.test --parallel 1` (con `DATABASE_URL` de PostgreSQL) | ídem |
| Pila completa (Docker) | — | Órdenes del README (`compose.yaml` + `compose.dev.yaml`): Mailpit en http://localhost:8025 y la web en https://localhost:8443 |
| CSS (solo si cambias clases) | `python scripts/tailwind.py build` (o `watch`) | ídem |
| OpenAPI (tras cambiar la API) | `python manage.py spectacular --file docs/api/openapi.yaml` | ídem |

### 12.3 Variables de entorno principales (valores ficticios)

| Variable | Para qué | Por defecto |
|---|---|---|
| `DJANGO_SECRET_KEY` | Firma de sesiones, tokens y JWT | `dev-insecure-...` solo en `dev.py`; obligatoria en producción (≥ 32 bytes) |
| `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_ADMIN_URL` | Básicos | `True` en dev; `localhost,127.0.0.1`; `admin/` |
| `DATABASE_URL` | PostgreSQL (p. ej. `postgres://usuario:contrasena-ficticia@localhost:5432/caneca_furada`) | SQLite |
| `EMAIL_BACKEND`, `EMAIL_HOST`… | Correo | Consola en dev |
| `SITE_BASE_URL` | Enlaces de los emails | `http://localhost:8000` (https obligatorio en producción) |
| `CACHE_URL` | Caché compartida | `locmemcache://` en desarrollo; producción exige una compartida (Redis en Compose) |
| `DJANGO_TRUSTED_PROXY_COUNT` | IP real tras proxies | 0 |
| `API_*` | Duración de los tokens y throttling | 15 min, 30 días, 60/240/10 por minuto |
| `CANECA_OWNER_*` | `create_owner --noinput` | Solo durante el comando |

Los parámetros de negocio **no** son variables de entorno salvo los indicados: se cambian en `config/settings/base.py` (cap. 7, tabla de límites).

### 12.4 Correo en desarrollo
Por defecto los emails se imprimen en la consola de `runserver` (`config/settings/dev.py:14`). Para un SMTP local (p. ej. Mailpit), ver los comentarios de `.env.example:31-35`; la pila de Docker en local ya incluye Mailpit.

### 12.5 Errores frecuentes (documentados en el README)
- `UnicodeEncodeError` al imprimir emails en Windows → arrancar con `$env:PYTHONUTF8=1`.
- La cámara del lector de QR no funciona → solo funciona en `localhost` o con HTTPS (requisito del navegador); alternativa: teclear el código.
- Imágenes subidas que no se ven sin Nginx → `static()` solo sirve `media/` con `DEBUG = True` (`config/urls.py:28-31`); en producción las sirve Nginx desde el volumen `media`.

**Docker:** la pila de producción se puede levantar en local con `compose.yaml` y `compose.dev.yaml` (certificado autofirmado, Mailpit y un servicio de tests). Órdenes en el README y en [`docs/despliegue.md`](../despliegue.md).

---

## 13. Despliegue y mantenimiento

**Estado real: preparado y probado en local; no desplegado en un servidor.** La Fase 12 dejó en el repositorio la imagen, la pila de producción, las copias y el CI, y todos los procedimientos se ejecutaron sobre una pila local en WSL partiendo de volúmenes vacíos. Falta contratar el VPS y hacer las acciones manuales (§13.3). Detalle completo: [`docs/fase-12-despliegue.md`](../fase-12-despliegue.md) y guía operativa en [`docs/despliegue.md`](../despliegue.md).

### 13.1 Arquitectura de producción

```mermaid
flowchart LR
    U["Navegadores y app móvil"] -->|"HTTPS 443"| NX["nginx<br/>TLS Let's Encrypt, /static con hash,<br/>/media solo imágenes, límites de login"]
    NX -->|"HTTP interno"| WEB["web<br/>Gunicorn + Django (config.settings.prod)<br/>usuario no root, FS de solo lectura"]
    WEB --> PG[("db<br/>PostgreSQL 17, rol sin privilegios,<br/>sin puertos publicados")]
    WEB --> RD[("redis<br/>caché compartida, sin persistencia")]
    WEB --> SMTP["Proveedor SMTP<br/>EMAIL_*"]
    SCH["scheduler (supercronic)<br/>process_notifications cada 5 min;<br/>cumpleaños, caducidad de canjes<br/>y purgas diarias"] --> PG
    CB["certbot<br/>renovación cada 12 h"] -.-> NX
    PG -.->|"pg_dump cifrado con restic"| BK[("Destino externo de copias<br/>(S3, B2 o rest-server)")]
```

| Elemento | Estado verificado | Evidencia |
|---|---|---|
| Configuración de producción | `prod` no arranca sin clave (≥ 32 bytes), `ALLOWED_HOSTS`, PostgreSQL, caché compartida, SMTP real o `SITE_BASE_URL` https | `config/settings/prod.py`; `check --deploy`: solo W021 |
| Imagen | Multietapa, usuario `app` no root, sin `.env` ni secretos; estáticos con hash en la imagen de Nginx | `Dockerfile`, `.dockerignore` |
| Servidor de aplicaciones | Gunicorn, 3 workers síncronos, `timeout` 30 s > `EMAIL_TIMEOUT` 10 s | `deploy/gunicorn.conf.py` |
| Proxy inverso y HTTPS | Nginx con TLS, hosts desconocidos cerrados (444), `limit_req` en el login, logs sin tokens ni cadena de consulta | `deploy/nginx/templates/` |
| Base de datos | PostgreSQL 17 con ICU `es-ES`; la app usa un rol sin privilegios | `deploy/postgres/10-app-role.sh` |
| Caché | Redis en la red interna `backend` | `compose.yaml` |
| Healthcheck | Middleware `/healthz` interno (`SELECT 1`); Nginx devuelve 404 desde fuera | `apps/core/middleware.py`; `tests/core/test_health.py` |
| Tareas programadas | supercronic en el servicio `scheduler` | `deploy/cron/crontab` |
| Copias y restauración | restic: BD y `media/` cifradas, retención 7 diarias y 4 semanales, restauración de prueba | `deploy/scripts/backup.sh`, `restore.sh` |
| Despliegue y rollback | Etiquetas `:<commit>`, `:current` y `:previous`; copia previa; migraciones como paso único | `deploy/scripts/deploy.sh` |
| CI | Suite en PostgreSQL sin omitidos, `check --deploy`, OpenAPI, build, pila Compose, prueba de humo y copia/restauración | `.github/workflows/ci.yml`; en verde en GitHub con la versión congelada (2026-10-15, [ejecución](https://github.com/Jav-VM/CanecaFurada/actions/runs/38776430860), commit `decff8f`) |
| Monitorización | **No implementada** (siguiente paso) | — |

### 13.2 Procedimientos probados en local (2026-10-15)

| Paso | Resultado |
|---|---|
| `deploy.sh --first` y `create_owner` | Pila arrancada y propietario creado |
| Prueba de humo por HTTPS a través de Nginx | 25/25 OK (cabeceras, estáticos, 404 en `/healthz`, registro con email en Mailpit, JWT, `limit_req`) |
| `backup.sh run` y `restore.sh check` | Copia sin errores; recuentos idénticos tras restaurar |
| Desastre simulado (se borran la BD y una imagen) y `restore.sh full --yes` | Datos e imagen recuperados; la portada vuelve a dar 200 |
| `deploy.sh` con copia previa y `deploy.sh rollback` | Actualización y vuelta a la imagen anterior en segundos |

**Si una migración falla en producción:** cada migración de Django en PostgreSQL se ejecuta en una transacción (DDL transaccional): si falla, se deshace. `deploy.sh` hace una copia antes de migrar. Si una versión nueva trae migraciones incompatibles con la anterior, el rollback exige restaurar esa copia y se pierde lo escrito después.

**Rotación de secretos:** procedimiento en [`fase-12-despliegue.md` §8.6](../fase-12-despliegue.md). Rotar `API_JWT_SIGNING_KEY` cierra todas las sesiones de la app (`.env.example:71`).

### 13.3 Acciones manuales pendientes en el VPS

Contratar el VPS y endurecerlo (usuario sin root, SSH con clave, UFW, actualizaciones automáticas); DNS del dominio y SPF, DKIM y DMARC del remitente; `.env.prod` y `.env.backup` con valores reales; destino externo de restic; primer despliegue con el certificado real; comprobar la entrega por el SMTP real; programar las copias en el host; y revisión visual y de la cámara en dispositivos reales.

---

## 14. Evolución del proyecto por fases

### 14.1 Fuentes y fiabilidad

- **Historial de Git:** 25 commits en la versión congelada. **Uno por fase** del 0 al 11 (más 3 previos de preparación), del 13 y 14-10-2026; después, el 15-10-2026, la documentación de la defensa, la migración a PostgreSQL, la auditoría previa a la Fase 12, la Fase 12 y la refactorización final. Los archivos de cada commit hasta la Fase 11 están en [`_trabajo/historial_fases.md`](_trabajo/historial_fases.md) (generado con `git show --name-status`; usa los hashes del historial anterior a la reescritura).
- **Reescritura del historial:** en la auditoría se reescribió el historial para eliminar `db.sqlite3.bak` (P2-6). Cambiaron los hashes desde la Fase 10: la F10 era `a85ce95` y ahora es `b91d8bd`; la F11 era `ac5903a` y ahora es `eec6abc`.
- **Documentación de cada fase:** `docs/fase-XX-*.md`.
- **Límite:** cada fase es un único commit, así que se conoce **qué** entró en cada fase, pero **no el orden interno** ni las iteraciones dentro de ella.

### 14.2 Correspondencia entre la hipótesis del prompt y las fases reales

| Hipótesis del prompt (11 fases) | Fase real en el repositorio | Commit |
|---|---|---|
| 1. Base del proyecto, configuración y roles | **F0** Fundación + **F1** Perfil de cliente y preparación para la app | `4d842da`, `b2cf7f6` |
| 2. Registro, perfiles, verificación de email y privacidad | **F2** | `d948db7` |
| 3. Web pública | **F3** Sistema de diseño y web pública | `35424be` |
| 4. Carta y catálogo | **F4** | `b035ca4` |
| 5. QR y registro de compras | **F5** | `d1c1a89` |
| 6. Puntos | **F6** Ledger, promociones y base de cumpleaños | `99711bc` |
| 7. Recompensas y canjes | **F7** | `c185ff4` |
| 8. Panel del empleado | **F8** | `1131258` |
| 9. Panel del propietario y estadísticas | **F9** | `70fb531` |
| 10. Eventos, reservas, contenido y notificaciones | **F10** | `b91d8bd` |
| 11. Auditoría, seguridad, API, documentación **y despliegue** | **F11** API, auditoría y seguridad; el despliegue se hizo después como **F12**, tras la migración a PostgreSQL y una auditoría | `eec6abc`; F12: `955c1be` |

Reordenaciones documentadas (`docs/plan-de-fases.md`): registro ↔ sistema de diseño (F2/F3), compras ↔ ledger (F5/F6) y la inserción del panel de empleados como F8 (desplazando eventos y API). **Los documentos de las fases 0 a 7 conservan la numeración antigua** en sus referencias.

### 14.3 Ficha de cada fase

| Fase | Objetivo y problema que resuelve | Archivos y modelos relevantes (según el commit) | Cambios de arquitectura | Depende de | Tests añadidos (carpeta) | Estado actual | Pendiente |
|---|---|---|---|---|---|---|---|
| **F0** `4d842da` (54 archivos, +1988) | Base técnica sin rehacer migraciones de usuario | `apps/accounts/models.py`, `services.py`, `permissions.py`, `create_owner`; `apps/core/models.py` y `services.py`; `config/settings/*` | Monolito modular; usuario propio con roles **antes de la primera migración**; capa de servicios; auditoría | — | `tests/accounts`, `tests/core` | Completa | — |
| **F1** `b2cf7f6` (10 archivos) | Que todo cliente tenga perfil | `CustomerProfile` (mínimo), migración de datos `0003_backfill` | Perfil 1:1 separado de `User`; `public_id` | F0 | `test_customer_profile.py` | Completa | — |
| **F2** `d948db7` (64 archivos, +4064) | Alta segura y datos personales | `accounts/views.py`, `forms.py`, `validators.py`, `emails.py`; `EmailVerificationToken`, `CommunicationPreferenceChange`; plantillas de cuenta y emails | Formularios que solo convierten y servicios que validan | F0-F1 | `test_registration`, `test_email_verification`, `test_profile`… | Completa | SMTP real |
| **F3** `35424be` (61 archivos) | Imagen de marca y web pública | `apps/web/`, `templates/base.html`, `components/`, `assets/css/input.css`, `scripts/tailwind.py`, `static/css/app.css` | Tailwind CLI sin Node; JS de mejora progresiva | F0-F2 | `tests/web/` | Completa | Contenido del propietario; revisión visual |
| **F4** `b035ca4` (32 archivos) | Carta gestionable | `apps/catalog/*` (Category, BeerStyle, Product, TapMenu) | Selectores con las reglas de visibilidad; admin restringido | F0-F1, F3 | `tests/catalog/` | Completa | Almacenamiento de imágenes en producción |
| **F5** `d1c1a89` (44 archivos, +12462, incluye jsQR) | Identificar al cliente y registrar compras | `apps/loyalty/models.py` (`CustomerQRCode`), `services.py`; `apps/purchases/*`; `static/js/qr-scanner.js`, `static/vendor/jsqr/` | Idempotencia por clave; transacción con bloqueo | F2-F3 | `test_qr.py`, `tests/purchases/` | Completa | Dispositivos físicos |
| **F6** `99711bc` (31 archivos) | Puntos sin manipulación | `apps/loyalty/ledger.py`, `conversion.py`, `promotions.py`, `selectors.py`; `apps/purchases/selectors.py` | Ledger inmutable con saldo derivado; UNIQUE condicionales | F5 | `test_points.py`, `test_promotions.py`… | Completa | Confirmar la conversión |
| **F7** `c185ff4` (45 archivos) | Canjear puntos sin doble consumo | `apps/rewards/*` (Reward, Redemption, codes), comando `expire_redemptions` | UPDATE condicionado; orden de bloqueo | F5-F6 | `tests/rewards/` (incluida la concurrencia) | Completa | Plazo de 30 días |
| **F8** `1131258` (38 archivos) | Herramienta de barra | `apps/staff/*`, `templates/staff/*` | App solo de presentación | F5, F7 | `tests/staff/` | Completa | Dispositivos físicos |
| **F9** `70fb531` (55 archivos) | Gestión y cifras del propietario | `apps/dashboard/*`, `apps/accounts/selectors.py`, `apps/web/models.py` (`BusinessInfo`) | Modelo híbrido dashboard + admin; consultas auditadas | F2-F8 | `tests/dashboard/` | Completa | Revisión visual |
| **F10** `b91d8bd` (112 archivos) | Eventos, reservas, contenido y comunicaciones | `apps/events/*`, `apps/notifications/*`, `apps/loyalty/birthdays.py`, `loyalty/0003_birthday_gift` | Registro de notificaciones con estado real; tareas por comandos (sin Celery) | F2-F3, F6-F7, F9 | `tests/events/`, `tests/notifications/`, `test_birthdays.py` | Completa | SMTP real, SMS |
| **F11** `eec6abc` (60 archivos, +6758) | App móvil y auditoría de seguridad | `apps/api/*` (tokens, autenticación, permisos, serializadores, vistas), `apps/core/http.py`, `purge_email_tokens`, `docs/api/openapi.yaml`, `docs/guia-app-flutter.md`, `docs/despliegue.md` | DRF + JWT reutilizando los servicios; 6 correcciones de auditoría (`docs/fase-11-api-auditoria.md` §3) | Todas | `tests/api/`, `tests/core/test_phase11_audit.py` | Completa | — |
| **PostgreSQL** `f72cbd1` (12 archivos) | Validar el motor objetivo | `config/settings/*`, `apps/events/services.py`; `docs/migracion-postgresql.md` | Suite en PostgreSQL; corregido un `FOR UPDATE` sobre un `LEFT JOIN` que solo fallaba en PostgreSQL (C8.13) | F11 | — | Completa | — |
| **Auditoría** `eb32b52` (21 archivos) | Corregir lo que comprometiera el despliegue | `apps/accounts/forms.py` (límite del login del admin), `config/settings/prod.py` (caché compartida), `apps/rewards/services.py` (interbloqueo), `requirements/` (versiones exactas) | `tests/concurrency.py` y tests de concurrencia en compras, ajustes y reservas | PostgreSQL | `tests/*/test_concurrency.py` | Completa | P2-9 y los P3 pospuestos |
| **F12** `955c1be` (37 archivos) | Desplegar y mantener con garantías | `Dockerfile`, `compose.yaml`, `deploy/`, `.github/workflows/ci.yml`, `apps/core/middleware.py` (healthcheck) | Contenedores, Nginx, Redis, scheduler, copias con restic y CI | Auditoría | `tests/core/test_health.py`, concurrencia | Completa en local | VPS, DNS, certificado, SMTP real |
| **Refactorización** `d0bac7c` (16 archivos) | Mantenibilidad sin cambiar el comportamiento | `apps/core/querysets.py`, selectores, `apps/accounts/services.py` y `admin.py` | Filtro de periodo común; estadísticas con menos consultas; orden de bloqueo único en la regla del último propietario (R-1) | F12 | `tests/dashboard/test_stats_selectors.py`, `tests/accounts/test_concurrency.py` | Completa | — |

> Nota: la atribución de archivos a cada fase sale de `git show`, no de su nombre. Algunos archivos se modificaron en varias fases (p. ej. `apps/core/models.py` en todas, para añadir acciones de auditoría).

---

## 15. Decisiones de diseño y alternativas

Para cada decisión se distingue la **justificación técnica** (razonable por el código) del **motivo documentado** (si consta en `docs/`). No se inventan motivos históricos.

| # | Decisión | Necesidad | Alternativas | Ventajas / desventajas | Motivo documentado | Cómo defenderla |
|---|---|---|---|---|---|---|
| D1 | Monolito modular Django con capa de servicios | Web, panel, dashboard y API comparten reglas | Microservicios; lógica en las vistas | + Una sola fuente de reglas, transacciones locales, sencillez operativa / − Escala como bloque | `docs/arquitectura.md` §1 | «Para un local, un monolito bien modularizado es más fiable y barato; la API reutiliza los mismos servicios, así que no se duplica lógica» |
| D2 | Usuario personalizado con roles **antes de la primera migración** | Cambiar `AUTH_USER_MODEL` después es muy costoso | Usuario por defecto + grupos | + Roles simples y restricciones en la BD / − Menos granularidad que los permisos de Django | Plan F0 | «Es la recomendación oficial de Django: decidir el modelo de usuario al principio» |
| D3 | `CustomerProfile` separado de `User` | Solo los clientes tienen datos personales | Todo en `User` | + Minimización: el personal no tiene esos campos / − Un JOIN más | `docs/arquitectura.md` §2 | «Separa los datos sensibles del cliente de la identidad de acceso» |
| D4 | `public_id` UUID en URLs y API | Evitar la enumeración (IDOR) | IDs secuenciales | + No se pueden adivinar / − URLs largas | `docs/arquitectura.md` §3 | «Aunque haya control de acceso, no damos pistas: los ids no son secuenciales» |
| D5 | Ledger de puntos inmutable con saldo derivado | Trazabilidad y corrección sin borrar | Campo `saldo` editable | + Auditable y reconstruible / − Coste de `SUM` (mejorable) | Plan F6 | «Como un libro contable: se corrige con un apunte contrario» |
| D6 | `Decimal` + `ROUND_DOWN` | Exactitud monetaria | `float` | + Sin errores binarios; nunca se regalan puntos | `conversion.py:1-11` | «El dinero nunca se calcula con float» |
| D7 | Idempotencia con clave única + replay | Doble clic, reintentos de red y de la app | Bloqueo del botón solo en el cliente | + Garantía en el servidor y la BD | Plan F5 | «El JS evita el doble envío, pero la garantía real la da la base de datos» |
| D8 | `select_for_update` + UPDATE condicionados + UNIQUE, con un orden de bloqueo fijo | Concurrencia | Bloqueo optimista con versión | + Simple y correcto; verificado con 17 tests de hilos en PostgreSQL / − Hay que respetar el orden en cada servicio (dos interbloqueos corregidos: P2-1 y R-1) | Docstrings de los servicios | «Tres capas: bloqueo, condición en el UPDATE y restricción única; y siempre se bloquea en el mismo orden» |
| D9 | Puntos del canje descontados al **solicitarlo** | Saldo real y no prometer dos veces | Descontar al validar | + El saldo visible es real / − Requiere devolver en la caducidad | Plan F7 | «Si no se recoge, se devuelve automáticamente» |
| D10 | Tareas con comandos + programador (supercronic en el servicio `scheduler`, sin Celery) | Simplicidad | Celery + Redis | + Sin infraestructura extra / − Granularidad de minutos | Ajuste de la F10 (decisión del usuario); F12 | «Para el volumen de un local basta; los comandos son idempotentes y supercronic no solapa ejecuciones» |
| D17 | Docker Compose en un único VPS | Desplegar y recuperar con garantías a bajo coste | Instalación directa; PaaS; Kubernetes | + Reproducible, rollback por etiquetas, copias probadas / − Sin alta disponibilidad | Decisión del usuario (2026-10-14), `docs/fase-12-despliegue.md` | «Para un local, un servidor con copias cifradas y restauración probada es suficiente y barato» |
| D18 | Refactorizar solo con tests de caracterización previos y mediciones | No romper nada al mejorar el código | Refactorizar sin red | + Comportamiento fijado antes de tocar / − Más tests que mantener | `docs/refactorizacion-final.md` | «Primero fijé el comportamiento con tests; después cambié el código y medí las consultas» |
| D11 | Admin de Django para las fichas completas + dashboard para las acciones rápidas | Productividad | CRUD propio completo | + Menos código / − Interfaz menos guiada | Decisión de la F9 | «El admin es seguro y está probado; el dashboard cubre el día a día» |
| D12 | JWT con refresh rotatorio + lista negra + `pwv` | App móvil sin cookies | Tokens de DRF; sesión | + Revocable, sin CSRF / − Más piezas | `docs/fase-11-api-auditoria.md` §5 | «Un access corto y la revocación inmediata al cambiar la contraseña» |
| D13 | Sin CORS en la API | Solo una app nativa | `django-cors-headers` con lista blanca | + Ninguna web ajena lee las respuestas | `docs/fase-11-api-auditoria.md:155` | «Si mañana hay una web cliente en otro dominio, se añade con lista blanca» |
| D14 | Tailwind CLI standalone con checksum | Estilos sin Node | Bootstrap; npm | + Sin cadena npm; integridad del binario verificada | `scripts/tailwind.py` | «Menos dependencias y el binario verificado» |
| D15 | Regalo de cumpleaños sin exigir consentimiento publicitario | Que el consentimiento sea libre | Condicionar el regalo al opt-in | + Coherencia legal razonable | `loyalty/birthdays.py:14-17` | «No condicionamos un beneficio a aceptar publicidad» |
| D16 | Notificaciones con registro de estado real | No dar por enviado lo simulado | Enviar sin registro | + Honestidad operativa y reintentos | `notifications/models.py:1-15` | «El dashboard distingue un envío real de uno simulado» |

---

## 16. Limitaciones y mejoras futuras

Resumen; la lista completa con prioridad, coste y beneficio está en [05_limitaciones_y_pendientes.md](05_limitaciones_y_pendientes.md).

- **Limitaciones actuales (alcance deliberado):** no hay facturación, caja ni TPV; no hay SMS; no hay app móvil; las reservas de mesa no tienen aforo; un precio por producto.
- **Funcionalidades incompletas:** anulación de compras (`VOIDED` reservado), integración con TPV (`POS` reservado), exportación y supresión de datos personales (decisión tomada, P2-9), campo `birthday_window_days` sin uso, `CancelReservationForm` sin uso.
- **Pendiente antes de producción:** las acciones manuales en el VPS (DNS, certificado, SMTP real, destino de copias), monitorización y alertas, y los controles pospuestos de la auditoría (CSP, EXIF).
- **Mejoras a medio plazo:** saldo materializado, 2FA para el propietario, `pip-audit` en el CI, cobertura, tests E2E del QR, Swagger UI local y auditoría con inmutabilidad en la BD.
- **Ampliaciones futuras:** app Flutter (la API ya existe), integración con TPV, anulación de compras con compensación en el ledger y proveedor de SMS.

---

## 19. Glosario técnico

| Término | Definición sencilla | Ejemplo en Caneca Furada |
|---|---|---|
| **Modelo** | Clase Python que representa una tabla de la BD | `Purchase` (`apps/purchases/models.py:21`) → tabla `purchases_purchase` |
| **Vista** | Función o clase que recibe una petición HTTP y devuelve una respuesta | `purchases.views.register` |
| **URL / URLconf** | Tabla que asocia rutas con vistas | `path("registrar/", views.register, name="register")` |
| **Formulario** | Clase que convierte y valida la entrada de un usuario | `PurchaseForm` (`apps/purchases/forms.py:22`) |
| **Serializador** | Equivalente del formulario en la API (JSON ↔ Python) | `PurchaseCreateSerializer` |
| **ORM** | Capa que traduce operaciones Python a SQL | `Purchase.objects.filter(registered_by=staff)` |
| **Migración** | Archivo versionado que cambia el esquema de la BD | `loyalty/0002_points_ledger_promotions.py` |
| **Migración de datos** | Migración que modifica filas con código (`RunPython`) | `accounts/0003_backfill_customer_profiles.py` |
| **Middleware** | Capa que procesa todas las peticiones y respuestas | `CsrfViewMiddleware` valida el token CSRF |
| **Decorador** | Función que envuelve otra para añadir comportamiento | `@role_required(User.Role.OWNER)` |
| **Servicio de negocio** | Función que aplica las reglas, los permisos y la transacción de una operación | `rewards.services.request_redemption` |
| **Selector** | Función de solo lectura que encapsula una consulta con sus reglas | `catalog.selectors.public_menu` |
| **Transacción** | Grupo de operaciones que se confirman todas o ninguna | `with transaction.atomic():` al registrar una compra y sus puntos |
| **Savepoint** | Transacción anidada que se puede deshacer sin deshacer la externa | El `atomic()` interno que captura `IntegrityError` |
| **`select_for_update`** | Bloqueo de filas hasta el final de la transacción (`SELECT ... FOR UPDATE`) | `ledger._lock_customer` |
| **Clave foránea (FK)** | Columna que apunta a otra tabla | `Purchase.customer` → `User` |
| **`on_delete=PROTECT`** | Impide borrar un objeto referenciado | No se puede borrar una recompensa con canjes |
| **Índice** | Estructura que acelera las búsquedas | `Index(fields=["customer", "created_at"])` en el ledger |
| **Restricción CHECK** | Condición que la BD exige a cada fila | `balance_after >= 0` |
| **Restricción UNIQUE condicional** | Unicidad solo para las filas que cumplen una condición (índice parcial) | Un solo canje `PENDING` por cliente y recompensa |
| **Hash de contraseña** | Transformación irreversible con sal para no guardar la contraseña | `user.set_password()` (Django usa PBKDF2 por defecto) |
| **Hash SHA-256** | Resumen irreversible de un dato | El token de verificación se guarda como `sha256(token)` |
| **HMAC** | Hash con clave secreta que prueba la autenticidad | La reclamación `pwv` de los JWT |
| **Token** | Cadena que representa un permiso o una identidad temporal | Enlace de verificación, JWT, código de canje |
| **JWT** | Token firmado con datos (claims) que el servidor verifica sin sesión | `access` de 15 min con `sub = public_id` |
| **Refresh rotatorio** | Cada renovación invalida el refresh usado y entrega otro | `tokens.rotate_refresh_token` |
| **CSRF** | Ataque que fuerza una petición desde otro sitio usando la cookie de la víctima | Se evita con `{% csrf_token %}`; la API no usa cookies |
| **XSS** | Inyección de scripts en una página | Se evita con el autoescape y rechazando SVG y enlaces no https |
| **IDOR / BOLA** | Acceder a un objeto ajeno cambiando un identificador | 404 si un cliente pide el canje de otro |
| **Asignación masiva** | Que el cliente envíe campos que no debería poder cambiar (p. ej. `role`) | Formularios y serializadores con campos explícitos |
| **Idempotencia** | Repetir una operación produce el mismo resultado que hacerla una vez | Reenviar la misma compra devuelve la existente |
| **Clave de idempotencia** | Identificador único de una operación para detectar reintentos | `Purchase.idempotency_key`, cabecera `Idempotency-Key` |
| **Concurrencia** | Varias operaciones al mismo tiempo sobre los mismos datos | Dos empleados validando el mismo código |
| **Condición de carrera** | Error que depende del orden de ejecución concurrente | Dos canjes que pasan la comprobación de saldo a la vez |
| **Ledger** | Libro de movimientos inmutable del que se deriva un saldo | `PointsTransaction` |
| **Movimiento compensatorio** | Apunte de signo contrario que anula otro sin borrarlo | `REVERSAL` |
| **Throttling / rate limiting** | Limitar el número de peticiones por tiempo | 5 fallos de login por email en 15 min |
| **API REST** | Interfaz HTTP con recursos y verbos estándar | `GET /api/v1/me/points/` |
| **OpenAPI** | Especificación estándar que describe una API | `docs/api/openapi.yaml` |
| **Entorno virtual** | Instalación aislada de Python y sus paquetes | `.venv/` |
| **Variable de entorno** | Configuración externa al código | `DJANGO_SECRET_KEY`, `DATABASE_URL` |
| **Contenedor** | Paquete aislado con la app y sus dependencias (Docker) | Servicios `web`, `db`, `redis`, `nginx`, `scheduler` y `certbot` de `compose.yaml` |
| **Proxy inverso** | Servidor delante de la app que recibe las peticiones (TLS, estáticos) | Nginx (cap. 13); `TRUSTED_PROXY_COUNT = 1` |
| **Interbloqueo (deadlock)** | Dos transacciones que esperan cada una un bloqueo de la otra; la BD aborta una | R-1: dos propietarios retirándose mutuamente; se evita bloqueando siempre en el mismo orden |
| **Test de caracterización** | Test que fija el comportamiento actual antes de cambiar el código | `tests/dashboard/test_stats_selectors.py` |
| **HSTS** | Cabecera que obliga al navegador a usar HTTPS | `SECURE_HSTS_SECONDS` = 1 año en producción |
| **Backup** | Copia de seguridad restaurable | `deploy/scripts/backup.sh` (restic, cifrada) y `restore.sh` |
| **CI/CD** | Integración y despliegue continuos automatizados | CI en GitHub Actions (`.github/workflows/ci.yml`); el despliegue es manual con `deploy.sh` |
| **Mejora progresiva** | Funcionar sin JS y mejorar con JS si está disponible | Lector de QR: cámara si se puede, si no, código tecleado |
| **Singleton (modelo)** | Tabla con una sola fila | `BusinessInfo` (`id = 1`) |
| **Data URI** | Imagen incrustada en el HTML como texto | El QR en SVG de `my_qr` |
| **E.164** | Formato internacional de teléfono (`+34…`) | `CustomerProfile.phone_number` |

---

## 20. Conclusiones y valoración técnica

**Qué se ha construido realmente.** Una aplicación Django completa y probada (849 tests que pasan en PostgreSQL 17 sin omitidos, también dentro del contenedor de producción) que cubre la web pública, el programa de fidelización de punta a punta (registro verificado → QR → compra → puntos → canje → validación), el panel del personal, el dashboard del propietario con estadísticas reales y geográficas, eventos y reservas, notificaciones con consentimiento y una API REST v1 documentada con OpenAPI. Está preparada para producción con Docker Compose (Nginx, Gunicorn, PostgreSQL, Redis, tareas programadas, copias cifradas y CI), probada de extremo a extremo en local.

**Qué necesidades satisface.** Fidelizar sin tarjetas físicas, operar rápido en la barra, impedir abusos (puntos duplicados, canjes repetidos, autorregistro de compras) y dar al propietario información útil sin exponer datos personales al resto del personal.

**Qué conocimientos técnicos demuestra.** Arquitectura en capas en Django (vistas finas, servicios, selectores); modelado relacional con invariantes en la BD (CHECK, UNIQUE condicionales, PROTECT); control de concurrencia (`select_for_update`, UPDATE condicionados) e idempotencia; seguridad aplicada (autorización por rol en varias capas, anti-enumeración, IDOR, tokens con hash, JWT revocables, IP tras proxies); privacidad por diseño (minimización, consultas auditadas, consentimiento con historial); pruebas automatizadas amplias, también de concurrencia real; despliegue con contenedores, copias y CI; refactorización controlada con tests de caracterización y mediciones; y documentación por fases.

**Decisiones más importantes.** El ledger inmutable con saldo derivado, la idempotencia con clave única, el modelo de usuario con roles desde la primera migración, la separación del perfil personal y la reutilización de los mismos servicios en la web y en la API.

**Limitaciones presentes.** No está desplegada en un servidor real; el SMTP real y el SMS no están configurados; no hay exportación ni supresión de datos; no hay monitorización ni medición de cobertura; JS y accesibilidad sin pruebas automáticas.

**Condiciones antes de producción.** (1) Contratar y endurecer el VPS, con DNS y certificado; (2) proveedor SMTP real con SPF, DKIM y DMARC; (3) destino externo de las copias y su programación en el host; (4) monitorización y alertas; (5) revisión de los textos legales y de los derechos de los interesados (P2-9); (6) revisión visual y de accesibilidad en dispositivos reales. Ya están resueltas la validación en PostgreSQL con concurrencia, la caché compartida, el servidor WSGI con proxy TLS, la programación de las tareas y las copias con restauración probada.

**Posibilidades de evolución.** App Flutter sobre la API ya existente, integración con TPV (el modelo ya reserva `POS` y `external_reference`), anulación de compras con compensación en el ledger, SMS con un proveedor real y 2FA para el propietario.
