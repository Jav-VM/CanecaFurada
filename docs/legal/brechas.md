# Procedimiento ante brechas de seguridad (arts. 33 y 34 RGPD) — BORRADOR

> **Borrador para el asesor legal (Fase 25).** Qué hacer si se pierden, se roban o se exponen datos personales (por ejemplo: acceso no autorizado al servidor o al panel, filtración de la base de datos o de una copia, envío de datos a quien no corresponde).

## 1. Detectar y contener (en cuanto se sepa)
- Cortar el acceso: cambiar las contraseñas del propietario y del servidor (cambiar la contraseña cierra las demás sesiones web), desactivar las cuentas comprometidas (Dashboard → Empleados o admin). Para la app, los tokens de una cuenta se revocan al cambiar su contraseña desde la app o con «cerrar todas las sesiones» (`apps/api/tokens.revoke_all_tokens`). Rotar `DJANGO_SECRET_KEY` invalida todas las sesiones web y los enlaces de recuperación pendientes.
- Conservar evidencias: logs del servidor y de Nginx, eventos de auditoría (admin → Auditoría), fecha y hora.
- Si el problema es una vulnerabilidad del código, corregirla y desplegar antes de reabrir.

## 2. Evaluar el riesgo
- Qué datos (identificativos, fecha de nacimiento, teléfono, dirección, historial de compras), de cuántas personas y si estaban cifrados (las contraseñas lo están con hash; las copias de restic, cifradas).
- Si es improbable que suponga un riesgo para las personas, se registra y no se notifica.

## 3. Notificar
- **A la AEPD**, en **72 horas** desde que se conoce, si hay riesgo: sede electrónica de la AEPD (formulario de notificación de brechas).
- **A los afectados**, sin dilación, si el riesgo es **alto**: qué ha pasado, qué datos, qué se ha hecho y qué pueden hacer (por ejemplo, cambiar su contraseña). Se puede usar el email de la web.

## 4. Registrar (siempre, aunque no se notifique)

| Fecha | Qué pasó | Datos y personas afectadas | Medidas tomadas | ¿Notificada a la AEPD? | ¿A los afectados? |
|---|---|---|---|---|---|
| | | | | | |

**Contacto interno responsable:** [pendiente].
