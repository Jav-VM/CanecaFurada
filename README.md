# Caneca Furada — Plataforma web

Plataforma de la cervecería artesanal Caneca Furada (A Coruña): web pública, programa de fidelización, panel de empleados, dashboard del propietario y backend preparado para una futura app móvil.

Monolito modular **Django 5.2 + PostgreSQL**, con Django Templates en la web y una API REST prevista para la app móvil.

## Estado

| Fase | Estado |
|---|---|
| 0 — Fundación del proyecto | **Completa** |
| 1 — Proyecto base: perfil de cliente, módulos y preparación para la app | **Completa** |
| 2 — Autenticación, registro, perfiles, verificación de email y permisos | **Completa** (pendiente validar en PostgreSQL y con SMTP real) |
| 3 — Sistema de diseño y web pública | **Completa** (contenidos del local pendientes de aportar por el propietario) |
| 4 — Carta y cervezas | **Completa** (pendiente almacenamiento de imágenes en producción y validar en PostgreSQL) |
| 5 — QR personal y registro de compras manuales | **Completa** (pendiente probar el escaneo en dispositivos físicos y la concurrencia en PostgreSQL) |
| 6 — Fidelización: ledger de puntos, promociones y base de cumpleaños | **Completa** (pendiente validar la concurrencia en PostgreSQL y confirmar la conversión por defecto) |
| 7 — Recompensas y canjes | **Completa** (pendiente validar la concurrencia en PostgreSQL y confirmar el plazo de recogida) |
| 8–12 | Pendientes |

Plan completo: [docs/plan-de-fases.md](docs/plan-de-fases.md).

## Requisitos

- Python 3.12+ (desarrollado con 3.14).
- PostgreSQL (recomendado; sin `DATABASE_URL` se usa SQLite solo para desarrollo).

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
- Web pública: Inicio (`/`), La cervecería (`/la-cerveceria/`), Carta (`/carta/`), Recompensas (`/recompensas/`), Eventos (`/eventos/`) y Contacto (`/contacto/`). Recompensas muestra el catálogo real; Eventos, un estado vacío hasta su fase.
- QR personal del cliente (email verificado) en `/cuenta/mi-qr/`, sus puntos (saldo, movimientos y compras) en `/cuenta/puntos/` y sus canjes en `/cuenta/canjes/`.
- Panel del personal (empleados y propietarios) para registrar compras en `/panel/compras/` y validar canjes en `/panel/canjes/`.
- Cuentas en `/cuenta/`: registro (`/cuenta/registro/`), entrar, salir, perfil, preferencias, cambio de email y de contraseña, recuperación de contraseña y verificación de email.
- Admin técnico en `/<DJANGO_ADMIN_URL>` (por defecto `/admin/`), solo para propietarios. Desde ahí se gestiona la carta (sección **Carta**).

## Gestionar la carta

El propietario crea estilos, categorías y productos en el admin, publica, archiva o marca como agotado con las acciones de la lista y sube la imagen de la carta de grifos. Nada se borra: los productos se archivan. Las imágenes subidas solo se sirven en desarrollo hasta la Fase 12. Guía paso a paso: [docs/fase-04-carta.md](docs/fase-04-carta.md#4-gestión-de-la-carta-guía-para-el-propietario).

En desarrollo los emails (verificación, recuperación de contraseña…) se imprimen en la consola de `runserver`. En Windows, si aparece `UnicodeEncodeError` al enviar un email, arranca con `$env:PYTHONUTF8=1`. Configuración del correo y de producción: [docs/fase-02-registro-perfil-verificacion.md](docs/fase-02-registro-perfil-verificacion.md#6-configuración-del-correo-y-variables-de-entorno).

## Probar el registro de compras

Crea un empleado desde el admin y un cliente con el registro público; verifica su email con el enlace que aparece en la consola. El cliente abre *Mi código QR* y el empleado, en *Registrar compra*, lo escanea con la cámara (solo en `localhost` o HTTPS) o teclea el código que aparece bajo el QR, confirma el nombre e introduce el importe. Guía completa y casos de prueba: [docs/fase-05-qr-compras.md](docs/fase-05-qr-compras.md#5-cómo-probar-el-flujo-de-compra).

## Puntos y promociones

Cada compra registrada suma puntos (por defecto 1 punto por euro, redondeando hacia abajo) en un ledger inmutable, en la misma transacción que la compra. El propietario cambia la conversión y crea promociones (puntos fijos o multiplicador, con fechas, condiciones, límites y estado, incluidas las de cumpleaños) en el admin, sección **Fidelización**. Esta fase no envía promociones. Reglas completas, anti-abuso de cumpleaños, API prevista y pruebas: [docs/fase-06-fidelizacion.md](docs/fase-06-fidelizacion.md).

## Recompensas y canjes

El propietario crea recompensas (coste en puntos, imagen, estado, fechas y unidades opcionales) en el admin, sección **Recompensas**. El cliente canjea desde `/recompensas/`: los puntos se descuentan en el ledger en la misma transacción y recibe un código de un solo uso (QR y texto) que enseña en la barra. El personal lo valida en `/panel/canjes/`; un código usado no vuelve a servir. Si el cliente cancela o el código caduca (30 días por defecto), recupera los puntos. `python manage.py expire_redemptions` caduca los vencidos. Proceso completo, validaciones, concurrencia, API prevista y pruebas: [docs/fase-07-recompensas-canjes.md](docs/fase-07-recompensas-canjes.md).

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
apps/web/          páginas públicas, contenido del local y context processor
templates/         plantilla base, componentes, páginas públicas, de cuenta, de error y emails
assets/css/        fuente de Tailwind (tokens y componentes)
static/            CSS compilado, JS de mejora progresiva (menú, lector QR), jsQR incluido (vendor/) y recursos gráficos oficiales (img/brand/)
scripts/           tailwind.py (descarga verificada y compilación del CSS)
tests/             pruebas por app
docs/              plan de fases y documentación de cada fase
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
