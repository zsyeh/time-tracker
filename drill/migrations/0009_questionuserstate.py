from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('drill', '0008_question_topic_classification_confidence_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='QuestionUserState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('note', models.TextField(blank=True)),
                ('is_favorite', models.BooleanField(db_index=True, default=False)),
                ('review_later', models.BooleanField(db_index=True, default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_states', to='drill.question')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='question_user_states', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name='questionuserstate',
            constraint=models.UniqueConstraint(fields=('user', 'question'), name='drill_user_question_state_unique'),
        ),
        migrations.AddIndex(
            model_name='questionuserstate',
            index=models.Index(fields=['user', 'is_favorite'], name='drill_state_favorite_idx'),
        ),
        migrations.AddIndex(
            model_name='questionuserstate',
            index=models.Index(fields=['user', 'review_later'], name='drill_state_review_idx'),
        ),
    ]
