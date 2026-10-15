# Documentación para la defensa del proyecto — Caneca Furada

Documentación técnica y funcional del proyecto final, elaborada a partir del **código real** del repositorio (commit `ac5903a`, 14-10-2026) y de comprobaciones ejecutadas el 15-10-2026. Requisitos de esta documentación: [`docs/prompt_funcionamiento.md`](../prompt_funcionamiento.md).

## Resultados verificados

| Comprobación | Resultado |
|---|---|
| `python manage.py check` | Sin incidencias |
| `python manage.py makemigrations --check --dry-run` | Sin cambios pendientes |
| `python manage.py test --settings=config.settings.test` | **802 tests, OK, 3 omitidos** (concurrencia; requieren una BD con varias conexiones) |
| Tests de concurrencia con SQLite en fichero (settings temporal fuera del repositorio) | 3 OK; **no ejercitan los bloqueos de fila** (pendiente PostgreSQL) |
| `spectacular --validate` + `diff` con `docs/api/openapi.yaml` | Sin errores; **idéntico** |
| `check --deploy` (`config.settings.prod`, variables ficticias) | Solo `security.W021` (HSTS preload desactivado a propósito) |

Detalle: [`_trabajo/resultados_pruebas.md`](_trabajo/resultados_pruebas.md).

## Archivos

| Archivo | Propósito |
|---|---|
| [01_memoria_tecnica_funcional.md](01_memoria_tecnica_funcional.md) | **Documento principal**: capítulos 1-16, 19 y 20 (presentación, requisitos, arquitectura, tecnologías, repositorio, modelo de datos, funcionalidades, código comentado, flujos, seguridad, pruebas, instalación, despliegue, fases, decisiones, limitaciones, glosario y conclusiones) |
| [02_guion_defensa_oral.md](02_guion_defensa_oral.md) | Capítulo 17: resúmenes de 30 s y 2 min, guiones de 10 y 15 min, orden de demostración y mensajes clave |
| [03_preguntas_y_respuestas_tribunal.md](03_preguntas_y_respuestas_tribunal.md) | Capítulo 18: 75 preguntas con respuesta razonada, por tema y dificultad |
| [04_mapa_codigo_y_funcionalidades.md](04_mapa_codigo_y_funcionalidades.md) | Índice funcionalidad → URL → vista → servicio → modelo → plantilla → test, comandos y funciones clave |
| [05_limitaciones_y_pendientes.md](05_limitaciones_y_pendientes.md) | Lo no verificado, las discrepancias, los riesgos antes de producción y las mejoras con prioridad, coste y beneficio |
| [diagramas/](diagramas/) | 14 diagramas Mermaid (`.mmd`): arquitectura, módulos, petición, entidad-relación, autenticación, flujos, estados, roles y despliegue (propuesta) |
| [_trabajo/](_trabajo/) | Evidencias del análisis: inventario, volcados de URLs y modelos, historial de Git por fase, matriz de evidencia, discrepancias, notas de lectura del código, resultados de las pruebas y progreso |

## Orden de lectura recomendado para preparar la defensa

1. **Memoria, caps. 1-3** (qué es y cómo está construido) + diagrama `01_arquitectura_general.mmd`.
2. **Guion oral** (`02`), para tener el hilo de la presentación.
3. **Memoria, caps. 6-9** (datos, funcionalidades, código y flujos), sobre todo los fragmentos C8.7, C8.8, C8.10, C8.11 y C8.12.
4. **Memoria, caps. 10-11** (seguridad y pruebas).
5. **Banco de preguntas** (`03`): primero las 🔴, que son las que más cuesta improvisar.
6. **Limitaciones** (`05`) y **memoria, caps. 13-16**: para responder con honestidad a lo que falta.
7. **Mapa de código** (`04`) para localizar rápidamente cualquier archivo durante las preguntas.

## Etiquetas de estado

**Implementado y verificado** (hay código y un test ejecutado que pasa) · **Implementado, pendiente de verificación** (depende de PostgreSQL, SMTP, un dispositivo o una revisión visual) · **Parcialmente implementado** · **Planificado** · **No identificado**.

## Cómo ver los diagramas

Los `.mmd` y los bloques ` ```mermaid ` se ven en GitHub y en la vista previa de Markdown de VS Code (con soporte de Mermaid). En esta tarea no se generaron imágenes (decisión del autor: solo Markdown) ni un DOCX.
