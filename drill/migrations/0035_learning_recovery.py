from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('drill', '0034_questionexamtypeedit'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name='questiontimingsession', name='recovery', field=models.JSONField(blank=True, default=dict, null=True)),
        migrations.CreateModel(name='LearningRecoveryState', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('locations', models.JSONField(blank=True, default=dict)),
            ('last_workspace', models.CharField(blank=True, max_length=16)),
            ('version', models.PositiveIntegerField(default=0)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('active_timer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='drill.questiontimingsession')),
            ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='learning_recovery', to=settings.AUTH_USER_MODEL)),
        ]),
    ]
