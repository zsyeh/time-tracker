import re

from django.db import migrations


VARIANT_RE = re.compile(r'数(?:学)?\s*([一二三](?:\s*[一二三])*)')


def backfill_explicit_variants(apps, schema_editor):
    Question = apps.get_model('drill', 'Question')
    updates = []
    questions = Question.objects.filter(exam_variant='').only(
        'pk', 'source_label', 'display_label', 'exam_variant',
    )
    for question in questions.iterator(chunk_size=500):
        found = set()
        for match in VARIANT_RE.finditer(
            f'{question.source_label} {question.display_label}',
        ):
            found.update(re.findall(r'[一二三]', match.group(1)))
        ordered = ''.join(value for value in '一二三' if value in found)
        if not ordered:
            continue
        question.exam_variant = f'数{ordered}'
        updates.append(question)
    Question.objects.bulk_update(updates, ('exam_variant',), batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ('drill', '0015_question_type_neighbor_consensus'),
    ]

    operations = [
        migrations.RunPython(backfill_explicit_variants, migrations.RunPython.noop),
    ]
