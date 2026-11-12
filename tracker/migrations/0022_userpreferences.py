from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tracker', '0021_alter_knowledgepoint_category_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserPreferences',
            fields=[
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    primary_key=True, related_name='ui_preferences', serialize=False,
                    to=settings.AUTH_USER_MODEL,
                )),
                ('schema_version', models.PositiveSmallIntegerField(default=1)),
                ('revision', models.PositiveBigIntegerField(default=0)),
                ('values', models.JSONField(default=dict)),
                ('field_revisions', models.JSONField(default=dict)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
