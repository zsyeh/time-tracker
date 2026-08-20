from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('drill', '0005_questionasset_render_provenance'),
    ]

    operations = [
        migrations.AddField(
            model_name='questionattempt',
            name='confidence',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='questionattempt',
            name='note',
            field=models.TextField(blank=True, null=True),
        ),
    ]
