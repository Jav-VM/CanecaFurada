# Volcado de modelos (generado con apps.get_models() y _meta)

> **Registro histórico.** Evidencia de la primera versión de la documentación de la defensa, sobre la Fase 11 (commit `ac5903a` del historial anterior, hoy `eec6abc`). No se ha actualizado: el estado de la versión congelada (commit `d0bac7c`, 849 tests) está en la [memoria](../01_memoria_tecnica_funcional.md) y en [`05_limitaciones_y_pendientes.md`](../05_limitaciones_y_pendientes.md).

## core.AuditEvent  (`apps/core/models.py:15`) — tabla `core_auditevent`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| id | BigAutoField | False | True | True |  |  |
| actor | ForeignKey | True | True | False |  | → accounts.User (on_delete=SET_NULL) |
| action | CharField(40) | False | False | False |  | choices: OWNER_CREATED, EMPLOYEE_CREATED, CUSTOMER_CREATED, ROLE_CHANGED, ACCOUNT_ACTIVATED, ACCOUNT_DEACTIVATED, EMAIL_VERIFIED, EMAIL_CHANGE_REQUESTED, EMAIL_CHANGED,  |
| target_public_id | UUIDField(32) | True | True | False |  |  |
| metadata | JSONField | False | True | False | dict |  |
| created_at | DateTimeField | False | True | False |  |  |

**Índices:**
- `core_audite_action_3957f4_idx`: ['action', 'created_at'] 

**ordering:** ['-created_at', '-id']

## accounts.User  (`apps/accounts/models.py:21`) — tabla `accounts_user`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| logentry | ManyToOneRel | | | | | ← inverso de LogEntry.user |
| outstandingtoken | ManyToOneRel | | | | | ← inverso de OutstandingToken.user |
| audit_events | ManyToOneRel | | | | | ← inverso de AuditEvent.actor |
| customer_profile | OneToOneRel | | | | | ← inverso de CustomerProfile.user |
| email_tokens | ManyToOneRel | | | | | ← inverso de EmailVerificationToken.user |
| communication_preference_changes | ManyToOneRel | | | | | ← inverso de CommunicationPreferenceChange.user |
| qr_code | OneToOneRel | | | | | ← inverso de CustomerQRCode.user |
| points_transactions | ManyToOneRel | | | | | ← inverso de PointsTransaction.customer |
| purchases | ManyToOneRel | | | | | ← inverso de Purchase.customer |
| registered_purchases | ManyToOneRel | | | | | ← inverso de Purchase.registered_by |
| redemptions | ManyToOneRel | | | | | ← inverso de Redemption.customer |
| validated_redemptions | ManyToOneRel | | | | | ← inverso de Redemption.validated_by |
| notifications | ManyToOneRel | | | | | ← inverso de Notification.recipient |
| reservations | ManyToOneRel | | | | | ← inverso de Reservation.customer |
| id | BigAutoField | False | True | True |  |  |
| password | CharField(128) | False | False | False |  |  |
| last_login | DateTimeField | True | True | False |  |  |
| is_superuser | BooleanField | False | False | False | False |  |
| public_id | UUIDField(32) | False | False | True | uuid4 |  |
| email | EmailField(254) | False | False | True |  |  |
| first_name | CharField(150) | False | False | False |  |  |
| last_name | CharField(150) | False | False | False |  |  |
| role | CharField(16) | False | False | False | User.Role.CUSTOMER | choices: OWNER, EMPLOYEE, CUSTOMER |
| is_active | BooleanField | False | False | False | True |  |
| email_verified_at | DateTimeField | True | True | False |  |  |
| is_staff | BooleanField | False | False | False | False |  |
| date_joined | DateTimeField | False | False | False | now |  |
| groups | ManyToManyField | False | True | False |  | → auth.Group (M2M) |
| user_permissions | ManyToManyField | False | True | False |  | → auth.Permission (M2M) |

**Constraints:**
- `accounts_user_email_ci_unique`: UniqueConstraint  
- `accounts_user_role_valid`: CheckConstraint  condición: (AND: ('role__in', ['OWNER', 'EMPLOYEE', 'CUSTOMER'])) check: (AND: ('role__in', ['OWNER', 'EMPLOYEE', 'CUSTOMER']))
- `accounts_user_staff_only_owner`: CheckConstraint  condición: (OR: ('is_staff', False), ('role', 'OWNER')) check: (OR: ('is_staff', False), ('role', 'OWNER'))
- `accounts_user_superuser_only_owner`: CheckConstraint  condición: (OR: ('is_superuser', False), ('role', 'OWNER')) check: (OR: ('is_superuser', False), ('role', 'OWNER'))

**Manager por defecto:** `UserManager`

## accounts.CustomerProfile  (`apps/accounts/models.py:157`) — tabla `accounts_customerprofile`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| id | BigAutoField | False | True | True |  |  |
| created_at | DateTimeField | False | True | False |  |  |
| updated_at | DateTimeField | False | True | False |  |  |
| user | OneToOneField | False | False | True |  | → accounts.User (on_delete=CASCADE) |
| address_line_1 | CharField(200) | False | True | False |  |  |
| address_line_2 | CharField(200) | False | True | False |  |  |
| postal_code | CharField(12) | False | True | False |  |  |
| city | CharField(100) | False | True | False |  |  |
| province | CharField(100) | False | True | False |  |  |
| country | CharField(2) | False | True | False | 'ES' |  |
| date_of_birth | DateField | True | True | False |  |  |
| date_of_birth_changed_at | DateTimeField | True | True | False |  |  |
| phone_number | CharField(16) | False | True | False |  |  |
| promo_email_opt_in | BooleanField | False | False | False | False |  |
| promo_sms_opt_in | BooleanField | False | False | False | False |  |

**Constraints:**
- `accounts_profile_sms_opt_in_requires_phone`: CheckConstraint  condición: (OR: ('promo_sms_opt_in', False), (NOT (AND: ('phone_number', '')))) check: (OR: ('promo_sms_opt_in', False), (NOT (AND: ('phone_number', ''))))

## accounts.EmailVerificationToken  (`apps/accounts/models.py:262`) — tabla `accounts_emailverificationtoken`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| id | BigAutoField | False | True | True |  |  |
| user | ForeignKey | False | False | False |  | → accounts.User (on_delete=CASCADE) |
| purpose | CharField(16) | False | False | False |  | choices: VERIFY, CHANGE |
| email | EmailField(254) | False | False | False |  |  |
| token_hash | CharField(64) | False | False | True |  |  |
| created_at | DateTimeField | False | False | False | now |  |
| expires_at | DateTimeField | False | False | False |  |  |
| used_at | DateTimeField | True | True | False |  |  |
| revoked_at | DateTimeField | True | True | False |  |  |

**Constraints:**
- `accounts_emailtoken_purpose_valid`: CheckConstraint  condición: (AND: ('purpose__in', ['VERIFY', 'CHANGE'])) check: (AND: ('purpose__in', ['VERIFY', 'CHANGE']))

**Índices:**
- `accounts_em_user_id_6989e4_idx`: ['user', 'created_at'] 

## accounts.CommunicationPreferenceChange  (`apps/accounts/models.py:308`) — tabla `accounts_communicationpreferencechange`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| id | BigAutoField | False | True | True |  |  |
| user | ForeignKey | False | False | False |  | → accounts.User (on_delete=CASCADE) |
| channel | CharField(8) | False | False | False |  | choices: EMAIL, SMS |
| opted_in | BooleanField | False | False | False |  |  |
| source | CharField(16) | False | False | False |  | choices: REGISTRATION, PROFILE, SYSTEM, UNSUBSCRIBE |
| created_at | DateTimeField | False | False | False | now |  |

**Constraints:**
- `accounts_prefchange_channel_valid`: CheckConstraint  condición: (AND: ('channel__in', ['EMAIL', 'SMS'])) check: (AND: ('channel__in', ['EMAIL', 'SMS']))

**ordering:** ['-created_at', '-id']

## catalog.Category  (`apps/catalog/models.py:40`) — tabla `catalog_category`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| products | ManyToOneRel | | | | | ← inverso de Product.category |
| id | BigAutoField | False | True | True |  |  |
| created_at | DateTimeField | False | True | False |  |  |
| updated_at | DateTimeField | False | True | False |  |  |
| name | CharField(80) | False | False | False |  |  |
| slug | SlugField(80) | False | False | True |  |  |
| description | TextField(500) | False | True | False |  |  |
| position | PositiveSmallIntegerField | False | False | False | 0 |  |
| is_published | BooleanField | False | False | False | True |  |

**Constraints:**
- `catalog_category_name_ci_unique`: UniqueConstraint  

**ordering:** ['position', 'name']

## catalog.BeerStyle  (`apps/catalog/models.py:72`) — tabla `catalog_beerstyle`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| products | ManyToOneRel | | | | | ← inverso de Product.style |
| id | BigAutoField | False | True | True |  |  |
| created_at | DateTimeField | False | True | False |  |  |
| updated_at | DateTimeField | False | True | False |  |  |
| name | CharField(60) | False | False | False |  |  |

**Constraints:**
- `catalog_beerstyle_name_ci_unique`: UniqueConstraint  

**ordering:** ['name']

## catalog.Product  (`apps/catalog/models.py:89`) — tabla `catalog_product`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| id | BigAutoField | False | True | True |  |  |
| created_at | DateTimeField | False | True | False |  |  |
| updated_at | DateTimeField | False | True | False |  |  |
| public_id | UUIDField(32) | False | False | True | uuid4 |  |
| category | ForeignKey | False | False | False |  | → catalog.Category (on_delete=PROTECT) |
| kind | CharField(16) | False | False | False | Product.Kind.FIXED | choices: FIXED, HOUSE_BEER, GUEST_BEER, ROTATING_BEER |
| name | CharField(120) | False | False | False |  |  |
| description | TextField(1000) | False | True | False |  |  |
| style | ForeignKey | True | True | False |  | → catalog.BeerStyle (on_delete=PROTECT) |
| abv | DecimalField(4,1) | True | True | False |  |  |
| brewery | CharField(120) | False | True | False |  |  |
| price | DecimalField(6,2) | False | False | False |  |  |
| serving | CharField(40) | False | True | False |  |  |
| image | ImageField(100) | False | True | False |  |  |
| image_width | PositiveIntegerField | True | True | False |  |  |
| image_height | PositiveIntegerField | True | True | False |  |  |
| position | PositiveSmallIntegerField | False | False | False | 0 |  |
| is_featured | BooleanField | False | False | False | False |  |
| status | CharField(16) | False | False | False | Product.Status.DRAFT | choices: DRAFT, PUBLISHED, ARCHIVED |
| published_at | DateTimeField | True | True | False |  |  |
| archived_at | DateTimeField | True | True | False |  |  |
| is_available | BooleanField | False | False | False | True |  |
| availability_changed_at | DateTimeField | True | True | False |  |  |

**Constraints:**
- `catalog_product_price_positive`: CheckConstraint  condición: (AND: ('price__gte', Decimal('0.01'))) check: (AND: ('price__gte', Decimal('0.01')))
- `catalog_product_abv_range`: CheckConstraint  condición: (OR: ('abv__isnull', True), (AND: ('abv__gte', Decimal('0.0')), ('abv__lte', Decimal('100.0')))) check: (OR: ('abv__isnull', True), (AND: ('abv__gte', Decimal('0.0')), ('abv__lte', Decimal('100.0'))))
- `catalog_product_kind_valid`: CheckConstraint  condición: (AND: ('kind__in', ['FIXED', 'HOUSE_BEER', 'GUEST_BEER', 'ROTATING_BEER'])) check: (AND: ('kind__in', ['FIXED', 'HOUSE_BEER', 'GUEST_BEER', 'ROTATING_BEER']))
- `catalog_product_status_valid`: CheckConstraint  condición: (AND: ('status__in', ['DRAFT', 'PUBLISHED', 'ARCHIVED'])) check: (AND: ('status__in', ['DRAFT', 'PUBLISHED', 'ARCHIVED']))
- `catalog_product_beer_fields`: CheckConstraint  condición: (OR: (AND: ('kind', 'FIXED'), ('style__isnull', True)), (AND: (NOT (AND: ('kind', 'FIXED'))), ('style__isnull', False), ('abv__isnull', False))) check: (OR: (AND: ('kind', 'FIXED'), ('style__isnull', True)), (AND: (NOT (AND: ('kind', 'FIXED'))), ('style__isnull', False), ('abv__isnull', False)))
- `catalog_product_archived_at_consistent`: CheckConstraint  condición: (OR: (AND: ('archived_at__isnull', False), ('status', 'ARCHIVED')), (AND: (NOT (AND: ('status', 'ARCHIVED'))), ('archived_at__isnull', True))) check: (OR: (AND: ('archived_at__isnull', False), ('status', 'ARCHIVED')), (AND: (NOT (AND: ('status', 'ARCHIVED'))), ('archived_at__isnull', True)))

**Índices:**
- `catalog_pro_status_9b3667_idx`: ['status', 'category'] 

**ordering:** ['category__position', 'position', 'name']

## catalog.TapMenu  (`apps/catalog/models.py:259`) — tabla `catalog_tapmenu`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| id | BigAutoField | False | True | True |  |  |
| created_at | DateTimeField | False | True | False |  |  |
| updated_at | DateTimeField | False | True | False |  |  |
| title | CharField(80) | False | False | False | 'Carta de grifos' |  |
| image | ImageField(100) | False | False | False |  |  |
| image_width | PositiveIntegerField | True | True | False |  |  |
| image_height | PositiveIntegerField | True | True | False |  |  |
| text_alternative | TextField(2000) | False | True | False |  |  |
| is_published | BooleanField | False | False | False | False |  |

**ordering:** ['-updated_at', '-id']

## loyalty.CustomerQRCode  (`apps/loyalty/models.py:15`) — tabla `loyalty_customerqrcode`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| id | BigAutoField | False | True | True |  |  |
| created_at | DateTimeField | False | True | False |  |  |
| updated_at | DateTimeField | False | True | False |  |  |
| user | OneToOneField | False | False | True |  | → accounts.User (on_delete=CASCADE) |
| token | CharField(32) | False | False | True |  |  |
| rotated_at | DateTimeField | True | True | False |  |  |

**Constraints:**
- `loyalty_qr_token_format`: CheckConstraint  condición: (AND: ('token__regex', '^[A-Z2-7]{32}$')) check: (AND: ('token__regex', '^[A-Z2-7]{32}$'))

## loyalty.LoyaltyRule  (`apps/loyalty/models.py:56`) — tabla `loyalty_loyaltyrule`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| id | BigAutoField | False | True | True |  |  |
| public_id | UUIDField(32) | False | False | True | uuid4 |  |
| points_per_euro | DecimalField(6,2) | False | False | False |  |  |
| valid_from | DateTimeField | False | False | False | now |  |
| note | CharField(200) | False | True | False |  |  |
| created_by | ForeignKey | True | True | False |  | → accounts.User (on_delete=PROTECT) |
| created_at | DateTimeField | False | True | False |  |  |

**Constraints:**
- `loyalty_rule_rate_range`: CheckConstraint  condición: (AND: ('points_per_euro__gte', Decimal('0.01')), ('points_per_euro__lte', Decimal('100.00'))) check: (AND: ('points_per_euro__gte', Decimal('0.01')), ('points_per_euro__lte', Decimal('100.00')))

**ordering:** ['-valid_from', '-id']

## loyalty.Promotion  (`apps/loyalty/models.py:112`) — tabla `loyalty_promotion`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| points_transactions | ManyToOneRel | | | | | ← inverso de PointsTransaction.promotion |
| id | BigAutoField | False | True | True |  |  |
| created_at | DateTimeField | False | True | False |  |  |
| updated_at | DateTimeField | False | True | False |  |  |
| public_id | UUIDField(32) | False | False | True | uuid4 |  |
| name | CharField(100) | False | False | False |  |  |
| description | CharField(300) | False | True | False |  |  |
| kind | CharField(10) | False | False | False | Promotion.Kind.PURCHASE | choices: PURCHASE, BIRTHDAY |
| bonus_type | CharField(16) | False | False | False |  | choices: FIXED_POINTS, MULTIPLIER |
| fixed_points | PositiveIntegerField | True | True | False |  |  |
| multiplier | DecimalField(4,2) | True | True | False |  |  |
| min_purchase_amount | DecimalField(8,2) | True | True | False |  |  |
| starts_at | DateTimeField | False | False | False |  |  |
| ends_at | DateTimeField | True | True | False |  |  |
| max_uses_per_customer | PositiveIntegerField | True | True | False |  |  |
| max_total_uses | PositiveIntegerField | True | True | False |  |  |
| birthday_window_days | PositiveSmallIntegerField | False | False | False | 7 |  |
| status | CharField(8) | False | False | False | Promotion.Status.DRAFT | choices: DRAFT, ACTIVE, PAUSED, ENDED |

**Constraints:**
- `loyalty_promo_kind_valid`: CheckConstraint  condición: (AND: ('kind__in', ['PURCHASE', 'BIRTHDAY'])) check: (AND: ('kind__in', ['PURCHASE', 'BIRTHDAY']))
- `loyalty_promo_status_valid`: CheckConstraint  condición: (AND: ('status__in', ['DRAFT', 'ACTIVE', 'PAUSED', 'ENDED'])) check: (AND: ('status__in', ['DRAFT', 'ACTIVE', 'PAUSED', 'ENDED']))
- `loyalty_promo_bonus_valid`: CheckConstraint  condición: (OR: (AND: ('bonus_type', 'FIXED_POINTS'), ('fixed_points__gte', 1), ('fixed_points__isnull', False), ('fixed_points__lte', 10000), ('multiplier__isnull', True)), (AND: ('bonus_type', 'MULTIPLIER'), ('fixed_points__isnull', True), ('multiplier__gt', Decimal('1.00')), ('multiplier__isnull', False), ('multiplier__lte', Decimal('10.00')))) check: (OR: (AND: ('bonus_type', 'FIXED_POINTS'), ('fixed_points__gte', 1), ('fixed_points__isnull', False), ('fixed_points__lte', 10000), ('multiplier__isnull', True)), (AND: ('bonus_type', 'MULTIPLIER'), ('fixed_points__isnull', True), ('multiplier__gt', Decimal('1.00')), ('multiplier__isnull', False), ('multiplier__lte', Decimal('10.00'))))
- `loyalty_promo_dates_valid`: CheckConstraint  condición: (OR: ('ends_at__isnull', True), ('ends_at__gt', F(starts_at))) check: (OR: ('ends_at__isnull', True), ('ends_at__gt', F(starts_at)))
- `loyalty_promo_min_amount_positive`: CheckConstraint  condición: (OR: ('min_purchase_amount__isnull', True), ('min_purchase_amount__gte', Decimal('0.01'))) check: (OR: ('min_purchase_amount__isnull', True), ('min_purchase_amount__gte', Decimal('0.01')))
- `loyalty_promo_customer_limit_positive`: CheckConstraint  condición: (OR: ('max_uses_per_customer__isnull', True), ('max_uses_per_customer__gte', 1)) check: (OR: ('max_uses_per_customer__isnull', True), ('max_uses_per_customer__gte', 1))
- `loyalty_promo_total_limit_positive`: CheckConstraint  condición: (OR: ('max_total_uses__isnull', True), ('max_total_uses__gte', 1)) check: (OR: ('max_total_uses__isnull', True), ('max_total_uses__gte', 1))
- `loyalty_promo_birthday_window_range`: CheckConstraint  condición: (AND: ('birthday_window_days__lte', 31)) check: (AND: ('birthday_window_days__lte', 31))
- `loyalty_promo_birthday_fixed_points`: CheckConstraint  condición: (OR: (NOT (AND: ('kind', 'BIRTHDAY'))), ('bonus_type', 'FIXED_POINTS')) check: (OR: (NOT (AND: ('kind', 'BIRTHDAY'))), ('bonus_type', 'FIXED_POINTS'))

**ordering:** ['-starts_at', '-id']

## loyalty.PointsTransaction  (`apps/loyalty/models.py:276`) — tabla `loyalty_pointstransaction`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| reversal | OneToOneRel | | | | | ← inverso de PointsTransaction.reverses |
| redemption | OneToOneRel | | | | | ← inverso de Redemption.spend_movement |
| refunded_redemption | OneToOneRel | | | | | ← inverso de Redemption.refund_movement |
| id | BigAutoField | False | True | True |  |  |
| public_id | UUIDField(32) | False | False | True | uuid4 |  |
| customer | ForeignKey | False | False | False |  | → accounts.User (on_delete=PROTECT) |
| kind | CharField(16) | False | False | False |  | choices: EARN_PURCHASE, PROMOTION_BONUS, ADJUSTMENT, REVERSAL, REDEMPTION, BIRTHDAY_GIFT |
| points | IntegerField | False | False | False |  |  |
| balance_after | IntegerField | False | False | False |  |  |
| purchase | ForeignKey | True | True | False |  | → purchases.Purchase (on_delete=PROTECT) |
| promotion | ForeignKey | True | True | False |  | → loyalty.Promotion (on_delete=PROTECT) |
| birthday_year | PositiveSmallIntegerField | True | True | False |  |  |
| reverses | OneToOneField | True | True | True |  | → loyalty.PointsTransaction (on_delete=PROTECT) |
| rule | ForeignKey | True | True | False |  | → loyalty.LoyaltyRule (on_delete=PROTECT) |
| base_amount | DecimalField(8,2) | True | True | False |  |  |
| points_per_euro | DecimalField(6,2) | True | True | False |  |  |
| created_by | ForeignKey | True | True | False |  | → accounts.User (on_delete=PROTECT) |
| reason | CharField(200) | False | True | False |  |  |
| idempotency_key | UUIDField(32) | True | True | True |  |  |
| created_at | DateTimeField | False | True | False |  |  |

**Constraints:**
- `loyalty_points_kind_valid`: CheckConstraint  condición: (AND: ('kind__in', ['EARN_PURCHASE', 'PROMOTION_BONUS', 'ADJUSTMENT', 'REVERSAL', 'REDEMPTION', 'BIRTHDAY_GIFT'])) check: (AND: ('kind__in', ['EARN_PURCHASE', 'PROMOTION_BONUS', 'ADJUSTMENT', 'REVERSAL', 'REDEMPTION', 'BIRTHDAY_GIFT']))
- `loyalty_points_nonzero`: CheckConstraint  condición: (NOT (AND: ('points', 0))) check: (NOT (AND: ('points', 0)))
- `loyalty_points_balance_nonnegative`: CheckConstraint  condición: (AND: ('balance_after__gte', 0)) check: (AND: ('balance_after__gte', 0))
- `loyalty_points_earn_shape`: CheckConstraint  condición: (OR: (NOT (AND: ('kind', 'EARN_PURCHASE'))), (AND: ('points__gt', 0), ('promotion__isnull', True), ('purchase__isnull', False))) check: (OR: (NOT (AND: ('kind', 'EARN_PURCHASE'))), (AND: ('points__gt', 0), ('promotion__isnull', True), ('purchase__isnull', False)))
- `loyalty_points_promotion_shape`: CheckConstraint  condición: (OR: (NOT (AND: ('kind', 'PROMOTION_BONUS'))), (AND: ('points__gt', 0), ('promotion__isnull', False), ('purchase__isnull', False))) check: (OR: (NOT (AND: ('kind', 'PROMOTION_BONUS'))), (AND: ('points__gt', 0), ('promotion__isnull', False), ('purchase__isnull', False)))
- `loyalty_points_reversal_shape`: CheckConstraint  condición: (OR: (NOT (AND: ('kind', 'REVERSAL'))), ('reverses__isnull', False)) check: (OR: (NOT (AND: ('kind', 'REVERSAL'))), ('reverses__isnull', False))
- `loyalty_points_adjustment_shape`: CheckConstraint  condición: (OR: (NOT (AND: ('kind', 'ADJUSTMENT'))), (AND: ('created_by__isnull', False), (NOT (AND: ('reason', ''))))) check: (OR: (NOT (AND: ('kind', 'ADJUSTMENT'))), (AND: ('created_by__isnull', False), (NOT (AND: ('reason', '')))))
- `loyalty_points_redemption_negative`: CheckConstraint  condición: (OR: (NOT (AND: ('kind', 'REDEMPTION'))), ('points__lt', 0)) check: (OR: (NOT (AND: ('kind', 'REDEMPTION'))), ('points__lt', 0))
- `loyalty_points_birthday_only_promotion`: CheckConstraint  condición: (OR: ('birthday_year__isnull', True), ('kind__in', ['PROMOTION_BONUS', 'BIRTHDAY_GIFT'])) check: (OR: ('birthday_year__isnull', True), ('kind__in', ['PROMOTION_BONUS', 'BIRTHDAY_GIFT']))
- `loyalty_points_birthday_gift_shape`: CheckConstraint  condición: (OR: (NOT (AND: ('kind', 'BIRTHDAY_GIFT'))), (AND: ('birthday_year__isnull', False), ('points__gt', 0), ('promotion__isnull', False), ('purchase__isnull', True))) check: (OR: (NOT (AND: ('kind', 'BIRTHDAY_GIFT'))), (AND: ('birthday_year__isnull', False), ('points__gt', 0), ('promotion__isnull', False), ('purchase__isnull', True)))
- `loyalty_points_one_earn_per_purchase`: UniqueConstraint ('purchase',) condición: (AND: ('kind', 'EARN_PURCHASE'))
- `loyalty_points_one_bonus_per_promotion_purchase`: UniqueConstraint ('promotion', 'purchase') condición: (AND: ('kind', 'PROMOTION_BONUS'))
- `loyalty_points_one_birthday_per_year`: UniqueConstraint ('customer', 'birthday_year') condición: (AND: ('birthday_year__isnull', False))

**Índices:**
- `loyalty_poi_custome_a0293a_idx`: ['customer', 'created_at'] 

**ordering:** ['-created_at', '-id']

## purchases.Purchase  (`apps/purchases/models.py:21`) — tabla `purchases_purchase`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| points_transactions | ManyToOneRel | | | | | ← inverso de PointsTransaction.purchase |
| id | BigAutoField | False | True | True |  |  |
| public_id | UUIDField(32) | False | False | True | uuid4 |  |
| customer | ForeignKey | False | False | False |  | → accounts.User (on_delete=PROTECT) |
| registered_by | ForeignKey | False | False | False |  | → accounts.User (on_delete=PROTECT) |
| amount | DecimalField(8,2) | False | False | False |  |  |
| created_at | DateTimeField | False | True | False |  |  |
| source | CharField(10) | False | False | False | Purchase.Source.MANUAL | choices: MANUAL, POS |
| status | CharField(10) | False | False | False | Purchase.Status.COMPLETED | choices: COMPLETED, VOIDED |
| idempotency_key | UUIDField(32) | False | False | True |  |  |
| external_reference | CharField(64) | False | True | False |  |  |

**Constraints:**
- `purchases_amount_positive`: CheckConstraint  condición: (AND: ('amount__gte', Decimal('0.01'))) check: (AND: ('amount__gte', Decimal('0.01')))
- `purchases_source_valid`: CheckConstraint  condición: (AND: ('source__in', ['MANUAL', 'POS'])) check: (AND: ('source__in', ['MANUAL', 'POS']))
- `purchases_status_valid`: CheckConstraint  condición: (AND: ('status__in', ['COMPLETED', 'VOIDED'])) check: (AND: ('status__in', ['COMPLETED', 'VOIDED']))
- `purchases_not_self_registered`: CheckConstraint  condición: (NOT (AND: ('customer', F(registered_by)))) check: (NOT (AND: ('customer', F(registered_by))))
- `purchases_unique_external_reference`: UniqueConstraint ('source', 'external_reference') condición: (NOT (AND: ('external_reference', '')))

**Índices:**
- `purchases_p_custome_e67c4a_idx`: ['customer', 'created_at'] 
- `purchases_p_registe_925886_idx`: ['registered_by', 'created_at'] 

**ordering:** ['-created_at', '-id']

## rewards.Reward  (`apps/rewards/models.py:36`) — tabla `rewards_reward`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| redemptions | ManyToOneRel | | | | | ← inverso de Redemption.reward |
| id | BigAutoField | False | True | True |  |  |
| created_at | DateTimeField | False | True | False |  |  |
| updated_at | DateTimeField | False | True | False |  |  |
| public_id | UUIDField(32) | False | False | True | uuid4 |  |
| name | CharField(100) | False | False | False |  |  |
| description | TextField(1000) | False | True | False |  |  |
| image | ImageField(100) | False | True | False |  |  |
| image_width | PositiveIntegerField | True | True | False |  |  |
| image_height | PositiveIntegerField | True | True | False |  |  |
| points_cost | PositiveIntegerField | False | False | False |  |  |
| status | CharField(10) | False | False | False | Reward.Status.DRAFT | choices: DRAFT, ACTIVE, PAUSED, ARCHIVED |
| valid_from | DateTimeField | False | False | False | now |  |
| valid_until | DateTimeField | True | True | False |  |  |
| stock | PositiveIntegerField | True | True | False |  |  |
| position | PositiveSmallIntegerField | False | False | False | 0 |  |

**Constraints:**
- `rewards_reward_status_valid`: CheckConstraint  condición: (AND: ('status__in', ['DRAFT', 'ACTIVE', 'PAUSED', 'ARCHIVED'])) check: (AND: ('status__in', ['DRAFT', 'ACTIVE', 'PAUSED', 'ARCHIVED']))
- `rewards_reward_cost_range`: CheckConstraint  condición: (AND: ('points_cost__gte', 1), ('points_cost__lte', 100000)) check: (AND: ('points_cost__gte', 1), ('points_cost__lte', 100000))
- `rewards_reward_dates_valid`: CheckConstraint  condición: (OR: ('valid_until__isnull', True), ('valid_until__gt', F(valid_from))) check: (OR: ('valid_until__isnull', True), ('valid_until__gt', F(valid_from)))
- `rewards_reward_stock_nonnegative`: CheckConstraint  condición: (OR: ('stock__isnull', True), ('stock__gte', 0)) check: (OR: ('stock__isnull', True), ('stock__gte', 0))

**ordering:** ['position', 'points_cost', 'name']

## rewards.Redemption  (`apps/rewards/models.py:133`) — tabla `rewards_redemption`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| id | BigAutoField | False | True | True |  |  |
| public_id | UUIDField(32) | False | False | True | uuid4 |  |
| customer | ForeignKey | False | False | False |  | → accounts.User (on_delete=PROTECT) |
| reward | ForeignKey | False | False | False |  | → rewards.Reward (on_delete=PROTECT) |
| points_cost | PositiveIntegerField | False | False | False |  |  |
| code | CharField(12) | False | False | True |  |  |
| status | CharField(10) | False | False | False | Redemption.Status.PENDING | choices: PENDING, USED, EXPIRED, CANCELLED |
| created_at | DateTimeField | False | False | False | now |  |
| expires_at | DateTimeField | False | False | False |  |  |
| idempotency_key | UUIDField(32) | False | False | True |  |  |
| spend_movement | OneToOneField | False | False | True |  | → loyalty.PointsTransaction (on_delete=PROTECT) |
| refund_movement | OneToOneField | True | True | True |  | → loyalty.PointsTransaction (on_delete=PROTECT) |
| validated_by | ForeignKey | True | True | False |  | → accounts.User (on_delete=PROTECT) |
| validated_at | DateTimeField | True | True | False |  |  |
| closed_at | DateTimeField | True | True | False |  |  |

**Constraints:**
- `rewards_redemption_status_valid`: CheckConstraint  condición: (AND: ('status__in', ['PENDING', 'USED', 'EXPIRED', 'CANCELLED'])) check: (AND: ('status__in', ['PENDING', 'USED', 'EXPIRED', 'CANCELLED']))
- `rewards_redemption_cost_positive`: CheckConstraint  condición: (AND: ('points_cost__gte', 1)) check: (AND: ('points_cost__gte', 1))
- `rewards_redemption_code_format`: CheckConstraint  condición: (AND: ('code__regex', '^[A-HJKMNP-Z2-9]{12}$')) check: (AND: ('code__regex', '^[A-HJKMNP-Z2-9]{12}$'))
- `rewards_redemption_expiry_after_creation`: CheckConstraint  condición: (AND: ('expires_at__gt', F(created_at))) check: (AND: ('expires_at__gt', F(created_at)))
- `rewards_redemption_validation_consistent`: CheckConstraint  condición: (OR: (AND: ('status', 'USED'), ('validated_at__isnull', False), ('validated_by__isnull', False)), (AND: (NOT (AND: ('status', 'USED'))), ('validated_at__isnull', True), ('validated_by__isnull', True))) check: (OR: (AND: ('status', 'USED'), ('validated_at__isnull', False), ('validated_by__isnull', False)), (AND: (NOT (AND: ('status', 'USED'))), ('validated_at__isnull', True), ('validated_by__isnull', True)))
- `rewards_redemption_refund_consistent`: CheckConstraint  condición: (OR: (AND: ('closed_at__isnull', False), ('refund_movement__isnull', False), ('status__in', ['EXPIRED', 'CANCELLED'])), (AND: ('status__in', ['PENDING', 'USED']), ('closed_at__isnull', True), ('refund_movement__isnull', True))) check: (OR: (AND: ('closed_at__isnull', False), ('refund_movement__isnull', False), ('status__in', ['EXPIRED', 'CANCELLED'])), (AND: ('status__in', ['PENDING', 'USED']), ('closed_at__isnull', True), ('refund_movement__isnull', True)))
- `rewards_redemption_not_self_validated`: CheckConstraint  condición: (NOT (AND: ('validated_by', F(customer)))) check: (NOT (AND: ('validated_by', F(customer))))
- `rewards_redemption_one_pending_per_reward`: UniqueConstraint ('customer', 'reward') condición: (AND: ('status', 'PENDING'))

**Índices:**
- `rewards_red_custome_594ec5_idx`: ['customer', 'created_at'] 
- `rewards_red_status_6ef441_idx`: ['status', 'expires_at'] 
- `rewards_red_validat_f3fda1_idx`: ['validated_by', 'validated_at'] 

**ordering:** ['-created_at', '-id']

## notifications.Campaign  (`apps/notifications/models.py:36`) — tabla `notifications_campaign`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| notifications | ManyToOneRel | | | | | ← inverso de Notification.campaign |
| id | BigAutoField | False | True | True |  |  |
| created_at | DateTimeField | False | True | False |  |  |
| updated_at | DateTimeField | False | True | False |  |  |
| public_id | UUIDField(32) | False | False | True | uuid4 |  |
| name | CharField(100) | False | False | False |  |  |
| channel | CharField(8) | False | False | False | Channel.EMAIL | choices: EMAIL, SMS |
| subject | CharField(120) | False | True | False |  |  |
| body | TextField(2000) | False | False | False |  |  |
| status | CharField(12) | False | False | False | Campaign.Status.DRAFT | choices: DRAFT, QUEUED, DISPATCHED, CANCELLED |
| created_by | ForeignKey | False | False | False |  | → accounts.User (on_delete=PROTECT) |
| queued_at | DateTimeField | True | True | False |  |  |
| dispatched_at | DateTimeField | True | True | False |  |  |
| recipients_count | PositiveIntegerField | True | True | False |  |  |

**Constraints:**
- `notifications_campaign_status_valid`: CheckConstraint  condición: (AND: ('status__in', ['DRAFT', 'QUEUED', 'DISPATCHED', 'CANCELLED'])) check: (AND: ('status__in', ['DRAFT', 'QUEUED', 'DISPATCHED', 'CANCELLED']))
- `notifications_campaign_channel_valid`: CheckConstraint  condición: (AND: ('channel__in', ['EMAIL', 'SMS'])) check: (AND: ('channel__in', ['EMAIL', 'SMS']))
- `notifications_campaign_email_subject`: CheckConstraint  condición: (OR: (NOT (AND: ('channel', 'EMAIL'))), (NOT (AND: ('subject', '')))) check: (OR: (NOT (AND: ('channel', 'EMAIL'))), (NOT (AND: ('subject', ''))))

**ordering:** ['-created_at', '-id']

## notifications.Notification  (`apps/notifications/models.py:80`) — tabla `notifications_notification`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| id | BigAutoField | False | True | True |  |  |
| public_id | UUIDField(32) | False | False | True | uuid4 |  |
| recipient | ForeignKey | False | False | False |  | → accounts.User (on_delete=CASCADE) |
| kind | CharField(32) | False | False | False |  | choices: EMAIL_VERIFICATION, EMAIL_CHANGE, EMAIL_CHANGED_NOTICE, EXISTING_ACCOUNT, PASSWORD_RESET, RESERVATION_RECEIVED, RESERVATION_CONFIRMED, RESERVATION_REJECTED, RES |
| category | CharField(16) | False | False | False |  | choices: TRANSACTIONAL, PROMOTIONAL |
| channel | CharField(8) | False | False | False | Channel.EMAIL | choices: EMAIL, SMS |
| status | CharField(8) | False | False | False | Notification.Status.PENDING | choices: PENDING, SENDING, SENT, FAILED, SKIPPED |
| context | JSONField | False | True | False | dict |  |
| dedup_key | CharField(120) | True | True | True |  |  |
| campaign | ForeignKey | True | True | False |  | → notifications.Campaign (on_delete=PROTECT) |
| attempts | PositiveSmallIntegerField | False | False | False | 0 |  |
| next_attempt_at | DateTimeField | True | True | False |  |  |
| last_error | CharField(100) | False | True | False |  |  |
| sent_at | DateTimeField | True | True | False |  |  |
| created_at | DateTimeField | False | True | False |  |  |
| updated_at | DateTimeField | False | True | False |  |  |

**Constraints:**
- `notifications_status_valid`: CheckConstraint  condición: (AND: ('status__in', ['PENDING', 'SENDING', 'SENT', 'FAILED', 'SKIPPED'])) check: (AND: ('status__in', ['PENDING', 'SENDING', 'SENT', 'FAILED', 'SKIPPED']))
- `notifications_channel_valid`: CheckConstraint  condición: (AND: ('channel__in', ['EMAIL', 'SMS'])) check: (AND: ('channel__in', ['EMAIL', 'SMS']))
- `notifications_category_matches_kind`: CheckConstraint  condición: (OR: (AND: ('category', 'PROMOTIONAL'), ('kind__in', ['CAMPAIGN', 'BIRTHDAY'])), (AND: (NOT (AND: ('kind__in', ['CAMPAIGN', 'BIRTHDAY']))), ('category', 'TRANSACTIONAL'))) check: (OR: (AND: ('category', 'PROMOTIONAL'), ('kind__in', ['CAMPAIGN', 'BIRTHDAY'])), (AND: (NOT (AND: ('kind__in', ['CAMPAIGN', 'BIRTHDAY']))), ('category', 'TRANSACTIONAL')))
- `notifications_sent_at_matches_status`: CheckConstraint  condición: (OR: (AND: ('sent_at__isnull', False), ('status', 'SENT')), (AND: (NOT (AND: ('status', 'SENT'))), ('sent_at__isnull', True))) check: (OR: (AND: ('sent_at__isnull', False), ('status', 'SENT')), (AND: (NOT (AND: ('status', 'SENT'))), ('sent_at__isnull', True)))

**Índices:**
- `notificatio_status_444bb6_idx`: ['status', 'next_attempt_at'] 

**ordering:** ['-created_at', '-id']

## events.Event  (`apps/events/models.py:42`) — tabla `events_event`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| reservations | ManyToOneRel | | | | | ← inverso de Reservation.event |
| id | BigAutoField | False | True | True |  |  |
| created_at | DateTimeField | False | True | False |  |  |
| updated_at | DateTimeField | False | True | False |  |  |
| public_id | UUIDField(32) | False | False | True | uuid4 |  |
| title | CharField(120) | False | False | False |  |  |
| summary | CharField(300) | False | True | False |  |  |
| description | TextField(3000) | False | True | False |  |  |
| starts_at | DateTimeField | False | False | False |  |  |
| ends_at | DateTimeField | True | True | False |  |  |
| image | ImageField(100) | False | True | False |  |  |
| image_width | PositiveIntegerField | True | True | False |  |  |
| image_height | PositiveIntegerField | True | True | False |  |  |
| status | CharField(10) | False | False | False | Event.Status.DRAFT | choices: DRAFT, PUBLISHED, ARCHIVED |
| is_featured | BooleanField | False | False | False | False |  |
| accepts_reservations | BooleanField | False | False | False | False |  |
| capacity | PositiveIntegerField | True | True | False |  |  |
| published_at | DateTimeField | True | True | False |  |  |

**Constraints:**
- `events_event_status_valid`: CheckConstraint  condición: (AND: ('status__in', ['DRAFT', 'PUBLISHED', 'ARCHIVED'])) check: (AND: ('status__in', ['DRAFT', 'PUBLISHED', 'ARCHIVED']))
- `events_event_dates_valid`: CheckConstraint  condición: (OR: ('ends_at__isnull', True), ('ends_at__gt', F(starts_at))) check: (OR: ('ends_at__isnull', True), ('ends_at__gt', F(starts_at)))
- `events_event_capacity_range`: CheckConstraint  condición: (OR: ('capacity__isnull', True), (AND: ('capacity__gte', 1), ('capacity__lte', 1000))) check: (OR: ('capacity__isnull', True), (AND: ('capacity__gte', 1), ('capacity__lte', 1000)))

**ordering:** ['starts_at', 'id']

## events.Reservation  (`apps/events/models.py:112`) — tabla `events_reservation`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| id | BigAutoField | False | True | True |  |  |
| public_id | UUIDField(32) | False | False | True | uuid4 |  |
| customer | ForeignKey | False | False | False |  | → accounts.User (on_delete=PROTECT) |
| event | ForeignKey | True | True | False |  | → events.Event (on_delete=PROTECT) |
| requested_for | DateTimeField | False | False | False |  |  |
| party_size | PositiveSmallIntegerField | False | False | False |  |  |
| notes | CharField(300) | False | True | False |  |  |
| status | CharField(10) | False | False | False | Reservation.Status.PENDING | choices: PENDING, CONFIRMED, REJECTED, CANCELLED, COMPLETED |
| owner_message | CharField(300) | False | True | False |  |  |
| status_changed_at | DateTimeField | True | True | False |  |  |
| status_changed_by | ForeignKey | True | True | False |  | → accounts.User (on_delete=PROTECT) |
| idempotency_key | UUIDField(32) | False | False | True |  |  |
| created_at | DateTimeField | False | False | False | now |  |
| updated_at | DateTimeField | False | True | False |  |  |

**Constraints:**
- `events_reservation_status_valid`: CheckConstraint  condición: (AND: ('status__in', ['PENDING', 'CONFIRMED', 'REJECTED', 'CANCELLED', 'COMPLETED'])) check: (AND: ('status__in', ['PENDING', 'CONFIRMED', 'REJECTED', 'CANCELLED', 'COMPLETED']))
- `events_reservation_party_size_range`: CheckConstraint  condición: (AND: ('party_size__gte', 1), ('party_size__lte', 50)) check: (AND: ('party_size__gte', 1), ('party_size__lte', 50))
- `events_reservation_decision_dated`: CheckConstraint  condición: (OR: ('status', 'PENDING'), ('status_changed_at__isnull', False)) check: (OR: ('status', 'PENDING'), ('status_changed_at__isnull', False))
- `events_reservation_one_active_per_event`: UniqueConstraint ('customer', 'event') condición: (AND: ('event__isnull', False), ('status__in', ['PENDING', 'CONFIRMED']))

**Índices:**
- `events_rese_custome_109d67_idx`: ['customer', 'status'] 

**ordering:** ['-requested_for', '-id']

## web.BusinessInfo  (`apps/web/models.py:43`) — tabla `web_businessinfo`

| Campo | Tipo | null | blank | unique | default | relación / choices |
|---|---|---|---|---|---|---|
| id | BigAutoField | False | True | True |  |  |
| address | CharField(200) | False | True | False |  |  |
| opening_hours | TextField(1000) | False | True | False |  |  |
| email | EmailField(254) | False | True | False |  |  |
| phone | CharField(20) | False | True | False |  |  |
| social_links | TextField(1000) | False | True | False |  |  |
| about_text | TextField(2000) | False | True | False |  |  |
| hero_text | CharField(300) | False | True | False |  |  |
| announcement | CharField(200) | False | True | False |  |  |
| updated_at | DateTimeField | False | True | False |  |  |

**Constraints:**
- `web_businessinfo_singleton`: CheckConstraint  condición: (AND: ('id', 1)) check: (AND: ('id', 1))


Total de modelos propios: 21
