"""Versioned, fixed Math II image-only training definitions; no learning data edits."""
from django.db import migrations


def seed(apps, schema_editor):
    Blueprint = apps.get_model('drill', 'ExamBlueprint')
    Section = apps.get_model('drill', 'ExamBlueprintSection')
    Blueprint.objects.filter(subject='math2', is_active=True).update(is_active=False)
    for mode, minutes, counts, title in (
        ('standard', 180, (7, 3, 5, 1, 5, 1), '数学二 · 3 小时标准训练'),
        ('intensive', 240, (11, 4, 7, 2, 7, 2), '数学二 · 4 小时强化训练'),
    ):
        blueprint, _ = Blueprint.objects.get_or_create(
            code=f'math2-focus-{mode}-v2', defaults=dict(
                title=title, subject='math2', mode=mode, version=2,
                duration_minutes=minutes, total_score=150 if mode == 'standard' else 225,
                cooldown_days=0, is_active=True,
            ),
        )
        for order, (count, kind, area, label) in enumerate(zip(
            counts,
            ('single_choice', 'single_choice', 'fill_blank', 'fill_blank', 'solution', 'solution'),
            ('calculus', 'linear', 'calculus', 'linear', 'calculus', 'linear'),
            ('高数选择', '线代选择', '高数填空', '线代填空', '高数解答', '线代解答'),
        ), 1):
            Section.objects.get_or_create(blueprint=blueprint, order=order, defaults=dict(
                title=label, question_type=kind, question_count=count,
                score_per_question=5 if order <= 4 else (11 if order == 5 else (15 if mode == 'standard' else 14)),
                chapter_weights={'$subject_area': area}, max_per_topic=2,
            ))


def reverse(apps, schema_editor):
    Blueprint = apps.get_model('drill', 'ExamBlueprint')
    Blueprint.objects.filter(code__startswith='math2-focus-').update(is_active=False)
    Blueprint.objects.filter(subject='math2', version=1).update(is_active=True)


class Migration(migrations.Migration):
    dependencies = [('drill', '0041_query_access_paths')]
    operations = [migrations.RunPython(seed, reverse)]
