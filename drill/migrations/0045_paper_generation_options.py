from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('drill', '0044_ei_focus_blueprint')]
    operations = [migrations.AddField(
        model_name='exampaper', name='generation_options',
        field=models.JSONField(default=dict, blank=True),
    )]
