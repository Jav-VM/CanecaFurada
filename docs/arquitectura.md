# Arquitectura — Caneca Furada

Documento de referencia sobre la estructura modular, el modelo de usuario y la preparación del backend para la futura app móvil. Se actualiza cuando una fase cambia alguna de estas decisiones.

## 1. Monolito modular

Un único proyecto Django (`config/`) con una app por dominio en `apps/`. Reglas:

- **Lógica de negocio en servicios** (`apps/<dominio>/services.py`). Vistas web, admin, comandos, tareas y la futura API solo validan la entrada, comprueban permisos y llaman a servicios; no modifican modelos directamente en operaciones sensibles.
- **Permisos centralizados** en `apps/accounts/permissions.py` (`has_role`, `is_owner`, `is_staff_member`, `role_required`, `RoleRequiredMixin`). Las demás apps los reutilizan y no reimplementan comprobaciones de rol.
- **Dependencias en un solo sentido:** las apps de presentación (web, panel, dashboard, API) dependen de las de dominio, nunca al revés. `core` no depende de ninguna otra app.
- **Una app se crea cuando empieza su fase**, no antes: así no hay apps vacías en `INSTALLED_APPS` ni migraciones especulativas.

### Mapa de módulos

Es provisional y se revisa al empezar cada fase ([plan de fases](plan-de-fases.md)).

| App | Responsabilidad | Fase | Estado |
|---|---|---|---|
| `apps.core` | Modelos base (`TimeStampedModel`), auditoría (`AuditEvent`), limitador de intentos (`throttling`) e IP del cliente tras proxies de confianza (`http`, Fase 11); condición de periodo `[start, end)` común a los selectores (`querysets.period_q`, refactorización final) | 0 | Existe |
| `apps.accounts` | Usuario, roles, `CustomerProfile`, registro, verificación y cambio de email, preferencias de comunicación, login y contraseñas, servicios, permisos, `create_owner` | 0 (perfil: Fase 1; registro y datos: Fase 2) | Existe |
| `apps.web` | Páginas públicas, contenido del local (`content.py` y, desde la Fase 9, `BusinessInfo` editable con `services.py`) y context processor común; la plantilla base, los componentes y las páginas de error están en `templates/` | 3 (contenido editable: 9) | Existe |
| `apps.catalog` | Carta: categorías, estilos, productos (fijos y cervezas), imagen de la carta de grifos, selectores públicos y servicios de publicación/disponibilidad | 4 | Existe |
| `apps.loyalty` | Token QR del cliente (Fase 5); ledger de puntos, conversión, promociones y base de cumpleaños (Fase 6): `conversion`, `ledger` (única vía de escritura), `promotions`, `selectors` (lectura) | 5–6 | Existe |
| `apps.purchases` | Registro de compras manuales y panel del personal; `on_purchase_registered` genera los puntos en la misma transacción; `selectors` (historial del cliente y estadísticas de compras registradas) | 5–6 | Existe |
| `apps.rewards` | Catálogo de recompensas y canjes: `codes` (código de un solo uso), `services` (solicitud, validación, cancelación, caducidad), `selectors`; descuenta y devuelve puntos solo a través de `loyalty.ledger` | 7 | Existe |
| `apps.staff` | Panel del personal en `/panel/`: inicio, perfil del empleado y consulta de sus resultados; layout común de las pantallas de compras y canjes. Solo presentación, sin modelos | 8 | Existe |
| `apps.dashboard` | Dashboard del propietario en `/dashboard/`: resumen, clientes, estadísticas geográficas, empleados, compras, puntos, recompensas, carta, promociones, contenido y configuración. Solo presentación, sin modelos | 9 | Existe |
| `apps.events` | Eventos y reservas: `services` (única vía de escritura, transiciones y aforo), `selectors` (público, cliente, propietario). Depende de `accounts` y `notifications` | 10 | Existe |
| `apps.api` | API REST v1 en `/api/v1/` (solo presentación sobre los servicios): JWT, permisos DRF que envuelven `accounts.permissions`, serializadores explícitos, errores, paginación, throttling y OpenAPI | 11 | Existe |
| `apps.notifications` | Registro y envío de notificaciones (email; SMS opcional sin proveedor), cola con reintentos, campañas promocionales, enlace de baja. Infraestructura: no depende de dominios salvo `accounts` (consentimiento, importado en diferido porque `accounts` envía sus emails por aquí). El flujo de cumpleaños vive en `loyalty.birthdays` | 10 | Existe |

Los nombres son los previstos. Si una fase justifica separar o unir módulos, se cambia esta tabla en la misma tarea.

## 2. Usuario y perfil de cliente

### Decisión: perfil separado (`CustomerProfile` 1:1)

`accounts.User` contiene solo lo que comparten los tres roles: credencial (email), nombre, apellidos, rol y estado. Los datos personales propios del cliente (dirección, fecha de nacimiento, teléfono, preferencias de comunicación) van en `accounts.CustomerProfile`.

Motivos:
- **Minimización de datos:** propietarios y empleados no tienen dirección ni fecha de nacimiento; con campos en `User` serían columnas vacías y un riesgo de pedírselas o mostrarlas por error.
- **Exposición mínima:** las consultas de autenticación, permisos y paneles cargan `User` sin arrastrar datos personales; solo el código que los necesita accede al perfil.
- **Evolución:** el perfil crecerá (dirección estructurada, preferencias con historial) sin tocar el modelo de usuario, que es el más delicado de migrar.

Coste asumido: un `JOIN`/consulta extra al leer datos del cliente y la necesidad de garantizar que el perfil existe (ver abajo). Se considera menor que los beneficios.

Desde la Fase 1 el perfil existe; en la Fase 2 recibió sus campos (dirección estructurada, fecha de nacimiento, teléfono, consentimientos promocionales) y sus validaciones. Detalle en [fase-02-registro-perfil-verificacion.md](fase-02-registro-perfil-verificacion.md).

### Cómo se garantiza que todo cliente tiene perfil

1. **Servicios como única vía.** `services.ensure_customer_profile(user)` (idempotente, `get_or_create`) se ejecuta:
   - en el alta de cualquier cliente (`create_customer` y `create_user_by_owner` con rol `CUSTOMER`, que usa el admin);
   - al cambiar el rol de un usuario a `CUSTOMER` (`change_role`, usado por las acciones del admin).
2. **Transaccional.** Esas funciones están decoradas con `@transaction.atomic`: si la creación del perfil falla, el alta o el cambio de rol se revierte entero (hay un test que lo comprueba).
3. **Sin duplicados en BD.** `OneToOneField` crea una restricción `UNIQUE` sobre `user_id`.
4. **Datos existentes.** La migración `accounts/0003_backfill_customer_profiles` crea el perfil a los clientes dados de alta antes de existir el modelo. Es repetible y no toca a empleados ni propietarios.

Límites conocidos:
- La base de datos no puede exigir que exista una fila relacionada ("todo `CUSTOMER` tiene perfil") sin triggers específicos; la garantía la dan los servicios. Los atajos de bajo nivel (`User.objects.create_user`, SQL directo) no crean el perfil: solo se usan en tests y en migraciones.
- Al pasar de cliente a empleado o propietario **se conserva el perfil** con sus datos personales. La política de conservación y borrado está pendiente de decisión (ver [Fase 2](fase-02-registro-perfil-verificacion.md#10-limitaciones-riesgos-y-pendientes)).
- El código que lea el perfil en fases posteriores debe usar `ensure_customer_profile` (o tratar `CustomerProfile.DoesNotExist`) en lugar de suponer que `user.customer_profile` siempre existe.

## 3. Preparación para la app móvil

### Identificadores estables
- Toda entidad expuesta fuera del backend se identifica por un `public_id` UUID no secuencial (ya existe en `User`). La PK interna (`id`) no aparece en URLs, API, QR ni auditoría.
- El email no es un identificador: puede cambiar.
- El QR del cliente (Fase 5) usa un token opaco y rotable propio (`CF1:<token>`), no el `public_id` ni datos personales. Identifica, pero no autoriza: las operaciones exigen una sesión de personal y las validaciones de `apps/purchases/services.py`. Ver [Fase 5](fase-05-qr-compras.md).
- El perfil de cliente no tiene identificador propio: se accede siempre a través de su usuario (`/me/profile` en la API), nunca por ID, lo que evita IDOR.

### Independencia de las plantillas
- Validación de reglas de negocio en servicios y modelos, no en formularios ni plantillas. Los formularios web solo convierten la entrada; la API usará serializadores que llamen a los mismos servicios.
- Los servicios lanzan `ValidationError`/`PermissionDenied` de Django, que la web traduce a mensajes y la API a respuestas 400/403. `services.RateLimited` se traducirá a 429.
- Los servicios de cuentas no reciben `request` ni dependen de la sesión: actúan sobre un `user` ya autenticado (por sesión en la web o por token en la API). Los enlaces de los emails se construyen con `SITE_BASE_URL`. Operaciones de cuentas que necesitará la app: [Fase 2, §8](fase-02-registro-perfil-verificacion.md#8-preparación-para-la-app-móvil).

### Carta
- Reglas de visibilidad en `apps/catalog/selectors.py` y cambios de estado y disponibilidad en `apps/catalog/services.py`. La web y la futura API usan los mismos. Endpoints previstos: [Fase 4, §7](fase-04-carta.md#7-preparación-para-la-app-móvil-y-la-futura-api-fase-11).

### Puntos y promociones
- Escrituras solo por `apps/loyalty/ledger.py`; lecturas por `apps/loyalty/selectors.py` y `apps/purchases/selectors.py`. Los servicios reciben el cliente ya resuelto (el usuario autenticado), nunca un ID enviado por él. Endpoints previstos: [Fase 6, §8](fase-06-fidelizacion.md#8-preparación-para-la-app-y-la-api-fase-11).

### Recompensas y canjes
- Escrituras por `apps/rewards/services.py` (que usa `loyalty.ledger.spend_points`/`refund_spent_points` en la misma transacción); lecturas por `apps/rewards/selectors.py`. `rewards` depende de `loyalty`, nunca al revés: el movimiento del ledger no conoce el canje, es el canje quien enlaza sus movimientos. Los códigos viajan siempre en el cuerpo de la petición, nunca en la URL. Endpoints previstos: [Fase 7, §8](fase-07-recompensas-canjes.md#8-preparación-para-la-app-y-la-api-fase-11).

### Panel del personal
- `apps.staff` solo presenta: las escrituras siguen en `purchases.services` y `rewards.services`, y las lecturas propias del empleado están en `purchases.selectors` (`purchases_registered_by`, `staff_purchases_summary`) y `rewards.selectors` (`validations_by`), filtradas siempre por el usuario autenticado. Endpoints previstos: [Fase 8, §8](fase-08-panel-empleados.md#8-preparación-para-la-app).

### Dashboard del propietario
- `apps.dashboard` solo presenta. Las lecturas están en selectores de dominio que exigen un propietario (`accounts.selectors`, `purchases.selectors`, `loyalty.selectors`, `rewards.selectors`, `catalog.selectors`) y las escrituras en los servicios existentes. Los datos personales completos del cliente solo salen de `accounts.selectors.customer_for_owner`, y su consulta se audita. Endpoints previstos: [Fase 9, §5](fase-09-dashboard-propietario.md#5-separación-de-responsabilidades-y-preparación-para-la-app).

### Eventos, reservas y notificaciones
- Escrituras por `apps/events/services.py` y `apps/notifications/{services,campaigns}.py`; lecturas por sus `selectors`. Ninguna petición web envía campañas: lo hace el comando `process_notifications`. Los mensajes con token se envían al momento sin guardar su contexto. Endpoints previstos: [Fase 10, §10](fase-10-eventos-reservas-notificaciones.md#10-preparación-para-la-app-y-la-api-fase-11).

### Presentación web
- Sistema de diseño (tokens, componentes, Tailwind): [Fase 3](fase-03-sistema-diseno-web-publica.md). Las plantillas solo presentan; el JavaScript (`static/js/app.js`) es mejora progresiva sin reglas de negocio.

### API REST v1 (implementada en la Fase 11)

La API existe en `apps.api` y sigue las pautas de abajo. Detalle de endpoints, autenticación JWT, errores y seguridad: [fase-11-api-auditoria.md](fase-11-api-auditoria.md); guía para la app: [guia-app-flutter.md](guia-app-flutter.md). Diferencias con el plan original: la autenticación es JWT (simplejwt) con access corto, refresh rotatorio con lista negra y revocación inmediata al cambiar la contraseña; la idempotencia llega en la cabecera `Idempotency-Key`.

### Cómo se incorporó Django REST Framework (pautas originales)
1. Añadir `djangorestframework` con versión acotada a `requirements/base.txt` e incluirlo en `INSTALLED_APPS`.
2. Crear `apps.api` con rutas bajo `/api/v1/` (versión en la URL para poder convivir con versiones anteriores de la app).
3. Configurar `REST_FRAMEWORK` con, como mínimo: permiso por defecto `IsAuthenticated`, paginación, throttling (anónimo y por usuario) y renderizado JSON solamente.
4. Autenticación para móvil por token revocable (por ejemplo, `TokenAuthentication` de DRF o una librería mantenida de tokens/JWT); la elección se documenta en la Fase 11. Sin sesión ni cookies para la app.
5. Permisos DRF como envoltorio de las funciones existentes, sin duplicar lógica:
   ```python
   class HasRole(BasePermission):
       def has_permission(self, request, view):
           return has_role(request.user, *view.allowed_roles)
   ```
   Además, comprobación por objeto (`has_object_permission`) para cualquier recurso de un cliente.
6. Serializadores con lista explícita de campos (`fields = [...]`, nunca `__all__`), `lookup_field = "public_id"` y campos sensibles (rol, puntos, saldo, estado) de solo lectura.
7. CORS: la app nativa no lo necesita. Solo se añadiría `django-cors-headers` con una lista blanca si existiera un cliente web en otro dominio.
8. Tests de API: permisos, IDOR, asignación masiva y throttling.
