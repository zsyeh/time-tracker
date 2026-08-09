from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('tracker', '0004_dailystudystat'),
    ]

    operations = [
        migrations.AlterField(
            model_name='timelog',
            name='note',
            field=models.TextField(blank=True, null=True),
        ),
    ]
