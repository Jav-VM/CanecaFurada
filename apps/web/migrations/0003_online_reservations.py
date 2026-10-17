from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0002_home_texts'),
    ]

    operations = [
        migrations.AddField(
            model_name='businessinfo',
            name='online_reservations_enabled',
            field=models.BooleanField(default=True, verbose_name='reservas online activadas'),
        ),
    ]
