# Registro de actividades de tratamiento (art. 30 RGPD) — BORRADOR

> **Borrador para el asesor legal (Fase 25).** Recoge los tratamientos que hace el sistema tal como está programado. El titular y su asesor deben completarlo, revisar las bases legales y los plazos, y conservarlo actualizado. No es un documento firmado ni garantiza por sí mismo el cumplimiento.

**Responsable:** [pendiente: titular, NIF, domicilio, email de contacto] (se rellenan en Dashboard → Contenido → titular del sitio).
**Delegado de protección de datos:** [pendiente: indicar si se designa; normalmente no es obligatorio para un local de este tamaño].

| # | Tratamiento | Finalidad | Base legal | Interesados | Categorías de datos | Destinatarios / encargados | Plazo propuesto (ver `conservacion.md`) | Medidas |
|---|---|---|---|---|---|---|---|---|
| 1 | Cuentas de cliente y programa de puntos | Registro, compras con QR, puntos, canjes, cumpleaños | Contrato (condiciones del programa, art. 6.1.b) | Clientes mayores de edad | Identificativos (nombre, email), fecha de nacimiento, CP/localidad/país, opcionales (sexo, teléfono, dirección), compras, puntos, canjes | Hosting, proveedor de email | Mientras exista la cuenta; compras y puntos anonimizados tras la baja | Contraseñas con hash, roles, QR opaco, personal solo ve nombre abreviado |
| 2 | Comunicaciones promocionales | Campañas por email/SMS y aviso de cumpleaños | Consentimiento (art. 6.1.a; art. 21 LSSI-CE) | Clientes que lo aceptan | Email, teléfono, nombre, preferencias e historial de consentimiento | Proveedor de email; de SMS si se usa | Hasta la retirada del consentimiento; registro de envíos con plazo | Doble comprobación del consentimiento, enlace de baja, `List-Unsubscribe` |
| 3 | Avisos del servicio | Verificación de email, recuperación de contraseña, reservas, caducidad de puntos | Contrato | Clientes | Email, nombre | Proveedor de email | Registro de envíos con plazo | Tokens con hash y caducidad; sin enlaces en logs |
| 4 | Reservas de mesa | Gestionar reservas de eventos y mesas | Contrato / medidas precontractuales | Clientes | Nombre, contacto (de la cuenta), fecha, personas, notas | — | Notas con plazo tras la fecha | Consulta de datos de contacto auditada |
| 5 | Personal | Acceso al panel del personal y al dashboard | Relación laboral / interés legítimo | Empleados y propietario | Nombre, email, rol, actividad (compras registradas, canjes validados) | Hosting | Mientras dure la relación | Roles, auditoría |
| 6 | Seguridad y auditoría | Prevenir fraude, accesos indebidos y demostrar acciones | Interés legítimo (art. 6.1.f) | Todos los usuarios | IP en logs del servidor, eventos de auditoría (sin textos ni datos personales en `metadata`) | Hosting | Logs con rotación (10 MB × 5); auditoría con plazo | Logs sin tokens ni emails; IPs con retención limitada |
| 7 | Copias de seguridad | Recuperación ante incidentes | Interés legítimo / obligación de seguridad (art. 32) | Todos | Copia cifrada de la BD y de `media/` | Destino de restic [pendiente] | 7 diarias y 4 semanales | Cifrado de restic, acceso restringido |

**Transferencias internacionales:** [pendiente: depende de dónde estén el hosting, el proveedor de email y el destino de las copias].
**Decisiones automatizadas / perfiles:** no. Las estadísticas del dashboard son agregadas.
