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
| `apps.core` | Modelos base (`TimeStampedModel`) y auditoría (`AuditEvent`) | 0 | Existe |
| `apps.accounts` | Usuario, roles, `CustomerProfile`, servicios de cuentas, permisos, `create_owner` | 0 (perfil: Fase 1; campos: Fase 3) | Existe |
| `apps.web` | Plantilla base, páginas públicas y páginas de error | 2 | Pendiente |
| `apps.catalog` | Carta: categorías, productos, cervezas y grifos | 4 | Pendiente |
| `apps.loyalty` | Ledger de puntos, configuración de conversión y token QR | 5 | Pendiente |
| `apps.purchases` | Registro de compras y panel de empleado (genera puntos mediante `loyalty`) | 6 | Pendiente |
| `apps.rewards` | Catálogo de recompensas y canjes | 7 | Pendiente |
| `apps.events` | Eventos y reservas | 8 | Pendiente |
| `apps.dashboard` | Panel del propietario y estadísticas (solo presentación) | 9 | Pendiente |
| `apps.notifications` | Registro y envío de notificaciones; promociones de cumpleaños | 10 | Pendiente |
| `apps.api` | API REST v1 (solo presentación sobre los servicios) | 11 | Pendiente |

Los nombres son los previstos. Si una fase justifica separar o unir módulos, se cambia esta tabla en la misma tarea.

## 2. Usuario y perfil de cliente

### Decisión: perfil separado (`CustomerProfile` 1:1)

`accounts.User` contiene solo lo que comparten los tres roles: credencial (email), nombre, apellidos, rol y estado. Los datos personales propios del cliente (dirección, fecha de nacimiento, teléfono, preferencias de comunicación) van en `accounts.CustomerProfile`.

Motivos:
- **Minimización de datos:** propietarios y empleados no tienen dirección ni fecha de nacimiento; con campos en `User` serían columnas vacías y un riesgo de pedírselas o mostrarlas por error.
- **Exposición mínima:** las consultas de autenticación, permisos y paneles cargan `User` sin arrastrar datos personales; solo el código que los necesita accede al perfil.
- **Evolución:** el perfil crecerá (dirección estructurada, preferencias con historial) sin tocar el modelo de usuario, que es el más delicado de migrar.

Coste asumido: un `JOIN`/consulta extra al leer datos del cliente y la necesidad de garantizar que el perfil existe (ver abajo). Se considera menor que los beneficios.

Desde la Fase 1 el perfil existe pero es **mínimo**: solo la relación con el usuario y las fechas de creación/modificación. Sus campos se añaden en la Fase 3 (registro), con sus validaciones.

### Cómo se garantiza que todo cliente tiene perfil

1. **Servicios como única vía.** `services.ensure_customer_profile(user)` (idempotente, `get_or_create`) se ejecuta:
   - en el alta de cualquier cliente (`create_customer` y `create_user_by_owner` con rol `CUSTOMER`, que usa el admin);
   - al cambiar el rol de un usuario a `CUSTOMER` (`change_role`, usado por las acciones del admin).
2. **Transaccional.** Esas funciones están decoradas con `@transaction.atomic`: si la creación del perfil falla, el alta o el cambio de rol se revierte entero (hay un test que lo comprueba).
3. **Sin duplicados en BD.** `OneToOneField` crea una restricción `UNIQUE` sobre `user_id`.
4. **Datos existentes.** La migración `accounts/0003_backfill_customer_profiles` crea el perfil a los clientes dados de alta antes de existir el modelo. Es repetible y no toca a empleados ni propietarios.

Límites conocidos:
- La base de datos no puede exigir que exista una fila relacionada ("todo `CUSTOMER` tiene perfil") sin triggers específicos; la garantía la dan los servicios. Los atajos de bajo nivel (`User.objects.create_user`, SQL directo) no crean el perfil: solo se usan en tests y en migraciones.
- Al pasar de cliente a empleado o propietario **se conserva el perfil**. Hasta la Fase 3 no tiene datos personales; la política de conservación o borrado de esos datos se decide en la Fase 3.
- El código que lea el perfil en fases posteriores debe usar `ensure_customer_profile` (o tratar `CustomerProfile.DoesNotExist`) en lugar de suponer que `user.customer_profile` siempre existe.

## 3. Preparación para la app móvil

### Identificadores estables
- Toda entidad expuesta fuera del backend se identifica por un `public_id` UUID no secuencial (ya existe en `User`). La PK interna (`id`) no aparece en URLs, API, QR ni auditoría.
- El email no es un identificador: puede cambiar.
- El QR del cliente (Fase 5) usará un token opaco y rotable propio, no el `public_id` ni datos personales.
- El perfil de cliente no tiene identificador propio: se accede siempre a través de su usuario (`/me/profile` en la API), nunca por ID, lo que evita IDOR.

### Independencia de las plantillas
- Validación de reglas de negocio en servicios y modelos, no en formularios ni plantillas. Los formularios web solo convierten la entrada; la API usará serializadores que llamen a los mismos servicios.
- Los servicios lanzan `ValidationError`/`PermissionDenied` de Django, que la web traduce a mensajes y la API a respuestas 400/403.

### Cómo incorporar Django REST Framework (Fase 11)
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
