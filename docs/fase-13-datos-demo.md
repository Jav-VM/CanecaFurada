# Fase 13 — Datos de demostración (`seed_demo_data`)

**Estado:** Completa (2026-10-16).

> **Solo desarrollo.** Las cuentas y la contraseña de este documento son ficticias e inseguras. El comando no existe en producción: la app `apps.demo` no está instalada en `config.settings.prod`.

## 1. Objetivo, alcance y exclusiones

**Objetivo:** un conjunto de datos ficticio, coherente y reproducible que pueble todas las áreas implementadas. Sirve para probar a mano cada rol, desarrollar nuevas funcionalidades y preparar demostraciones, sin riesgo para producción.

**Alcance:**
- comando `python manage.py seed_demo_data` con `--reset`, `--clean`, `--reference-date` y `--noinput`;
- app solo de desarrollo `apps.demo` (sin modelos ni migraciones);
- tests en `tests/demo/`;
- esta documentación.

**Exclusiones (decididas el 2026-10-16):**

| No se crea | Motivo |
|---|---|
| `BusinessInfo` (dirección, horario, redes del local) | El proyecto prohíbe inventar datos del negocio (Fase 3); la web los sigue mostrando como pendientes. Decisión del usuario. |
| Compras `VOIDED` y origen `POS` | Están reservados en el modelo, pero no hay ningún servicio que los use. No se simulan. |
| Tokens JWT de la API (`OutstandingToken`) | Las sesiones de la app se crean al iniciar sesión; los tests de la API ya los cubren. |
| Notificaciones `FAILED` y SMS enviados | No hay proveedor de SMS, y forzar fallos exigiría saltarse el servicio. Los avisos SMS quedan `SKIPPED`. |
| Datos inválidos | No se cargan nunca: los casos negativos son tests (§8). |

Sin cambios en modelos, migraciones, reglas de negocio, contratos de la API ni `config/settings/base.py`/`prod.py`. Sin dependencias nuevas.

## 2. Decisiones técnicas

| Decisión | Motivo |
|---|---|
| **App `apps.demo` solo en `dev.py` y `test.py`** | Es la primera barrera: con `config.settings.prod` el comando no existe (`Unknown command`). |
| **Guarda del módulo de configuración cargado** (`guard.py`) | Solo acepta `config.settings.test`, o `config.settings.dev` con `DEBUG=True`. No se fía de una variable suelta: lee el módulo de configuración realmente cargado, también bajo `override_settings`. |
| **Todo por los servicios reales** | El registro, la verificación por enlace, el QR, las compras, el ledger, los canjes, los eventos, las reservas y las campañas pasan por los mismos servicios que la web. No se escriben saldos, estados ni hashes a mano, y se generan la auditoría y las notificaciones reales. |
| **Reloj simulado** (`clock.py`, decisión del usuario) | Las compras, los puntos y los canjes guardan la hora actual, y algunas reglas dependen de ella (confirmar exige una reserva futura, publicar exige un evento no empezado, los canjes caducan a 30 días). El comando parchea `django.utils.timezone.now` **solo durante la carga** y ejecuta cada paso en su fecha. Así el historial cumple todas las reglas y el ledger se escribe en orden cronológico. |
| **Excepciones al reloj** | `User.date_joined` y `CommunicationPreferenceChange.created_at` usan `default=timezone.now`, que se resolvió al importar el modelo. Se fijan con un `update()` justo después de crearlos. No se modifica ninguna fila del ledger. |
| **Base de datos sin datos ajenos** (decisión del usuario) | La carga aborta si hay usuarios fuera de `@demo.example.com` o filas de la carta, eventos, recompensas, promociones, reglas, campañas o cartas de grifos que no sean de demo. Así nunca se mezclan los datos, y `create_owner` (que solo crea el primer propietario) funciona. |
| **Sin transacción global** | Cada servicio confirma su transacción y los `on_commit` (emails, avisos) ocurren en su fecha. Si un paso falla, el comando ejecuta la limpieza y avisa: nunca queda una carga a medias. |
| **Correo en memoria durante la carga** | `EMAIL_BACKEND=locmem` y `SMS_BACKEND=""` mientras dura el comando. No sale ningún email, ni siquiera a la consola, donde se verían enlaces con tokens. |
| **Fechas relativas a una referencia** | `--reference-date`, por defecto hoy en `Europe/Madrid`. El contenido es determinista para una misma referencia; los importes salen de un `random.Random` con semilla fija por cliente. Los identificadores (UUID, token QR, códigos de canje) son aleatorios, como en producción. |

**Marcas que identifican los datos de demo** (`apps/demo/selectors.py`):

| Datos | Marca |
|---|---|
| Usuarios (y todo lo que cuelga de ellos) | email `@demo.example.com` (dominio reservado, RFC 2606) |
| Categorías | slug `demo-…` |
| Productos, eventos, recompensas, promociones, campañas | `public_id` determinista (`uuid5` con un espacio de nombres propio) |
| Reglas de conversión, carta de grifos | prefijo `[DEMO]` en la nota o el título |
| Estilos de cerveza | lista `data.STYLE_NAMES` (se borran solo si quedan sin uso) |

## 3. Archivos

| Archivo | Contenido |
|---|---|
| `apps/demo/__init__.py`, `apps.py` | App sin modelos. |
| `apps/demo/data.py` | Datos ficticios declarativos (personas, carta, promociones, recompensas, canjes, eventos, reservas, campañas) y marcas. |
| `apps/demo/builder.py` | Traduce los escenarios en pasos fechados que llaman a los servicios y los ejecuta en orden con el reloj simulado. |
| `apps/demo/clock.py` | Reloj simulado (patch de `timezone.now`, solo hacia delante). |
| `apps/demo/guard.py` | Comprobación del entorno y etiqueta de la BD (motor y nombre, sin credenciales). |
| `apps/demo/selectors.py` | Qué es dato de demo, datos ajenos y recuentos. |
| `apps/demo/cleanup.py` | Limpieza atómica de lo identificable como demo. |
| `apps/demo/images.py` | Imágenes de relleno generadas con Pillow, sin descargas. |
| `apps/demo/management/commands/seed_demo_data.py` | Comando. |
| `config/settings/dev.py`, `config/settings/test.py` | `INSTALLED_APPS += ["apps.demo"]`. |
| `tests/demo/test_seed_demo_data.py` | 18 tests. |
| `pruebas_dev/pruebas.md` | Guía de órdenes de prueba en desarrollo (§4.2). |

No hay migraciones, modelos, rutas ni plantillas nuevos, ni variables de entorno obligatorias. Hay una opcional: `CANECA_DEMO_PASSWORD`, que sustituye la contraseña de las cuentas demo.

## 4. Uso

```powershell
# 1. Una BD solo para la demo (recomendado). Ejemplo con SQLite:
$env:DATABASE_URL = "sqlite:///pruebas_dev/demo.sqlite3"   # ignorado por Git
python manage.py migrate
# 2. Cargar (pide confirmación; --noinput para no preguntar)
python manage.py seed_demo_data
python manage.py runserver
```

Con PostgreSQL, crea una base de datos aparte (p. ej. `caneca_demo`) y apunta `DATABASE_URL` a ella. Si la BD de desarrollo habitual tiene datos propios, el comando se niega a cargar y lo explica.

| Orden | Efecto |
|---|---|
| `seed_demo_data` | Carga los datos. Si ya hay datos de demo, no cambia nada y muestra el resumen (idempotente). |
| `seed_demo_data --reset` | Borra los datos de demo y vuelve a cargarlos. Sirve para refrescar las fechas: lo "futuro" lo es respecto al momento de la carga. |
| `seed_demo_data --clean` | Solo borra los datos de demo. |
| `--reference-date 2026-10-01` | Fecha de referencia (no futura). |
| `-v 2` | Muestra también los logs de cada operación (solo identificadores públicos). |

Al terminar, el comando muestra:
- los recuentos por entidad;
- la tabla de cuentas (email, rol y estado).

Nunca muestra la contraseña, los tokens QR ni los códigos de canje.

**Nunca** se ejecuta automáticamente: no está en `migrate`, en el arranque, en `deploy.sh`, en el `Dockerfile` ni en Compose (un test lo comprueba). Con la pila Docker local (`config.settings.prod`) no existe.

### 4.1 Cerrar la versión de pruebas y volver a la original

La demo vive en otra base de datos: la original (la `DATABASE_URL` del `.env`) no se toca en ningún momento.

1. **Detén el servidor** de pruebas con `Ctrl+C`.
2. **(Opcional) Borra la demo**, todavía apuntando a la base de pruebas. Las imágenes de demo están en la carpeta `media/` del proyecto, que comparten las dos bases:
   ```powershell
   python manage.py seed_demo_data --clean --noinput
   ```
3. **Quita la variable**, que tiene prioridad sobre el `.env` (o cierra la terminal):
   ```powershell
   Remove-Item Env:DATABASE_URL
   ```
4. **Comprueba** a qué base apuntas. Debe salir la del `.env` (p. ej. `postgresql caneca_furada`):
   ```powershell
   python manage.py shell -c "from django.db import connection; print(connection.vendor, connection.settings_dict['NAME'])"
   ```
5. **Arranca la original** (`python manage.py runserver`) y **vuelve a iniciar sesión**: la sesión del navegador pertenecía a la otra base.

Para volver a la demo, define otra vez `$env:DATABASE_URL`. Si la borraste, ejecuta `migrate` y `seed_demo_data`.

### 4.2 Guía de pruebas de desarrollo

[`pruebas_dev/pruebas.md`](../pruebas_dev/pruebas.md) reúne todas las órdenes para probar sin afectar al proyecto:
- base de pruebas en SQLite o PostgreSQL;
- servidor en otro puerto;
- tareas programadas y Mailpit;
- consultas de solo lectura;
- tests y comprobaciones del CI;
- pila Docker local;
- cierre y eliminación de todo rastro.

Los ficheros de prueba (`pruebas_dev/*.sqlite3`) los ignora Git.

## 5. Cuentas de demostración

**Contraseña de todas:** `Demo-Caneca-2026`, salvo que se defina `CANECA_DEMO_PASSWORD`. **Solo desarrollo, insegura.**

| Rol | Email | Para probar |
|---|---|---|
| Propietario | `propietaria@demo.example.com` | Dashboard completo, admin, gestión de reservas y campañas. |
| Empleado | `brais.empregado@demo.example.com` | Panel `/panel/`: escaneo, compras, validación de canjes, resultados. |
| Empleado | `uxia.empregada@demo.example.com`, `iago.empregado@demo.example.com` | Ídem, con otros resultados. |
| Empleado inactivo | `noa.empregada@demo.example.com` | Una cuenta dada de baja no inicia sesión. |
| Cliente habitual | `lua.proba@demo.example.com` | Saldo, QR renovado, canje pendiente, reservas activas, opt-in de email y SMS. |
| Cliente con muchos puntos | `martin.exemplo@demo.example.com` | Compra de 1000 € (máximo), tres canjes usados, la camiseta agotada. |
| Cliente con canje caducado / ajuste | `xoan.proba@demo.example.com` | Canje caducado con devolución, ajuste +50, solicitud pendiente que superaría el aforo. |
| Cliente con canje cancelado | `carme.ficticia@demo.example.com` | Cancelación con devolución de puntos. |
| Cliente con cumpleaños | `breixo.proba@demo.example.com` | Regalo de cumpleaños de hace 20 días, con aviso por email. |
| Cliente con ajuste compensado | `daniel.ficticio@demo.example.com` | Ajuste y compensación, opt-in de SMS (sin proveedor: `SKIPPED`). |
| Saldo insuficiente | `tiago.exemplo@demo.example.com`, `maria.ficticia@demo.example.com` | No alcanzan la recompensa más barata. María: compra de 0,99 € sin puntos base. |
| Sin compras, saldo 0 | `hugo.proba@demo.example.com` | Cliente verificado sin historial. |
| Cliente inactivo | `noelia.exemplo@demo.example.com` | Su QR ya no identifica a nadie; no inicia sesión. |
| Pendientes de verificar | `xiana.pendente@…` (registrada 1 h antes de la carga, enlace vigente), `uxio.pendente@…` (caducado), `lois.pendente@…` (reenvío: el primero revocado) | Sin QR, puntos, canjes ni reservas. El valor del enlace no se conserva: para verificar se pide un reenvío y el email sale por el backend de desarrollo. |

Del resto de clientes (`sabela`, `roi`, `iria`, `anxo`, `alba`, `olalla`, `antia`, `pablo`, `nerea`), todos `@demo.example.com`:
- tienen historiales variados;
- residen en distintos códigos postales de A Coruña, Arteixo, Oleiros, Culleredo, Lugo y Braga (PT), para las estadísticas por zonas.

## 6. Datos y escenarios

Recuentos reales de una carga (referencia 16/10/2026). Los "aprox." dependen de la referencia: los cumpleaños que coinciden con ese día y las ventanas de las promociones.

| Entidad | Nº | Escenarios |
|---|---|---|
| Propietario / empleados / clientes | 1 / 4 / 22 | Verificados, 3 pendientes, 2 cuentas inactivas, antigüedad de 1 a 13 meses, perfiles completos y sin campos opcionales, 29 de febrero, opt-in y baja del consentimiento con historial. |
| Categorías / productos | 6 / 18 | Una categoría oculta. Cervezas propias, invitadas y rotativas, y productos fijos. Publicados, borradores y uno archivado; 2 agotadas; 3 destacadas; con y sin imagen. |
| Carta de grifos | 1 | Publicada, con texto alternativo. |
| Reglas de conversión | 2 | 1,00 pt/€ desde hace 410 días; 1,50 desde hace 60. |
| Promociones | 5 | Bienvenida (un uso por cliente), puntos dobles finalizada, «martes» pausada, borrador futuro, cumpleaños activa. |
| Compras | 61 aprox. | Durante 13 meses, por los distintos empleados y la propietaria; importes de 0,99 € a 1000 €. |
| Movimientos de puntos | 107 aprox. | Las seis clases: compra, promoción, ajuste, compensación, canje, regalo de cumpleaños. |
| Recompensas | 7 | Activas con y sin límite, agotada (stock 0), pausada, borrador y archivada. |
| Canjes | 9 | 5 usados, 2 pendientes, 1 cancelado y 1 caducado (los dos últimos con devolución). |
| Eventos | 9 | Futuros publicados (con y sin reservas, destacados, con y sin imagen), uno con 9 de 10 plazas confirmadas, un borrador futuro, tres pasados archivados y uno pasado aún publicado. |
| Reservas | 25 | Las cinco situaciones: pendiente, confirmada, rechazada, cancelada (por el cliente y por el local) y completada. Además: una confirmada pasada sin completar, mesas y eventos, y un grupo de 20 personas (máximo). |
| Campañas | 3 | Borrador, cancelada y repartida a los 6 clientes con consentimiento vigente. |
| Notificaciones | 105 aprox. | Verificación, avisos de reservas (cliente y propietaria), campaña, cumpleaños. |
| Auditoría | la que generan los servicios | Altas, verificaciones, cambios de estado, ajustes, validaciones... |

**Coherencia garantizada:**
- **Saldos:** cada saldo es la suma de sus movimientos y coincide con `balance_after`, que nunca es negativo.
- **Compras:** una acumulación por compra como máximo.
- **Canjes:** los cerrados tienen su devolución.
- **Aforo:** ninguno superado.
- **Límites de reservas:** como máximo 3 activas por cliente y una activa por cliente y evento.
- **Fechas:** ninguna está en el futuro de la hora real.

## 7. Seguridad y privacidad

- **Datos personales:** ningún dato real. Nombres con «Proba», «Exemplo» o «Ficticio», calles «Rúa Ficticia N», emails del dominio reservado `demo.example.com`, teléfonos del rango ficticio que ya usan los tests (`600 000 0xx`). Los códigos postales son reales, pero no identifican a nadie.
- **Roles:** exactamente un propietario. `is_staff`/`is_superuser` solo en él, derivados por `_apply_role_flags`.
- **Contraseñas:** se crean con `set_password` (validadores incluidos) a través de los servicios; nunca se escriben hashes.
- **Verificación:** se consume el enlace real (`confirm_email_token`), sin ningún atajo que pueda usarse en producción. En la BD solo quedan hashes SHA-256 de los tokens.
- **Salida del comando:** sin contraseñas, tokens QR, códigos de canje, enlaces ni datos personales más allá del email ficticio de cada cuenta.
- **Ningún email sale del proceso.**
- **Limpieza:** atómica y solo sobre datos identificables como demo. Si un dato ajeno depende de uno de demo (p. ej. una compra registrada a un cliente real por un empleado demo), **no borra nada** y lo explica.
- **Historiales:** la limpieza es la única excepción a «no se borran historiales», porque retira un conjunto ficticio completo, no corrige datos reales.

## 8. Fixtures frente a tests negativos

- **Datos de demo:** solo contienen datos válidos. Ninguno incumple una restricción; se crean por los servicios.
- **Tests negativos:** intentan operaciones inválidas **sobre los datos cargados** y comprueban el rechazo:
  - validar dos veces un código usado;
  - canjear con saldo insuficiente;
  - confirmar una reserva por encima del aforo;
  - cancelar el canje de otro cliente;
  - una segunda reserva activa en el mismo evento;
  - una compra con el QR de una cuenta inactiva;
  - el QR de un cliente sin verificar;
  - un empleado que intenta ajustar puntos.
- **Concurrencia, doble envío e idempotencia:** siguen cubiertos por sus tests específicos sobre PostgreSQL (`tests/*/test_concurrency.py`). Los datos de demo no los sustituyen.

## 9. Tests

`tests/demo/test_seed_demo_data.py`: 18 tests. La carga usa `TransactionTestCase`, porque la verificación lee el enlace enviado al confirmar la transacción.

| Grupo | Comprueba |
|---|---|
| Guardas (7) | Rechazo con prod, con un módulo desconocido y con dev y `DEBUG=False`; fecha futura; app ausente de `base.py`/`prod.py`; el comando no aparece en `Dockerfile`, Compose ni `deploy/`. |
| Precondición (1) | Con un usuario ajeno, aborta sin crear nada. |
| Carga (10) | Recuentos mínimos por área, roles y privilegios, perfiles, QR, tokens solo como hash y sin enlaces vigentes en los verificados, salida sin secretos, saldos = ledger, todos los estados, idempotencia y `--reset`, limpieza que respeta datos ajenos y borra los ficheros, limpieza bloqueada por dependencias ajenas, escenarios negativos. |

```powershell
python manage.py test tests.demo --settings=config.settings.test   # SQLite o la DATABASE_URL del .env
```

**Resultados reales (2026-10-16):**

| Ejecución | Resultado |
|---|---|
| `tests.demo` en SQLite | 18 tests OK (14,6 s). |
| `tests.demo` en PostgreSQL 17 local | 18 tests OK (29,4 s). |
| Suite completa en PostgreSQL 17 (`--parallel 1`) | **867 tests OK** (849 previos + 18 nuevos), sin omitidos (70,8 s). |
| Suite completa en SQLite | **867 tests OK** (34,7 s); 18 omitidos, los de concurrencia ya existentes que solo corren en PostgreSQL. Los 18 de demo se ejecutan. |
| `check` y `makemigrations --check --dry-run` | Sin problemas; sin cambios. |
| `spectacular --validate --fail-on-warn` | Esquema idéntico a `docs/api/openapi.yaml`. |
| `seed_demo_data` con `config.settings.prod` | `Unknown command: 'seed_demo_data'`. |

**Manual (BD SQLite temporal, fuera del repositorio):**
- **Carga:** 204 operaciones en unos 15 s.
- **Repetición:** sin cambios.
- **`--reset`:** recarga y borra las imágenes anteriores.
- **Páginas:**
  - públicas: inicio con destacados, carta con «Agotada» y sin productos ocultos ni borradores, eventos, recompensas;
  - dashboard: todas las secciones;
  - panel del empleado;
  - páginas del cliente.

  Todas responden 200 con su rol, y 403 a un cliente sin verificar en «Mis puntos».

## 10. Limitaciones y riesgos

- **Envejecimiento:** los eventos y las reservas "futuros" lo son respecto a la carga. Pasados unos días, conviene `--reset`. `xiana.pendente` se registra una hora antes de la carga: su enlace caduca unas 23 h después (con una `--reference-date` pasada, ya está caducado).
- **Reloj simulado:** parchea `django.utils.timezone.now`. Un código que importara `now` directamente (`from django.utils.timezone import now`) o usara `Now()` en SQL no lo vería; hoy no hay ninguno en `apps/` (comprobado). Si se añade, la carga fallaría al validar o daría fechas reales, nunca datos inválidos.
- **Límites anti-abuso en caché:** las solicitudes de reserva se cuentan por cliente y hora en la caché. Con una caché compartida (Redis) y SQLite, que reutiliza ids tras borrar, varios `--reset` en menos de una hora podrían alcanzar el límite y la carga se desharía. Con la caché en memoria por defecto no ocurre.
- **Restos tras la limpieza:**
  - los eventos de auditoría agregados sin actor ni objetivo (`BIRTHDAY_PROMOTIONS_RUN`), que no contienen datos personales;
  - las sesiones web de las cuentas demo, que caducan solas.
- **Estado de las notificaciones:** las de la demo figuran como `SENT` porque el backend en memoria las aceptó, aunque no salió ningún correo.
- **BD de desarrollo del usuario:** no se ha cargado ninguna demo en ella; se probó en BD temporales y en las BD de test.

## 11. Criterios de aceptación

| Criterio | Estado |
|---|---|
| Datos en todas las áreas implementadas relevantes | Cumplido (salvo las exclusiones de §1) |
| Relaciones coherentes | Cumplido (tests de ledger, estados y aforo) |
| Carga reproducible e idempotente | Cumplido (determinista por referencia; repetir no cambia nada; `--reset`) |
| Escenarios de cada rol | Cumplido (§5, prueba de humo por rol) |
| Fidelización cuadra con sus movimientos | Cumplido (test de saldos) |
| Sin datos personales reales | Cumplido |
| No se ejecuta automáticamente en producción | Cumplido (app no instalada, guarda y test de despliegue) |
| Instrucciones de carga y prueba | Cumplido (§4, §9) |
| Pruebas ejecutadas y reportadas | Cumplido (§9) |

**Dependencias para siguientes fases:** ninguna. Si se añade un modelo o un estado nuevo:
1. hay que añadir su escenario en `data.py` y `builder.py`;
2. si cuelga de algo que no sea un usuario demo, también su marca en `selectors.py` y su paso en `cleanup.py`.
