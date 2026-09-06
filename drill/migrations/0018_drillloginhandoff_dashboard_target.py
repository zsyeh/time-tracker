from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('drill', '0017_math2_blueprint_document_weights'),
    ]

    operations = [
        migrations.AlterField(
            model_name='drillloginhandoff',
            name='target_site',
            field=models.CharField(
                choices=[
                    ('drill', 'Mathematics drill'),
                    ('ei', 'Electronic information'),
                    ('dash', 'Operations dashboard'),
                ],
                default='drill',
                max_length=16,
            ),
        ),
    ]
