from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('drill', '0029_state_versions_and_mastery_source'),
    ]

    operations = [
        migrations.CreateModel(
            name='QuestionTimingSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('client_key', models.UUIDField()),
                ('starts_at', models.DateTimeField()),
                ('stopped_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timing_sessions', to='drill.question')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name='questiontimingsession',
            constraint=models.UniqueConstraint(fields=('user', 'question', 'client_key'), name='drill_timing_user_question_client_unique'),
        ),
        migrations.AddIndex(
            model_name='questiontimingsession',
            index=models.Index(fields=['user', 'question', 'stopped_at'], name='drill_timing_active_idx'),
        ),
    ]
