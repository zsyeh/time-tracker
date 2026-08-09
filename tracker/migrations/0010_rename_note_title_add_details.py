from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('tracker', '0009_english_interface_choices'),
    ]

    operations = [
        migrations.RenameField(
            model_name='timelog',
            old_name='note',
            new_name='title',
        ),
        migrations.AddField(
            model_name='timelog',
            name='details',
            field=models.TextField(blank=True, default=''),
            preserve_default=False,
        ),
    ]
