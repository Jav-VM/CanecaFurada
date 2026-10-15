# Caneca Furada — Limitaciones, discrepancias, riesgos y mejoras

Basado en el análisis del commit `ac5903a` y en las comprobaciones ejecutadas el 15-10-2026 ([`_trabajo/resultados_pruebas.md`](_trabajo/resultados_pruebas.md)). Las decisiones de alcance deliberadas **no** se presentan como defectos.

Escala: **prioridad** Alta / Media / Baja · **coste aproximado** S (< 1 día) / M (1-3 días) / L (> 3 días) · **beneficio** Alto / Medio / Bajo.

## 1. Lo que no se ha podido verificar

| Elemento | Por qué no se ha verificado | Estado |
|---|---|---|
| Comportamiento con **PostgreSQL** (motor objetivo) | No hay una instancia; la suite se ejecutó con SQLite | Implementado, pendiente de verificación |
| **Concurrencia real** (bloqueos de fila) | 3 tests omitidos con SQLite en memoria; con SQLite en fichero pasan, pero la BD serializa las escrituras | Implementado, pendiente de verificación |
| **Envío real de email** | Sin proveedor SMTP; los tests usan locmem y el desarrollo, la consola | Implementado, pendiente de verificación |
| **Escaneo con cámara** en móviles y tablets | Requiere dispositivo y HTTPS o `localhost` | Implementado, pendiente de verificación |
| **Aspecto visual, contraste AA y diseño responsive** | No hay pruebas automáticas; no se ha hecho una revisión visual en esta tarea | Implementado, pendiente de verificación |
| **Tareas programadas** | No hay programación (cron o Programador de tareas) | Parcialmente implementado (los comandos existen) |
| **Despliegue** | No existe | Planificado |
| **Sintaxis de los diagramas Mermaid** | No hay Node/npx en el equipo para `mermaid-cli` | Revisión estructural automática + revisión manual (ver la Etapa D en `_trabajo/progreso.md`) |

## 2. Discrepancias encontradas (código frente a requisitos o documentación)

| # | Discrepancia | Evidencia | Valoración |
|---|---|---|---|
| 1 | El prompt de documentación supone 11 fases con el despliegue en la última; el repositorio tiene las fases 0 a 11 y el despliegue **sin número y pendiente** | `docs/plan-de-fases.md:19`; `git log` | Documentado en la memoria, cap. 14.2 |
| 2 | Los documentos de las fases 0 a 7 usan la numeración antigua en sus referencias | `docs/plan-de-fases.md:35, 75` | Conviene revisarlos antes de entregarlos |
| 3 | El plan pedía «CORS restrictivo»; se implementó **sin CORS** | `docs/fase-11-api-auditoria.md:155` | Decisión justificada y probada |
| 4 | `Purchase.Status.VOIDED`, `Purchase.Source.POS` y `external_reference` existen sin flujo | `apps/purchases/models.py:22-32, 66-72` | Planificado (reservado a propósito) |
| 5 | `Promotion.birthday_window_days` sin uso desde la Fase 10 | `apps/loyalty/models.py:187-192` | Deuda técnica menor |
| 6 | `CancelReservationForm` definido y no usado | `apps/events/forms.py:61-62` | Código muerto |
| 7 | La Fase 4 pedía 14 grifos; se implementó una imagen de la carta de grifos | Plan, ajuste de la F4 | Decisión del usuario |
| 8 | La bonificación de cumpleaños en la compra (F6) se sustituyó por un regalo el mismo día (F10) | Plan, ajuste de la F10; `promotions.py:116` | Decisión del usuario |

## 3. Limitaciones actuales (alcance deliberado)

- No hay facturación, caja ni TPV: las **compras registradas no son la facturación** (`apps/purchases/selectors.py:1-9`).
- No hay SMS (no hay proveedor integrado; `apps/notifications/sms.py:4-10`).
- No hay app móvil (solo API y guía).
- Las reservas de **mesa no tienen aforo** (la confirmación es manual).
- Un precio por producto; la carta de grifos es una imagen.
- El dashboard no exporta informes.

## 4. Funcionalidades incompletas

| Funcionalidad | Situación | Prioridad | Coste | Beneficio |
|---|---|---|---|---|
| Anulación de compras con compensación de puntos | Estado reservado `VOIDED`; el ledger ya tiene `reverse_movement` | Media | M | Alto |
| Integración con TPV | `POS` y `external_reference` reservados (con UNIQUE) | Baja | L | Alto |
| Exportación y supresión de datos personales (derechos del interesado) | **No identificadas**; las cuentas se desactivan | Alta (antes de producción) | M | Alto |
| Programación de las tareas | Comandos listos, sin programar | Alta | S | Alto |
| SMS | Canal preparado (`SMS_BACKEND`), sin proveedor | Baja | M | Medio |

## 5. Riesgos que deberían resolverse antes de producción

| Riesgo | Detalle | Prioridad | Coste | Beneficio |
|---|---|---|---|---|
| Sin pruebas en PostgreSQL | La concurrencia depende de `SELECT FOR UPDATE` real | **Alta** | S | Alto |
| Límites por proceso | `CACHE_URL` por defecto `locmem`: con varios procesos, cada uno cuenta por separado | **Alta** | S | Alto |
| SMTP real | Sin él no sale ningún email (verificación incluida) | **Alta** | S | Alto |
| Infraestructura | Servidor WSGI, proxy con TLS, estáticos y medios, dominio | **Alta** | M | Alto |
| Copias de seguridad | No existen; tampoco el procedimiento de restauración | **Alta** | S | Alto |
| Monitorización y alertas | Solo logs por consola | Media | M | Medio |
| Revisión legal (RGPD) | Textos legales, base jurídica y conservación | Alta | M | Alto |
| Clave de idempotencia regenerada al reenviar la identificación | Si el navegador reenvía el paso «identificar» (volver atrás), se genera una clave nueva y un segundo «Registrar» crearía **otra compra** legítima. El doble clic en «Registrar» sí está cubierto (misma clave + `app.js`) | Media | S | Medio |
| Duplicado en `recover_stale` | Si un proceso muere después de que el SMTP aceptara el mensaje, puede reenviarse (reconocido en `apps/notifications/services.py:306-312`) | Baja | M | Bajo |

## 6. Mejoras recomendadas a medio plazo

| Mejora | Motivo | Prioridad | Coste | Beneficio |
|---|---|---|---|---|
| CI (tests + `pip-audit` + `makemigrations --check`) en cada push | Hoy no hay ninguna automatización | Alta | S | Alto |
| Medición de cobertura | No se puede afirmar un porcentaje | Media | S | Medio |
| Tests E2E del lector de QR (Playwright) | El JS no tiene pruebas | Media | M | Medio |
| Saldo de puntos materializado | `ledger.balance()` hace `SUM` de todos los movimientos en cada escritura | Baja (a esta escala) | M | Medio con volumen |
| 2FA para el propietario | Es la cuenta con más privilegios | Media | M | Alto |
| Auditoría inmutable en la BD (permisos o triggers) | Hoy la inmutabilidad depende de la aplicación | Baja | M | Medio |
| Servir Swagger UI localmente (`drf-spectacular-sidecar`) | `/api/v1/docs/` carga recursos de un CDN (ya reconocido en `docs/despliegue.md:109`) | Baja | S | Bajo |
| Atar la clave de idempotencia a la sesión o firmarla | Cerrar el caso de la tabla anterior | Media | S | Medio |
| Limpiar la deuda menor (`birthday_window_days`, `CancelReservationForm`) | Claridad | Baja | S | Bajo |
| Actualizar la numeración antigua en los docs de las fases 0-7 | Coherencia documental | Baja | S | Bajo |

## 7. Ampliaciones futuras

- App Flutter sobre la API v1 (`docs/guia-app-flutter.md`).
- Integración con TPV y estadísticas de facturación real.
- Proveedor de SMS.
- Aforo de mesas y franjas horarias de reserva.
- Exportación de informes del dashboard.
