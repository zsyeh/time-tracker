from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('drill', '0004_questiondocument_attribution'),
    ]

    operations = [
        migrations.AddField(
            model_name='questionasset',
            name='render_dpi',
            field=models.PositiveSmallIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='questionasset',
            name='source_page_index',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='questionasset',
            name='source_x0',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='questionasset',
            name='source_x1',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='questionasset',
            name='source_y0',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='questionasset',
            name='source_y1',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
