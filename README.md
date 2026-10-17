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
| 4 — Carta y cervezas | **Completa** (imágenes servidas por Nginx en producción, Fase 12) |
| 5 — QR personal y registro de compras manuales | **Completa** (pendiente probar el escaneo en dispositivos físicos) |
| 6 — Fidelización: ledger de puntos, promociones y base de cumpleaños | **Completa** (pendiente confirmar la conversión por defecto) |
| 7 — Recompensas y canjes | **Completa** (pendiente confirmar el plazo de recogida) |
| 8 — Panel de empleados | **Completa** (pendiente probar en móviles y tablets físicos) |
| 9 — Dashboard del propietario y estadísticas | **Completa** (pendiente revisión visual en navegador) |
| 10 — Eventos, reservas, contenido y notificaciones | **Completa** (tareas programadas en la Fase 12; pendientes el SMTP real y el proveedor de SMS) |
| 11 — API, auditoría, seguridad y preparación para la app | **Completa** |
| Migración a PostgreSQL (endurecimiento y despliegue) | **Completa en desarrollo**: suite completa OK en PostgreSQL 17 (pendiente el VPS) |
| Auditoría previa a la Fase 12 (endurecimiento y despliegue) | **Completa**: 817 tests OK en PostgreSQL 17 y en SQLite; los pendientes de despliegue van a la Fase 12 |
| 12 — Despliegue y endurecimiento | **Completa en local**: Docker Compose (Nginx, Gunicorn, PostgreSQL 17, Redis, scheduler), copias con restic, CI. 833 tests OK. CI en verde en GitHub. **Pendiente**: VPS, DNS, certificado y SMTP real |
| Refactorización final controlada | **Completa**: helper de periodo común, estadísticas con menos consultas (resumen del dashboard 17 → 12; API de estadísticas 12 → 7) y regla del último propietario sin duplicar. Corregido además el interbloqueo previo R-1 de la regla del último propietario. **849 tests OK** en PostgreSQL 17 (local y en contenedor) y en SQLite. CI en verde en GitHub ([ejecución](https://github.com/Jav-VM/CanecaFurada/actions/runs/38776430860)) |
| 13 — Datos de demostración | **Completa**: comando `seed_demo_data` (solo desarrollo y tests) con 27 cuentas ficticias y datos de todas las áreas creados por los servicios reales; `--reset` y `--clean`. 867 tests OK en PostgreSQL 17 y en SQLite |
| 14 — Caducidad de puntos y regalo de cumpleaños | **Completa**: caducidad configurable (FIFO, sin retroactividad, aviso por email, comando `expire_points`) y regalo y aviso de cumpleaños editables en Dashboard → Configuración. 930 tests OK en PostgreSQL 17. Pendiente revisión visual |
| 15 — Web en gallego con selector gallego/castellano | **Completa**: toda la interfaz en gallego por defecto; banderas de Galicia y España en la cabecera (castellano en la web pública y el área de cliente); panel, dashboard, emails y SMS siempre en gallego; «Recompensas» se llama «Agasallos» en gallego. 953 tests OK. Pendiente la revisión nativa de las traducciones y la visual |
| 16 — Registro con código postal, localidad por CP y sexo | **Completa**: del domicilio solo el CP es obligatorio (provincia deducida, localidad por CP con datos de GeoNames), campo sexo y aviso de mayoría de edad al instante. 980 tests OK en PostgreSQL 17 y en SQLite. Pendiente la revisión visual |

Plan completo: [docs/plan-de-fases.md](docs/plan-de-fases.md).

## Requisitos

- Python 3.12+ (desarrollado con 3.14).
- PostgreSQL 14+ (probado con 17). Obligatorio en producción; sin `DATABASE_URL`, desarrollo y tests usan SQLite. Guía: [docs/migracion-postgresql.md](docs/migracion-postgresql.md).
- GNU gettext, para compilar las traducciones al gallego (Fase 15). En Windows: `winget install --id mlocati.GetText --exact`; en Debian/Ubuntu: `apt-get install gettext`.

## Instalación

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements/dev.txt
copy .env.example .env    # ajusta los valores; nunca subas .env
python manage.py migrate
python scripts/i18n.py compile   # traducciones al gallego (los .mo no se versionan)
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

## Datos de demostración

Para probar la aplicación con datos ficticios de todas las áreas (clientes, carta, compras, puntos, canjes, eventos, reservas, campañas), en una base de datos **solo para la demo**:

```powershell
$env:DATABASE_URL = "sqlite:///pruebas_dev/demo.sqlite3"   # o una BD PostgreSQL aparte
python manage.py migrate
python manage.py seed_demo_data                # --reset recarga, --clean borra solo lo de demo
python manage.py runserver 8001
```

**Para volver a la versión original:**
1. Detén el servidor (`Ctrl+C`).
2. Opcional: ejecuta `python manage.py seed_demo_data --clean --noinput`, que borra la demo y sus imágenes de `media/`.
3. Quita la variable con `Remove-Item Env:DATABASE_URL` (o cierra la terminal).
4. Arranca con `python manage.py runserver`. Vuelve a usarse la base del `.env`.

Todas las órdenes para probar sin afectar al proyecto (bases de pruebas, tareas programadas, Mailpit, tests, Docker y limpieza) están en [pruebas_dev/pruebas.md](pruebas_dev/pruebas.md).

Solo funciona con `config.settings.dev` (`DEBUG=True`) y en los tests: en producción el comando no existe. Se niega a cargar si la base de datos tiene datos propios. Cuentas por rol (contraseña **solo de desarrollo**), escenarios y limitaciones: [docs/fase-13-datos-demo.md](docs/fase-13-datos-demo.md).

## Gestionar la carta

El propietario crea estilos, categorías y productos en el admin, publica, archiva o marca como agotado con las acciones de la lista y sube la imagen de la carta de grifos. Nada se borra: los productos se archivan. En producción, Nginx sirve las imágenes subidas desde el volumen `media` (Fase 12). Guía paso a paso: [docs/fase-04-carta.md](docs/fase-04-carta.md#4-gestión-de-la-carta-guía-para-el-propietario).

En desarrollo los emails (verificación, recuperación de contraseña…) se imprimen en la consola de `runserver`. En Windows, si aparece `UnicodeEncodeError` al enviar un email, arranca con `$env:PYTHONUTF8=1`. Configuración del correo y de producción: [docs/fase-02-registro-perfil-verificacion.md](docs/fase-02-registro-perfil-verificacion.md#6-configuración-del-correo-y-variables-de-entorno).

## Registro de clientes

El registro pide nombre, apellidos, fecha de nacimiento (18 años o más), sexo (Hombre, Mujer o Prefiero no decirlo), país, código postal y localidad. De la dirección solo el código postal es obligatorio: en España la provincia se deduce del CP y la localidad se elige entre las del CP (se marca sola si solo hay una; datos de GeoNames, CC BY 4.0). La calle se puede añadir después en el perfil. Para actualizar los datos de localidades: `python scripts/postal_codes.py build`. Detalle, reglas y pruebas: [docs/fase-16-registro-cp-sexo.md](docs/fase-16-registro-cp-sexo.md).

## Probar el registro de compras

Crea un empleado desde el admin y un cliente con el registro público; verifica su email con el enlace que aparece en la consola. El cliente abre *Mi código QR* y el empleado, en *Registrar compra*, lo escanea con la cámara (solo en `localhost` o HTTPS) o teclea el código que aparece bajo el QR, confirma el nombre e introduce el importe. Guía completa y casos de prueba: [docs/fase-05-qr-compras.md](docs/fase-05-qr-compras.md#5-cómo-probar-el-flujo-de-compra).

## Panel de empleados

Al entrar, un empleado llega a `/panel/`: botones grandes para registrar una compra o validar un canje, el resumen de lo que ha hecho hoy, sus resultados por periodo y su perfil. Está pensado para móvil y tablet. Solo ve el nombre abreviado de cada cliente (nunca su dirección, fecha de nacimiento, teléfono, email ni saldo) y no puede cambiar roles, puntos ni configuración. Flujo completo, seguridad y pruebas: [docs/fase-08-panel-empleados.md](docs/fase-08-panel-empleados.md).

## Dashboard del propietario

Al entrar, el propietario llega a `/dashboard/`. Ve cifras reales del periodo que elija (clientes, compras registradas e importe —que **no** es la facturación total del local—, puntos emitidos y canjeados, recompensas utilizadas), busca y filtra clientes, abre su ficha completa (consulta auditada), ve de qué zonas proceden según las direcciones que declararon (país, provincia, localidad o código postal, sin direcciones completas ni geolocalización por IP), gestiona empleados, ajusta o compensa puntos, cambia estados de productos, recompensas y promociones, edita el contenido público del local, la conversión de puntos y, en **Configuración** (Fase 14), la caducidad de los puntos y el regalo y aviso de cumpleaños, y si las reservas online están activadas (Fase 17; desactivadas, los botones de reserva llevan a Contacto para reservar por teléfono: [docs/fase-17-reservas-online.md](docs/fase-17-reservas-online.md)). Todos los listados se pueden ordenar con las flechas ↑/↓ de cada columna (Fase 18: [docs/fase-18-ordenacion-listados.md](docs/fase-18-ordenacion-listados.md)). En Clientes se filtra a quien no ha gastado nada y se eligen clientes en la columna «Envío» para mandarles una campaña, con imagen y puntos de regalo si se quiere (Fase 19: [docs/fase-19-campanas-seleccion.md](docs/fase-19-campanas-seleccion.md)). En Contenido también ordena u oculta las secciones de Inicio y La cervecería (Fase 20: [docs/fase-20-orden-secciones.md](docs/fase-20-orden-secciones.md)), edita su contenido y publica artículos con imágenes en La cervecería (Fase 21: [docs/fase-21-contenido-secciones.md](docs/fase-21-contenido-secciones.md)); lo mismo, solo con textos, en Carta, Recompensas, Eventos y Contacto (Fase 22: [docs/fase-22-secciones-otras-paginas.md](docs/fase-22-secciones-otras-paginas.md)). Desde la Fase 23 también publica artículos con imágenes en Inicio y Eventos ([docs/fase-23-articulos-y-ajustes-visuales.md](docs/fase-23-articulos-y-ajustes-visuales.md)). Las fichas completas de productos, recompensas y promociones se siguen editando en el admin. Solo propietarios; los empleados nunca acceden a la dirección ni a la fecha de nacimiento. Secciones, definiciones, seguridad y pruebas: [docs/fase-09-dashboard-propietario.md](docs/fase-09-dashboard-propietario.md).

## Puntos y promociones

Cada compra registrada suma puntos (por defecto 1 punto por euro, redondeando hacia abajo) en un ledger inmutable, en la misma transacción que la compra. El propietario cambia la conversión y crea promociones (puntos fijos o multiplicador, con fechas, condiciones, límites y estado) en el admin, sección **Fidelización**. Las de cumpleaños regalan puntos fijos el día del cumpleaños desde la Fase 10. Desde la Fase 14 el propietario puede hacer que los puntos caduquen (los más antiguos primero, con aviso por email) y editar los puntos y el texto del regalo de cumpleaños en el dashboard: [docs/fase-14-caducidad-puntos-cumpleanos.md](docs/fase-14-caducidad-puntos-cumpleanos.md). Reglas completas, anti-abuso de cumpleaños, API prevista y pruebas: [docs/fase-06-fidelizacion.md](docs/fase-06-fidelizacion.md).

## Recompensas y canjes

El propietario crea recompensas (coste en puntos, imagen, estado, fechas y unidades opcionales) en el admin, sección **Recompensas**. El cliente canjea desde `/recompensas/`: los puntos se descuentan en el ledger en la misma transacción y recibe un código de un solo uso (QR y texto) que enseña en la barra. El personal lo valida en `/panel/canjes/`; un código usado no vuelve a servir. Si el cliente cancela o el código caduca (30 días por defecto), recupera los puntos. `python manage.py expire_redemptions` caduca los vencidos. Proceso completo, validaciones, concurrencia, API prevista y pruebas: [docs/fase-07-recompensas-canjes.md](docs/fase-07-recompensas-canjes.md).

## Eventos, reservas y notificaciones

El propietario crea, edita, publica y archiva eventos en `/dashboard/eventos/` (la lista se ajusta al ancho de la pantalla, sin desplazamiento lateral) y edita los textos del inicio en `/dashboard/contenido/`. Los clientes con email verificado piden mesa o plaza en un evento; la reserva queda **pendiente** hasta que el propietario la confirma, rechaza o cancela en `/dashboard/reservas/` (cada cambio envía un email al cliente). Todo lo que envía la plataforma (verificación, recuperación de la cuenta, reservas, campañas y cumpleaños) queda en un registro con su estado real; las promociones solo llegan a quien lo ha autorizado y siempre llevan enlace de baja. El regalo de cumpleaños son puntos el mismo día (29-F → 28-F en años no bisiestos), uno por cliente y año.

**Qué requiere configuración externa:** un proveedor **SMTP** (variables `EMAIL_*`) para que salga cualquier email real. Las tareas `process_notifications` (cada 5 min), `run_birthday_promotions`, `expire_redemptions` y `expire_points` (diarias) ya las programa el servicio `scheduler` de Docker Compose (Fase 12); los **SMS no funcionan** hasta integrar un proveedor (`SMS_BACKEND`). Detalle, tabla de qué funciona, flujos, privacidad, API prevista y pruebas: [docs/fase-10-eventos-reservas-notificaciones.md](docs/fase-10-eventos-reservas-notificaciones.md).

## API REST v1 y app móvil

La API (`/api/v1/`) expone a la futura app móvil el registro, la verificación del email, el login, la recuperación de la cuenta, el perfil, las preferencias, el cambio de email, los puntos, las compras, el QR, las recompensas, los canjes, los eventos y las reservas, además de las operaciones del personal en barra y las estadísticas y reservas del propietario. Usa los mismos servicios que la web, serializadores explícitos y tokens JWT (access de 15 min y refresh rotatorio y revocable; sin cookies). Un cliente solo accede a sus propios datos.

```powershell
python manage.py spectacular --file docs/api/openapi.yaml   # regenera el esquema OpenAPI tras cambiar la API
```

Endpoints, autenticación, auditoría y seguridad: [docs/fase-11-api-auditoria.md](docs/fase-11-api-auditoria.md). Guía para el desarrollador de la app: [docs/guia-app-flutter.md](docs/guia-app-flutter.md). Despliegue, correo y tareas programadas: [docs/despliegue.md](docs/despliegue.md).

## Despliegue (Docker Compose)

Producción en un VPS: `compose.yaml` con Nginx (TLS), Gunicorn y Django, PostgreSQL 17, Redis, tareas programadas y certbot. Las variables van en `.env.prod` (plantilla [.env.prod.example](.env.prod.example), nunca en Git).

```bash
deploy/scripts/deploy.sh --first     # primer despliegue; después: deploy.sh / deploy.sh rollback
deploy/scripts/backup.sh run         # copia cifrada con restic (BD + media)
deploy/scripts/restore.sh check      # restauración de prueba
```

Pila completa en local, con la imagen de producción, Mailpit (http://localhost:8025) y https://localhost:8443. Requiere Docker; en Windows vale Docker Engine dentro de WSL:

```bash
docker compose -f compose.yaml -f compose.dev.yaml --env-file deploy/dev.env build web nginx
docker compose -f compose.yaml -f compose.dev.yaml --env-file deploy/dev.env up -d --wait db redis mailpit
docker compose -f compose.yaml -f compose.dev.yaml --env-file deploy/dev.env run --rm migrate
docker compose -f compose.yaml -f compose.dev.yaml --env-file deploy/dev.env up -d --wait
docker compose -f compose.yaml -f compose.dev.yaml --env-file deploy/dev.env --profile test run --rm tests   # suite en PostgreSQL
```

Guía operativa: [docs/despliegue.md](docs/despliegue.md). Diseño, procedimientos (primer despliegue, actualización, rollback, restauración, rotación de secretos), endurecimiento del VPS y resultados: [docs/fase-12-despliegue.md](docs/fase-12-despliegue.md).

## Estilos (Tailwind CSS)

El CSS compilado (`static/css/app.css`) está versionado, así que no hace falta nada para ejecutar el proyecto. Si cambias clases en las plantillas o en `assets/css/input.css`, recompila con la CLI standalone de Tailwind (sin Node; el script descarga la versión fijada y verifica su checksum):

```powershell
python scripts/tailwind.py build    # o "watch" mientras desarrollas
```

Paleta, componentes y datos del local (`apps/web/content.py`): [docs/fase-03-sistema-diseno-web-publica.md](docs/fase-03-sistema-diseno-web-publica.md).

## Pruebas

```powershell
python manage.py check
python manage.py test --settings=config.settings.test                 # SQLite o la DATABASE_URL del .env
```

Con `DATABASE_URL` de PostgreSQL se ejecutan también los tests de concurrencia (`--parallel 1`); con SQLite en memoria se omiten. El CI (`.github/workflows/ci.yml`) ejecuta en cada push y pull request:
- `check` y `makemigrations --check`;
- la validación del esquema OpenAPI;
- la suite contra PostgreSQL 17 sin tests omitidos;
- `check --deploy`;
- el build de la imagen, el arranque de la pila y una copia con restauración.

## Estructura

Arquitectura, mapa de módulos y preparación para la app móvil: [docs/arquitectura.md](docs/arquitectura.md).

```text
config/            settings por entorno (base, dev, test, prod), urls, wsgi/asgi
apps/core/         modelos base, auditoría, limitador de intentos y utilidades de consulta (periodo `[start, end)`)
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
apps/demo/         datos de demostración (solo desarrollo y tests): comando seed_demo_data, sin modelos
templates/         plantilla base, componentes, páginas públicas, de cuenta, del panel del personal, de error y emails
assets/css/        fuente de Tailwind (tokens y componentes)
static/            CSS compilado, JS de mejora progresiva (menú, lector QR), jsQR incluido (vendor/) y recursos gráficos oficiales (img/brand/)
scripts/           tailwind.py (descarga verificada y compilación del CSS)
tests/             pruebas por app
pruebas_dev/       guía de pruebas de desarrollo (pruebas.md); sus *.sqlite3 no se versionan
docs/              plan de fases, documentación de cada fase, guías (app Flutter, despliegue) y esquema OpenAPI (api/)
requirements/      dependencias por entorno
deploy/            Gunicorn, Nginx, crontab, rol de PostgreSQL, variables ficticias de la pila local y scripts (deploy, backup, restore)
Dockerfile, compose.yaml, compose.dev.yaml   imagen y pilas de producción y local (Fase 12)
.github/workflows/ CI (GitHub Actions)
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
- [Fase 12 — Despliegue y endurecimiento](docs/fase-12-despliegue.md): arquitectura Docker Compose, decisiones, procedimientos (primer despliegue, actualización, rollback, restauración, rotación de secretos), copias, CI, endurecimiento del VPS, pruebas y pendientes.
- [Refactorización final](docs/refactorizacion-final.md): línea base, diagnóstico, cambios por grupos, mediciones de consultas, pruebas antes y después, corrección del interbloqueo R-1 y lo que se decidió no refactorizar.
- [Fase 13 — Datos de demostración](docs/fase-13-datos-demo.md): comando `seed_demo_data`, protecciones frente a producción, cuentas por rol, escenarios, limpieza, tests y limitaciones.
- [Fase 14 — Caducidad de puntos y regalo de cumpleaños](docs/fase-14-caducidad-puntos-cumpleanos.md): política versionada sin retroactividad, cálculo FIFO, aviso previo, comando `expire_points`, textos editables del aviso de cumpleaños, seguridad, tests y pendientes.
- [Fase 15 — Web en gallego](docs/fase-15-idioma-gallego.md): idioma por zonas, selector de banderas, emails en gallego, API, cómo añadir y traducir textos (`scripts/i18n.py`), seguridad, tests y pendientes.
- [Fase 16 — Registro con código postal y sexo](docs/fase-16-registro-cp-sexo.md): solo CP obligatorio, provincia deducida, localidad por CP (GeoNames), campo sexo, aviso de mayoría de edad, endpoints de localidades, migración, tests y pendientes.
- [Fase 17 — Interruptor de reservas online](docs/fase-17-reservas-online.md): activar o desactivar las reservas desde Configuración; desactivadas, los enlaces llevan a Contacto para reservar por teléfono; bloqueo en web, servicio y API, tests y pendientes.
- [Fase 18 — Ordenar los listados del dashboard](docs/fase-18-ordenacion-listados.md): flechas ↑/↓ en cada columna, lista blanca de columnas, filtros conservados, listados y columnas ordenables, tests y pendientes.
- [Fase 19 — Campañas a clientes seleccionados](docs/fase-19-campanas-seleccion.md): filtro «sin gasto», columna «Envío» y selección, formulario único de campaña con imagen y puntos de regalo con o sin caducidad, consentimiento, seguridad, tests y pendientes.
- [Fase 20 — Orden de las secciones](docs/fase-20-orden-secciones.md): subir, bajar u ocultar las secciones de Inicio y La cervecería desde Contenido, lista blanca, seguridad, tests y pendientes.
- [Fase 21 — Contenido de las secciones y artículos](docs/fase-21-contenido-secciones.md): editar textos de Inicio, textos e imágenes de La cervecería, artículos con galería, seguridad, tests y pendientes.
- [Fase 22 — Secciones de Carta, Agasallos, Eventos y Contacto](docs/fase-22-secciones-otras-paginas.md): ordenar, ocultar y editar los textos de esas cuatro páginas, textos que dependen del estado, tests y pendientes.
- [Fase 23 — Artículos en Inicio y Eventos, y ajustes visuales](docs/fase-23-articulos-y-ajustes-visuales.md): artículos con imágenes en Inicio y Eventos, migración de la restricción, rutas, seguridad, tests; resumen de los ajustes de Contacto, Carta y el carrusel de A cervexaría.
- [Pruebas de desarrollo](pruebas_dev/pruebas.md): órdenes para probar con bases de datos aparte, tareas programadas, Mailpit, tests, Docker local, volver a la versión original y limpiar.
- [Despliegue](docs/despliegue.md): guía operativa con variables, órdenes habituales, HTTPS, estáticos y multimedia, copias, correo, tareas programadas, logs y lista de comprobación.
- [Esquema OpenAPI](docs/api/openapi.yaml) de la API v1.
- [Documentación para la defensa del proyecto](docs/defensa_proyecto/README.md): memoria técnica y funcional, guion de la defensa oral, banco de preguntas del tribunal, mapa del código, limitaciones y diagramas Mermaid.
