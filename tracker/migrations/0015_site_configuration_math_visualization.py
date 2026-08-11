from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0014_site_configuration'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfiguration',
            name='math_visualization_enabled',
            field=models.BooleanField(
                default=False,
                help_text='Show Markdown formula launch buttons and enable the visualization window.',
            ),
        ),
    ]
