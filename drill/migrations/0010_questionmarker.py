from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('drill', '0009_questionuserstate'),
    ]

    operations = [
        migrations.CreateModel(
            name='QuestionMarker',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(choices=[('overconfident', 'Overconfident'), ('concept_gap', 'Concept Gap'), ('rusty', 'Rusty'), ('forgotten', 'Forgotten')], max_length=24)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='markers', to='drill.question')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='question_markers', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name='questionmarker',
            constraint=models.UniqueConstraint(fields=('user', 'question', 'code'), name='drill_user_question_marker_unique'),
        ),
        migrations.AddIndex(
            model_name='questionmarker',
            index=models.Index(fields=['user', 'code'], name='drill_marker_user_code_idx'),
        ),
        migrations.AddIndex(
            model_name='questionmarker',
            index=models.Index(fields=['user', 'question'], name='drill_marker_user_q_idx'),
        ),
    ]
