"""EI training composition; item counts are not specified by the syllabus."""
from django.db import migrations


def seed(apps, schema_editor):
    Blueprint = apps.get_model('drill', 'ExamBlueprint')
    Section = apps.get_model('drill', 'ExamBlueprintSection')
    blueprint, _ = Blueprint.objects.get_or_create(
        code='ei-focus-standard-v1', defaults=dict(
            title='电子信息 · 3 小时标准训练', subject='ei', mode='standard',
            version=1, duration_minutes=180, total_score=150,
            cooldown_days=0, is_active=True,
        ),
    )
    # Source PDF page 1 fixes scores, duration and approximate course weights,
    # but no question counts. This is a feasible 30-item training configuration.
    courses = (
        ('circuit', '电路原理', (0, 2, 2, 1)),
        ('analog', '模拟电子技术', (4, 4, 1, 0)),
        ('digital', '数字电子技术', (4, 2, 0, 1)),
        ('signals', '信号与系统', (2, 2, 1, 1)),
        ('communication', '通信原理', (0, 0, 1, 2)),
    )
    order = 0
    for index, (exam_type, legacy, label, score) in enumerate((
        ('choice', 'single_choice', '选择', 3),
        ('fill', 'fill_blank', '填空', 3),
        ('short_answer', 'solution', '简答', 6),
        ('large', 'solution', '计算及证明', 12),
    )):
        for course, course_label, counts in courses:
            count = counts[index]
            if not count:
                continue
            order += 1
            Section.objects.get_or_create(blueprint=blueprint, order=order, defaults=dict(
                title=f'{course_label} · {label}', question_type=legacy,
                question_count=count, score_per_question=score,
                chapter_weights={'$course': course, '$exam_type': exam_type},
                max_per_topic=2,
            ))


def reverse(apps, schema_editor):
    apps.get_model('drill', 'ExamBlueprint').objects.filter(code='ei-focus-standard-v1').update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [('drill', '0043_paper_self_evaluation')]
    operations = [migrations.RunPython(seed, reverse)]
