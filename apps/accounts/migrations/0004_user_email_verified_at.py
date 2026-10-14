from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Único cambio sobre la tabla de usuarios en la Fase 2: una columna nullable.
    No modifica datos; las cuentas existentes quedan como "pendientes de
    verificación" (no se presume que su email esté confirmado).
    """

    dependencies = [
        ("accounts", "0003_backfill_customer_profiles"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email_verified_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Vacío mientras el email actual no se haya confirmado con un enlace.",
                null=True,
                verbose_name="email verificado el",
            ),
        ),
    ]
