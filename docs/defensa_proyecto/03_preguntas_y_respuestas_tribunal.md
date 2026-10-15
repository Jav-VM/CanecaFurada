# Caneca Furada — Banco de preguntas del tribunal (cap. 18)

Respuestas basadas en el código de la versión congelada (commit `d0bac7c`, 15-10-2026), que incluye la migración a PostgreSQL, la auditoría previa a la Fase 12, la Fase 12 y la refactorización final. Dificultad: 🟢 básica · 🟡 media · 🔴 difícil. Cuando un control **no existe**, se dice y se propone una solución.

---

## A. Conceptos generales

**1. 🟢 ¿Qué es Caneca Furada en una frase?**
La web de una cervecería con un programa de fidelización completo (QR, compras, puntos y canjes), un panel para el personal, un dashboard para el propietario, eventos y reservas, y una API REST para una futura app. Todo en Django.

**2. 🟢 ¿Quiénes son los usuarios?**
Visitantes anónimos y tres roles definidos en el enumerado `User.Role` (`apps/accounts/models.py:34-37`) y guardados en el campo `role` (`:45-47`): `CUSTOMER`, `EMPLOYEE` y `OWNER`. Cada uno tiene permisos distintos, comprobados en el servidor (memoria, cap. 2.2).

**3. 🟢 ¿Qué aporta frente a una web informativa?**
Estado de negocio con reglas (saldo, canjes de un solo uso, reservas con aforo), autorización por rol, integridad transaccional y trazabilidad. Una web informativa solo muestra contenido.

**4. 🟡 ¿Qué queda fuera del alcance?**
Facturación y caja (las compras registradas **no** son la facturación, `apps/purchases/selectors.py:1-9`), SMS (sin proveedor), TPV y anulación de compras (reservados), app móvil, monitorización y exportación o borrado de datos a petición. El despliegue está preparado y probado en local, pero no hecho en un servidor real.

## B. Arquitectura

**5. 🟢 ¿Qué patrón arquitectónico usaste?**
Monolito modular Django con capa de servicios: las vistas traducen HTTP, los servicios aplican permisos, validación, transacción y auditoría, y los selectores hacen las lecturas con permisos. Doce apps con responsabilidades separadas (`config/settings/base.py:40-53`).

**6. 🟡 ¿Por qué no microservicios?**
Para un local, un monolito es más sencillo de operar, permite transacciones locales (compra + puntos en una sola transacción) y evita la consistencia eventual. La modularidad interna (apps con dependencias claras) deja abierta una separación futura.

**7. 🟡 ¿Dónde está la lógica de negocio y por qué no en las vistas?**
En `services.py`, `ledger.py`, `promotions.py` y `campaigns.py`. Así la web, el admin, los comandos y la API llaman al mismo código: p. ej. `register_purchase` lo usan `purchases/views.py:95` y `api/views/staff.py:51`. Si estuviera en las vistas, habría que duplicarlo en la API.

**8. 🟡 ¿Qué diferencia hay entre un servicio y un selector?**
El servicio **escribe** (transacción y auditoría); el selector **solo lee** y encapsula las reglas de visibilidad o los permisos (p. ej. `catalog.selectors.public_products` decide qué es público para la web y para cualquier otro consumidor).

**9. 🔴 ¿Hay dependencias circulares entre módulos?**
Dos dependencias mutuas: `accounts ↔ notifications` (los emails de cuentas usan el servicio de notificaciones y este consulta el consentimiento en `accounts`; se resuelve con una importación diferida en `apps/notifications/services.py:208-209`) y `loyalty ↔ purchases` (FK por cadena `"purchases.Purchase"` y un selector en una vista). Funcionan, pero son un punto de acoplamiento; se podrían romper con un módulo de eventos de dominio o invirtiendo la dependencia.

**10. 🟢 ¿Cómo viaja una petición?**
Navegador → middleware (sesión, CSRF, autenticación) → `config/urls.py` → vista con decoradores (rol y método) → formulario → servicio (transacción) → ORM → BD → redirección o plantilla. Diagrama `03_ciclo_peticion.mmd`.

## C. Django y ORM

**11. 🟢 ¿Por qué Django?**
Por sus «baterías incluidas»: ORM, migraciones, autenticación, CSRF, admin y plantillas; versión 5.2 LTS; seguridad por defecto. El admin le da al propietario una gestión completa sin programar.

**12. 🟡 ¿Para qué sirve `select_related` y dónde lo usas?**
Hace un JOIN para no lanzar una consulta por cada objeto (el problema N+1). P. ej. `purchases/selectors.py:113` carga el cliente y el empleado de cada compra del listado.

**13. 🟡 ¿Qué hace `select_for_update`?**
`SELECT ... FOR UPDATE`: bloquea las filas hasta el final de la transacción. Lo uso para serializar las operaciones del mismo cliente (`ledger._lock_customer`, `ledger.py:63-64`) y para que dos validaciones del mismo canje no se pisen. En SQLite no hay bloqueo de fila real (bloquea la BD entera); por eso hace falta probar con PostgreSQL.

**14. 🟡 ¿Por qué `ATOMIC_REQUESTS = False`?**
Para controlar las transacciones explícitamente en los servicios (`base.py:98`): solo se abren donde hacen falta y con el alcance justo (p. ej. enviar el email **después** del commit con `on_commit`).

**15. 🔴 ¿Para qué el `atomic()` anidado en `register_purchase`?**
Es un savepoint: si `Purchase.objects.create` falla por el UNIQUE de la clave (otra petición ganó la carrera), se captura el `IntegrityError` sin invalidar la transacción externa y se devuelve la compra existente (`_replay`) (`purchases/services.py:175-189`).

## D. Modelos y base de datos

**16. 🟢 ¿Cuántos modelos hay?**
21 concretos más uno abstracto (`TimeStampedModel`), verificado con `apps.get_models()`. Los principales: `User`, `CustomerProfile`, `Product`, `CustomerQRCode`, `PointsTransaction`, `Purchase`, `Reward`, `Redemption`, `Event`, `Reservation` y `Notification`.

**17. 🟡 ¿Por qué un `public_id` UUID además del `id`?**
Para que las URLs y la API no expongan identificadores secuenciales que se puedan enumerar (`/canjes/1`, `/canjes/2`…). El `id` interno solo se usa en la BD.

**18. 🟡 ¿Por qué separaste `CustomerProfile` de `User`?**
Solo los clientes tienen dirección, fecha de nacimiento y teléfono; separarlos minimiza los datos personales y los aísla de la identidad de acceso. El perfil se crea en la misma transacción que el alta (`services._create_user`, `:115-116`).

**19. 🟡 ¿Qué restricciones de BD destacarías?**
`balance_after >= 0` en el ledger; un `EARN_PURCHASE` por compra; un cumpleaños por cliente y año; un canje `PENDING` por cliente y recompensa; `customer != registered_by` en las compras; `is_staff` solo para OWNER; email único sin distinguir mayúsculas; un solo `BusinessInfo` (memoria, cap. 6.3).

**20. 🔴 ¿Por qué el comentario sobre `NULL` en los CHECK de `Promotion`?**
En SQL, `NULL >= 1` es «desconocido» y un CHECK desconocido **se da por cumplido**. Por eso se añade `fixed_points__isnull=False` explícitamente (`apps/loyalty/models.py:206-216`). Sin eso, una promoción de puntos fijos con `fixed_points = NULL` pasaría el CHECK.

**21. 🟡 ¿Por qué `on_delete=PROTECT` casi siempre?**
Para no perder el historial: no se puede borrar una recompensa con canjes ni un cliente con movimientos. Se desactiva o se archiva en su lugar.

**22. 🟡 ¿Cómo evolucionó el esquema?**
26 migraciones; cada fase añade la suya y una de `core` con nuevas acciones de auditoría. Hay dos migraciones de datos (`RunPython`): crear los perfiles que faltaban (F1) y una comprobación en el regalo de cumpleaños (F10). `makemigrations --check` confirma que no hay cambios pendientes.

## E. Formularios y validaciones

**23. 🟢 ¿Dónde se valida la entrada?**
En tres niveles: el formulario o serializador (formato), el servicio (reglas con el estado actual, dentro de la transacción) y la BD (CHECK y UNIQUE).

**24. 🟡 ¿Por qué los formularios son `forms.Form` y no `ModelForm`?**
Para declarar los campos explícitamente: no existe ningún campo de rol, estado o verificación que el navegador pueda asignar (`apps/accounts/forms.py:1-9`). La excepción, `EventForm`, es un `ModelForm` con una lista de campos explícita, y el servicio vuelve a filtrar con `EVENT_FIELDS`.

**25. 🟡 ¿Cómo validas el importe de una compra?**
`parse_amount` (`purchases/services.py:63-83`): acepta coma o punto, convierte a `Decimal` (un `float` se pasa antes por `repr` para no arrastrar errores binarios), como máximo 2 decimales y entre 0,01 y 1000 €. Y la BD exige `amount >= 0.01`.

**26. 🟡 ¿Cómo validas la fecha de nacimiento?**
No puede ser futura, la edad debe estar entre 18 (`ACCOUNTS_MIN_CUSTOMER_AGE`) y 120 años, y el 29 de febrero se trata bien (`validators.py:92-110`). Además, solo se puede cambiar una vez cada 365 días para proteger el regalo de cumpleaños.

## F. Autenticación y permisos

**27. 🟢 ¿Cómo se elige el rol al registrarse?**
No se elige: el registro público siempre crea un CUSTOMER (`register_customer` no acepta `role`). Los empleados los crea un propietario (dashboard o admin) y el primer propietario, el comando `create_owner`.

**28. 🟡 ¿Qué impide que un empleado entre en el dashboard tecleando la URL?**
`role_required(User.Role.OWNER)` en cada vista (403), y además cada selector y servicio vuelve a comprobar `is_owner` (test `test_owner_only_selectors_reject_employee`). Ocultar el botón es solo cosmético.

**29. 🟡 ¿Qué pasa si se desactiva a un empleado con la sesión abierta?**
`has_role` exige `user.is_active`, que se lee en cada petición: pierde el acceso en la siguiente petición. En la API, simplejwt rechaza el token (`CHECK_USER_IS_ACTIVE`).

**30. 🔴 ¿Cómo revocas un JWT si cambia la contraseña?**
Cada token lleva `pwv` = HMAC del hash de la contraseña (`apps/api/tokens.py:43-49`); `JWTAuthentication.get_user` lo compara en cada petición. Si cambia la contraseña por cualquier vía, todos los tokens dejan de valer al momento. Además, `PasswordChangeView` añade todos los refresh a la lista negra.

**31. 🟡 ¿Por qué no se puede quedar el sistema sin propietario?**
`change_role` y `set_user_active` bloquean primero los propietarios activos, en orden de pk, y después al usuario afectado; con los bloqueos tomados comprueban que quien actúa sigue siendo propietario activo y rechazan quitar el último (`accounts/services.py:85-109, 233-240, 269-274`). El orden único evita interbloqueos si dos propietarios se retiran mutuamente a la vez (corrección R-1, [refactorización final](../refactorizacion-final.md)); lo prueban `tests/accounts/test_concurrency.py` en PostgreSQL. En el dashboard, además, nadie puede desactivarse ni cambiarse el rol a sí mismo.

## G. Seguridad y privacidad

**32. 🔴 ¿Qué impediría que un usuario se concediera puntos a sí mismo?**
(1) Los puntos **nunca** llegan del cliente: se calculan en el servidor a partir del importe guardado (`conversion.py`). (2) Registrar una compra exige ser empleado o propietario (`is_staff_member`) y un cliente no puede tener otro rol. (3) La BD impide `customer = registered_by` (`purchases_not_self_registered`). (4) Los ajustes manuales solo los hace el propietario (`ledger.adjust_points`), auditados. **Riesgo residual:** un empleado podría registrar compras falsas a un amigo; se mitiga con la auditoría de qué empleado registró cada compra (`registered_by`) y con los informes por empleado del dashboard, pero no hay un control automático de patrones anómalos.

**33. 🟡 ¿Cómo proteges frente a CSRF?**
`CsrfViewMiddleware` y `{% csrf_token %}` en todos los formularios, incluido el logout (que es POST). La API no usa cookies, sino una cabecera `Authorization` que el navegador no envía solo, así que no tiene superficie CSRF.

**34. 🟡 ¿Y frente a XSS?**
Autoescape de las plantillas de Django; el QR es un SVG generado en el servidor; se rechazan los SVG subidos (Pillow solo acepta JPEG, PNG y WebP); los enlaces sociales solo admiten `https` (`web/models.py:38-40`).

**35. 🟡 ¿Qué es IDOR y cómo lo evitas?**
Acceder a un objeto ajeno cambiando su id. Las vistas no reciben ids de usuario (usan `request.user`) y los objetos se buscan filtrando por el dueño: `customer_redemption(customer, public_id)` devuelve `None` → 404 si el canje es de otro, sin revelar que existe. Tests: `test_cannot_see_or_cancel_others_reservations` y `test_other_employee_gets_404`.

**36. 🔴 ¿Cómo se protege la información personal?**
Minimización (listados con `.only()`, el empleado ve «Lúa F.»), consultas auditadas (ficha del cliente, reserva con teléfono), búsqueda por POST guardada en la sesión (no queda en la URL ni en los logs), estadísticas geográficas solo con direcciones declaradas, logs y auditoría sin datos personales, notificaciones sin destinatario ni cuerpo guardados, IPs como hash en la caché. **Lo que falta:** exportación y supresión a petición del interesado y textos legales; el código no garantiza por sí mismo el cumplimiento del RGPD.

**37. 🟡 ¿Cómo evitas que alguien averigüe si un email está registrado?**
El registro, el reenvío y la recuperación responden igual exista o no la cuenta; con un email existente se calcula igualmente un hash de la contraseña para igualar los tiempos (`accounts/services.py:442-446`), y se avisa por email al titular.

**38. 🟡 ¿Cómo limitas los ataques de fuerza bruta?**
Login: 5 fallos por email y 30 por IP en 15 minutos; formularios públicos: 20 por IP y hora; QR o códigos de canje no válidos: 20 en 15 minutos por empleado; throttling DRF. Las claves se guardan como hash SHA-256. **Limitación:** con la caché por defecto (`locmem`), los contadores son **por proceso**; en producción hace falta Redis o caché en la BD.

**39. 🔴 Si pongo un proxy delante, ¿un atacante puede falsear su IP con `X-Forwarded-For`?**
No si `TRUSTED_PROXY_COUNT` es correcto: `client_ip` toma la N-ésima entrada por la derecha (la que añadió el proxy propio) y sin proxies ignora la cabecera (`apps/core/http.py:18-27`). Si se configurara un número mayor que el real, sí podría; está advertido en `base.py:153-156`.

## H. QR

**40. 🟢 ¿Qué contiene el QR?**
`CF1:` + 32 caracteres aleatorios en base32 (160 bits de `secrets`). Ni nombre, ni email, ni saldo.

**41. 🟡 ¿Qué pasa si alguien fotografía mi QR?**
Solo podría hacer que **me** sumen puntos (no robarlos ni canjearlos: canjear exige mi sesión). Puedo renovarlo en `/cuenta/mi-qr/renovar/` (hasta 5 veces al día) y el anterior deja de valer.

**42. 🟡 ¿Por qué el token se guarda en claro si los de verificación se guardan con hash?**
Porque hay que volver a dibujar el QR cada vez que el cliente lo abre. Para compensarlo, nunca se escribe en logs, auditoría ni URLs, y `__str__` no lo muestra (`loyalty/models.py:24-26, 48-50`).

**43. 🟡 ¿Cómo se lee el QR en la barra?**
`qr-scanner.js` usa `BarcodeDetector` si el navegador lo tiene y, si no, jsQR servido desde el propio sitio; si no hay cámara se teclea el código. La validación la hace siempre el servidor. La cámara exige HTTPS o `localhost`. **Pendiente:** probarlo en dispositivos físicos.

## I. Compras y puntos

**44. 🔴 ¿Cómo se evitarían dos asignaciones de puntos para la misma compra?**
Tres capas: (1) idempotencia de la compra (clave única + `_replay`): un reenvío no crea otra compra; (2) `award_points_for_purchase` es idempotente: si la compra ya tiene movimientos, los devuelve (`ledger.py:87-93`); (3) UNIQUE condicional `loyalty_points_one_earn_per_purchase` en la BD (`models.py:405-407`). Además, compra y puntos van en la misma transacción.

**45. 🟡 ¿Cómo se calculan los puntos y por qué se redondea hacia abajo?**
`importe × puntos_por_euro` en `Decimal`, truncado (`ROUND_DOWN`): 12,50 € → 12 puntos. Truncar evita regalar puntos por redondeo y es predecible para el cliente.

**46. 🟡 Si el propietario cambia la conversión, ¿cambian los puntos antiguos?**
No. Las reglas son versionadas (`LoyaltyRule` no se edita, se añade otra con `valid_from`) y cada movimiento guarda una copia de la tasa aplicada (`points_per_euro`, `rule`). Se usa la tasa vigente **en la fecha de la compra**.

**47. 🟡 ¿Cómo se corrige un error de puntos?**
Nunca borrando: `reverse_movement` crea un movimiento de signo contrario (una sola vez gracias al OneToOne `reverses`) o `adjust_points` hace un ajuste con motivo; ambos los hace solo el propietario y quedan auditados. Los canjes no se compensan: se cancelan.

**48. 🔴 ¿Por qué el saldo no es un campo del usuario?**
Porque un campo editable se puede desincronizar o manipular sin dejar rastro. El saldo se deriva de los movimientos (como un libro contable). Coste: `SUM` en cada escritura (`ledger.balance`), lineal en el número de movimientos; con mucho volumen se añadiría un saldo materializado actualizado en la misma transacción.

**49. 🟡 ¿Las compras registradas son las ventas del local?**
No. Solo las que el personal registró con el QR de un cliente. El sistema no tiene caja ni TPV y lo dice expresamente en las estadísticas (`NOT_REVENUE_NOTE`; `business_revenue` siempre es `None`).

**50. 🔴 ¿Qué pasa si el empleado vuelve atrás en el navegador y reenvía la pantalla de confirmación?**
Reenviar el **registro** con la misma clave devuelve la compra existente. Pero si el navegador reenvía el paso de **identificación**, este genera una **clave nueva** y el siguiente «Registrar» crearía otra compra. Es una limitación real (la clave se genera en cada identificación). Mitigaciones existentes: `app.js` evita el doble clic y el detalle muestra la compra recién creada. Mejora posible: atar la clave a la sesión o avisar si hay una compra idéntica muy reciente del mismo empleado y cliente.

## J. Recompensas y canjes

**51. 🔴 ¿Qué ocurriría si dos empleados intentaran canjear simultáneamente la misma recompensa (validar el mismo código)?**
`validate_redemption` bloquea la fila del canje (`select_for_update`) y hace `UPDATE ... SET status='USED' WHERE status='PENDING' AND expires_at > now` (`rewards/services.py:387-389`). Solo una petición actualiza 1 fila; la otra obtiene 0 y recibe «Este código ya se utilizó el …». Lo prueba `test_same_code_validated_concurrently_is_used_once` con 4 hilos: **omitido** con SQLite en memoria; **pasa** con SQLite en fichero (que serializa las escrituras); **pendiente en PostgreSQL**.

**52. 🔴 ¿Y si un cliente pide cuatro canjes a la vez sin saldo para todos?**
Cada solicitud bloquea al cliente y recalcula el saldo dentro de la transacción; las que no alcanzan reciben `insufficient_points`. Test `test_concurrent_requests_never_overspend`: como mucho uno con saldo 60 y canjes de 40, y el saldo nunca negativo (CHECK en la BD).

**53. 🟡 ¿Por qué se descuentan los puntos al solicitar y no al recoger?**
Para que el saldo mostrado sea real y no se puedan prometer los mismos puntos dos veces. Si no se recoge en 30 días o se cancela, se devuelven con un movimiento compensatorio y se devuelve la unidad.

**54. 🟡 ¿Cómo se generan los códigos de canje?**
12 caracteres con `secrets.choice` sobre un alfabeto de 31 símbolos sin 0, O, 1, I ni L (≈ 59 bits). La BD garantiza la unicidad y el formato (CHECK con expresión regular). El prefijo `CFR1:` es distinto del QR personal.

**55. 🔴 ¿Puede quedar el stock negativo?**
No: la resta es `UPDATE reward SET stock = stock - 1 WHERE stock >= 1` (`rewards/services.py:192`) y hay un CHECK `stock >= 0`. Test `test_stock_cannot_go_negative_even_if_check_was_stale`.

## K. Transacciones y concurrencia

**56. 🔴 ¿Qué pasa si falla algo a mitad del registro de una compra?**
Todo está en un `transaction.atomic()`: si falla la creación de un movimiento de puntos, se deshace también la compra. Nunca queda una compra sin puntos ni puntos sin compra.

**57. 🔴 ¿Cómo evitas interbloqueos (deadlocks)?**
Bloqueando siempre en el mismo orden: cliente → recompensa → canje (docstring de `rewards/services.py:21-22`, aplicado en `_create_redemption` y en `_close`). Probarlo en PostgreSQL destapó dos casos que no lo respetaban y que SQLite no detectaba: `validate_redemption` bloqueaba canje, cliente y recompensa a la vez (auditoría P2-1, se corrigió con `of=("self",)`) y la regla del último propietario bloqueaba primero al usuario y luego a los propietarios (R-1, refactorización final). Ambos tienen ahora un test de concurrencia.

**58. 🔴 ¿Qué pasa si falla el envío de un correo después de crear una cuenta?**
El email se envía con `transaction.on_commit`: la cuenta ya está guardada. `send_immediately` captura el error, marca la notificación como `FAILED` (sin guardar el enlace) y no rompe el flujo. El cliente puede pedir otro enlace desde `/cuenta/verificar-email/reenviar/` (con límites). En las notificaciones de la cola (reservas), el fallo se reintenta con espera creciente hasta 5 veces: `process_notifications` se ejecuta cada 5 minutos en el servicio `scheduler`.

**59. 🟡 ¿Puede `process_notifications` enviar dos veces el mismo mensaje si se lanza dos veces a la vez?**
No en condiciones normales: cada notificación se «reclama» con `UPDATE ... WHERE status='PENDING'` (`notifications/services.py:270-274`). Excepción reconocida en el código: si un proceso muere después de que el proveedor aceptara el mensaje, `recover_stale` lo reencola y podría duplicarlo.

## L. Pruebas

**60. 🟢 ¿Cuántos tests hay y pasan?**
849, y pasan todos en PostgreSQL 17 sin omitir ninguno (unos 42 s), también dentro del contenedor de producción y en el CI de GitHub. Con SQLite en memoria se omiten 18: los 17 de concurrencia, que necesitan varias conexiones, y uno exclusivo de PostgreSQL.

**61. 🟡 ¿Qué tipos de prueba tienes?**
De reglas (redondeo, validadores), de integración servicio + BD, de restricciones de BD (forzando `UPDATE` directos), de permisos y escalada, de IDOR, de formularios, de idempotencia, de seguridad de la API (sin CORS, `no-store`, solo JSON, paginación limitada, throttling), de concurrencia con hilos (17), de caracterización antes de refactorizar y de número de consultas (`assertNumQueries`).

**62. 🔴 ¿Qué NO garantizan tus tests?**
El servidor real (DNS, certificado, SMTP), el envío real de correo, el JavaScript del lector de QR, la accesibilidad, el diseño visual y el rendimiento con carga. Tampoco hay medición de cobertura, así que no puedo dar un porcentaje.

**63. 🟡 ¿Por qué en los tests se usa MD5 para las contraseñas?**
Solo en `config/settings/test.py` para acelerar los tests; nunca fuera de ellos. En desarrollo y producción se usa el hasher por defecto de Django.

## M. Rendimiento

**64. 🔴 ¿Qué parte del sistema cambiarías si aumentara mucho el número de clientes?**
(1) **El saldo del ledger:** materializarlo (o usar `balance_after` del último movimiento) en lugar de `SUM` de todos los movimientos. (2) **Más workers o servidores:** la caché ya es compartida (Redis), así que los límites siguen siendo correctos con varios procesos. (3) **Las notificaciones y campañas:** `dispatch_queued` crea una notificación por destinatario en una transacción por campaña; con decenas de miles convendría hacerlo por lotes o con una cola (Celery). (4) **El conteo de usos de las promociones** (`uses.count()` en cada compra) → contadores. (5) Varios procesos WSGI + PostgreSQL con pool de conexiones (`DATABASE_CONN_MAX_AGE`).

**65. 🟡 ¿Qué has hecho para evitar consultas N+1?**
`select_related` y `prefetch_related` en los selectores (p. ej. `public_menu` con `Prefetch(... to_attr="public_products")`), agregaciones condicionales en una sola consulta (`Count(filter=...)`) y `only()` o `defer()` para cargar menos columnas. Lo medí en la refactorización final: el número de consultas de cada página no crece con los datos, y unificar las estadísticas de canjes y reservas bajó el resumen del dashboard de 17 a 12 consultas.

## N. Despliegue

**66. 🟢 ¿Está desplegada la aplicación?**
En un servidor real, todavía no. Está **lista y probada en local**: la Fase 12 dejó una imagen Docker y una pila Compose (Nginx con TLS, Gunicorn, PostgreSQL 17, Redis, tareas programadas y certbot), scripts de despliegue, rollback, copia y restauración, y un CI en GitHub. Todo se probó desde volúmenes vacíos, incluido un desastre simulado con restauración. Faltan las acciones manuales en el VPS: contratarlo, DNS, certificado, SMTP real y destino de las copias.

**67. 🔴 ¿Qué sucede si una migración falla en producción?**
En PostgreSQL, cada migración de Django se ejecuta en una transacción (DDL transaccional): si falla, se deshace esa migración y el esquema queda en el estado anterior. `deploy.sh` hace una copia antes de aplicar las migraciones, que se ejecutan una sola vez en un contenedor aparte. Si hay que volver atrás, `deploy.sh rollback` cambia a la imagen anterior en segundos; si la versión nueva traía migraciones incompatibles, además hay que restaurar la copia y se pierde lo escrito después. Las dos migraciones de datos tienen una inversa `noop`, así que revertirlas no deshace los datos creados.

**68. 🟡 ¿Qué tareas hay que programar?**
`process_notifications` (cada 5 min), `run_birthday_promotions`, `expire_redemptions`, `purge_email_tokens`, `flushexpiredtokens` y `clearsessions` (diarias). Las ejecuta supercronic en el servicio `scheduler` de Docker Compose (`deploy/cron/crontab`), sin solapar ejecuciones. Las copias se programan aparte, en el host.

## O. Decisiones de diseño

**69. 🟡 ¿Por qué Tailwind sin Node?**
La CLI standalone evita la cadena npm; `scripts/tailwind.py` descarga la v4.3.3 y **verifica su SHA-256** antes de usarla. El CSS compilado está versionado: no hace falta compilar para ejecutar.

**70. 🟡 ¿Por qué no Celery para las tareas?**
Por simplicidad operativa a esta escala (decisión del usuario en la F10): comandos idempotentes programados con supercronic. Se cambiaría con volumen alto o si se necesitara inmediatez.

**71. 🟡 ¿Por qué el regalo de cumpleaños no exige aceptar publicidad?**
Para que el consentimiento publicitario sea libre: condicionar un beneficio a aceptarlo podría invalidarlo. El regalo exige el email verificado (requisito del programa) y el aviso solo se envía si hay consentimiento (`loyalty/birthdays.py:14-21`).

**72. 🟡 ¿Por qué la API no tiene CORS?**
Porque su cliente previsto es una app nativa, que no lo necesita, y sin cabeceras CORS ninguna web de terceros puede leer las respuestas desde un navegador (test `test_no_store_and_no_cors`). Si hubiera un cliente web en otro dominio, se añadiría con lista blanca.

## P. Limitaciones y mejoras

**73. 🟢 ¿Qué es lo primero que harías antes de producción?**
Las acciones manuales del VPS (servidor endurecido, DNS, certificado), el SMTP real con SPF, DKIM y DMARC, el destino externo de las copias y la monitorización con alertas. Lo que antes estaba aquí (PostgreSQL, caché compartida, tareas programadas) ya está hecho.

**74. 🟡 ¿Qué funcionalidades están a medias?**
Anulación de compras (`VOIDED`) y TPV (`POS`, `external_reference`): reservados en el modelo, sin flujo. SMS: canal sin proveedor. `birthday_window_days`: campo sin uso. `CancelReservationForm`: definido y sin usar.

**75. 🟡 ¿Qué mejoras de seguridad añadirías?**
2FA para el propietario, Content-Security-Policy, borrar los metadatos EXIF de las imágenes, auditoría inmutable en la BD, Swagger UI servido localmente, `pip-audit` en el CI, exportación y supresión de datos, y firmar la clave de idempotencia.

## Q. PostgreSQL, despliegue, auditoría y refactorización (añadidas el 15-10-2026)

**76. 🔴 ¿Qué encontraste al pasar de SQLite a PostgreSQL?**
Que SQLite ignora `SELECT ... FOR UPDATE`, así que algunos errores no aparecían. El más claro: los cambios de estado de una reserva bloqueaban la reserva con un `JOIN` al evento, que es nulo en las reservas de mesa, y PostgreSQL no admite `FOR UPDATE` en el lado nulo de un `LEFT JOIN`. Fallaban 15 tests. Se corrigió con `select_for_update(of=("self",))` (C8.13). Por eso la verificación que cuenta se hace en PostgreSQL y el CI falla si se omite algún test.

**77. 🔴 ¿Cómo has desplegado la aplicación y por qué así?**
Con Docker Compose en un único VPS: Nginx (TLS, estáticos con hash, límites en el login), Gunicorn con Django, PostgreSQL 17 con un rol sin privilegios, Redis como caché compartida, supercronic para las tareas y certbot. Los contenedores de la app no son root y tienen el sistema de ficheros de solo lectura; la BD y Redis no publican puertos. Para un local es reproducible, barato y con rollback rápido; no tiene alta disponibilidad, que a esta escala no compensa (D17).

**78. 🟡 ¿Cómo haces las copias de seguridad y cómo sabes que funcionan?**
Con restic: un volcado de PostgreSQL y `media/`, cifrados en el cliente y enviados a un destino externo, con retención de 7 diarias y 4 semanales. El volcado nunca queda sin cifrar en el disco del servidor. Funcionan porque se ha restaurado: `restore.sh check` restaura en una BD aparte y compara recuentos, y en local se simuló un desastre (BD e imágenes borradas) y se recuperó todo.

**79. 🔴 ¿Qué hiciste en la refactorización final y cómo garantizas que no rompiste nada?**
Primero ejecuté la suite (833 OK) y escribí tests de caracterización para las zonas que iba a tocar, que pasaron con el código original. Después cambié el código por grupos pequeños, con la suite completa tras cada uno: un helper de periodo común (sustituye unas 9 copias), estadísticas con agregados condicionales (resumen del dashboard de 17 a 12 consultas, medido) y la regla del último propietario en un solo sitio. Al final pasé la suite en PostgreSQL, en SQLite y en el contenedor, `check --deploy` y la comparación del esquema OpenAPI (`docs/refactorizacion-final.md`).

**80. 🔴 ¿Encontraste algún error durante la refactorización?**
Sí, uno que ya existía: si dos propietarios se desactivaban mutuamente a la vez, PostgreSQL detectaba un interbloqueo y una operación terminaba en error 500 (la regla de no quedarse sin propietario sí se cumplía). Lo reproduje con un test de hilos, lo documenté como R-1 y, con aprobación, lo corregí: ahora siempre se bloquea a los propietarios antes que al usuario afectado y, con los bloqueos tomados, se vuelve a comprobar que quien actúa sigue siendo propietario. Ese segundo detalle cerraba otro caso: un propietario recién desactivado podía completar una operación que había quedado esperando.
