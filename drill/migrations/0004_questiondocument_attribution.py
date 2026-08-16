from django.db import migrations, models


ATTRIBUTION = 'Question bank collected and organized by Bilibili creator cxy (澄潇宇).'


def add_cxy_attribution(apps, schema_editor):
    QuestionDocument = apps.get_model('drill', 'QuestionDocument')
    QuestionDocument.objects.filter(attribution='').update(attribution=ATTRIBUTION)


def remove_cxy_attribution(apps, schema_editor):
    QuestionDocument = apps.get_model('drill', 'QuestionDocument')
    QuestionDocument.objects.filter(attribution=ATTRIBUTION).update(attribution='')


class Migration(migrations.Migration):
    dependencies = [
        ('drill', '0003_question_bank_cleanup'),
    ]

    operations = [
        migrations.AddField(
            model_name='questiondocument',
            name='author',
            field=models.CharField(blank=True, max_length=240),
        ),
        migrations.AddField(
            model_name='questiondocument',
            name='attribution',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.RunPython(add_cxy_attribution, remove_cxy_attribution),
    ]
