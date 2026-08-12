import uuid

from django.db import migrations, models
import django.db.models.deletion


def populate_session_uuids(apps, schema_editor):
    TimeLog = apps.get_model('tracker', 'TimeLog')
    for session_id in TimeLog.objects.filter(uuid__isnull=True).values_list('pk', flat=True).iterator():
        TimeLog.objects.filter(pk=session_id).update(uuid=uuid.uuid4())


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0015_site_configuration_math_visualization'),
    ]

    operations = [
        migrations.AddField(
            model_name='timelog',
            name='uuid',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(populate_session_uuids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='timelog',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.CreateModel(
            name='SessionShare',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_digest', models.CharField(max_length=64, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shares', to='tracker.timelog')),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.AddConstraint(
            model_name='sessionshare',
            constraint=models.UniqueConstraint(
                condition=models.Q(('is_active', True)),
                fields=('session',),
                name='one_active_share_per_session',
            ),
        ),
    ]
