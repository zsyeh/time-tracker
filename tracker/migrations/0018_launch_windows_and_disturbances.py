import datetime

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0017_user_data_encryption'),
    ]

    operations = [
        migrations.AddField(
            model_name='timelog',
            name='disturbance_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='timelog',
            name='last_disturbance_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='launchtoken',
            name='available_from',
            field=models.TimeField(default=datetime.time(6, 0)),
        ),
        migrations.AddField(
            model_name='launchtoken',
            name='available_until',
            field=models.TimeField(default=datetime.time(22, 0)),
        ),
        migrations.AddField(
            model_name='launchtoken',
            name='disturbance_token_digest',
            field=models.CharField(blank=True, editable=False, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='launchtoken',
            name='is_paused',
            field=models.BooleanField(default=False),
        ),
    ]
