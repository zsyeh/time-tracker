from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('drill', '0002_drillloginhandoff'),
    ]

    operations = [
        migrations.AddField(
            model_name='questiondocument',
            name='display_title',
            field=models.CharField(blank=True, max_length=240),
        ),
        migrations.AddField(
            model_name='questiontopic',
            name='display_title',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='question',
            name='display_label',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='question',
            name='source_category',
            field=models.CharField(
                choices=[
                    ('past_exam', 'Past exam'),
                    ('adapted_exam', 'Adapted past exam'),
                    ('mock_exam', 'Mock paper'),
                    ('workbook', 'Workbook'),
                    ('competition', 'Competition'),
                    ('unclassified', 'Unclassified'),
                ],
                db_index=True,
                default='unclassified',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='question',
            name='record_kind',
            field=models.CharField(
                choices=[
                    ('question', 'Question'),
                    ('grouped', 'Grouped extract'),
                    ('section', 'Source outline'),
                ],
                db_index=True,
                default='question',
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name='question',
            name='is_practiceable',
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddField(
            model_name='question',
            name='classification_reason',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='question',
            name='classification_confidence',
            field=models.FloatField(default=0.0),
        ),
        migrations.AlterField(
            model_name='questionattempt',
            name='result',
            field=models.CharField(
                choices=[
                    ('done', 'Done'),
                    ('correct', 'Correct'),
                    ('review', 'Needs review'),
                    ('reset', 'Reset to unattempted'),
                ],
                default='done',
                max_length=12,
            ),
        ),
    ]
