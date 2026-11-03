from django.db import migrations, models


def backfill_system_grade(apps, schema_editor):
    TopicMastery = apps.get_model('drill', 'TopicMastery')
    TopicMastery.objects.update(system_grade=models.F('grade'))


class Migration(migrations.Migration):
    dependencies = [('drill', '0028_ip_login_handoff')]

    operations = [
        migrations.AddField(
            model_name='questionuserstate', name='version',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='topicmastery', name='system_grade',
            field=models.CharField(
                choices=[('A', 'Stable'), ('B', 'Developing'), ('C', 'Weak'), ('D', 'Not learned')],
                default='D', max_length=1,
            ),
        ),
        migrations.AddField(
            model_name='topicmastery', name='manual_grade',
            field=models.CharField(
                blank=True,
                choices=[('A', 'Stable'), ('B', 'Developing'), ('C', 'Weak'), ('D', 'Not learned')],
                max_length=1, null=True,
            ),
        ),
        migrations.RunPython(backfill_system_grade, migrations.RunPython.noop),
    ]
