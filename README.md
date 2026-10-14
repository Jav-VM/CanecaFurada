# Caneca Furada — Plataforma web

Plataforma de la cervecería artesanal Caneca Furada (A Coruña): web pública, programa de fidelización, panel de empleados, dashboard del propietario y backend preparado para una futura app móvil.

Monolito modular **Django 5.2 + PostgreSQL**, con Django Templates en la web y una API REST prevista para la app móvil.

## Estado

| Fase | Estado |
|---|---|
| 0 — Fundación del proyecto | **Completa** |
| 1–11 | Pendientes |

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

Por ahora solo existe el admin técnico en `/<DJANGO_ADMIN_URL>` (por defecto `/admin/`), accesible únicamente para propietarios.

## Pruebas

```powershell
python manage.py check
python manage.py test --settings=config.settings.test
```

## Estructura

```text
config/            settings por entorno (base, dev, test, prod), urls, wsgi/asgi
apps/core/         modelos base y auditoría
apps/accounts/     usuario personalizado, roles, servicios, permisos, create_owner
static/img/brand/  recursos gráficos oficiales
tests/             pruebas por app
docs/              plan de fases y documentación de cada fase
requirements/      dependencias por entorno
```

## Documentación

- [Plan de fases](docs/plan-de-fases.md)
- [Fase 0 — Fundación](docs/fase-00-fundacion.md): decisiones, modelo de datos, roles, seguridad, tests y limitaciones.
