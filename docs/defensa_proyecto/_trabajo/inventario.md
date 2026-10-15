# Inventario del repositorio (Etapa A)

> **Registro histórico.** Evidencia de la primera versión de la documentación de la defensa, sobre la Fase 11 (commit `ac5903a` del historial anterior, hoy `eec6abc`). No se ha actualizado: el estado de la versión congelada (commit `d0bac7c`, 849 tests) está en la [memoria](../01_memoria_tecnica_funcional.md) y en [`05_limitaciones_y_pendientes.md`](../05_limitaciones_y_pendientes.md).

Estado del repositorio analizado: rama `main`, commit `ac5903a` (2026-10-14), árbol limpio salvo `docs/prompt_funcionamiento.md` (sin versionar). Herramientas: Python 3.14.2 y Django 5.2.18 (versiones instaladas en `.venv`).

## Cifras verificadas

| Elemento | Cifra | Cómo se ha obtenido |
|---|---|---|
| Commits | 15 (12 de fase: de la 0 a la 11) | `git log --oneline` |
| Archivos versionados | 397 | `git ls-files` |
| Apps locales | 12 (`core`, `accounts`, `catalog`, `loyalty`, `purchases`, `rewards`, `notifications`, `events`, `staff`, `dashboard`, `api`, `web`) | `config/settings/base.py:40-53` |
| Modelos concretos propios | 21 (+ `TimeStampedModel` abstracto) | `apps.get_models()` → `volcado_modelos.md` |
| Archivos de migración | 26 (de ellos 2 de datos con `RunPython`) | `git ls-files 'apps/*/migrations/0*.py'` |
| Rutas propias | 117 (de ellas 38 de la API) + 7 de terceros + admin | `get_resolver()` → `volcado_urls.md` |
| Líneas de Python en `apps/*/*.py` y `apps/api/*/*.py` (sin migraciones ni tests) | ~13 700 | `wc -l` |
| Tests | 802 (3 omitidos con SQLite en memoria) | `manage.py test` |
| Plantillas HTML/TXT | 109 en `templates/` | `git ls-files templates \| wc -l` |
| JavaScript propio | 2 archivos (`app.js` de 65 líneas, `qr-scanner.js` de 136) + jsQR de terceros | `wc -l` |

## Revisión por categoría

| Categoría | Archivos | ¿Revisado? | Notas |
|---|---|---|---|
| Configuración | `config/settings/{base,dev,prod,test}.py`, `config/urls.py`, `manage.py`, `wsgi.py`, `asgi.py`, `.env.example`, `requirements/*.txt` | Sí (completo) | `notas_codigo.md#config` |
| core | `models.py`, `services.py`, `throttling.py`, `http.py`, `admin.py`, 9 migraciones | Sí | — |
| accounts | `models`, `managers`, `permissions`, `services`, `views`, `forms`, `validators`, `emails`, `normalization`, `selectors`, `admin`, `birthdays`, 2 comandos | Sí (completo) | `countries.py` solo por encima (es una lista de países) |
| catalog | `models`, `selectors`, `services`, `validators`, `admin` (parcial) | Sí | — |
| loyalty | `models`, `ledger`, `conversion`, `promotions`, `birthdays`, `services`, `selectors`, `views`, `urls`, comando, `admin` (parcial) | Sí | — |
| purchases | `models`, `services`, `forms`, `views`, `urls`, `selectors`, `admin` | Sí | — |
| rewards | `models`, `codes`, `services`, `views`, `urls`, `panel_urls`, `forms`, `selectors`, comando, `admin` (parcial) | Sí | — |
| staff | `views`, `forms`, `urls` | Sí | — |
| dashboard | `views` (completo), `forms` (completo) | Sí | `urls.py` contrastado con el volcado |
| events | `models`, `services`, `views`, `forms`, `selectors`, `urls` | Sí | — |
| notifications | `models`, `services`, `campaigns`, `unsubscribe`, `sms`, `views`, `urls`, `selectors`, comando | Sí | — |
| web | `models`, `services`, `views`, `context_processors`, `urls`, `content` | Sí | — |
| api | `authentication`, `tokens`, `permissions`, `throttling`, `exceptions`, `pagination`, `schema`, `urls`, `views/*` | Sí | Serializadores: estructura (todos `Serializer` explícitos) |
| Plantillas | `templates/base.html` (assets y CSRF) | Parcial | Sin HTMX ni Alpine.js (grep sin resultados) |
| Estáticos | `static/js/app.js`, `static/js/qr-scanner.js`, `static/vendor/jsqr/`, `assets/css/input.css`, `scripts/tailwind.py` | Sí | Tailwind v4.3.3 con checksum SHA-256 |
| Migraciones | Commit de origen de cada una y las 2 con `RunPython` | Sí | `historial_fases.md` |
| Tests | Recuento por módulo, nombres de los tests de IDOR, idempotencia, seguridad y bordes; `test_concurrency.py`, `test_security.py` (parcial) y `purchases/test_services.py` (parcial) | Sí | `resultados_pruebas.md` |
| Documentación existente | `README.md`, `docs/plan-de-fases.md`, `docs/arquitectura.md` (encabezados), `docs/fase-11-api-auditoria.md` (partes) y `docs/despliegue.md` (tareas) | Parcial | Se contrasta con el código; manda el código |
| Docker / CI/CD | No existen | Sí | `git ls-files` no muestra `Dockerfile`, `docker-compose*` ni workflows |
