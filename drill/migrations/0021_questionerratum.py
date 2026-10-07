from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('drill', '0020_cloud_question_timer'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='QuestionErratum',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('crop', 'Image / crop'), ('question', 'Question content'), ('answer', 'Answer / explanation'), ('formula', 'Formula rendering'), ('metadata', 'Label / topic'), ('other', 'Other')], db_index=True, default='other', max_length=16)),
                ('description', models.TextField()),
                ('status', models.CharField(choices=[('open', 'Open'), ('reviewing', 'Reviewing'), ('resolved', 'Resolved'), ('declined', 'Declined')], db_index=True, default='open', max_length=16)),
                ('resolution', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='errata', to='drill.question')),
                ('reporter', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='question_errata', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ('-created_at', '-pk')},
        ),
        migrations.AddIndex(model_name='questionerratum', index=models.Index(fields=['status', 'created_at'], name='drill_erratum_status_idx')),
        migrations.AddIndex(model_name='questionerratum', index=models.Index(fields=['question', 'created_at'], name='drill_erratum_question_idx')),
    ]
