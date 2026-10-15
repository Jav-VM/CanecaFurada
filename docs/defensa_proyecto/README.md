# Documentación para la defensa del proyecto — Caneca Furada

Documentación técnica y funcional del proyecto final, elaborada a partir del **código real** del repositorio. Describe la **versión congelada para la defensa** (commit `d0bac7c`, 15-10-2026), que incluye la [migración a PostgreSQL](../migracion-postgresql.md), la [auditoría previa a la Fase 12](../auditoria-pre-fase-12.md), la [Fase 12 de despliegue](../fase-12-despliegue.md) y la [refactorización final](../refactorizacion-final.md). La primera versión se redactó sobre la Fase 11 (commit `ac5903a` del historial anterior, hoy `eec6abc`) y se actualizó el 15-10-2026: se recalcularon las referencias `archivo:línea` y se volvieron a comparar los bloques de código real con el código. Requisitos de esta documentación: [`docs/prompt_funcionamiento.md`](../prompt_funcionamiento.md).

## Resultados verificados (versión congelada, 15-10-2026)

| Comprobación | Resultado |
|---|---|
| `python manage.py check` | Sin incidencias |
| `python manage.py makemigrations --check --dry-run` | Sin cambios pendientes |
| `python manage.py test --settings=config.settings.test --parallel 1` con PostgreSQL 17 | **849 tests OK, 0 omitidos**, incluidos 17 de concurrencia con bloqueos de fila reales |
| La misma suite dentro del contenedor de producción (Docker Compose) | **849 OK** |
| La misma suite con SQLite en memoria | 849 OK, 18 omitidos (concurrencia y una prueba exclusiva de PostgreSQL) |
| `spectacular --validate --fail-on-warn` + `diff` con `docs/api/openapi.yaml` | Sin errores; **idéntico** |
| `check --deploy` (`config.settings.prod`, variables ficticias) | Solo `security.W021` (HSTS preload desactivado a propósito) |
| CI de GitHub Actions | En verde en la Fase 12 (commit `0589cfb`); la versión congelada aún no se ha subido |

Detalle: [`refactorizacion-final.md` §6](../refactorizacion-final.md) y [`fase-12-despliegue.md` §10](../fase-12-despliegue.md). Los resultados de la primera versión (802 tests sobre la Fase 11) quedan como registro histórico en [`_trabajo/resultados_pruebas.md`](_trabajo/resultados_pruebas.md).

## Archivos

| Archivo | Propósito |
|---|---|
| [01_memoria_tecnica_funcional.md](01_memoria_tecnica_funcional.md) | **Documento principal**: capítulos 1-16, 19 y 20 (presentación, requisitos, arquitectura, tecnologías, repositorio, modelo de datos, funcionalidades, código comentado, flujos, seguridad, pruebas, instalación, despliegue, fases, decisiones, limitaciones, glosario y conclusiones) |
| [02_guion_defensa_oral.md](02_guion_defensa_oral.md) | Capítulo 17: resúmenes de 30 s y 2 min, guiones de 10 y 15 min, orden de demostración y mensajes clave |
| [03_preguntas_y_respuestas_tribunal.md](03_preguntas_y_respuestas_tribunal.md) | Capítulo 18: 80 preguntas con respuesta razonada, por tema y dificultad (las 76-80, sobre PostgreSQL, despliegue y refactorización) |
| [04_mapa_codigo_y_funcionalidades.md](04_mapa_codigo_y_funcionalidades.md) | Índice funcionalidad → URL → vista → servicio → modelo → plantilla → test, comandos y funciones clave |
| [05_limitaciones_y_pendientes.md](05_limitaciones_y_pendientes.md) | Lo no verificado, las discrepancias, lo pendiente antes de producción y las mejoras con prioridad, coste y beneficio |
| [diagramas/](diagramas/) | 14 diagramas Mermaid (`.mmd`): arquitectura, módulos, petición, entidad-relación, autenticación, flujos, estados, roles y despliegue (Fase 12) |
| [_trabajo/](_trabajo/) | Evidencias del análisis de la primera versión (Fase 11, commit `ac5903a`): inventario, volcados de URLs y modelos, historial de Git por fase, matriz de evidencia, discrepancias, notas de lectura del código, resultados de las pruebas y progreso. **Registro histórico**: no se han actualizado |

## Orden de lectura recomendado para preparar la defensa

1. **Memoria, caps. 1-3** (qué es y cómo está construido) + diagrama `01_arquitectura_general.mmd`.
2. **Guion oral** (`02`), para tener el hilo de la presentación.
3. **Memoria, caps. 6-9** (datos, funcionalidades, código y flujos), sobre todo los fragmentos C8.7, C8.8, C8.10, C8.11 y C8.12.
4. **Memoria, caps. 10-11** (seguridad y pruebas).
5. **Banco de preguntas** (`03`): primero las 🔴, que son las que más cuesta improvisar.
6. **Limitaciones** (`05`) y **memoria, caps. 13-16** (despliegue, fases, decisiones y limitaciones): para responder con honestidad a lo que falta.
7. **Refactorización final** ([`../refactorizacion-final.md`](../refactorizacion-final.md)): qué se mejoró, cómo se midió y el interbloqueo R-1.
8. **Mapa de código** (`04`) para localizar rápidamente cualquier archivo durante las preguntas.

## Etiquetas de estado

**Implementado y verificado** (hay código y un test ejecutado que pasa) · **Implementado, pendiente de verificación** (depende de PostgreSQL, SMTP, un dispositivo o una revisión visual) · **Parcialmente implementado** · **Planificado** · **No identificado**.

## Cómo ver los diagramas

Los `.mmd` y los bloques ` ```mermaid ` se ven en GitHub y en la vista previa de Markdown de VS Code (con soporte de Mermaid). En esta tarea no se generaron imágenes (decisión del autor: solo Markdown) ni un DOCX.
