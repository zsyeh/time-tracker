from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('drill', '0027_attempt_method_notes')]

    operations = [
        migrations.AlterField(
            model_name='drillloginhandoff',
            name='target_site',
            field=models.CharField(
                choices=[
                    ('drill', 'Mathematics drill'),
                    ('ei', 'Electronic information'),
                    ('dash', 'Operations dashboard'),
                    ('ip', 'Direct IP entry point'),
                ],
                default='drill',
                max_length=16,
            ),
        ),
    ]
