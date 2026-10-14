import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """Tablas nuevas: tokens de verificación de email e historial de consentimientos."""

    dependencies = [
        ("accounts", "0005_customer_profile_personal_data"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailVerificationToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("purpose", models.CharField(choices=[("VERIFY", "Verificación del email"), ("CHANGE", "Cambio de email")], max_length=16, verbose_name="finalidad")),
                ("email", models.EmailField(max_length=254, verbose_name="email a confirmar")),
                ("token_hash", models.CharField(max_length=64, unique=True, verbose_name="hash del token")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="creado")),
                ("expires_at", models.DateTimeField(verbose_name="caduca")),
                ("used_at", models.DateTimeField(blank=True, null=True, verbose_name="usado")),
                ("revoked_at", models.DateTimeField(blank=True, null=True, verbose_name="revocado")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="email_tokens", to=settings.AUTH_USER_MODEL, verbose_name="usuario")),
            ],
            options={
                "verbose_name": "token de verificación de email",
                "verbose_name_plural": "tokens de verificación de email",
                "indexes": [models.Index(fields=["user", "created_at"], name="accounts_em_user_id_6989e4_idx")],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("purpose__in", ["VERIFY", "CHANGE"])), name="accounts_emailtoken_purpose_valid"),
                ],
            },
        ),
        migrations.CreateModel(
            name="CommunicationPreferenceChange",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel", models.CharField(choices=[("EMAIL", "Email promocional"), ("SMS", "SMS promocional")], max_length=8, verbose_name="canal")),
                ("opted_in", models.BooleanField(verbose_name="consiente")),
                ("source", models.CharField(choices=[("REGISTRATION", "Registro"), ("PROFILE", "Perfil del cliente"), ("SYSTEM", "Automático (teléfono eliminado)")], max_length=16, verbose_name="origen")),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="fecha")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="communication_preference_changes", to=settings.AUTH_USER_MODEL, verbose_name="cliente")),
            ],
            options={
                "verbose_name": "cambio de preferencia de comunicación",
                "verbose_name_plural": "cambios de preferencias de comunicación",
                "ordering": ["-created_at", "-id"],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("channel__in", ["EMAIL", "SMS"])), name="accounts_prefchange_channel_valid"),
                ],
            },
        ),
    ]
