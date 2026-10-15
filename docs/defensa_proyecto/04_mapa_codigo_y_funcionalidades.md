# Caneca Furada — Mapa de código y funcionalidades

Índice para localizar rápidamente el código de cada funcionalidad. Las rutas URL se han obtenido con `get_resolver()` (volcado completo en [`_trabajo/volcado_urls.md`](_trabajo/volcado_urls.md)) y las líneas son las del commit `ac5903a`. Abreviaturas: `acc` = `apps/accounts`, `loy` = `apps/loyalty`, `pur` = `apps/purchases`, `rew` = `apps/rewards`, `evt` = `apps/events`, `ntf` = `apps/notifications`, `dash` = `apps/dashboard`, `T` = `templates/`.

## 1. Funcionalidad → URL → vista → servicio o selector → modelo → plantilla → tests

### Web pública

| Funcionalidad | URL (nombre) | Vista | Servicio / selector | Modelo | Plantilla | Tests |
|---|---|---|---|---|---|---|
| Inicio | `/` (`web:home`) | `apps/web/views.py:15` `HomeView` | `catalog.selectors.featured_beers`, `events.selectors.featured_events` | Product, Event | `T/web/home.html` | `tests/web/test_public_pages.py` |
| La cervecería | `/la-cerveceria/` (`web:about`) | `views.py:25` | `web.services.business_info` (context processor) | BusinessInfo | `T/web/about.html` | ídem |
| Carta | `/carta/` (`web:menu`) | `views.py:29` `MenuView` | `catalog.selectors.public_menu`, `current_tap_menu` | Category, Product, TapMenu | `T/web/menu.html`, `T/components/product_card.html`, `tap_menu.html` | `tests/web/test_menu_page.py` |
| Recompensas (públicas) | `/recompensas/` (`web:rewards`) | `views.py:39` | `rewards.selectors.public_rewards` | Reward | `T/web/rewards.html` | `tests/web/*` |
| Eventos | `/eventos/` (`web:events`), `/eventos/<uuid>/` (`events:event_detail`) | `views.py:48`; `evt/views.py:38` | `events.selectors.public_events`, `public_event`, `is_bookable`, `seats_left` | Event | `T/web/events.html`, `T/events/event_detail.html` | `tests/events/test_views.py` |
| Contacto | `/contacto/` (`web:contact`) | `views.py:57` | `business_info` | BusinessInfo | `T/web/contact.html` | `tests/web/*` |

### Cuentas (`/cuenta/`)

| Funcionalidad | URL (nombre) | Vista | Servicio | Modelo | Plantilla | Tests |
|---|---|---|---|---|---|---|
| Registro | `registro/` (`accounts:register`) | `acc/views.py:42` | `services.register_customer` (`:373`), `notify_existing_account` (`:454`) | User, CustomerProfile, CommunicationPreferenceChange, EmailVerificationToken | `T/accounts/register.html`, `register_done.html` | `tests/accounts/test_registration.py` |
| Verificar email | `verificar-email/<token>/` (`accounts:verify_email`) | `views.py:71` | `confirm_email_token` (`:562`) | EmailVerificationToken | `verify_email_confirm.html`, `verify_email_result.html` | `test_email_verification.py` |
| Reenviar verificación | `verificar-email/reenviar/`, `reenviar-mio/` | `views.py:93`, `:109` | `request_verification_resend` (`:534`), `resend_verification_email` (`:521`) | ídem | `resend_verification.html` | ídem |
| Login / logout | `entrar/` (`accounts:login`), `salir/` (`accounts:logout`) | `views.py:222` `LoginView`; `LogoutView` de Django | `login_throttle_keys` (`:350`) | User | `login.html` | `test_auth_views.py` |
| Redirección por rol | `/cuenta/` (`accounts:home`) | `views.py:126` | — | — | — | `test_auth_views.py` |
| Perfil | `perfil/` (`accounts:profile`) | `views.py:146` | `update_customer_profile` (`:753`) | CustomerProfile | `profile.html` | `test_profile.py` |
| Preferencias | `perfil/preferencias/` | `views.py:184` | `set_communication_preferences` (`:822`) | CustomerProfile, CommunicationPreferenceChange | `profile.html` (#preferencias) | `test_profile.py` |
| Cambio de email | `perfil/email/` | `views.py:200` | `request_email_change` (`:629`) | EmailVerificationToken | `email_change.html` | `test_email_verification.py` |
| Cambio de contraseña | `perfil/contrasena/` | `views.py:258` | `record_password_change` (`:683`) | User | `password_change.html` | `tests/core/test_phase11_audit.py` |
| Recuperación | `contrasena/recuperar/`, `.../enviado/`, `restablecer/<uidb64>/<token>/`, `restablecida/` | `views.py:228`, `:248` + vistas de Django | `forms.NotifyingPasswordResetForm` → `emails.send_password_reset` | User, Notification | `password_reset_*.html`, `T/emails/password_reset_*.txt` | ídem |

### Fidelización del cliente (`/cuenta/`, cliente verificado)

| Funcionalidad | URL (nombre) | Vista | Servicio / selector | Modelo | Plantilla | Tests |
|---|---|---|---|---|---|---|
| Mi QR | `mi-qr/` (`loyalty:my_qr`) | `loy/views.py:28` | `services.get_customer_qr` (`:97`), `qr_payload`, `format_code` | CustomerQRCode | `T/loyalty/my_qr.html` | `tests/loyalty/test_qr.py` |
| Renovar QR | `mi-qr/renovar/` (`loyalty:rotate`) | `views.py:68` | `rotate_customer_qr` (`:112`) | CustomerQRCode, AuditEvent | — | ídem |
| Mis puntos | `puntos/` (`loyalty:my_points`) | `views.py:47` | `selectors.points_summary`, `points_history`; `purchases.selectors.customer_purchases` | PointsTransaction, Purchase | `T/loyalty/my_points.html` | `test_points_views.py` |
| Ver y canjear una recompensa | `recompensas/<uuid>/`, `.../canjear/` (`rewards:reward_detail`, `rewards:redeem`) | `rew/views.py:71`, `:79` | `services.request_redemption` (`:213`) | Reward, Redemption, PointsTransaction | `T/rewards/reward_detail.html` | `tests/rewards/test_services.py`, `test_views.py` |
| Mis canjes / detalle / cancelar | `canjes/`, `canjes/<uuid>/`, `.../cancelar/` | `views.py:105`, `:122`, `:137` | `selectors.customer_redemptions`, `customer_redemption`; `services.cancel_redemption` (`:281`) | Redemption | `my_redemptions.html`, `redemption_detail.html` | ídem |
| Reservas | `reservas/`, `reservas/nueva/`, `reservas/evento/<uuid>/`, `reservas/<uuid>/`, `.../cancelar/` | `evt/views.py:63`, `:85`, `:102`, `:136`, `:144` | `events.services.request_reservation` (`:307`), `cancel_own_reservation` (`:413`) | Reservation, Event | `T/events/*` | `tests/events/*` |

### Panel del personal (`/panel/`)

| Funcionalidad | URL (nombre) | Vista | Servicio / selector | Modelo | Plantilla | Tests |
|---|---|---|---|---|---|---|
| Inicio, perfil y resultados | `/panel/`, `perfil/`, `resultados/` (`staff:*`) | `apps/staff/views.py:41`, `:48`, `:56` | `purchases.selectors.staff_purchases_summary`, `purchases_registered_by`; `rewards.selectors.validations_by` | Purchase, Redemption | `T/staff/*` | `tests/staff/test_panel.py` |
| Registrar compra | `compras/`, `compras/identificar/`, `compras/registrar/`, `compras/<uuid>/` (`purchases:*`) | `pur/views.py:56`, `:63`, `:87`, `:123` | `services.identify_for_purchase` (`:112`), `register_purchase` (`:158`), `visible_purchases` (`:200`) | Purchase, PointsTransaction | `T/purchases/scan.html`, `confirm.html`, `detail.html` | `tests/purchases/*` |
| Validar canje | `canjes/`, `canjes/consultar/`, `canjes/validar/`, `canjes/<uuid>/` (`rewards_panel:*`) | `rew/views.py:171`, `:178`, `:195`, `:213` | `lookup_redemption` (`:356`), `validate_redemption` (`:370`), `visible_redemptions_for_staff` (`:431`) | Redemption | `T/rewards/staff_*.html` | `tests/rewards/*` |

### Dashboard del propietario (`/dashboard/`)

| Sección | URL | Vista (`dash/views.py`) | Servicios / selectores | Tests |
|---|---|---|---|---|
| Resumen | `/dashboard/` | `home` `:122` | `customer_counts`, `registered_purchases_stats`, `points_stats`, `redemption_stats`, `reservation_stats`, `geographic_distribution` | `tests/dashboard/test_stats.py` |
| Clientes | `clientes/`, `clientes/<uuid>/`, `.../ajustar-puntos/`, `.../compensar/`, `clientes/zonas/` | `customers` `:149`, `customer_detail` `:200`, `customer_adjust_points` `:231`, `customer_reverse_movement` `:258`, `customer_zones` `:283` | `accounts.selectors.*`, `record_customer_data_access`, `ledger.adjust_points`, `reverse_movement` | `test_customers_and_actions.py` |
| Empleados | `empleados/`, `nuevo/`, `<uuid>/estado/`, `<uuid>/rol/` | `employees` `:361`, `employee_create` `:368`, `employee_status` `:395`, `employee_role` `:416` | `accounts.services.create_employee`, `set_user_active`, `change_role` | `test_access.py` |
| Compras / Puntos | `compras/`, `puntos/` | `purchases` `:440`, `points` `:470` | `purchases.selectors.all_purchases`; `loyalty.selectors.all_movements` | `test_stats.py` |
| Recompensas / Promociones | `recompensas/`, `.../estado/`, `promociones/`, `.../estado/` | `rewards_view` `:497`, `reward_status` `:522`, `promotions_view` `:538`, `promotion_status` `:553` | `rewards.services.set_reward_status`; `promotions.set_promotion_status` | `test_customers_and_actions.py` |
| Carta / Cervezas | `carta/`, `cervezas/`, `productos/<uuid>/estado/`, `.../disponibilidad/` | `menu` `:596`, `beers` `:603`, `product_status` `:622`, `product_availability` `:636` | `catalog.services.*`, `products_for_management` | `test_access.py` |
| Eventos | `eventos/`, `nuevo/`, `<uuid>/editar/`, `<uuid>/estado/` | `events` `:662`, `event_create` `:698`, `event_edit` `:705`, `event_status` `:712` | `events.services.save_event`, `set_event_status` | `tests/events/*` |
| Reservas | `reservas/`, `<uuid>/`, `<uuid>/estado/` | `reservations` `:729`, `reservation_detail` `:760`, `reservation_action` `:796` | `events.services.*_reservation`, `record_reservation_data_access` | `tests/events/*` |
| Comunicaciones | `comunicaciones/`, `nueva/`, `<uuid>/editar/`, `programar/`, `cancelar/` | `communications` `:826`, `campaign_create` `:882`, `campaign_edit` `:889`, `campaign_queue` `:900`, `campaign_cancel` `:917` | `notifications.campaigns.*`, `selectors.*` | `tests/notifications/*` |
| Contenido / Configuración | `contenido/`, `configuracion/` | `content` `:934`, `settings_view` `:956` | `web.services.update_business_info`; `loyalty.conversion.create_rule` | `tests/dashboard/*` |

### Otros

| Funcionalidad | Ubicación | Notas |
|---|---|---|
| Baja de comunicaciones | `/comunicaciones/baja/<token>/` → `ntf/views.py:21` → `unsubscribe.read_token`, `accounts.services.withdraw_promotional_consent` | `T/notifications/unsubscribe.html` |
| Envío de notificaciones | `ntf/services.py`: `send_immediately` `:130`, `enqueue` `:165`, `deliver` `:264`, `process_due` `:325` | Plantillas `T/emails/*.txt` (cuentas) y `T/notifications/*.txt` (resto) |
| Admin técnico | `/<DJANGO_ADMIN_URL>` (`admin/` por defecto) | Admins en `apps/*/admin.py` (solo propietario; sin borrado) |
| API REST v1 | `/api/v1/...` (38 rutas) | Ver la tabla del cap. 7.14 de la memoria; `apps/api/urls.py` |
| Documentación de la API | `/api/v1/schema/`, `/api/v1/docs/` | `CanReadApiDocs` |

## 2. Comandos de gestión

| Comando | Archivo | Servicio | Frecuencia prevista |
|---|---|---|---|
| `create_owner [--noinput]` | `acc/management/commands/create_owner.py` | `accounts.services.create_owner` | Una vez |
| `purge_email_tokens [--days N]` | `acc/management/commands/purge_email_tokens.py` | `purge_email_tokens` | Diaria |
| `run_birthday_promotions [--days-back N] [--date AAAA-MM-DD]` | `loy/management/commands/run_birthday_promotions.py` | `loyalty.birthdays.run_birthday_promotions` | Diaria |
| `expire_redemptions` | `rew/management/commands/expire_redemptions.py` | `rewards.services.expire_pending_redemptions` | Diaria |
| `process_notifications [--limit N]` | `ntf/management/commands/process_notifications.py` | `campaigns.dispatch_queued` + `services.process_due` | Cada 5 min |
| `flushexpiredtokens` | simplejwt | — | Diaria |

## 3. Clases y funciones clave por módulo

| Módulo | Elementos clave (archivo:línea) |
|---|---|
| core | `TimeStampedModel` `models.py:5`; `AuditEvent` `:15`; `record_audit_event` `services.py:4`; `is_limited` `throttling.py:19`; `register_attempt` `throttling.py:23`; `client_ip` `http.py:18`; `ip_limited` `:30` |
| accounts | `User` `models.py:21`; `CustomerProfile` `:157`; `EmailVerificationToken` `:262`; `CommunicationPreferenceChange` `:308`; `UserManager` `managers.py:6`; `has_role` `permissions.py:17`; `role_required` `:35`; `verified_email_required` `:55`; `RoleRequiredMixin` `:72`; `_create_user` `services.py:96`; `change_role` `:198`; `set_user_active` `:241`; `register_customer` `:373`; `_issue_email_token` `:469`; `confirm_email_token` `:562`; `update_customer_profile` `:753`; `can_receive_promotional_email` `:885`; `geographic_distribution` `selectors.py:195`; `ThrottledAuthenticationForm` `forms.py:173` |
| catalog | `Product` `models.py:89`; `public_menu` `selectors.py:31`; `set_product_status` `services.py:27`; `validate_image_file` `validators.py:29`; `OwnerOnlyAdminMixin` `admin.py:22` |
| loyalty | `CustomerQRCode` `models.py:15`; `LoyaltyRule` `:56`; `Promotion` `:112`; `PointsTransaction` `:276`; `generate_token` `services.py:54`; `identify_customer` `:127`; `balance` `ledger.py:58`; `_append` `:67`; `award_points_for_purchase` `:75`; `adjust_points` `:182`; `reverse_movement` `:250`; `spend_points` `:291`; `grant_birthday_gift` `:319`; `calculate_points` `conversion.py:43`; `bonuses_for_purchase` `promotions.py:107`; `birthday_year_for` `:77`; `run_birthday_promotions` `birthdays.py:69`; `points_summary` `selectors.py:49` |
| purchases | `Purchase` `models.py:21`; `parse_amount` `services.py:63`; `register_purchase` `:158`; `_replay` `:140`; `registered_purchases_stats` `selectors.py:49` |
| rewards | `Reward` `models.py:36`; `Redemption` `:133`; `generate_code` `codes.py:26`; `_create_redemption` `services.py:176`; `request_redemption` `:213`; `_close` `:246`; `validate_redemption` `:370`; `redemption_stats` `selectors.py:87` |
| events | `Event` `models.py:42`; `Reservation` `:112` (`TRANSITIONS` `:121`); `save_event` `services.py:95`; `_create` `:267`; `request_reservation` `:307`; `_transition` `:340`; `public_events` `selectors.py:42` |
| notifications | `Campaign` `models.py:36`; `Notification` `:80`; `send_immediately` `services.py:130`; `enqueue` `:165`; `deliver` `:264`; `dispatch_queued` `campaigns.py:127`; `make_token` `unsubscribe.py:25`; `read_token` `unsubscribe.py:33` |
| web | `BusinessInfo` `models.py:43`; `business_info` `services.py:55`; `site` `context_processors.py:4` |
| api | `JWTAuthentication` `authentication.py:16`; `password_version` `tokens.py:43`; `rotate_refresh_token` `:85`; `HasRole` `permissions.py:15`; `exception_handler` `exceptions.py:103`; `PageNumberPagination` `pagination.py:4` |
| dashboard / staff | `SECTIONS` `dashboard/views.py:59`; `PeriodForm` `dashboard/forms.py:63`; `staff.views.results` `staff/views.py:56` |

## 4. Diagramas

| Diagrama | Archivo |
|---|---|
| Arquitectura general | [diagramas/01_arquitectura_general.mmd](diagramas/01_arquitectura_general.mmd) |
| Dependencias entre módulos | [diagramas/02_modulos_dependencias.mmd](diagramas/02_modulos_dependencias.mmd) |
| Ciclo de una petición | [diagramas/03_ciclo_peticion.mmd](diagramas/03_ciclo_peticion.mmd) |
| Entidad-relación | [diagramas/04_entidad_relacion.mmd](diagramas/04_entidad_relacion.mmd) |
| Autenticación (web y JWT) | [diagramas/05_autenticacion.mmd](diagramas/05_autenticacion.mmd) |
| Registro y verificación | [diagramas/06_registro_verificacion.mmd](diagramas/06_registro_verificacion.mmd) |
| Compra y puntos | [diagramas/07_compra_puntos.mmd](diagramas/07_compra_puntos.mmd) |
| Canje y validación | [diagramas/08_canje_recompensa.mmd](diagramas/08_canje_recompensa.mmd) |
| Estados del canje | [diagramas/09_estados_canje.mmd](diagramas/09_estados_canje.mmd) |
| Estados de la reserva | [diagramas/10_estados_reserva.mmd](diagramas/10_estados_reserva.mmd) |
| Roles y permisos | [diagramas/11_roles_permisos.mmd](diagramas/11_roles_permisos.mmd) |
| Flujo de una reserva | [diagramas/12_reserva_flujo.mmd](diagramas/12_reserva_flujo.mmd) |
| Estados de una notificación | [diagramas/13_notificaciones.mmd](diagramas/13_notificaciones.mmd) |
| Despliegue (propuesta) | [diagramas/14_despliegue_propuesta.mmd](diagramas/14_despliegue_propuesta.mmd) |
