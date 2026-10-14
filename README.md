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
| 4–12 | Pendientes |

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
- Web pública: Inicio (`/`), La cervecería (`/la-cerveceria/`), Carta (`/carta/`), Recompensas (`/recompensas/`), Eventos (`/eventos/`) y Contacto (`/contacto/`). Carta, Recompensas y Eventos muestran un estado vacío hasta sus fases.
- Cuentas en `/cuenta/`: registro (`/cuenta/registro/`), entrar, salir, perfil, preferencias, cambio de email y de contraseña, recuperación de contraseña y verificación de email.
- Admin técnico en `/<DJANGO_ADMIN_URL>` (por defecto `/admin/`), solo para propietarios.

En desarrollo los emails (verificación, recuperación de contraseña…) se imprimen en la consola de `runserver`. En Windows, si aparece `UnicodeEncodeError` al enviar un email, arranca con `$env:PYTHONUTF8=1`. Configuración del correo y de producción: [docs/fase-02-registro-perfil-verificacion.md](docs/fase-02-registro-perfil-verificacion.md#6-configuración-del-correo-y-variables-de-entorno).

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
apps/web/          páginas públicas, contenido del local y context processor
templates/         plantilla base, componentes, páginas públicas, de cuenta, de error y emails
assets/css/        fuente de Tailwind (tokens y componentes)
static/            CSS compilado, JS de mejora progresiva y recursos gráficos oficiales (img/brand/)
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
