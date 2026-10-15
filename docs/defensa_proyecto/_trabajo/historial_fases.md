# Historial de Git por fase (generado con git log / git show --name-status)

> **Registro histórico.** Evidencia de la primera versión de la documentación de la defensa, sobre la Fase 11 (commit `ac5903a` del historial anterior, hoy `eec6abc`). No se ha actualizado: el estado de la versión congelada (commit `d0bac7c`, 849 tests) está en la [memoria](../01_memoria_tecnica_funcional.md) y en [`05_limitaciones_y_pendientes.md`](../05_limitaciones_y_pendientes.md).

Cada fase corresponde a **un único commit**. Todos son del 13 y 14-10-2026, así que el orden *dentro* de cada fase no se puede reconstruir. A = añadido, M = modificado, D = borrado.

## `40faf00` — 2026-10-13 · Creacion de carpeta con venv y gitignore y creacion de repositorio(primer commit)

2 files changed, 0 insertions(+), 0 deletions(-)

```text
A .gitignore
A requirements.txt
```

## `b2cfd56` — 2026-10-13 · Creacion de README, copilot-instructions, carpeta para media y carpeta para documentacion-Preparado para implementacion

6 files changed, 103 insertions(+)

```text
A .github/copilot-instructions.md
A README.md
A media/appejemplo.jpeg
A media/bannerknk.jpeg
A media/logoknk.jpeg
A media/logoknkany.jpeg
```

## `ea1a81a` — 2026-10-14 · Añadido CLAUDE.md

1 file changed, 114 insertions(+)

```text
A CLAUDE.md
```

## `4d842da` — 2026-10-14 · Planificacion de proyecto e implementacion de fase 0

54 files changed, 1988 insertions(+), 1 deletion(-)

```text
A .env.example
M .gitignore
M README.md
A apps/__init__.py
A apps/accounts/__init__.py
A apps/accounts/admin.py
A apps/accounts/apps.py
A apps/accounts/management/__init__.py
A apps/accounts/management/commands/__init__.py
A apps/accounts/management/commands/create_owner.py
A apps/accounts/managers.py
A apps/accounts/migrations/0001_initial.py
A apps/accounts/migrations/__init__.py
A apps/accounts/models.py
A apps/accounts/normalization.py
A apps/accounts/permissions.py
A apps/accounts/services.py
A apps/core/__init__.py
A apps/core/admin.py
A apps/core/apps.py
A apps/core/migrations/0001_initial.py
A apps/core/migrations/__init__.py
A apps/core/models.py
A apps/core/services.py
A config/__init__.py
A config/asgi.py
A config/settings/__init__.py
A config/settings/base.py
A config/settings/dev.py
A config/settings/prod.py
A config/settings/test.py
A config/urls.py
A config/wsgi.py
A docs/fase-00-fundacion.md
A docs/plan-de-fases.md
A manage.py
M requirements.txt
A requirements/base.txt
A requirements/dev.txt
A requirements/prod.txt
R100 media/appejemplo.jpeg static/img/brand/appejemplo.jpeg
R100 media/bannerknk.jpeg static/img/brand/bannerknk.jpeg
R100 media/logoknk.jpeg static/img/brand/logoknk.jpeg
R100 media/logoknkany.jpeg static/img/brand/logoknkany.jpeg
A tests/__init__.py
A tests/accounts/__init__.py
A tests/accounts/factories.py
A tests/accounts/test_admin.py
A tests/accounts/test_create_owner_command.py
A tests/accounts/test_models.py
A tests/accounts/test_permissions.py
A tests/accounts/test_services.py
A tests/core/__init__.py
A tests/core/test_audit_and_settings.py
```

## `b2cf7f6` — 2026-10-14 · Fase 1 implementada

10 files changed, 399 insertions(+), 47 deletions(-)

```text
M README.md
A apps/accounts/migrations/0002_customer_profile.py
A apps/accounts/migrations/0003_backfill_customer_profiles.py
M apps/accounts/models.py
M apps/accounts/services.py
A docs/arquitectura.md
M docs/fase-00-fundacion.md
A docs/fase-01-proyecto-base.md
M docs/plan-de-fases.md
A tests/accounts/test_customer_profile.py
```

## `d948db7` — 2026-10-14 · Fase 2 Implementada

64 files changed, 4064 insertions(+), 49 deletions(-)

```text
M .env.example
M README.md
M apps/accounts/admin.py
A apps/accounts/birthdays.py
A apps/accounts/countries.py
A apps/accounts/emails.py
A apps/accounts/forms.py
A apps/accounts/migrations/0004_user_email_verified_at.py
A apps/accounts/migrations/0005_customer_profile_personal_data.py
A apps/accounts/migrations/0006_email_tokens_and_preference_history.py
M apps/accounts/models.py
M apps/accounts/permissions.py
M apps/accounts/services.py
A apps/accounts/urls.py
A apps/accounts/validators.py
A apps/accounts/views.py
A apps/core/migrations/0002_audit_actions_phase2.py
M apps/core/models.py
A apps/core/throttling.py
M config/settings/base.py
M config/settings/dev.py
M config/settings/prod.py
M config/urls.py
M docs/arquitectura.md
M docs/fase-01-proyecto-base.md
A docs/fase-02-registro-perfil-verificacion.md
M docs/plan-de-fases.md
M requirements/base.txt
A static/css/base.css
A templates/accounts/_field.html
A templates/accounts/_verification_notice.html
A templates/accounts/email_change.html
A templates/accounts/login.html
A templates/accounts/password_change.html
A templates/accounts/password_reset_complete.html
A templates/accounts/password_reset_confirm.html
A templates/accounts/password_reset_done.html
A templates/accounts/password_reset_form.html
A templates/accounts/profile.html
A templates/accounts/register.html
A templates/accounts/register_done.html
A templates/accounts/resend_verification.html
A templates/accounts/staff_home.html
A templates/accounts/verify_email_confirm.html
A templates/accounts/verify_email_result.html
A templates/base.html
A templates/emails/email_change_body.txt
A templates/emails/email_change_subject.txt
A templates/emails/email_changed_notice_body.txt
A templates/emails/email_changed_notice_subject.txt
A templates/emails/existing_account_body.txt
A templates/emails/existing_account_subject.txt
A templates/emails/password_reset_body.txt
A templates/emails/password_reset_subject.txt
A templates/emails/verify_email_body.txt
A templates/emails/verify_email_subject.txt
M tests/accounts/factories.py
M tests/accounts/test_admin.py
A tests/accounts/test_auth_views.py
A tests/accounts/test_email_verification.py
A tests/accounts/test_profile.py
A tests/accounts/test_registration.py
A tests/accounts/test_validators.py
M tests/core/test_audit_and_settings.py
```

## `35424be` — 2026-10-14 · Fase 3 completada e implementada - Implementamos tailwind para estilo

61 files changed, 1679 insertions(+), 242 deletions(-)

```text
M .gitignore
M README.md
M apps/accounts/forms.py
A apps/web/__init__.py
A apps/web/apps.py
A apps/web/content.py
A apps/web/context_processors.py
A apps/web/urls.py
A apps/web/views.py
A assets/css/input.css
M config/settings/base.py
M config/urls.py
M docs/arquitectura.md
M docs/fase-02-registro-perfil-verificacion.md
A docs/fase-03-sistema-diseno-web-publica.md
M docs/plan-de-fases.md
A scripts/tailwind.py
A static/css/app.css
D static/css/base.css
A static/js/app.js
A templates/400.html
A templates/403.html
A templates/404.html
A templates/500.html
M templates/accounts/_field.html
A templates/accounts/_layout.html
M templates/accounts/_verification_notice.html
M templates/accounts/email_change.html
M templates/accounts/login.html
M templates/accounts/password_change.html
M templates/accounts/password_reset_complete.html
M templates/accounts/password_reset_confirm.html
M templates/accounts/password_reset_done.html
M templates/accounts/password_reset_form.html
M templates/accounts/profile.html
M templates/accounts/register.html
M templates/accounts/register_done.html
M templates/accounts/resend_verification.html
M templates/accounts/staff_home.html
M templates/accounts/verify_email_confirm.html
M templates/accounts/verify_email_result.html
M templates/base.html
A templates/components/business_info.html
A templates/components/empty_state.html
A templates/components/error_page.html
A templates/components/footer.html
A templates/components/form_errors.html
A templates/components/loyalty_steps.html
A templates/components/page_header.html
A templates/components/pending.html
A templates/components/section_heading.html
A templates/web/about.html
A templates/web/contact.html
A templates/web/events.html
A templates/web/home.html
A templates/web/menu.html
A templates/web/rewards.html
M tests/accounts/test_registration.py
A tests/web/__init__.py
A tests/web/test_account_forms_ui.py
A tests/web/test_public_pages.py
```

## `b035ca4` — 2026-10-14 · Fase 4 finalizada

32 files changed, 1907 insertions(+), 19 deletions(-)

```text
M README.md
A apps/catalog/__init__.py
A apps/catalog/admin.py
A apps/catalog/apps.py
A apps/catalog/migrations/0001_initial.py
A apps/catalog/migrations/__init__.py
A apps/catalog/models.py
A apps/catalog/selectors.py
A apps/catalog/services.py
A apps/catalog/validators.py
A apps/core/migrations/0003_audit_actions_phase4.py
M apps/core/models.py
M apps/web/views.py
M config/settings/base.py
M config/urls.py
M docs/arquitectura.md
A docs/fase-04-carta.md
M docs/plan-de-fases.md
M requirements/base.txt
M static/css/app.css
A templates/components/product_card.html
A templates/components/tap_menu.html
M templates/web/home.html
M templates/web/menu.html
A tests/catalog/__init__.py
A tests/catalog/factories.py
A tests/catalog/test_admin.py
A tests/catalog/test_models.py
A tests/catalog/test_selectors.py
A tests/catalog/test_services.py
A tests/catalog/test_validators.py
A tests/web/test_menu_page.py
```

## `d1c1a89` — 2026-10-14 · Fase 5 completada y migraciones pendientes realizadas

44 files changed, 12462 insertions(+), 17 deletions(-)

```text
M README.md
A apps/core/migrations/0004_audit_actions_phase5.py
M apps/core/models.py
A apps/loyalty/__init__.py
A apps/loyalty/apps.py
A apps/loyalty/migrations/0001_initial.py
A apps/loyalty/migrations/__init__.py
A apps/loyalty/models.py
A apps/loyalty/services.py
A apps/loyalty/urls.py
A apps/loyalty/views.py
A apps/purchases/__init__.py
A apps/purchases/admin.py
A apps/purchases/apps.py
A apps/purchases/forms.py
A apps/purchases/migrations/0001_initial.py
A apps/purchases/migrations/__init__.py
A apps/purchases/models.py
A apps/purchases/services.py
A apps/purchases/urls.py
A apps/purchases/views.py
M config/settings/base.py
M config/urls.py
M docs/arquitectura.md
A docs/fase-05-qr-compras.md
M docs/plan-de-fases.md
M requirements/base.txt
M static/css/app.css
A static/js/qr-scanner.js
A static/vendor/jsqr/LICENSE
A static/vendor/jsqr/jsQR.js
M templates/accounts/profile.html
M templates/accounts/staff_home.html
M templates/base.html
A templates/loyalty/my_qr.html
A templates/purchases/confirm.html
A templates/purchases/detail.html
A templates/purchases/scan.html
A tests/loyalty/__init__.py
A tests/loyalty/factories.py
A tests/loyalty/test_qr.py
A tests/purchases/__init__.py
A tests/purchases/test_services.py
A tests/purchases/test_views.py
```

## `99711bc` — 2026-10-14 · Fase 6 completada

31 files changed, 2864 insertions(+), 28 deletions(-)

```text
M README.md
A apps/core/migrations/0005_audit_actions_phase6.py
M apps/core/models.py
A apps/loyalty/admin.py
A apps/loyalty/conversion.py
A apps/loyalty/ledger.py
A apps/loyalty/migrations/0002_points_ledger_promotions.py
M apps/loyalty/models.py
A apps/loyalty/promotions.py
A apps/loyalty/selectors.py
M apps/loyalty/urls.py
M apps/loyalty/views.py
A apps/purchases/selectors.py
M apps/purchases/services.py
M apps/purchases/views.py
M config/settings/base.py
M config/urls.py
M docs/arquitectura.md
M docs/fase-05-qr-compras.md
A docs/fase-06-fidelizacion.md
M docs/plan-de-fases.md
M static/css/app.css
M templates/accounts/profile.html
A templates/loyalty/my_points.html
M templates/purchases/detail.html
M tests/loyalty/factories.py
A tests/loyalty/test_points.py
A tests/loyalty/test_points_views.py
A tests/loyalty/test_promotions.py
A tests/purchases/test_stats.py
M tests/purchases/test_views.py
```

## `c185ff4` — 2026-10-14 · Fase 7 finalizada

45 files changed, 2902 insertions(+), 56 deletions(-)

```text
M README.md
A apps/core/migrations/0006_audit_actions_phase7.py
M apps/core/models.py
M apps/loyalty/ledger.py
M apps/loyalty/models.py
M apps/loyalty/selectors.py
A apps/rewards/__init__.py
A apps/rewards/admin.py
A apps/rewards/apps.py
A apps/rewards/codes.py
A apps/rewards/forms.py
A apps/rewards/management/__init__.py
A apps/rewards/management/commands/__init__.py
A apps/rewards/management/commands/expire_redemptions.py
A apps/rewards/migrations/0001_rewards_redemptions.py
A apps/rewards/migrations/__init__.py
A apps/rewards/models.py
A apps/rewards/panel_urls.py
A apps/rewards/selectors.py
A apps/rewards/services.py
A apps/rewards/urls.py
A apps/rewards/views.py
M apps/web/views.py
M config/settings/base.py
M config/urls.py
M docs/arquitectura.md
M docs/fase-06-fidelizacion.md
A docs/fase-07-recompensas-canjes.md
M docs/plan-de-fases.md
M static/css/app.css
M templates/accounts/profile.html
M templates/accounts/staff_home.html
M templates/loyalty/my_points.html
A templates/rewards/my_redemptions.html
A templates/rewards/redemption_detail.html
A templates/rewards/reward_detail.html
A templates/rewards/staff_confirm.html
A templates/rewards/staff_detail.html
A templates/rewards/staff_scan.html
M templates/web/rewards.html
A tests/rewards/__init__.py
A tests/rewards/factories.py
A tests/rewards/test_concurrency.py
A tests/rewards/test_services.py
A tests/rewards/test_views.py
```

## `1131258` — 2026-10-14 · Fase 8 completada

38 files changed, 919 insertions(+), 68 deletions(-)

```text
M README.md
M apps/accounts/views.py
M apps/purchases/forms.py
M apps/purchases/selectors.py
M apps/rewards/selectors.py
A apps/staff/__init__.py
A apps/staff/apps.py
A apps/staff/forms.py
A apps/staff/urls.py
A apps/staff/views.py
M assets/css/input.css
M config/settings/base.py
M config/urls.py
M docs/arquitectura.md
A docs/fase-08-panel-empleados.md
M docs/plan-de-fases.md
M static/css/app.css
D templates/accounts/staff_home.html
M templates/base.html
M templates/purchases/confirm.html
M templates/purchases/detail.html
M templates/purchases/scan.html
M templates/rewards/staff_confirm.html
M templates/rewards/staff_detail.html
M templates/rewards/staff_scan.html
A templates/staff/_done.html
A templates/staff/_layout.html
A templates/staff/_summary.html
A templates/staff/home.html
A templates/staff/profile.html
A templates/staff/results.html
M tests/accounts/test_admin.py
M tests/accounts/test_auth_views.py
M tests/accounts/test_profile.py
M tests/purchases/test_views.py
M tests/rewards/test_views.py
A tests/staff/__init__.py
A tests/staff/test_panel.py
```

## `70fb531` — 2026-10-14 · Fase 9 completada

55 files changed, 3416 insertions(+), 18 deletions(-)

```text
M README.md
A apps/accounts/selectors.py
M apps/accounts/services.py
M apps/accounts/views.py
M apps/catalog/selectors.py
A apps/core/migrations/0007_audit_actions_phase9.py
M apps/core/models.py
A apps/dashboard/__init__.py
A apps/dashboard/apps.py
A apps/dashboard/forms.py
A apps/dashboard/urls.py
A apps/dashboard/views.py
M apps/loyalty/conversion.py
M apps/loyalty/ledger.py
M apps/loyalty/promotions.py
M apps/loyalty/selectors.py
M apps/purchases/selectors.py
M apps/rewards/selectors.py
M apps/rewards/services.py
M apps/web/content.py
M apps/web/context_processors.py
A apps/web/migrations/0001_business_info.py
A apps/web/migrations/__init__.py
A apps/web/models.py
A apps/web/services.py
M assets/css/input.css
M config/settings/base.py
M config/urls.py
M docs/arquitectura.md
A docs/fase-09-dashboard-propietario.md
M docs/plan-de-fases.md
M static/css/app.css
M templates/base.html
A templates/dashboard/_layout.html
A templates/dashboard/_pagination.html
A templates/dashboard/_period_fields.html
A templates/dashboard/_period_notice.html
A templates/dashboard/content.html
A templates/dashboard/customer_detail.html
A templates/dashboard/customer_zones.html
A templates/dashboard/customers.html
A templates/dashboard/employees.html
A templates/dashboard/home.html
A templates/dashboard/pending_phase.html
A templates/dashboard/points.html
A templates/dashboard/products.html
A templates/dashboard/promotions.html
A templates/dashboard/purchases.html
A templates/dashboard/rewards.html
A templates/dashboard/settings.html
M tests/accounts/test_auth_views.py
A tests/dashboard/__init__.py
A tests/dashboard/test_access.py
A tests/dashboard/test_customers_and_actions.py
A tests/dashboard/test_stats.py
```

## `a85ce95` — 2026-10-14 · Fase 10 completada

112 files changed, 5187 insertions(+), 300 deletions(-)

```text
M .env.example
M README.md
M apps/accounts/emails.py
M apps/accounts/forms.py
A apps/accounts/migrations/0007_preference_source_unsubscribe.py
M apps/accounts/models.py
M apps/accounts/services.py
M apps/accounts/views.py
A apps/core/migrations/0008_audit_actions_phase10.py
M apps/core/models.py
M apps/dashboard/forms.py
M apps/dashboard/urls.py
M apps/dashboard/views.py
A apps/events/__init__.py
A apps/events/admin.py
A apps/events/apps.py
A apps/events/forms.py
A apps/events/migrations/0001_events_reservations.py
A apps/events/migrations/__init__.py
A apps/events/models.py
A apps/events/selectors.py
A apps/events/services.py
A apps/events/urls.py
A apps/events/views.py
M apps/loyalty/admin.py
A apps/loyalty/birthdays.py
M apps/loyalty/ledger.py
A apps/loyalty/management/__init__.py
A apps/loyalty/management/commands/__init__.py
A apps/loyalty/management/commands/run_birthday_promotions.py
A apps/loyalty/migrations/0003_birthday_gift.py
M apps/loyalty/models.py
M apps/loyalty/promotions.py
M apps/loyalty/selectors.py
A apps/notifications/__init__.py
A apps/notifications/admin.py
A apps/notifications/apps.py
A apps/notifications/campaigns.py
A apps/notifications/management/__init__.py
A apps/notifications/management/commands/__init__.py
A apps/notifications/management/commands/process_notifications.py
A apps/notifications/migrations/0001_notifications_campaigns.py
A apps/notifications/migrations/__init__.py
A apps/notifications/models.py
A apps/notifications/selectors.py
A apps/notifications/services.py
A apps/notifications/sms.py
A apps/notifications/unsubscribe.py
A apps/notifications/urls.py
A apps/notifications/views.py
M apps/rewards/management/commands/expire_redemptions.py
M apps/web/content.py
A apps/web/migrations/0002_home_texts.py
M apps/web/models.py
M apps/web/services.py
M apps/web/views.py
M config/settings/base.py
M config/settings/prod.py
M config/settings/test.py
M config/urls.py
M docs/arquitectura.md
M docs/fase-06-fidelizacion.md
M docs/fase-09-dashboard-propietario.md
A docs/fase-10-eventos-reservas-notificaciones.md
M docs/plan-de-fases.md
M static/css/app.css
M templates/accounts/profile.html
A templates/components/event_card.html
A templates/dashboard/campaign_form.html
A templates/dashboard/communications.html
A templates/dashboard/event_form.html
A templates/dashboard/events.html
M templates/dashboard/home.html
D templates/dashboard/pending_phase.html
M templates/dashboard/promotions.html
A templates/dashboard/reservation_detail.html
A templates/dashboard/reservations.html
A templates/events/event_detail.html
A templates/events/my_reservations.html
A templates/events/reservation_detail.html
A templates/events/reservation_form.html
A templates/notifications/birthday_body.txt
A templates/notifications/birthday_sms.txt
A templates/notifications/birthday_subject.txt
A templates/notifications/campaign_body.txt
A templates/notifications/campaign_sms.txt
A templates/notifications/campaign_subject.txt
A templates/notifications/reservation_cancelled_body.txt
A templates/notifications/reservation_cancelled_subject.txt
A templates/notifications/reservation_confirmed_body.txt
A templates/notifications/reservation_confirmed_subject.txt
A templates/notifications/reservation_owner_alert_body.txt
A templates/notifications/reservation_owner_alert_subject.txt
A templates/notifications/reservation_received_body.txt
A templates/notifications/reservation_received_subject.txt
A templates/notifications/reservation_rejected_body.txt
A templates/notifications/reservation_rejected_subject.txt
A templates/notifications/unsubscribe.html
M templates/web/events.html
M templates/web/home.html
M tests/accounts/test_email_verification.py
M tests/dashboard/test_access.py
M tests/dashboard/test_stats.py
A tests/events/__init__.py
A tests/events/factories.py
A tests/events/test_services.py
A tests/events/test_views.py
A tests/loyalty/test_birthdays.py
M tests/loyalty/test_promotions.py
A tests/notifications/__init__.py
A tests/notifications/test_notifications.py
```

## `ac5903a` — 2026-10-14 · Fase 11 y ultima completada, continuaremos con despliegue y futuras funciones

60 files changed, 6758 insertions(+), 46 deletions(-)

```text
M .env.example
M README.md
M apps/accounts/forms.py
A apps/accounts/management/commands/purge_email_tokens.py
M apps/accounts/services.py
M apps/accounts/views.py
A apps/api/__init__.py
A apps/api/admin.py
A apps/api/apps.py
A apps/api/authentication.py
A apps/api/exceptions.py
A apps/api/pagination.py
A apps/api/permissions.py
A apps/api/schema.py
A apps/api/serializers/__init__.py
A apps/api/serializers/accounts.py
A apps/api/serializers/auth.py
A apps/api/serializers/events.py
A apps/api/serializers/loyalty.py
A apps/api/serializers/owner.py
A apps/api/serializers/rewards.py
A apps/api/serializers/staff.py
A apps/api/throttling.py
A apps/api/tokens.py
A apps/api/urls.py
A apps/api/views/__init__.py
A apps/api/views/auth.py
A apps/api/views/base.py
A apps/api/views/events.py
A apps/api/views/loyalty.py
A apps/api/views/me.py
A apps/api/views/owner.py
A apps/api/views/rewards.py
A apps/api/views/staff.py
A apps/core/http.py
A apps/core/migrations/0009_audit_actions_phase11.py
M apps/core/models.py
M config/settings/base.py
M config/settings/dev.py
M config/settings/prod.py
M config/settings/test.py
M config/urls.py
A docs/api/openapi.yaml
M docs/arquitectura.md
A docs/despliegue.md
A docs/fase-11-api-auditoria.md
A docs/guia-app-flutter.md
M docs/plan-de-fases.md
M requirements/base.txt
M templates/web/home.html
A tests/api/__init__.py
A tests/api/base.py
A tests/api/test_auth.py
A tests/api/test_customer.py
A tests/api/test_me.py
A tests/api/test_security.py
A tests/api/test_staff_owner.py
M tests/core/test_audit_and_settings.py
A tests/core/test_phase11_audit.py
M tests/web/test_public_pages.py
```

