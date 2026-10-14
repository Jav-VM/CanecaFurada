# Fase 0 — Fundación del proyecto

**Estado:** Completa (con las limitaciones indicadas al final).
**Fecha:** 2026-10-14.

## 1. Objetivo, alcance y exclusiones

**Objetivo:** dejar una base técnica segura sobre la que implementar el resto de fases sin rehacer migraciones de usuarios.

**Incluye**
- Proyecto Django modular (`config/` + `apps/`), configuración por entorno y variables de entorno.
- Base de datos configurable con `DATABASE_URL` (PostgreSQL como objetivo).
- Modelo de usuario personalizado con roles `OWNER`, `EMPLOYEE`, `CUSTOMER`, creado **antes de la primera migración**.
- Servicios de cuentas y roles con auditoría.
- Permisos por rol reutilizables (decorador y mixin).
- Admin técnico restringido al propietario.
- Comando `create_owner` para el primer propietario.
- Recursos de marca movidos a `static/img/brand/`.
- Tests, plan de fases y documentación.

**Excluye** (fases posteriores, ver [plan-de-fases.md](plan-de-fases.md)): web pública y Tailwind, registro público, verificación de email, perfil de cliente (dirección, fecha de nacimiento, teléfono), preferencias de comunicación, carta, fidelización, compras, recompensas, reservas, eventos, dashboard, notificaciones y API.

## 2. Decisiones técnicas

| Decisión | Motivo |
|---|---|
| Django 5.2 LTS (`>=5.2.8,<5.3`) | Soporte largo; 5.2.8+ es compatible con Python 3.14 (el del `.venv`). |
| `manage.py` en la raíz del repositorio | El repositorio es el proyecto; evita un nivel de carpetas extra. |
| `django-environ` | Una sola dependencia para `.env` y `DATABASE_URL`. |
| SQLite como alternativa si falta `DATABASE_URL` | Decisión del usuario: en el equipo no hay PostgreSQL. Producción y la validación final deben usar PostgreSQL. |
| `User(AbstractBaseUser, PermissionsMixin)` sin `username` | El email es la credencial de acceso; no hace falta un nombre de usuario. |
| PK interna `BigAutoField` + `public_id` UUID | La PK no se expone; `public_id` es el identificador estable para URLs, auditoría, API y app móvil. El email no se usa como identificador interno. |
| Política de email: `strip()` + minúsculas | Evita cuentas duplicadas por mayúsculas. No se eliminan puntos ni `+etiqueta` porque dependen del proveedor. Se aplica en `save()`, `clean()`, el manager y el login (`get_by_natural_key`). |
| Restricciones en BD | `UniqueConstraint(Lower(email))`, rol dentro de los valores válidos y `is_staff`/`is_superuser` solo con rol `OWNER`. Protegen la invariante aunque se use `update()` o SQL. |
| `is_staff`/`is_superuser` derivados del rol | Solo el propietario accede al admin técnico mientras no exista el dashboard (Fase 8). Los empleados no tienen acceso al admin. |
| Datos del cliente fuera de `User` | Dirección, fecha de nacimiento, teléfono y preferencias irán en un `CustomerProfile` 1:1 (Fase 2): empleados y propietario no necesitan esos campos y se minimiza la exposición. |
| Servicios como única vía para crear usuarios y cambiar roles | Web, admin, comandos y la futura API reutilizan la misma lógica, los mismos permisos y la misma auditoría. |
| Rol del actor comprobado en BD | `_ensure_active_owner` consulta la base de datos; un rol manipulado en memoria no concede permisos. |
| Protección del último propietario | `change_role` bloquea las filas de propietarios (`select_for_update`) y no permite quedarse sin propietarios activos; el admin tampoco permite desactivar al último. |
| `AuditEvent` en `apps/core` | Registro mínimo de altas y cambios de rol. Identifica el objetivo por `public_id` y no guarda datos personales en `metadata`. Es de solo lectura en el admin. |
| Sin borrado de usuarios en el admin | Se desactivan cuentas para conservar el historial (compras y puntos en fases futuras). |
| Ruta del admin configurable (`DJANGO_ADMIN_URL`) | Reduce el ruido de bots sobre `/admin/`; no sustituye la autenticación. |
| `SECURE_HSTS_PRELOAD` desactivado por defecto | La inclusión en la lista de precarga es difícil de revertir; se activa conscientemente al desplegar. Por eso `check --deploy` muestra el aviso `security.W021`. |
| Recursos de marca en `static/img/brand/` | `media/` está ignorada por Git y se reserva para subidas; los recursos oficiales son estáticos versionados. |

## 3. Archivos creados o modificados

- **Configuración:** `manage.py`, `config/settings/{base,dev,test,prod}.py`, `config/urls.py`, `config/wsgi.py`, `config/asgi.py`, `.env.example`.
- **Dependencias:** `requirements/{base,dev,prod}.txt`; `requirements.txt` ahora apunta a `requirements/base.txt`.
- **`apps/core`:** `models.py` (`TimeStampedModel`, `AuditEvent`), `services.py` (`record_audit_event`), `admin.py`, `migrations/0001_initial.py`.
- **`apps/accounts`:** `models.py` (`User`), `managers.py` (`UserManager`), `normalization.py`, `services.py`, `permissions.py`, `admin.py`, `management/commands/create_owner.py`, `migrations/0001_initial.py`.
- **Recursos:** `media/*.jpeg` → `static/img/brand/` (`git mv`).
- **`.gitignore`:** estaba guardado en UTF-16, por lo que Git no aplicaba ninguna regla (ni `.env`, ni `db.sqlite3`, ni `media/`). Se ha convertido a UTF-8 sin cambiar su contenido; ahora las reglas se aplican (verificado con `git check-ignore`).
- **Tests:** `tests/accounts/` y `tests/core/`.
- **Documentación:** `docs/plan-de-fases.md`, este documento, `README.md`.

No se han creado rutas públicas ni plantillas: la única ruta es el admin.

## 4. Modelo de datos

### `accounts.User`
| Campo | Tipo | Notas |
|---|---|---|
| `id` | BigAutoField | Interno, no se expone. |
| `public_id` | UUID único, no editable | Identificador estable externo. |
| `email` | Email (254), único | Normalizado; único también sin distinguir mayúsculas en BD. |
| `first_name`, `last_name` | Char (150) | Obligatorios. |
| `role` | `OWNER` / `EMPLOYEE` / `CUSTOMER` | Por defecto `CUSTOMER`. Restricción CHECK. |
| `is_active` | Bool | Desactivación en lugar de borrado. |
| `is_staff`, `is_superuser` | Bool | Solo `True` si `role=OWNER` (CHECK). |
| `password`, `last_login`, `date_joined` | | Estándar de Django. |

### `core.AuditEvent`
`actor` (FK nullable, `SET_NULL`), `action` (`OWNER_CREATED`, `EMPLOYEE_CREATED`, `CUSTOMER_CREATED`, `ROLE_CHANGED`), `target_public_id`, `metadata` (JSON técnico, p. ej. `{"from": "CUSTOMER", "to": "EMPLOYEE"}`), `created_at`.

### Migraciones
`accounts/0001_initial` y `core/0001_initial`, generadas y revisadas: solo crean las tablas y restricciones descritas. `makemigrations --check` no detecta cambios pendientes.

## 5. Servicios y permisos

`apps/accounts/services.py`:
- `create_customer(email, first_name, last_name, password)`: no acepta `role`; siempre crea `CUSTOMER`. La usará el registro público de la Fase 2.
- `create_employee(actor, ...)`: solo propietario activo.
- `create_owner(..., actor=None)`: sin actor solo si no existe ningún propietario; con actor, este debe ser propietario.
- `create_user_by_owner(actor, role, ...)`: altas desde el admin.
- `change_role(actor, user, new_role)`: solo propietario; ajusta `is_staff`/`is_superuser`; protege al último propietario activo; audita.

Todas validan el modelo (`full_clean`), la contraseña con los validadores de Django (mínimo 10 caracteres, no común, no numérica, no parecida a los datos del usuario), se ejecutan en transacción y convierten una colisión de email concurrente en un `ValidationError`.

`apps/accounts/permissions.py`: `has_role`, `is_owner`, `is_staff_member`, decorador `role_required(*roles)` y `RoleRequiredMixin` (sin sesión → redirección al login; rol no permitido → 403). Un usuario inactivo no tiene ningún rol a efectos de permisos.

## 6. Configuración y variables de entorno

Ver [`.env.example`](../.env.example). Variables nuevas:

| Variable | Uso | Por defecto |
|---|---|---|
| `DJANGO_SECRET_KEY` | Clave secreta | Obligatoria en producción |
| `DJANGO_DEBUG` | Modo depuración | `True` en dev, `False` en prod |
| `DJANGO_ALLOWED_HOSTS` | Hosts permitidos | Obligatoria en producción |
| `DJANGO_ADMIN_URL` | Ruta del admin | `admin/` |
| `DJANGO_LOG_LEVEL` | Nivel de log | `INFO` |
| `DATABASE_URL` | Conexión a BD | SQLite local |
| `DATABASE_CONN_MAX_AGE` | Conexiones persistentes | `0` |
| `DEFAULT_FROM_EMAIL` | Remitente | `no-reply@example.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Orígenes CSRF (prod) | vacío |
| `DJANGO_SECURE_SSL_REDIRECT` | Redirección HTTPS (prod) | `True` |
| `DJANGO_SECURE_HSTS_SECONDS` / `_INCLUDE_SUBDOMAINS` / `_PRELOAD` | HSTS (prod) | 1 año / `True` / `False` |
| `DJANGO_BEHIND_TLS_PROXY` | Confiar en `X-Forwarded-Proto` (prod) | `False` |
| `CANECA_OWNER_*` | Solo para `create_owner --noinput` | — |

Módulos de settings: `config.settings.dev` (por defecto en `manage.py`), `config.settings.test`, `config.settings.prod` (por defecto en `wsgi.py`/`asgi.py`).

## 7. Instrucciones de uso

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements/dev.txt
copy .env.example .env        # y ajusta los valores
python manage.py migrate
python manage.py create_owner # pide email, nombre, apellidos y contraseña (oculta)
python manage.py runserver    # admin en http://127.0.0.1:8000/<DJANGO_ADMIN_URL>
```

### Creación del primer propietario
1. Ejecutar `python manage.py create_owner` en el servidor, con acceso administrativo.
2. Introducir los datos; la contraseña se pide dos veces con entrada oculta y nunca como argumento.
3. El comando falla si ya existe un propietario, si el email ya está registrado o si la contraseña no cumple los validadores.
4. Queda un `AuditEvent` `OWNER_CREATED` sin actor.
5. Despliegues automatizados: `python manage.py create_owner --noinput` con las variables `CANECA_OWNER_*` definidas solo durante esa ejecución.

Propietarios adicionales y empleados: los crea un propietario desde el admin (alta) o promocionando a un usuario existente con las acciones de rol del listado de usuarios.

`createsuperuser` sigue funcionando y siempre crea un `OWNER`, pero no deja auditoría ni comprueba si ya hay propietario: el procedimiento documentado es `create_owner`.

## 8. Tests

- `tests/accounts/test_models.py`: normalización de email, unicidad sin distinguir mayúsculas (también con `update()`), login sin distinguir mayúsculas, email inválido, roles por defecto, `create_superuser` → OWNER, `public_id`, restricciones de BD.
- `tests/accounts/test_services.py`: altas por rol, registro sin elección de rol, contraseña débil, duplicados, auditoría sin datos personales, escalada de privilegios denegada (cliente/empleado/anónimo/rol manipulado en memoria/propietario inactivo), protección del último propietario.
- `tests/accounts/test_permissions.py`: helpers, decorador y mixin (anónimo → login, rol no permitido → 403).
- `tests/accounts/test_create_owner_command.py`: modo interactivo, contraseñas distintas, contraseña débil, propietario ya existente, email duplicado, `--noinput`.
- `tests/accounts/test_admin.py`: acceso denegado a empleado y cliente, alta auditada, el formulario de cambio ignora `role`/`is_staff`/`is_superuser`, acciones de rol, último propietario, sin borrado.
- `tests/core/test_audit_and_settings.py`: auditoría y admin de solo lectura; settings de producción exigen `DJANGO_SECRET_KEY` y `DJANGO_ALLOWED_HOSTS`.

### Comandos ejecutados y resultados reales (SQLite, Python 3.14.2, Django 5.2.18)

| Comando | Resultado |
|---|---|
| `python manage.py check` | Sin incidencias |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| `python manage.py test --settings=config.settings.test` | **60 tests, OK** |
| `python manage.py check --deploy --settings=config.settings.prod` (variables ficticias) | 1 aviso intencionado: `security.W021` (HSTS preload) |
| `python manage.py migrate` (SQLite local) | Migraciones aplicadas |

No se han ejecutado contra PostgreSQL (no está instalado en el equipo de desarrollo).

## 9. Seguridad y privacidad

- El rol nunca se recibe del cliente en flujos públicos; `create_customer` no acepta el parámetro.
- Invariantes de rol y email protegidas también en la base de datos.
- Permisos comprobados en servidor contra la BD; pruebas de escalada de privilegios.
- Contraseñas: validadores de Django, hash por defecto (PBKDF2); el hasher MD5 solo existe en `config.settings.test`.
- `create_owner` no acepta la contraseña como argumento ni la imprime.
- Auditoría sin datos personales; logging solo a consola sin PII.
- Producción: `SECRET_KEY` y `ALLOWED_HOSTS` obligatorios, HTTPS, HSTS, cookies `Secure`/`HttpOnly`, `SameSite=Lax`, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: same-origin`.
- Sin CORS: no hay API todavía.
- Sin secretos ni datos reales en el repositorio; los ejemplos usan `example.com`.

## 10. Limitaciones, riesgos y pendientes

- **PostgreSQL:** los tests se han ejecutado en SQLite. `select_for_update` no bloquea en SQLite, por lo que la protección concurrente del último propietario y de `create_owner` solo es efectiva en PostgreSQL. Hay que repetir los tests con `DATABASE_URL` de PostgreSQL antes de producción (Fase 11 o antes).
- **Admin técnico:** es la herramienta temporal del propietario hasta el dashboard (Fase 8). Expone nombre y email de los usuarios al propietario, lo que se considera justificado para la gestión.
- **`createsuperuser`:** no audita ni impide crear más propietarios; usar `create_owner`.
- **Rate limiting** del login del admin: pendiente (Fase 2 para el login público y Fase 11 en general).
- **Sin servidor WSGI ni guía de despliegue** (Fase 11).
- Política de conservación y documentación completa de datos personales: se redactará en la Fase 2, cuando se recojan datos personales del cliente.

## 11. Estado de los criterios de aceptación

| Criterio | Estado |
|---|---|
| Esqueleto modular y settings por entorno | Completo |
| Usuario personalizado con roles antes de la primera migración | Completo |
| Registro público limitado a CUSTOMER (a nivel de servicio) | Completo |
| Procedimiento seguro y documentado para el primer propietario | Completo |
| Empleados creados o autorizados solo por el propietario | Completo |
| `check` y tests superados | Completo (SQLite) |
| Validación en PostgreSQL | Pendiente (sin PostgreSQL local) |
| Documentación en `docs/` y `README.md` | Completo |

## 12. Dependencias para la fase siguiente

La Fase 1 (sistema de diseño y web pública) necesita: la CLI standalone de Tailwind (sin Node), los textos e información real del negocio aportados por el propietario (no se inventarán) y los recursos de `static/img/brand/`.
