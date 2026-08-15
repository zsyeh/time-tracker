from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0019_task_presets_and_tags'),
    ]

    operations = [
        migrations.AddField(
            model_name='timelog',
            name='efficiency_grade',
            field=models.CharField(
                choices=[
                    ('A', 'A · 1.00'),
                    ('B', 'B · 0.95'),
                    ('C', 'C · 0.90'),
                    ('D', 'D · 0.85'),
                    ('E', 'E · 0.80'),
                    ('F', 'F · 0.75'),
                ],
                default='A',
                max_length=1,
            ),
        ),
    ]
