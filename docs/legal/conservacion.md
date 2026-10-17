# Plazos de conservación — PROPUESTA (para la Fase 26)

> **Propuesta técnica (Fase 25), pendiente de que el asesor fije los plazos.** La Fase 26 los aplicará con un comando programado y plazos configurables por variables de entorno. Hasta entonces, nada de esto se purga automáticamente (salvo lo indicado como «ya automático»).

| Dato | Propuesta | Motivo | Estado |
|---|---|---|---|
| Cuenta y perfil del cliente | Mientras exista la cuenta | Necesarios para el programa | — |
| Perfil tras la baja | Anonimizar al momento (nombre, email, teléfono, dirección, fecha de nacimiento, sexo) | Supresión (art. 17); decisión P2-9 | Fase 26 |
| Compras y movimientos de puntos | Conservar sin datos personales | Explican saldos y operaciones; posibles obligaciones contables [pendiente: confirmar plazo] | Fase 26 (desligar del cliente al suprimir) |
| Historial de consentimientos | Mientras exista la cuenta + plazo de prescripción de reclamaciones [pendiente] | Demostrar el consentimiento | Fase 26 |
| Registro de notificaciones (a quién se envió) | 24 meses | Demostrar envíos y bajas sin guardar indefinidamente el destinatario | Fase 26 |
| Auditoría de consultas de datos personales (`CUSTOMER_DATA_VIEWED`, `RESERVATION_DATA_VIEWED`) | 24 meses | Responsabilidad proactiva con límite | Fase 26 |
| Resto de la auditoría (acciones administrativas sin datos personales) | Conservar | No contiene datos personales | — |
| Notas libres de reservas | Vaciar 12 meses después de la fecha de la reserva | Pueden contener datos personales | Fase 26 |
| Tokens de verificación y recuperación | Purga diaria | Ya automático (`purge_email_tokens`) | Hecho |
| Sesiones y tokens de la app | Purga diaria | Ya automático (`clearsessions`, `flushexpiredtokens`) | Hecho |
| Logs del servidor (IPs) | Rotación 10 MB × 5 por servicio | Ya automático (Docker) | Hecho |
| Copias de seguridad | 7 diarias y 4 semanales | Ya automático (restic) | Hecho |
| Imágenes sustituidas en `media/` | Borrar las huérfanas | No son datos personales; espacio | Fase 26 |
