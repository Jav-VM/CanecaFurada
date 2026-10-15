# Progreso de la documentación de la defensa

> **Registro histórico.** Evidencia de la primera versión de la documentación de la defensa, sobre la Fase 11 (commit `ac5903a` del historial anterior, hoy `eec6abc`). No se ha actualizado: el estado de la versión congelada (commit `d0bac7c`, 849 tests) está en la [memoria](../01_memoria_tecnica_funcional.md) y en [`05_limitaciones_y_pendientes.md`](../05_limitaciones_y_pendientes.md).

**Léelo primero al retomar la tarea.** Plan aprobado: `C:\Users\jvmsp\.claude\plans\pasted-content-id-cda0-quiero-preparar-hashed-valley.md`. Requisitos: `docs/prompt_funcionamiento.md`.

Decisiones del usuario: solo Markdown en `docs/defensa_proyecto/`, diagramas en Mermaid y no mencionar un archivo concreto del repositorio que el usuario pidió ignorar.

## Etapas

| Etapa | Estado | Fecha | Notas |
|---|---|---|---|
| A — Inventario | **Completa** | 2026-10-15 | `inventario.md`, `volcado_urls.md`, `volcado_modelos.md`, `historial_fases.md` |
| B — Verificación | **Completa** | 2026-10-15 | `matriz_evidencia.md`, `discrepancias.md`, `resultados_pruebas.md`, `notas_codigo.md` |
| C — Redacción | **Completa** | 2026-10-15 | 6 documentos + 14 diagramas |
| D — Revisión de consistencia | **Completa** | 2026-10-15 | Ver abajo |
| E — Entrega | **Completa** | 2026-10-15 | Resumen entregado al usuario en la conversación |

## Entregables

| Archivo | Estado |
|---|---|
| `diagramas/*.mmd` (14) | Completa |
| `01_memoria_tecnica_funcional.md` (caps. 1-16, 19, 20) | Completa |
| `02_guion_defensa_oral.md` (cap. 17) | Completa |
| `03_preguntas_y_respuestas_tribunal.md` (cap. 18, 75 preguntas) | Completa |
| `04_mapa_codigo_y_funcionalidades.md` | Completa |
| `05_limitaciones_y_pendientes.md` | Completa |
| `README.md` de la carpeta | Completa |
| Enlace en el `README.md` raíz (sección Documentación) | Completa |

## Etapa D — comprobaciones de consistencia

Script de solo lectura guardado en el scratchpad de la sesión (no en el repositorio). Resultado final:

| Comprobación | Resultado |
|---|---|
| Referencias con ruta completa (`apps/...:NN`): el archivo existe y la línea está dentro de rango | 430 comprobadas, 0 errores |
| Referencias cortas (`services.py:NN`): algún archivo con ese nombre llega a esa línea | 150 comprobadas, 0 errores |
| Bloques «Código real» del cap. 8 idénticos al fuente | 23 bloques, 0 diferencias |
| URLs citadas presentes en `get_resolver()` | 47 URLs distintas, 0 errores |
| Comandos de gestión citados registrados en Django | 0 errores |
| Variables de entorno y ajustes citados presentes en `config/` o `.env.example` | 21 citados; 4 «errores» que resultan ser falsos positivos (nombres de enumerados: `API_SESSIONS_REVOKED`, `EMAIL_CHANGE`, `EMAIL_CHANGED_NOTICE` y `EMAIL_VERIFIED`, que existen en `apps/core/models.py` y `apps/notifications/models.py`) |
| Enlaces Markdown internos y anclas | 58 comprobados, 0 rotos |
| Funciones o clases del mapa en la línea citada (±3) | 86 comprobadas, 0 errores |
| Símbolo citado como «`nombre` (`archivo.py:NN`)» cerca de esa línea | 27 comprobados; 2 avisos revisados a mano (falsos positivos; uno se aclaró en el texto) |
| Mermaid: estructura (tipo de diagrama, comillas, corchetes, participantes declarados, entidades ER definidas) | 23 diagramas (14 `.mmd` + 9 incrustados), 0 errores. **Sin renderizado real**: no hay Node/npx para `mermaid-cli`; queda pendiente abrirlos en GitHub o en la vista previa de VS Code |
| Datos sensibles (emails no ficticios, secretos, mención del archivo excluido) | 0 apariciones |
| `manage.py check` + `test` repetidos al final | Sin incidencias; 802 tests, OK (skipped=3) |
| `git status` | Solo `M README.md` y archivos nuevos en `docs/` |

Durante la Etapa D se corrigieron: 3 rutas abreviadas de documentos de fase, una referencia mal formada a `record_audit_event`, 2 referencias ambiguas del mapa (`register_attempt` y `read_token`), la línea de `_random_image_path`, las líneas de los servicios del catálogo (que se habían tomado de una salida concatenada) y la referencia a `User.Role`.

## Si hay que retomar
- Para ampliar un capítulo, editar directamente `01_memoria_tecnica_funcional.md` (los borradores por capítulo se eliminaron tras ensamblarlo).
- Si cambia el código, volver a ejecutar: `manage.py test --settings=config.settings.test`, el volcado de URLs y modelos y la comprobación de que los bloques «Código real» coinciden con el fuente.
