import apps.accounts.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Datos personales y consentimientos del perfil de cliente. Todas las columnas
    admiten vacío o tienen valor por defecto, así que los perfiles existentes
    siguen siendo válidos (se completarán desde la página de perfil).
    """

    dependencies = [
        ("accounts", "0004_user_email_verified_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="customerprofile",
            name="address_line_1",
            field=models.CharField(blank=True, help_text="Calle, número, piso.", max_length=200, verbose_name="dirección"),
        ),
        migrations.AddField(
            model_name="customerprofile",
            name="address_line_2",
            field=models.CharField(blank=True, max_length=200, verbose_name="dirección (línea 2)"),
        ),
        migrations.AddField(
            model_name="customerprofile",
            name="postal_code",
            field=models.CharField(blank=True, max_length=12, verbose_name="código postal"),
        ),
        migrations.AddField(
            model_name="customerprofile",
            name="city",
            field=models.CharField(blank=True, max_length=100, verbose_name="localidad"),
        ),
        migrations.AddField(
            model_name="customerprofile",
            name="province",
            field=models.CharField(blank=True, help_text="Provincia, estado o región.", max_length=100, verbose_name="provincia"),
        ),
        migrations.AddField(
            model_name="customerprofile",
            name="country",
            field=models.CharField(blank=True, default="ES", help_text="Código ISO 3166-1.", max_length=2, verbose_name="país"),
        ),
        migrations.AddField(
            model_name="customerprofile",
            name="date_of_birth",
            field=models.DateField(blank=True, null=True, verbose_name="fecha de nacimiento"),
        ),
        migrations.AddField(
            model_name="customerprofile",
            name="date_of_birth_changed_at",
            field=models.DateTimeField(blank=True, help_text="Limita los cambios posteriores (promociones de cumpleaños).", null=True, verbose_name="última modificación de la fecha de nacimiento"),
        ),
        migrations.AddField(
            model_name="customerprofile",
            name="phone_number",
            field=models.CharField(blank=True, help_text="Opcional. Formato internacional E.164. No está verificado.", max_length=16, validators=[apps.accounts.validators.validate_e164], verbose_name="teléfono móvil"),
        ),
        migrations.AddField(
            model_name="customerprofile",
            name="promo_email_opt_in",
            field=models.BooleanField(default=False, verbose_name="acepta emails promocionales"),
        ),
        migrations.AddField(
            model_name="customerprofile",
            name="promo_sms_opt_in",
            field=models.BooleanField(default=False, verbose_name="acepta SMS promocionales"),
        ),
        migrations.AddConstraint(
            model_name="customerprofile",
            constraint=models.CheckConstraint(
                condition=models.Q(("promo_sms_opt_in", False), models.Q(("phone_number", ""), _negated=True), _connector="OR"),
                name="accounts_profile_sms_opt_in_requires_phone",
            ),
        ),
    ]
