from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def ensure_scope_columns(apps, schema_editor):
    table = schema_editor.connection.ops.quote_name('drill_question')
    with schema_editor.connection.cursor() as cursor:
        existing = {c.name for c in schema_editor.connection.introspection.get_table_description(cursor, 'drill_question')}
        if 'syllabus_scope' not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN syllabus_scope varchar(16) NOT NULL DEFAULT 'unclassified'")
        if 'syllabus_scope_confidence' not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN syllabus_scope_confidence double precision NULL")
        if 'syllabus_scope_reason' not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN syllabus_scope_reason varchar(240) NOT NULL DEFAULT ''")


class Migration(migrations.Migration):
    dependencies = [('drill', '0021_questionerratum'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(ensure_scope_columns, migrations.RunPython.noop)],
            state_operations=[
                migrations.AddField(model_name='question', name='syllabus_scope', field=models.CharField(choices=[('in_scope','In scope'),('out_of_scope','Out of scope'),('uncertain','Uncertain'),('unclassified','Unclassified')], db_index=True, default='unclassified', max_length=16)),
                migrations.AddField(model_name='question', name='syllabus_scope_confidence', field=models.FloatField(blank=True, null=True)),
                migrations.AddField(model_name='question', name='syllabus_scope_reason', field=models.CharField(blank=True, max_length=240)),
            ],
        ),
        migrations.AddField(model_name='questiontopic', name='syllabus_requirement', field=models.CharField(choices=[('unspecified','Not classified'),('master','Master'),('understand','Understand'),('know','Know')], db_index=True, default='unspecified', max_length=16)),
        migrations.CreateModel(
            name='TopicMastery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('grade', models.CharField(choices=[('A','Stable'),('B','Developing'),('C','Weak'),('D','Not learned')], db_index=True, default='D', max_length=1)),
                ('last_reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('next_review_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('correct_streak', models.PositiveSmallIntegerField(default=0)),
                ('independent_last_time', models.BooleanField(blank=True, null=True)),
                ('retention_score', models.PositiveSmallIntegerField(default=0)),
                ('review_count', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('topic', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mastery_records', to='drill.questiontopic')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ei_topic_mastery', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(model_name='topicmastery', constraint=models.UniqueConstraint(fields=('user','topic'), name='drill_user_topic_mastery_unique')),
        migrations.AddIndex(model_name='topicmastery', index=models.Index(fields=['user','grade'], name='drill_mastery_user_grade_idx')),
        migrations.AddIndex(model_name='topicmastery', index=models.Index(fields=['user','next_review_at'], name='drill_mastery_user_due_idx')),
    ]
