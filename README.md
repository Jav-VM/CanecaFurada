# Caneca Furada — Plataforma web

Plataforma de la cervecería artesanal Caneca Furada (A Coruña): web pública, programa de fidelización, panel de empleados, dashboard del propietario y backend preparado para una futura app móvil.

Monolito modular **Django 5.2 + PostgreSQL**, con Django Templates en la web y una API REST v1 (Django REST Framework) para la futura app móvil.

## Estado

| Fase | Estado |
|---|---|
| 0 — Fundación del proyecto | **Completa** |
| 1 — Proyecto base: perfil de cliente, módulos y preparación para la app | **Completa** |
| 2 — Autenticación, registro, perfiles, verificación de email y permisos | **Completa** (pendiente validar con SMTP real) |
| 3 — Sistema de diseño y web pública | **Completa** (contenidos del local pendientes de aportar por el propietario) |
| 4 — Carta y cervezas | **Completa** (pendiente almacenamiento de imágenes en producción) |
| 5 — QR personal y registro de compras manuales | **Completa** (pendiente probar el escaneo en dispositivos físicos) |
| 6 — Fidelización: ledger de puntos, promociones y base de cumpleaños | **Completa** (pendiente confirmar la conversión por defecto) |
| 7 — Recompensas y canjes | **Completa** (pendiente confirmar el plazo de recogida) |
| 8 — Panel de empleados | **Completa** (pendiente probar en móviles y tablets físicos) |
| 9 — Dashboard del propietario y estadísticas | **Completa** (pendiente revisión visual en navegador) |
| 10 — Eventos, reservas, contenido y notificaciones | **Completa** (pendiente SMTP real, programar las tareas y proveedor de SMS) |
| 11 — API, auditoría, seguridad y preparación para la app | **Completa** (pendiente el despliegue) |
| Migración a PostgreSQL (endurecimiento y despliegue) | **Completa en desarrollo**: suite completa OK en PostgreSQL 17 (pendiente el VPS) |
| Auditoría previa a la Fase 12 (endurecimiento y despliegue) | **Completa**: 817 tests OK en PostgreSQL 17 y en SQLite; los pendientes de despliegue van a la Fase 12 |

Plan completo: [docs/plan-de-fases.md](docs/plan-de-fases.md).

## Requisitos

- Python 3.12+ (desarrollado con 3.14).
- PostgreSQL 14+ (probado con 17). Obligatorio en producción; sin `DATABASE_URL`, desarrollo y tests usan SQLite. Guía: [docs/migracion-postgresql.md](docs/migracion-postgresql.md).

## Instalación

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements/dev.txt
copy .env.example .env    # ajusta los valores; nunca subas .env
python manage.py migrate
```

Variables de entorno: [.env.example](.env.example) y [docs/fase-00-fundacion.md](docs/fase-00-fundacion.md#6-configuración-y-variables-de-entorno).

## Primer propietario

```powershell
python manage.py create_owner
```

Pide los datos de forma interactiva (contraseña oculta) y solo funciona si todavía no hay propietario. Empleados y propietarios adicionales los crea un propietario desde el admin. Detalles: [docs/fase-00-fundacion.md](docs/fase-00-fundacion.md#creación-del-primer-propietario).

## Ejecutar

```powershell
python manage.py runserver
```

Rutas disponibles:
- Web pública: Inicio (`/`), La cervecería (`/la-cerveceria/`), Carta (`/carta/`), Recompensas (`/recompensas/`), Eventos (`/eventos/` y `/eventos/<id>/`) y Contacto (`/contacto/`).
- Reservas del cliente (email verificado) en `/cuenta/reservas/`: pedir mesa, reservar plaza en un evento, ver el estado y cancelar.
- Baja de comunicaciones promocionales desde el enlace de cada mensaje (`/comunicaciones/baja/<token>/`).
- QR personal del cliente (email verificado) en `/cuenta/mi-qr/`, sus puntos (saldo, movimientos y compras) en `/cuenta/puntos/` y sus canjes en `/cuenta/canjes/`.
- Panel del personal (empleados y propietarios) en `/panel/`: inicio, registrar compras (`/panel/compras/`), validar canjes (`/panel/canjes/`), consultar sus resultados (`/panel/resultados/`) y su perfil (`/panel/perfil/`).
- Dashboard del propietario en `/dashboard/`: resumen, clientes (con estadísticas geográficas), empleados, compras, puntos, recompensas, carta, cervezas, eventos, reservas, promociones, comunicaciones (campañas y registro de envíos), contenido del local y configuración.
- Cuentas en `/cuenta/`: registro (`/cuenta/registro/`), entrar, salir, perfil, preferencias, cambio de email y de contraseña, recuperación de contraseña y verificación de email.
- Admin técnico en `/<DJANGO_ADMIN_URL>` (por defecto `/admin/`), solo para propietarios. Desde ahí se gestiona la carta (sección **Carta**).
- API REST v1 para la app móvil en `/api/v1/` (JSON y JWT); documentación interactiva en `/api/v1/docs/` (en desarrollo sin sesión; en producción solo el propietario).

## Gestionar la carta

El propietario crea estilos, categorías y productos en el admin, publica, archiva o marca como agotado con las acciones de la lista y sube la imagen de la carta de grifos. Nada se borra: los productos se archivan. Las imágenes subidas solo se sirven en desarrollo hasta la fase de despliegue (antes Fase 12, hoy sin número asignado). Guía paso a paso: [docs/fase-04-carta.md](docs/fase-04-carta.md#4-gestión-de-la-carta-guía-para-el-propietario).

En desarrollo los emails (verificación, recuperación de contraseña…) se imprimen en la consola de `runserver`. En Windows, si aparece `UnicodeEncodeError` al enviar un email, arranca con `$env:PYTHONUTF8=1`. Configuración del correo y de producción: [docs/fase-02-registro-perfil-verificacion.md](docs/fase-02-registro-perfil-verificacion.md#6-configuración-del-correo-y-variables-de-entorno).

## Probar el registro de compras

Crea un empleado desde el admin y un cliente con el registro público; verifica su email con el enlace que aparece en la consola. El cliente abre *Mi código QR* y el empleado, en *Registrar compra*, lo escanea con la cámara (solo en `localhost` o HTTPS) o teclea el código que aparece bajo el QR, confirma el nombre e introduce el importe. Guía completa y casos de prueba: [docs/fase-05-qr-compras.md](docs/fase-05-qr-compras.md#5-cómo-probar-el-flujo-de-compra).

## Panel de empleados

Al entrar, un empleado llega a `/panel/`: botones grandes para registrar una compra o validar un canje, el resumen de lo que ha hecho hoy, sus resultados por periodo y su perfil. Está pensado para móvil y tablet. Solo ve el nombre abreviado de cada cliente (nunca su dirección, fecha de nacimiento, teléfono, email ni saldo) y no puede cambiar roles, puntos ni configuración. Flujo completo, seguridad y pruebas: [docs/fase-08-panel-empleados.md](docs/fase-08-panel-empleados.md).

## Dashboard del propietario

Al entrar, el propietario llega a `/dashboard/`. Ve cifras reales del periodo que elija (clientes, compras registradas e importe —que **no** es la facturación total del local—, puntos emitidos y canjeados, recompensas utilizadas), busca y filtra clientes, abre su ficha completa (consulta auditada), ve de qué zonas proceden según las direcciones que declararon (país, provincia, localidad o código postal, sin direcciones completas ni geolocalización por IP), gestiona empleados, ajusta o compensa puntos, cambia estados de productos, recompensas y promociones, edita el contenido público del local y la conversión de puntos. Las fichas completas de productos, recompensas y promociones se siguen editando en el admin. Solo propietarios; los empleados nunca acceden a la dirección ni a la fecha de nacimiento. Secciones, definiciones, seguridad y pruebas: [docs/fase-09-dashboard-propietario.md](docs/fase-09-dashboard-propietario.md).

## Puntos y promociones

Cada compra registrada suma puntos (por defecto 1 punto por euro, redondeando hacia abajo) en un ledger inmutable, en la misma transacción que la compra. El propietario cambia la conversión y crea promociones (puntos fijos o multiplicador, con fechas, condiciones, límites y estado) en el admin, sección **Fidelización**. Las de cumpleaños regalan puntos fijos el día del cumpleaños desde la Fase 10. Reglas completas, anti-abuso de cumpleaños, API prevista y pruebas: [docs/fase-06-fidelizacion.md](docs/fase-06-fidelizacion.md).

## Recompensas y canjes

El propietario crea recompensas (coste en puntos, imagen, estado, fechas y unidades opcionales) en el admin, sección **Recompensas**. El cliente canjea desde `/recompensas/`: los puntos se descuentan en el ledger en la misma transacción y recibe un código de un solo uso (QR y texto) que enseña en la barra. El personal lo valida en `/panel/canjes/`; un código usado no vuelve a servir. Si el cliente cancela o el código caduca (30 días por defecto), recupera los puntos. `python manage.py expire_redemptions` caduca los vencidos. Proceso completo, validaciones, concurrencia, API prevista y pruebas: [docs/fase-07-recompensas-canjes.md](docs/fase-07-recompensas-canjes.md).

## Eventos, reservas y notificaciones

El propietario crea, edita, publica y archiva eventos en `/dashboard/eventos/` y edita los textos del inicio en `/dashboard/contenido/`. Los clientes con email verificado piden mesa o plaza en un evento; la reserva queda **pendiente** hasta que el propietario la confirma, rechaza o cancela en `/dashboard/reservas/` (cada cambio envía un email al cliente). Todo lo que envía la plataforma (verificación, recuperación de la cuenta, reservas, campañas y cumpleaños) queda en un registro con su estado real; las promociones solo llegan a quien lo ha autorizado y siempre llevan enlace de baja. El regalo de cumpleaños son puntos el mismo día (29-F → 28-F en años no bisiestos), uno por cliente y año.

**Qué requiere configuración externa:** un proveedor **SMTP** (variables `EMAIL_*`) para que salga cualquier email real; programar con cron o el Programador de tareas `process_notifications` (cada 5 min), `run_birthday_promotions` y `expire_redemptions` (diarios); los **SMS no funcionan** hasta integrar un proveedor (`SMS_BACKEND`). Detalle, tabla de qué funciona, flujos, privacidad, API prevista y pruebas: [docs/fase-10-eventos-reservas-notificaciones.md](docs/fase-10-eventos-reservas-notificaciones.md).

## API REST v1 y app móvil

La API (`/api/v1/`) expone a la futura app móvil el registro, la verificación del email, el login, la recuperación de la cuenta, el perfil, las preferencias, el cambio de email, los puntos, las compras, el QR, las recompensas, los canjes, los eventos y las reservas, además de las operaciones del personal en barra y las estadísticas y reservas del propietario. Usa los mismos servicios que la web, serializadores explícitos y tokens JWT (access de 15 min y refresh rotatorio y revocable; sin cookies). Un cliente solo accede a sus propios datos.

```powershell
python manage.py spectacular --file docs/api/openapi.yaml   # regenera el esquema OpenAPI tras cambiar la API
```

Endpoints, autenticación, auditoría y seguridad: [docs/fase-11-api-auditoria.md](docs/fase-11-api-auditoria.md). Guía para el desarrollador de la app: [docs/guia-app-flutter.md](docs/guia-app-flutter.md). Despliegue, correo y tareas programadas: [docs/despliegue.md](docs/despliegue.md).

## Estilos (Tailwind CSS)

El CSS compilado (`static/css/app.css`) está versionado, así que no hace falta nada para ejecutar el proyecto. Si cambias clases en las plantillas o en `assets/css/input.css`, recompila con la CLI standalone de Tailwind (sin Node; el script descarga la versión fijada y verifica su checksum):

```powershell
python scripts/tailwind.py build    # o "watch" mientras desarrollas
```

Paleta, componentes y datos del local (`apps/web/content.py`): [docs/fase-03-sistema-diseno-web-publica.md](docs/fase-03-sistema-diseno-web-publica.md).

## Pruebas

```powershell
python manage.py check
python manage.py test --settings=config.settings.test
```

## Estructura

Arquitectura, mapa de módulos y preparación para la app móvil: [docs/arquitectura.md](docs/arquitectura.md).

```text
config/            settings por entorno (base, dev, test, prod), urls, wsgi/asgi
apps/core/         modelos base, auditoría y limitador de intentos
apps/accounts/     usuario, roles, perfil de cliente, registro, verificación de email, preferencias, servicios, permisos, vistas de cuenta
apps/catalog/      carta: categorías, estilos, productos, carta de grifos, selectores públicos, servicios y admin
apps/loyalty/      QR personal del cliente; ledger de puntos, conversión, promociones y cumpleaños
apps/purchases/    registro de compras manuales, panel del personal y estadísticas de compras registradas
apps/rewards/      catálogo de recompensas, canjes con código de un solo uso, panel de validación y caducidad
apps/staff/        panel del personal: inicio, perfil del empleado y consulta de resultados (solo presentación)
apps/dashboard/    dashboard del propietario: secciones de gestión y estadísticas (solo presentación)
apps/events/       eventos y reservas: modelos, transiciones de estado, aforo, vistas públicas y del cliente
apps/notifications/ registro y envío de notificaciones (email, SMS opcional), campañas, baja y process_notifications
apps/api/          API REST v1: autenticación JWT, permisos, serializadores, vistas y OpenAPI (solo presentación)
apps/web/          páginas públicas, contenido del local (editable desde el dashboard) y context processor
templates/         plantilla base, componentes, páginas públicas, de cuenta, del panel del personal, de error y emails
assets/css/        fuente de Tailwind (tokens y componentes)
static/            CSS compilado, JS de mejora progresiva (menú, lector QR), jsQR incluido (vendor/) y recursos gráficos oficiales (img/brand/)
scripts/           tailwind.py (descarga verificada y compilación del CSS)
tests/             pruebas por app
docs/              plan de fases, documentación de cada fase, guías (app Flutter, despliegue) y esquema OpenAPI (api/)
requirements/      dependencias por entorno
```

## Documentación

- [Plan de fases](docs/plan-de-fases.md)
- [Arquitectura](docs/arquitectura.md): módulos, usuario y perfil de cliente, identificadores, cómo incorporar DRF.
- [Fase 0 — Fundación](docs/fase-00-fundacion.md): decisiones, modelo de datos, roles, seguridad, tests y limitaciones.
- [Fase 1 — Proyecto base](docs/fase-01-proyecto-base.md): perfil de cliente transaccional, migraciones, tests y preparación para la app.
- [Fase 2 — Registro, perfiles y verificación de email](docs/fase-02-registro-perfil-verificacion.md): campos del registro, modelo de datos, flujo de verificación, configuración del correo, preferencias de comunicación, permisos, tests y pendientes.
- [Fase 3 — Sistema de diseño y web pública](docs/fase-03-sistema-diseno-web-publica.md): paleta y contraste, componentes, páginas, formulario de registro, accesibilidad, Tailwind, tests y contenido pendiente.
- [Fase 4 — Carta y cervezas](docs/fase-04-carta.md): modelo de datos, reglas de visibilidad y disponibilidad, guía de gestión para el propietario, validación de imágenes, API prevista, tests y pendientes.
- [Fase 5 — QR personal y registro de compras](docs/fase-05-qr-compras.md): token QR, escaneo, validaciones e idempotencia, cómo probar el flujo, TPV y API previstos, tests y pendientes.
- [Fase 6 — Fidelización](docs/fase-06-fidelizacion.md): reglas de puntos y redondeo, ledger y compensaciones, promociones, cumpleaños (29-F, anti-abuso, consentimiento), concurrencia, estadísticas, API prevista, tests y pendientes.
- [Fase 7 — Recompensas y canjes](docs/fase-07-recompensas-canjes.md): proceso de canje, validaciones del servidor, código de un solo uso, estados, ledger, concurrencia, panel del personal, API prevista, tests y pendientes.
- [Fase 8 — Panel de empleados](docs/fase-08-panel-empleados.md): flujo del empleado, rutas, diseño móvil, seguridad y privacidad, endpoints previstos, tests y pendientes.
- [Fase 9 — Dashboard del propietario](docs/fase-09-dashboard-propietario.md): secciones, definiciones de las estadísticas, estadísticas geográficas, privacidad, contenido editable, endpoints previstos, tests y pendientes.
- [Fase 10 — Eventos, reservas, contenido y notificaciones](docs/fase-10-eventos-reservas-notificaciones.md): estados de las reservas, privacidad, notificaciones que funcionan y las que requieren configuración, preferencias y baja, cumpleaños, tareas programadas, API prevista, tests y pendientes.
- [Fase 11 — API, auditoría y seguridad](docs/fase-11-api-auditoria.md): resumen de la auditoría y correcciones, endpoints, estrategia de autenticación, revisión de seguridad, privacidad, tests y pendientes.
- [Guía de la app Flutter](docs/guia-app-flutter.md): autenticación, renovación y revocación de tokens, errores, paginación, idempotencia y pantallas.
- [Migración a PostgreSQL](docs/migracion-postgresql.md): auditoría de compatibilidad, correcciones, configuración en desarrollo y en el VPS, resultados de la suite y copia/restauración.
- [Auditoría previa a la Fase 12](docs/auditoria-pre-fase-12.md): hallazgos priorizados (P0-P3), correcciones, riesgo aceptado del envío de correo, pruebas y lista de comprobación antes del despliegue.
- [Despliegue](docs/despliegue.md): variables de entorno, PostgreSQL, HTTPS, estáticos y multimedia, copias de seguridad, correo, tareas programadas y logs.
- [Esquema OpenAPI](docs/api/openapi.yaml) de la API v1.
- [Documentación para la defensa del proyecto](docs/defensa_proyecto/README.md): memoria técnica y funcional, guion de la defensa oral, banco de preguntas del tribunal, mapa del código, limitaciones y diagramas Mermaid.
