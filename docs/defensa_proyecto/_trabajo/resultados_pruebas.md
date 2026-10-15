# Resultados reales de las comprobaciones

> **Registro histórico.** Evidencia de la primera versión de la documentación de la defensa, sobre la Fase 11 (commit `ac5903a` del historial anterior, hoy `eec6abc`). No se ha actualizado: el estado de la versión congelada (commit `d0bac7c`, 849 tests) está en la [memoria](../01_memoria_tecnica_funcional.md) y en [`05_limitaciones_y_pendientes.md`](../05_limitaciones_y_pendientes.md). Resultados de la versión congelada: [`refactorizacion-final.md` §6](../../refactorizacion-final.md).

Ejecutadas el 2026-10-15 en Windows 11, Python 3.14.2, Django 5.2.18, sin `.env` (BD SQLite; la de test es SQLite en memoria).

| Comando | Resultado |
|---|---|
| `python manage.py check` | System check identified no issues (0 silenced) |
| `python manage.py check` con `DJANGO_SETTINGS_MODULE=config.settings.test` | System check identified no issues (0 silenced) |
| `python manage.py makemigrations --check --dry-run` | No changes detected |
| `python manage.py test --settings=config.settings.test -v 2` | Ran 802 tests in 16.407s — OK (skipped=3) |

## Tests omitidos

- test_concurrent_requests_for_same_reward_give_one_pending (tests.rewards.test_concurrency.ConcurrentRedemptionTests.test_concurrent_requests_for_same_reward_give_one_pending) ... skipped 'La BD de test de SQLite en memoria no admite varias conexiones'
- Saldo 60 tras el canje inicial; cuatro canjes simultáneos de 40: como mucho uno. ... skipped 'La BD de test de SQLite en memoria no admite varias conexiones'
- test_same_code_validated_concurrently_is_used_once (tests.rewards.test_concurrency.ConcurrentRedemptionTests.test_same_code_validated_concurrently_is_used_once) ... skipped 'La BD de test de SQLite en memoria no admite varias conexiones'

## Tests ejecutados por módulo

| Módulo | Tests |
|---|---|
| `tests.accounts.test_admin` | 15 |
| `tests.accounts.test_auth_views` | 11 |
| `tests.accounts.test_create_owner_command` | 7 |
| `tests.accounts.test_customer_profile` | 10 |
| `tests.accounts.test_email_verification` | 23 |
| `tests.accounts.test_models` | 12 |
| `tests.accounts.test_permissions` | 6 |
| `tests.accounts.test_profile` | 40 |
| `tests.accounts.test_registration` | 38 |
| `tests.accounts.test_services` | 22 |
| `tests.accounts.test_validators` | 11 |
| `tests.api.test_auth` | 28 |
| `tests.api.test_customer` | 15 |
| `tests.api.test_me` | 12 |
| `tests.api.test_security` | 9 |
| `tests.api.test_staff_owner` | 8 |
| `tests.catalog.test_admin` | 15 |
| `tests.catalog.test_models` | 17 |
| `tests.catalog.test_selectors` | 8 |
| `tests.catalog.test_services` | 10 |
| `tests.catalog.test_validators` | 9 |
| `tests.core.test_audit_and_settings` | 9 |
| `tests.core.test_phase11_audit` | 10 |
| `tests.dashboard.test_access` | 13 |
| `tests.dashboard.test_customers_and_actions` | 27 |
| `tests.dashboard.test_stats` | 19 |
| `tests.events.test_services` | 25 |
| `tests.events.test_views` | 16 |
| `tests.loyalty.test_birthdays` | 21 |
| `tests.loyalty.test_points` | 41 |
| `tests.loyalty.test_points_views` | 15 |
| `tests.loyalty.test_promotions` | 18 |
| `tests.loyalty.test_qr` | 22 |
| `tests.notifications.test_notifications` | 30 |
| `tests.purchases.test_services` | 25 |
| `tests.purchases.test_stats` | 6 |
| `tests.purchases.test_views` | 25 |
| `tests.rewards.test_concurrency` | 3 |
| `tests.rewards.test_services` | 54 |
| `tests.rewards.test_views` | 26 |
| `tests.staff.test_panel` | 31 |
| `tests.web.test_account_forms_ui` | 11 |
| `tests.web.test_menu_page` | 12 |
| `tests.web.test_public_pages` | 17 |

Total contado por módulo: 802 (coincide con el total de `Ran`). Los 3 omitidos son de `tests.rewards.test_concurrency` y requieren PostgreSQL.

## Esquema OpenAPI

| Comando | Resultado |
|---|---|
| `python manage.py spectacular --validate --file <scratchpad>/openapi_actual.yaml` | Sin errores ni avisos (exit 0) |
| `diff` entre el esquema regenerado y `docs/api/openapi.yaml` | **Idénticos**: la documentación de la API está sincronizada con el código |
| Rutas en `docs/api/openapi.yaml` | 38 (`/api/v1/...`, sin contar `schema/` ni `docs/`) |

## Tests de concurrencia con SQLite en fichero (ejecución adicional)

El docstring de `tests/rewards/test_concurrency.py` indica que estos tests se pueden ejecutar con una BD de test SQLite **en fichero**. Se ejecutaron con un módulo de settings temporal, guardado fuera del repositorio, que hereda `config.settings.test` y solo cambia `DATABASES["default"]["TEST"]["NAME"]` a un fichero temporal:

| Comando | Resultado |
|---|---|
| `python manage.py test tests.rewards.test_concurrency --settings=<settings temporal> -v 2` | `Ran 3 tests in 0.903s — OK` |

Tests: `test_concurrent_requests_for_same_reward_give_one_pending`, `test_concurrent_requests_never_overspend` y `test_same_code_validated_concurrently_is_used_once` (4 hilos con `threading.Barrier`).

**Alcance real de esta evidencia:** con SQLite en fichero las escrituras simultáneas las serializa la propia BD. La prueba demuestra que no hay doble consumo ni saldo negativo, pero **no ejercita los bloqueos de fila** (`select_for_update`). Esa verificación sigue pendiente en PostgreSQL, como dice el propio test.

## Comprobación de la configuración de producción

| Comando | Resultado |
|---|---|
| `python manage.py check --deploy --settings=config.settings.prod` con variables **ficticias** (`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS=www.example.com`, `EMAIL_HOST=smtp.example.com`, `SITE_BASE_URL=https://www.example.com`) | 1 aviso: `security.W021` (HSTS preload desactivado a propósito: `DJANGO_SECURE_HSTS_PRELOAD=False` por defecto). Coincide con lo que dice `docs/fase-11-api-auditoria.md:163`. |

Esto valida **la configuración**, no un despliegue real: no hay servidor, dominio, TLS ni PostgreSQL de producción.
