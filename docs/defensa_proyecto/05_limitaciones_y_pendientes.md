# Caneca Furada — Limitaciones, discrepancias, riesgos y mejoras

Estado de la versión congelada para la defensa (commit `d0bac7c`, 15-10-2026): incluye la [migración a PostgreSQL](../migracion-postgresql.md), la [auditoría previa a la Fase 12](../auditoria-pre-fase-12.md), la [Fase 12](../fase-12-despliegue.md) y la [refactorización final](../refactorizacion-final.md), más la [Fase 13](../fase-13-datos-demo.md) posterior (datos de demostración). Las decisiones de alcance deliberadas **no** se presentan como defectos.

Escala: **prioridad** Alta / Media / Baja · **coste aproximado** S (< 1 día) / M (1-3 días) / L (> 3 días) · **beneficio** Alto / Medio / Bajo.

## 1. Lo que no se ha podido verificar

| Elemento | Por qué no se ha verificado | Estado |
|---|---|---|
| **Despliegue en el VPS real** | No hay servidor contratado. La pila completa se probó en local (WSL) desde volúmenes vacíos, y en el CI de GitHub | Implementado, pendiente de verificación en el servidor |
| **Envío real de email** | Sin proveedor SMTP; los tests usan locmem y la pila local, Mailpit | Implementado, pendiente de verificación |
| **Escaneo con cámara** en móviles y tablets | Requiere dispositivo y HTTPS o `localhost` | Implementado, pendiente de verificación |
| **Aspecto visual, contraste AA y diseño responsive** | No hay pruebas automáticas ni revisión visual hecha | Implementado, pendiente de verificación |
| **Copias en un destino externo** | En local se usó un repositorio de restic en disco | Implementado; copia, restauración y desastre simulado probados en local |
| **Sintaxis de los diagramas Mermaid** | No hay Node/npx en el equipo para `mermaid-cli` | Revisión estructural automática + revisión manual (ver la Etapa D en `_trabajo/progreso.md`) |

**Ya verificado** (antes figuraba aquí): el comportamiento en **PostgreSQL 17** (849 tests sin omitidos, en local, en el contenedor y en el CI), la **concurrencia real** con bloqueos de fila (17 tests con hilos en canjes, compras, ajustes, reservas, tokens de la API y la regla del último propietario) y la **programación de las tareas** (servicio `scheduler`).

## 2. Discrepancias encontradas (código frente a requisitos o documentación)

| # | Discrepancia | Evidencia | Valoración |
|---|---|---|---|
| 1 | El prompt de documentación supone 11 fases con el despliegue en la última; el despliegue quedó «sin número» y se numeró después como **Fase 12** | `docs/plan-de-fases.md`; `git log` | Documentado en la memoria, cap. 14.2 |
| 2 | Los documentos de las fases 0 a 7 usan la numeración antigua en sus referencias | `docs/plan-de-fases.md:75` | Conviene revisarlos antes de entregarlos |
| 3 | El plan pedía «CORS restrictivo»; se implementó **sin CORS** | `docs/fase-11-api-auditoria.md:155` | Decisión justificada y probada |
| 4 | `Purchase.Status.VOIDED`, `Purchase.Source.POS` y `external_reference` existen sin flujo | `apps/purchases/models.py:22-32, 66-72` | Planificado (reservado a propósito) |
| 5 | `Promotion.birthday_window_days` sin uso desde la Fase 10 | `apps/loyalty/models.py:187-192` | Deuda técnica menor (auditoría P3-11) |
| 6 | `CancelReservationForm` definido y no usado | `apps/events/forms.py:61-62` | Código muerto (auditoría P3-11) |
| 7 | La Fase 4 pedía 14 grifos; se implementó una imagen de la carta de grifos | Plan, ajuste de la F4 | Decisión del usuario |
| 8 | La bonificación de cumpleaños en la compra (F6) se sustituyó por un regalo el mismo día (F10) | Plan, ajuste de la F10; `promotions.py:116` | Decisión del usuario |
| 9 | Los hashes de las fases 10 y 11 cambiaron al reescribir el historial (P2-6): `a85ce95` → `b91d8bd` y `ac5903a` → `eec6abc` | `docs/auditoria-pre-fase-12.md` §11 | Corregido en la memoria; los documentos de `_trabajo/` conservan los antiguos |

## 3. Limitaciones actuales (alcance deliberado)

- No hay facturación, caja ni TPV: las **compras registradas no son la facturación** (`apps/purchases/selectors.py:1-9`).
- No hay SMS (no hay proveedor integrado; `apps/notifications/sms.py:4-10`).
- No hay app móvil (solo API y guía).
- Las reservas de **mesa no tienen aforo** (la confirmación es manual).
- Un precio por producto; la carta de grifos es una imagen.
- El dashboard no exporta informes.
- Un solo servidor, sin alta disponibilidad (Fase 12, D17).
- **Datos de demostración (Fase 13):**
  - los eventos y reservas "futuros" lo son respecto a la carga y envejecen (se refrescan con `--reset`);
  - no se generan compras anuladas, TPV, sesiones de la API ni notificaciones fallidas;
  - las imágenes de la demo comparten `media/` con la base original (`--clean` las retira);
  - con caché Redis y SQLite, varios `--reset` en menos de una hora pueden alcanzar el límite de reservas por hora (la carga se deshace sola).

  Ver [`../fase-13-datos-demo.md`](../fase-13-datos-demo.md) §10.

## 4. Funcionalidades incompletas

| Funcionalidad | Situación | Prioridad | Coste | Beneficio |
|---|---|---|---|---|
| Exportación y supresión de datos personales (derechos del interesado) | Decisión tomada (auditoría P2-9): al suprimir una cuenta se conservan las compras y los movimientos de puntos. Sin implementar; las cuentas se desactivan | **Alta** (antes de abrir al público) | M | Alto |
| Anulación de compras con compensación de puntos | Estado reservado `VOIDED`; el ledger ya tiene `reverse_movement` | Media | M | Alto |
| Integración con TPV | `POS` y `external_reference` reservados (con UNIQUE) | Baja | L | Alto |
| SMS | Canal preparado (`SMS_BACKEND`), sin proveedor | Baja | M | Medio |

## 5. Pendiente antes de producción

| Riesgo o tarea | Detalle | Prioridad | Coste | Beneficio |
|---|---|---|---|---|
| Acciones manuales en el VPS | Contratar y endurecer el servidor, DNS, `.env.prod` y `.env.backup`, primer despliegue con el certificado real ([Fase 12 §13](../fase-12-despliegue.md)) | **Alta** | S | Alto |
| SMTP real | Sin él no sale ningún email (verificación incluida); SPF, DKIM y DMARC del remitente | **Alta** | S | Alto |
| Destino externo de las copias y su programación en el host | `backup.sh run` diario y `restore.sh check` semanal | **Alta** | S | Alto |
| Monitorización y alertas | Solo healthcheck interno y logs: falta un comprobador externo, avisos de copias fallidas y Sentry | **Alta** | M | Alto |
| Revisión legal (RGPD) | Textos legales, base jurídica y conservación (las copias guardan datos personales 4 semanas) | Alta | M | Alto |
| Controles pospuestos de la auditoría | Content-Security-Policy (P3-6), borrar EXIF de las imágenes (P3-7), `List-Unsubscribe-Post` (P3-8) | Media | M | Medio |
| Clave de idempotencia regenerada al reenviar la identificación | Si el navegador reenvía el paso «identificar» (volver atrás), se genera una clave nueva y un segundo «Registrar» crearía **otra compra** legítima. El doble clic en «Registrar» sí está cubierto (misma clave + `app.js`). Auditoría P3-10 | Media | S | Medio |
| Duplicado en `recover_stale` | Si un proceso muere después de que el SMTP aceptara el mensaje, puede reenviarse (reconocido en `apps/notifications/services.py:306-312`) | Baja | M | Bajo |

**Resuelto desde la primera versión de este documento:**
- PostgreSQL validado.
- Límites de intentos comunes a todos los workers (producción exige caché compartida).
- Servidor WSGI, proxy con TLS, estáticos y medios (Docker Compose con Nginx y Gunicorn).
- Copias cifradas con restauración probada.
- Tareas programadas.
- CI.
- El interbloqueo de la regla del último propietario (R-1, refactorización final).

## 6. Mejoras recomendadas a medio plazo

| Mejora | Motivo | Prioridad | Coste | Beneficio |
|---|---|---|---|---|
| `pip-audit` en el CI | El CI ya ejecuta tests, `check --deploy`, OpenAPI y la pila; falta auditar las dependencias | Media | S | Alto |
| Medición de cobertura | No se puede afirmar un porcentaje | Media | S | Medio |
| Tests E2E del lector de QR (Playwright) | El JS no tiene pruebas | Media | M | Medio |
| 2FA para el propietario | Es la cuenta con más privilegios | Media | M | Alto |
| Saldo de puntos materializado | `ledger.balance()` hace `SUM` de todos los movimientos en cada escritura (auditoría P3-9) | Baja (a esta escala) | M | Medio con volumen |
| Auditoría inmutable en la BD (permisos o triggers) | Hoy la inmutabilidad depende de la aplicación | Baja | M | Medio |
| Servir Swagger UI localmente (`drf-spectacular-sidecar`) | `/api/v1/docs/` carga su JavaScript desde jsDelivr ([Fase 12 §14](../fase-12-despliegue.md)) | Baja | S | Bajo |
| Atar la clave de idempotencia a la sesión o firmarla | Cerrar el caso de la tabla anterior | Media | S | Medio |
| Limpiar la deuda menor (`birthday_window_days`, `CancelReservationForm`) | Claridad | Baja | S | Bajo |
| Actualizar la numeración antigua en los docs de las fases 0-7 | Coherencia documental | Baja | S | Bajo |
| Fijar imágenes base y acciones de GitHub por digest o SHA | Reproducibilidad total y cadena de suministro | Baja | S | Medio |

## 7. Ampliaciones futuras

- App Flutter sobre la API v1 (`docs/guia-app-flutter.md`).
- Integración con TPV y estadísticas de facturación real.
- Proveedor de SMS.
- Aforo de mesas y franjas horarias de reserva.
- Exportación de informes del dashboard.
