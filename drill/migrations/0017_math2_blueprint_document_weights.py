from django.db import migrations


DOCUMENT_WEIGHTS = {
    '极限': 1.1,
    '一元微分': 1.2,
    '一元积分': 1.2,
    '二重积分': 0.8,
    '多元微分': 1.0,
    '微分方程': 0.9,
    '反常积分': 0.5,
    '线性代数': 1.8,
}


def add_document_weights(apps, schema_editor):
    Section = apps.get_model('drill', 'ExamBlueprintSection')
    sections = Section.objects.filter(blueprint__subject='math2')
    for section in sections.iterator():
        values = dict(section.chapter_weights or {})
        values.update({f'document:{key}': value for key, value in DOCUMENT_WEIGHTS.items()})
        section.chapter_weights = values
        section.save(update_fields=('chapter_weights',))


def remove_document_weights(apps, schema_editor):
    Section = apps.get_model('drill', 'ExamBlueprintSection')
    for section in Section.objects.filter(blueprint__subject='math2').iterator():
        values = dict(section.chapter_weights or {})
        for key in DOCUMENT_WEIGHTS:
            values.pop(f'document:{key}', None)
        section.chapter_weights = values
        section.save(update_fields=('chapter_weights',))


class Migration(migrations.Migration):

    dependencies = [
        ('drill', '0016_backfill_explicit_exam_variants'),
    ]

    operations = [
        migrations.RunPython(add_document_weights, remove_document_weights),
    ]
