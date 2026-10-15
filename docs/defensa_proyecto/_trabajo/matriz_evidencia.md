# Matriz de funcionalidades y evidencia (Etapa B)

Estados (`docs/prompt_funcionamiento.md` §2):
- **IV**: implementado y verificado. Hay código y algún test **ejecutado y aprobado** el 2026-10-15 (802 OK).
- **IP**: implementado, pendiente de verificación. Depende de un servicio externo, de PostgreSQL o de una prueba manual.
- **PA**: parcialmente implementado.
- **PL**: planificado o reservado, sin flujo.
- **NI**: no identificado.

Origen: **R** = requisito del plan de fases (`docs/plan-de-fases.md`); **D** = decisión tomada durante la implementación (documentada en el plan o en los docs de fase).

| ID | Funcionalidad | Origen | Evidencia principal | Tests | Estado |
|---|---|---|---|---|---|
| F01 | Usuario propio con roles OWNER/EMPLOYEE/CUSTOMER, `public_id` UUID y restricciones de rol en BD | R F0 | `apps/accounts/models.py:21-85` | `tests/accounts/test_models.py` | IV |
| F02 | Primer propietario con un comando seguro y auditado | R F0 | `apps/accounts/management/commands/create_owner.py`; `services.create_owner` | `tests/accounts/test_create_owner_command.py` | IV |
| F03 | El registro público solo crea CUSTOMER (sin campo de rol) | R F0/F2 | `apps/accounts/forms.py:1-9`; `services.register_customer:373` | `tests/accounts/test_registration.py` | IV |
| F04 | `CustomerProfile` 1:1 creado en la misma transacción que el alta | R F1 | `services._create_user:96`; `ensure_customer_profile:85`; migración `0003_backfill` | `tests/accounts/test_customer_profile.py` | IV |
| F05 | Perfil: dirección estructurada, fecha de nacimiento (≥ 18, no futura, ≤ 120), móvil E.164 y CP por país | R F2 | `apps/accounts/validators.py`; `CustomerProfile.clean` | `test_validators.py`, `test_profile.py` | IV |
| F06 | Verificación de email: token hash SHA-256, caducidad de 24 h, uso único, revocación y reenvío limitado | R F2 | `services._issue_email_token:469`; `confirm_email_token:562` | `tests/accounts/test_email_verification.py` | IV (envío SMTP real: IP) |
| F07 | Anti-enumeración en registro, reenvío, recuperación y cambio de email | R F2 + D F11 | `services.register_customer:423-430`; `views.register:52-55` | `test_registration.py:277`; `tests/core/test_phase11_audit.py:48-57` | IV |
| F08 | Login con límite de fallos por email (5) y por IP (30) en 15 minutos | R F2 | `forms.ThrottledAuthenticationForm:173`; `services.login_throttle_keys:350` | `test_auth_views.py`, `tests/api/test_auth.py` | IV (por proceso con locmem: D11) |
| F09 | Recuperación y cambio de contraseña (nativos de Django) auditados | R F2 + D F11 | `views.PasswordResetView:228`; `services.record_password_change:683` | `tests/core/test_phase11_audit.py:73-91` | IV |
| F10 | Cambio de email con nueva verificación y aviso a la dirección anterior | R F2 | `services.request_email_change:629`; `confirm_email_token:607-625` | `test_email_verification.py` | IV |
| F11 | Preferencias promocionales desactivadas por defecto, con historial inmutable | R F2 | `CustomerProfile.promo_*_opt_in`; `CommunicationPreferenceChange`; `services.set_communication_preferences:822` | `test_profile.py` | IV |
| F12 | Activación y desactivación auditadas; nunca se queda el sistema sin propietario activo | R F2 | `services.set_user_active:241`; `change_role:198` | `tests/accounts/test_services.py:155` | IV |
| F13 | Sistema de diseño Tailwind (CLI sin Node, binario con checksum), páginas públicas y páginas de error | R F3 | `scripts/tailwind.py:19-21`; `assets/css/input.css`; `templates/` | `tests/web/test_public_pages.py` | IV (aspecto visual: IP) |
| F14 | Contraste AA y diseño responsive | R F3 | Paleta en `assets/css/input.css`; `docs/fase-03-sistema-diseno-web-publica.md` | Sin test automático de contraste ni de diseño | IP |
| F15 | Carta: categorías, estilos, productos fijos y cervezas propias, invitadas o rotativas; precio Decimal; disponibilidad; archivado sin borrar | R F4 | `apps/catalog/models.py`; `services.py`; `selectors.py` | `tests/catalog/*` (59) | IV |
| F16 | Imágenes validadas por su contenido con Pillow y nombre aleatorio | R F4 | `apps/catalog/validators.py` | `tests/catalog/test_validators.py` | IV |
| F17 | Carta de grifos como imagen (`TapMenu`) en lugar de 14 grifos | D F4 | `apps/catalog/models.py:259` | `tests/web/test_menu_page.py` | IV |
| F18 | QR personal opaco (160 bits), renovable (5 al día) y sin datos personales | R F5 | `apps/loyalty/services.py:54-124`; CHECK `loyalty_qr_token_format` | `tests/loyalty/test_qr.py` | IV |
| F19 | Escaneo con la cámara (BarcodeDetector + jsQR local) o código tecleado | R F5 | `static/js/qr-scanner.js`; `static/vendor/jsqr/` | Sin test JS automático; el código tecleado está probado | IP (dispositivos físicos) |
| F20 | Registro de compra transaccional e idempotente; importe de 0,01 a 1000 € en Decimal; nadie se registra compras a sí mismo | R F5 | `apps/purchases/services.py:158-194`; CHECK `purchases_not_self_registered` | `tests/purchases/test_services.py:133-200` | IV |
| F21 | Ledger de puntos inmutable con saldo derivado, `balance_after` ≥ 0 y compensaciones | R F6 | `apps/loyalty/models.py:276-420`; `ledger.py` | `tests/loyalty/test_points.py` (41) | IV |
| F22 | Conversión versionada en Decimal con ROUND_DOWN, calculada solo en el servidor | R F6 | `apps/loyalty/conversion.py` | `test_points.py:52` | IV |
| F23 | Puntos generados en la misma transacción que la compra; uno por compra (UNIQUE) | R F6 | `purchases.services.on_purchase_registered:123`; UNIQUE `loyalty_points_one_earn_per_purchase` | `test_points.py:152-159` | IV |
| F24 | Promociones por compra (puntos fijos o multiplicador, fechas, importe mínimo y límites) | R F6 | `apps/loyalty/promotions.py:107-130` | `tests/loyalty/test_promotions.py` | IV |
| F25 | Ajuste manual y compensación del propietario, idempotentes y auditados | R F6/F9 | `ledger.adjust_points:182`; `reverse_movement:250` | `test_points.py:272-351`; `tests/dashboard/test_customers_and_actions.py:118-140` | IV |
| F26 | Regalo de cumpleaños el mismo día (29-F → 28-F), uno por año y con anti-abuso | R F6 + D F10 | `apps/loyalty/birthdays.py`; `ledger.grant_birthday_gift:319`; `promotions.birthday_year_for:77` | `tests/loyalty/test_birthdays.py` (21) | IV (programación diaria: IP) |
| F27 | Catálogo de recompensas (coste, estado, fechas, unidades, imagen) gestionado por el propietario | R F7 | `apps/rewards/models.py:36`; `services.save_reward:411` | `tests/rewards/test_services.py` | IV |
| F28 | Canje: descuento en el ledger, código de un solo uso, uno pendiente por recompensa, stock condicionado | R F7 | `apps/rewards/services.py:176-240` | `test_services.py:92-166` | IV |
| F29 | Validación en barra con UPDATE condicionado (sin doble consumo) | R F7 | `services.validate_redemption:370-405` | `test_services.py:286-371`; concurrencia (D10) | IV (lógica) / IP (PostgreSQL) |
| F30 | Cancelación y caducidad con devolución de puntos y stock; comando `expire_redemptions` | R F7 | `services._close:246`; `expire_pending_redemptions:297` | `test_services.py:333, 405, 452` | IV (programación: IP) |
| F31 | Panel del personal: inicio, perfil, resultados propios y solo el nombre abreviado del cliente | R F8 | `apps/staff/views.py` | `tests/staff/test_panel.py` (31) | IV (dispositivos: IP) |
| F32 | Dashboard del propietario con 14 secciones, solo OWNER | R F9 | `apps/dashboard/views.py:59-76` | `tests/dashboard/test_access.py` | IV |
| F33 | Estadísticas reales: compras registradas ≠ facturación | R F9 | `apps/purchases/selectors.py:1-9, 49-71` | `tests/purchases/test_stats.py`, `tests/dashboard/test_stats.py` | IV |
| F34 | Estadística geográfica por país, provincia, localidad o CP, solo con direcciones declaradas | R F9 | `apps/accounts/selectors.py:195-244` | `tests/dashboard/test_stats.py` | IV |
| F35 | Consulta auditada de la ficha del cliente y de la reserva con contacto | R F9/F10 | `services.record_customer_data_access:271`; `events.services.record_reservation_data_access:419` | `tests/dashboard/test_access.py:155` | IV |
| F36 | Contenido del local editable (singleton) con caché | D F9/F10 | `apps/web/models.py:43`; `services.py` | `tests/dashboard/*`, `tests/web/*` | IV |
| F37 | Eventos (borrador, publicado, archivado) gestionados desde el dashboard | R F10 | `apps/events/services.py:95-152` | `tests/events/test_services.py` | IV |
| F38 | Reservas de mesa y de evento, con estados, transiciones validadas, aforo y límites | R F10 | `apps/events/services.py:267-416`; `Reservation.TRANSITIONS` | `tests/events/*` (41) | IV |
| F39 | Notificaciones: registro con su estado real, reintentos y deduplicación | R F10 | `apps/notifications/services.py` | `tests/notifications/test_notifications.py` (30) | IV (con locmem) / IP (SMTP real) |
| F40 | Campañas promocionales solo a quien lo ha consentido, con enlace de baja firmado | R/D F10 | `apps/notifications/campaigns.py`; `unsubscribe.py` | `test_notifications.py` | IV (envío real: IP) |
| F41 | SMS | R F10 (opcional) | `apps/notifications/sms.py:1-12`: no hay proveedor | Backend locmem en tests | PL (sin proveedor) |
| F42 | Tareas programadas (`process_notifications`, `run_birthday_promotions`, `expire_redemptions`, `purge_email_tokens`, `flushexpiredtokens`) | R F10/despliegue | Existen los comandos; **no hay programación** (cron o Programador de tareas) | Tests de servicios | PA |
| F43 | API REST v1 con JWT (access de 15 min, refresh rotatorio y con lista negra, revocación al cambiar la contraseña) | R F11 | `apps/api/tokens.py`; `authentication.py` | `tests/api/test_auth.py` (28) | IV |
| F44 | Permisos DRF que envuelven los de accounts; IDOR → 404 | R F11 | `apps/api/permissions.py`; vistas `_own_*` | `tests/api/test_customer.py`, `test_staff_owner.py` | IV |
| F45 | Serializadores explícitos, paginación con tope de 50, errores `{code, detail, fields}`, solo JSON, `no-store`, sin CORS | R F11 | `apps/api/serializers/*`; `exceptions.py`; `pagination.py`; `views/base.py` | `tests/api/test_security.py` (9) | IV |
| F46 | OpenAPI sincronizado con el código | R F11 | `docs/api/openapi.yaml` | `spectacular --validate` + `diff` idéntico (2026-10-15) | IV |
| F47 | Auditoría (`AuditEvent`) de solo lectura y sin datos personales | R F0-F11 | `apps/core/models.py:15`; `admin.py` | `tests/core/*` (19) | IV |
| F48 | Configuración de producción endurecida (HTTPS, HSTS, cookies seguras, rechazo de backends simulados) | R F11 | `config/settings/prod.py` | `tests/core/test_audit_and_settings.py:54-87` (7 tests); `check --deploy` reproducido (solo W021) | IV (configuración) / PL (despliegue real) |
| F49 | IP real tras proxies de confianza (`TRUSTED_PROXY_COUNT`) | D F11 | `apps/core/http.py:18-27` | `tests/core/test_phase11_audit.py:30-40`; `tests/api/test_security.py:64` | IV |
| F50 | Purga de tokens de email caducados | D F11 | `services.purge_email_tokens:660`; comando | `tests/core/test_phase11_audit.py:110-124` | IV (programación: IP) |
| F51 | Despliegue (WSGI, estáticos y medios, backups, PostgreSQL, SMTP) | R «sin número» | `docs/despliegue.md` (guía); `requirements/prod.txt` sin servidor WSGI | — | PL |
| F52 | App móvil Flutter | Futuro | `docs/guia-app-flutter.md` (guía para el desarrollador) | — | PL (fuera de alcance) |
| F53 | Exportación o eliminación de datos personales a petición (derechos RGPD) | Prompt cap. 7.4 | No hay vista ni servicio de exportación o borrado; las cuentas se **desactivan**, no se borran | — | NI |
| F54 | Anulación de compras | Reservado | `Purchase.Status.VOIDED` sin flujo | `test_replay_of_voided_operation_is_rejected` (el estado se fuerza en el test) | PL |
| F55 | Integración con TPV | Reservado | `Purchase.Source.POS`, `external_reference` | — | PL |
