from django.db import migrations, models


def mark_neighbor_consensus(apps, schema_editor):
    Question = apps.get_model('drill', 'Question')
    # 0.87 was exclusively emitted by the bounded same-topic neighbor branch.
    Question.objects.filter(
        question_type_source='agent',
        question_type_confidence=0.87,
        question_type_human_verified=False,
    ).update(question_type_source='neighbor')


def restore_agent_source(apps, schema_editor):
    Question = apps.get_model('drill', 'Question')
    Question.objects.filter(
        question_type_source='neighbor',
        question_type_confidence=0.87,
        question_type_human_verified=False,
    ).update(question_type_source='agent')


class Migration(migrations.Migration):

    dependencies = [
        ('drill', '0014_question_revisions'),
    ]

    operations = [
        migrations.AlterField(
            model_name='question',
            name='question_type_source',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'Not classified'),
                    ('rule', 'Rule-assisted batch'),
                    ('agent', 'Agent batch'),
                    ('neighbor', 'Neighbor consensus'),
                    ('human', 'Human verified'),
                    ('import', 'Source metadata'),
                ],
                default='',
                max_length=12,
            ),
        ),
        migrations.RunPython(mark_neighbor_consensus, restore_agent_source),
    ]
