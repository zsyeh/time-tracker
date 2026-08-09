from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def assign_historical_owner(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
    TimeLog = apps.get_model('tracker', 'TimeLog')
    DailyStudyStat = apps.get_model('tracker', 'DailyStudyStat')

    # A brand-new installation has nothing to backfill and may not have its
    # first administrator yet. Historical installations must have an owner.
    if not TimeLog.objects.exists() and not DailyStudyStat.objects.exists():
        return

    owner = User.objects.filter(is_superuser=True, is_active=True).order_by('pk').first()
    if owner is None:
        owner = User.objects.filter(is_active=True).order_by('pk').first()
    if owner is None:
        raise RuntimeError(
            'Cannot migrate historical learning data without an existing active user.'
        )

    TimeLog.objects.filter(end_time__isnull=False).update(status='completed')
    TimeLog.objects.filter(end_time__isnull=True).update(status='running')
    # The partial unique constraint already exists at this point. Set statuses
    # before assigning one owner so historical completed rows never collide as
    # multiple "running" sessions during the backfill statement.
    TimeLog.objects.filter(user__isnull=True).update(user_id=owner.pk)
    DailyStudyStat.objects.filter(user__isnull=True).update(user_id=owner.pk)

    if TimeLog.objects.filter(user__isnull=True).exists():
        raise RuntimeError('Historical session ownership backfill is incomplete.')
    if DailyStudyStat.objects.filter(user__isnull=True).exists():
        raise RuntimeError('Historical daily-stat ownership backfill is incomplete.')


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tracker', '0007_knowledgepoint_launchtoken_learningissue_and_more'),
    ]

    operations = [
        migrations.RunPython(assign_historical_owner, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='timelog',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='study_sessions',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='dailystudystat',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='daily_study_stats',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
