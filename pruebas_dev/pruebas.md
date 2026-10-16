# Pruebas de desarrollo — Caneca Furada

Órdenes para probar la aplicación **sin tocar la base de datos de desarrollo habitual** (la `DATABASE_URL` del `.env`, `caneca_furada`), el repositorio ni producción.

> **Solo desarrollo.** Las cuentas y la contraseña de demostración son ficticias e inseguras. Detalle de los datos: [docs/fase-13-datos-demo.md](../docs/fase-13-datos-demo.md).

Todas las órdenes son para **PowerShell** y se ejecutan **desde la raíz del repositorio** (`webcaneca/`).

---

## 0. Reglas para no afectar al proyecto

1. **Una base de datos aparte para cada prueba.** La variable `$env:DATABASE_URL` vale solo para la terminal donde se define y tiene prioridad sobre el `.env`. Al cerrar la terminal, desaparece.
2. **Los ficheros de prueba, en esta carpeta.** `pruebas_dev/*.sqlite3` no se sube a Git (`.gitignore` ignora `*.sqlite3`).
3. **Los tests no tocan ninguna base real.** Django crea una base temporal (`test_…` en PostgreSQL, en memoria en SQLite) y la borra al terminar.
4. **`media/` es compartida.** Las imágenes de la demo se guardan en la misma carpeta `media/` que las del proyecto (ignorada por Git). `seed_demo_data --clean` las borra; hazlo **antes** de cambiar de base de datos.
5. **Comprueba siempre a qué base apuntas** antes de cargar o borrar (§2).
6. **No ejecutes nunca:**
   - `seed_demo_data` contra `caneca_furada` si tiene datos tuyos (se negará, pero no lo fuerces);
   - `flush`;
   - `migrate` con `config.settings.prod`;
   - `git add pruebas_dev/*.sqlite3`.

---

## 1. Activar el entorno

```powershell
.venv\Scripts\activate
$env:PYTHONUTF8 = "1"        # evita UnicodeEncodeError en la consola de Windows
```

## 2. ¿A qué base de datos apunto?

```powershell
python manage.py shell -c "from django.db import connection; print(connection.vendor, connection.settings_dict['NAME'])"
```

| Resultado | Significado |
|---|---|
| `postgresql caneca_furada` | Tu base de desarrollo habitual: **no cargues aquí la demo** |
| `sqlite …\pruebas_dev\demo.sqlite3` | La base de pruebas SQLite |
| `postgresql caneca_demo` | La base de pruebas PostgreSQL |

---

## 3. Base de pruebas con SQLite (recomendado, sin instalar nada)

```powershell
$env:DATABASE_URL = "sqlite:///pruebas_dev/demo.sqlite3"
python manage.py migrate
python manage.py seed_demo_data            # pide confirmación; añade --noinput para no preguntar
python manage.py runserver 8001            # otro puerto: puedes tener la original en el 8000
```

Abre http://localhost:8001.

## 4. Base de pruebas con PostgreSQL (opcional, más fiel a producción)

Se crea una sola vez, como el usuario `postgres`:

```powershell
psql -U postgres -h localhost -c "CREATE DATABASE caneca_demo OWNER caneca ENCODING 'UTF8';"
```

Para usarla, con la contraseña del rol `caneca` que tienes en tu `.env`, sin copiarla en ningún fichero:

```powershell
$env:DATABASE_URL = "postgres://caneca:<contraseña>@localhost:5432/caneca_demo"
python manage.py migrate
python manage.py seed_demo_data --noinput
python manage.py runserver 8001
```

---

## 5. Cuentas de demostración

Contraseña de todas: `Demo-Caneca-2026` (**solo desarrollo**). Para usar otra, defínela **antes** de cargar: `$env:CANECA_DEMO_PASSWORD = "otra-contraseña-larga"`.

| Rol | Email | Dónde entrar |
|---|---|---|
| Propietario | `propietaria@demo.example.com` | `/dashboard/` y `/admin/` |
| Empleado | `brais.empregado@demo.example.com` | `/panel/` |
| Cliente con puntos y canje pendiente | `lua.proba@demo.example.com` | `/cuenta/puntos/`, `/cuenta/mi-qr/`, `/cuenta/reservas/` |
| Cliente con muchos puntos | `martin.exemplo@demo.example.com` | `/cuenta/canjes/` |
| Cliente sin compras (saldo 0) | `hugo.proba@demo.example.com` | `/cuenta/puntos/` |
| Saldo insuficiente | `tiago.exemplo@demo.example.com` | `/recompensas/` |
| Pendiente de verificar | `xiana.pendente@demo.example.com` | `/cuenta/puntos/` → 403 (es lo esperado) |
| Cuentas inactivas | `noa.empregada@…`, `noelia.exemplo@…` | No pueden iniciar sesión |

La lista completa sale al terminar la carga y en la [§5 de la Fase 13](../docs/fase-13-datos-demo.md#5-cuentas-de-demostración).

**Consejo:** usa una ventana privada o un segundo navegador para tener a la vez un cliente y un empleado.

---

## 6. Gestionar los datos de demostración

```powershell
python manage.py seed_demo_data                          # carga; si ya están, no cambia nada
python manage.py seed_demo_data --reset --noinput        # recarga (refresca las fechas "futuras")
python manage.py seed_demo_data --clean --noinput        # borra solo lo de demo (y sus imágenes)
python manage.py seed_demo_data --reference-date 2026-10-01 --reset --noinput   # otra fecha de referencia (no futura)
python manage.py seed_demo_data --reset --noinput -v 2   # muestra cada operación (solo identificadores públicos)
```

Los eventos y reservas "futuros" lo son respecto al momento de la carga: pasados unos días, usa `--reset`.

---

## 7. Probar las tareas programadas sobre la demo

Ejecútalas **solo** con `DATABASE_URL` apuntando a la base de pruebas (§2). En desarrollo, los emails se imprimen en la consola, con los enlaces incluidos; es lo normal en local.

```powershell
python manage.py process_notifications                   # envía las notificaciones pendientes
python manage.py expire_redemptions                      # caduca los canjes vencidos y devuelve los puntos
python manage.py run_birthday_promotions --date 2026-10-16   # regalos de cumpleaños de ese día (no futuro)
python manage.py expire_points                          # avisos y caducidad de puntos (Fase 14); sin caducidad configurada no hace nada
python manage.py expire_points --at 2027-12-01          # solo con DEBUG: simula otra fecha para ver avisos y caducidades
python manage.py purge_email_tokens --days 30            # borra los enlaces de verificación caducados
python manage.py clearsessions
```

### Ver los emails en un buzón de pruebas (Mailpit, opcional)

Necesitas Docker. Mailpit recoge los correos sin enviarlos fuera.

```powershell
docker run -d --name mailpit-dev -p 127.0.0.1:1025:1025 -p 127.0.0.1:8025:8025 axllent/mailpit:v1.27
$env:EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
$env:EMAIL_HOST = "localhost"; $env:EMAIL_PORT = "1025"; $env:EMAIL_USE_TLS = "False"
python manage.py runserver 8001                          # buzón en http://localhost:8025
# Al terminar:
docker rm -f mailpit-dev
Remove-Item Env:EMAIL_BACKEND, Env:EMAIL_HOST, Env:EMAIL_PORT, Env:EMAIL_USE_TLS
```

`seed_demo_data` nunca envía correos, ni siquiera a Mailpit: durante la carga usa un buzón en memoria.

---

## 8. Consultar los datos (solo lectura)

```powershell
# Recuentos por entidad
python manage.py shell -c "from apps.demo.selectors import demo_counts; [print(f'{k:<24}{v:>5}') for k, v in demo_counts().items()]"

# Saldo de cada cliente (suma de su ledger)
python manage.py shell -c "from apps.accounts.models import User; from apps.loyalty.ledger import balance; [print(f'{u.email:<40}{balance(u):>6}') for u in User.objects.filter(role='CUSTOMER').order_by('email')]"

# Estados de reservas y canjes
python manage.py shell -c "from collections import Counter; from apps.events.models import Reservation; from apps.rewards.models import Redemption; print(Counter(Reservation.objects.values_list('status', flat=True))); print(Counter(Redemption.objects.values_list('status', flat=True)))"
```

---

## 9. Tests y comprobaciones (no tocan ninguna base real)

```powershell
# Comprobaciones rápidas
python manage.py check
python manage.py makemigrations --check --dry-run        # no crea migraciones: solo avisa si faltan

# Suite completa en SQLite en memoria (rápida; omite los 18 tests de concurrencia)
$env:DATABASE_URL = "sqlite:///pruebas_dev/tests.sqlite3"
python manage.py test --settings=config.settings.test --noinput

# Suite completa en PostgreSQL (la que cuenta; crea y borra test_caneca_furada)
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue   # vuelve a la del .env
python manage.py test --settings=config.settings.test --parallel 1 --noinput

# Solo una parte
python manage.py test tests.demo --settings=config.settings.test
python manage.py test tests.rewards.test_services --settings=config.settings.test
python manage.py test tests.demo.test_seed_demo_data.SeedDemoDataTests.test_points_match_the_ledger --settings=config.settings.test

# Esquema OpenAPI (como en el CI): el fichero va a pruebas_dev, nunca sobre docs/api/openapi.yaml
python manage.py spectacular --validate --fail-on-warn --file pruebas_dev/openapi.yaml
git diff --no-index --stat docs/api/openapi.yaml pruebas_dev/openapi.yaml   # sin salida = idéntico
Remove-Item pruebas_dev/openapi.yaml
```

### Comprobar la configuración de producción con valores ficticios (como el CI)

No se conecta a nada ni arranca nada:

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.prod"
$env:DJANGO_SECRET_KEY = "clave-ficticia-solo-para-check-deploy-0123456789abcdefghijkl"
$env:DJANGO_ALLOWED_HOSTS = "www.example.com"; $env:EMAIL_HOST = "smtp.example.com"
$env:SITE_BASE_URL = "https://www.example.com"; $env:CACHE_URL = "redis://localhost:6379/1"
$env:DATABASE_URL = "postgres://ficticio:ficticio@localhost:5432/ficticia"
python manage.py check --deploy                          # solo debe aparecer security.W021
python manage.py seed_demo_data                          # debe responder: Unknown command
# Deshacer (imprescindible antes de seguir):
Remove-Item Env:DJANGO_SETTINGS_MODULE, Env:DJANGO_SECRET_KEY, Env:DJANGO_ALLOWED_HOSTS, Env:EMAIL_HOST, Env:SITE_BASE_URL, Env:CACHE_URL, Env:DATABASE_URL
```

O, más sencillo, haz todo esto en una terminal nueva y ciérrala al terminar.

---

## 10. Pila Docker local (imagen de producción, opcional)

Es un proyecto aparte (`caneca-dev`), con su propio PostgreSQL (puerto 5433) y Mailpit. No toca tu base local. Usa `config.settings.prod`, así que **ahí no existe `seed_demo_data`**. Detalle: [docs/fase-12-despliegue.md](../docs/fase-12-despliegue.md).

```powershell
docker compose -f compose.yaml -f compose.dev.yaml --env-file deploy/dev.env up -d --build --wait
docker compose -f compose.yaml -f compose.dev.yaml --env-file deploy/dev.env run --rm migrate
docker compose -f compose.yaml -f compose.dev.yaml --env-file deploy/dev.env run --rm tests   # suite en su PostgreSQL
# Web: https://localhost:8443 (certificado autofirmado) · Mailpit: http://localhost:8025
docker compose -f compose.yaml -f compose.dev.yaml --env-file deploy/dev.env down        # detener (conserva sus volúmenes)
```

---

## 11. Cerrar la versión de pruebas y volver a la original

1. **Detén el servidor** de pruebas: `Ctrl+C` en su terminal.
2. **(Opcional) Borra la demo**, todavía con la variable apuntando a la base de pruebas, para retirar sus imágenes de `media/`:
   ```powershell
   python manage.py seed_demo_data --clean --noinput
   ```
3. **Quita la variable** (o cierra esa terminal):
   ```powershell
   Remove-Item Env:DATABASE_URL
   Remove-Item Env:CANECA_DEMO_PASSWORD -ErrorAction SilentlyContinue
   ```
4. **Comprueba** que vuelves a la original (§2): debe salir `postgresql caneca_furada`.
5. **Arranca la original:** `python manage.py runserver`.
6. **Vuelve a iniciar sesión** con tu cuenta real: la sesión del navegador era de la otra base.

Para **volver a la demo** más tarde, define otra vez `$env:DATABASE_URL` (§3 o §4). Si no la borraste, los datos siguen ahí; si la borraste, ejecuta `migrate` y `seed_demo_data`.

## 12. Eliminar todo rastro de las pruebas

```powershell
# Con la variable apuntando a la base de pruebas:
python manage.py seed_demo_data --clean --noinput
Remove-Item Env:DATABASE_URL
# Ficheros de esta carpeta (ignorados por Git)
Remove-Item pruebas_dev\*.sqlite3 -ErrorAction SilentlyContinue
# Base PostgreSQL de pruebas, si la creaste (comprueba el nombre antes)
psql -U postgres -h localhost -c "DROP DATABASE caneca_demo;"
# Comprobar que no queda nada pendiente de subir
git status --short
```
