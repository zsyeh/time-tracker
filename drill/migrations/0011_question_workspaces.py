from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('drill', '0010_questionmarker'),
    ]

    operations = [
        migrations.AddField(
            model_name='questiondocument',
            name='workspace',
            field=models.CharField(
                choices=[('drill', 'Mathematics drill'), ('ei', 'Electronic information')],
                db_index=True,
                default='drill',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='drillloginhandoff',
            name='target_site',
            field=models.CharField(
                choices=[('drill', 'Mathematics drill'), ('ei', 'Electronic information')],
                default='drill',
                max_length=16,
            ),
        ),
    ]
