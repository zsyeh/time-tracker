from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('tracker', '0005_alter_timelog_note'),
    ]

    operations = [
        migrations.AlterField(
            model_name='timelog',
            name='start_time',
            field=models.DateTimeField(
                db_index=True,
                default=django.utils.timezone.now,
            ),
        ),
    ]
