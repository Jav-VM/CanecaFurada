# Encargados del tratamiento (art. 28 RGPD) — BORRADOR

> **Borrador para el asesor legal (Fase 25).** Lista los servicios externos que tratan datos personales por cuenta del titular según la configuración del proyecto. Con cada uno hace falta un contrato o unas condiciones de encargo (muchos proveedores las incluyen como «DPA» en sus términos).

| Servicio | Para qué lo usa la web | Datos a los que accede | Configuración | Proveedor |
|---|---|---|---|---|
| Alojamiento (servidor, base de datos PostgreSQL, `media/`) | Ejecutar la web y guardar los datos | Todos | `deploy/`, `docs/despliegue.md` | [pendiente] |
| Envío de emails (SMTP) | Verificación, avisos, campañas | Email, nombre y contenido de los mensajes | `EMAIL_HOST`, `EMAIL_HOST_USER`… (`.env`) | [pendiente] |
| SMS | Campañas por SMS (hoy no hay proveedor integrado: no se envían SMS) | Teléfono y texto | — | No aplica mientras no se integre |
| Copias de seguridad (restic) | Copias cifradas fuera del servidor | Copia cifrada de la BD y de `media/` | `docs/despliegue.md` | [pendiente] |
| Dominio / DNS | Resolución del dominio | Ninguno personal | — | [pendiente] |

**El contrato debe recoger como mínimo (art. 28.3):** objeto, duración, naturaleza y finalidad; tipo de datos y categorías de interesados; tratar solo siguiendo instrucciones; confidencialidad; medidas de seguridad; subencargados con autorización; ayuda con los derechos y las brechas; devolución o borrado al terminar; auditorías.

**No hay** analítica web, publicidad, redes sociales incrustadas ni CDN de terceros que reciban datos de los visitantes (comprobado en las plantillas).
