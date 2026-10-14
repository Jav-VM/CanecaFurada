from django.db import migrations


def create_missing_customer_profiles(apps, schema_editor):
    """Crea el perfil de los clientes dados de alta antes de existir el modelo."""
    User = apps.get_model("accounts", "User")
    CustomerProfile = apps.get_model("accounts", "CustomerProfile")
    missing = User.objects.filter(role="CUSTOMER", customer_profile__isnull=True)
    CustomerProfile.objects.bulk_create(CustomerProfile(user=user) for user in missing.iterator())


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_customer_profile"),
    ]

    operations = [
        # La reversión no borra nada: al revertir 0002 desaparece la tabla entera.
        migrations.RunPython(create_missing_customer_profiles, migrations.RunPython.noop),
    ]
