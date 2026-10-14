# Fase 1 — Proyecto base: perfil de cliente, módulos y preparación para la app

**Estado:** Completa (validación en PostgreSQL pendiente).
**Fecha:** 2026-10-14.
**Depende de:** [Fase 0 — Fundación](fase-00-fundacion.md).

## 1. Objetivo y contexto

El prompt de la Fase 1 pide crear el proyecto Django, configurar PostgreSQL y los entornos, el usuario personalizado con roles, la estructura modular y la preparación para la app móvil. Al inspeccionar el repositorio se comprobó que la mayor parte ya existía desde la Fase 0 (settings por entorno, `DATABASE_URL`, `User` con `public_id` y roles antes de la primera migración, servicios, permisos, `create_owner`, `.env.example`, `.gitignore`, dependencias y tests). Esta fase verifica esa base y completa lo que faltaba:

- Decidir y crear el perfil de cliente, con creación transaccional.
- Preparar los módulos principales (mapa de apps).
- Documentar identificadores estables, permisos reutilizables y cómo incorporar DRF.

Las decisiones de arquitectura están en [arquitectura.md](arquitectura.md).

## 2. Alcance
- **Incluye:** modelo `CustomerProfile` mínimo con creación transaccional; mapa de módulos y guía de preparación para la app/DRF en [arquitectura.md](arquitectura.md).
- **Excluye:** campos personales del perfil y formulario de registro (Fase 3); creación de apps de dominio vacías (cada app se crea al empezar su fase); DRF (Fase 11).

## 3. Archivos creados o modificados
| Archivo | Cambio |
|---|---|
| `apps/accounts/models.py` | Nuevo `CustomerProfile` (`user` 1:1, `created_at`, `updated_at`). |
| `apps/accounts/services.py` | `ensure_customer_profile(user)` (idempotente); llamado en el alta de clientes (`_create_user`) y en `change_role` hacia `CUSTOMER`, dentro de la misma transacción. |
| `apps/accounts/migrations/0002_customer_profile.py` | Crea la tabla (`user_id` `UNIQUE`). |
| `apps/accounts/migrations/0003_backfill_customer_profiles.py` | Migración de datos: perfil para los clientes existentes. Reversión `noop` (al revertir 0002 desaparece la tabla). |
| `tests/accounts/test_customer_profile.py` | 10 tests nuevos. |
| `docs/arquitectura.md` | Nuevo: mapa de módulos, decisión del perfil, garantías, preparación para la app y DRF. |

## 4. Migraciones
- `0002`: solo `CREATE TABLE accounts_customerprofile` con FK única a `accounts_user` (revisado con `sqlmigrate`). No modifica `User`.
- `0003`: solo inserta perfiles a usuarios `CUSTOMER` sin perfil; repetible.
- Probadas hacia delante y hacia atrás (`migrate accounts 0001` → `migrate accounts`) sobre una base SQLite temporal, y aplicadas a la `db.sqlite3` local de desarrollo.

## 5. Tests añadidos
Perfil creado en `create_customer` y en altas de cliente por el propietario; empleados y propietarios sin perfil; `change_role` a cliente crea el perfil; ida y vuelta de rol sin duplicados; idempotencia; **reversión del alta si falla la creación del perfil**; alta fallida sin perfil; restricción única en BD; migración de datos (solo clientes, repetible).

## 6. Comandos ejecutados y resultados reales (SQLite, Python 3.14.2, Django 5.2.18)
| Comando | Resultado |
|---|---|
| `python manage.py check` | Sin incidencias |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| `python manage.py test --settings=config.settings.test` | **70 tests, OK** |
| `python manage.py migrate` / reversión a `accounts 0001` | OK |

No se han ejecutado contra PostgreSQL (no instalado en el equipo).

## 7. Seguridad y privacidad
- El perfil todavía no contiene datos personales.
- No tiene identificador público: se accederá siempre a través del usuario autenticado, no por ID (evita IDOR).
- No se registra en la auditoría: es un efecto del alta, que ya queda auditada.

## 8. Limitaciones, riesgos y pendientes
- La garantía "todo cliente tiene perfil" la dan los servicios y la migración de datos; la BD no la impone (ver [arquitectura.md](arquitectura.md#cómo-se-garantiza-que-todo-cliente-tiene-perfil)). `User.objects.create_user` no crea perfil.
- Al dejar de ser cliente se conserva el perfil; su política de conservación se decide en la Fase 3.
- El perfil no aparece en el admin (no tiene campos que mostrar).

## 9. Estado de los criterios de aceptación
| Criterio | Estado |
|---|---|
| Proyecto, settings por entorno, PostgreSQL por variables | Completo (validación en PostgreSQL pendiente) |
| Usuario personalizado y `AUTH_USER_MODEL` antes de la primera migración | Completo |
| Roles `OWNER`/`EMPLOYEE`/`CUSTOMER`; sin roles privilegiados por registro público | Completo |
| Perfil de cliente decidido, justificado y creado de forma transaccional | Completo |
| Estáticos y multimedia, `.env.example`, `.gitignore`, dependencias reproducibles | Completo |
| Módulos principales preparados | Completo (mapa documentado; apps se crean en su fase) |
| Identificadores estables, permisos reutilizables, guía de DRF | Completo |
| Primer propietario documentado | Completo |

## 10. Dependencias para la fase siguiente

La Fase 2 (sistema de diseño y web pública) necesita su prompt de fase, la CLI standalone de Tailwind (sin Node), los textos reales del negocio aportados por el propietario y los recursos de `static/img/brand/`.
