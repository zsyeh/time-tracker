import datetime

from django.db import transaction
from django.utils import timezone

from .models import DailyStudyStat, TimeLog


def local_study_date(start_time):
    """Return the configured local date used to attribute a study session."""
    if timezone.is_naive(start_time):
        start_time = timezone.make_aware(start_time, timezone.get_current_timezone())
    return timezone.localtime(start_time).date()


def local_day_bounds(study_date):
    current_timezone = timezone.get_current_timezone()
    start = timezone.make_aware(
        datetime.datetime.combine(study_date, datetime.time.min),
        current_timezone,
    )
    end = timezone.make_aware(
        datetime.datetime.combine(
            study_date + datetime.timedelta(days=1),
            datetime.time.min,
        ),
        current_timezone,
    )
    return start, end


def refresh_daily_stat(study_date):
    """Rebuild one denormalized row from completed TimeLog records."""
    day_start, next_day_start = local_day_bounds(study_date)
    logs = list(
        TimeLog.objects.filter(
            start_time__gte=day_start,
            start_time__lt=next_day_start,
            end_time__isnull=False,
        ).order_by('start_time')
    )

    with transaction.atomic():
        if not logs:
            DailyStudyStat.objects.filter(date=study_date).delete()
            return None

        stat, _ = DailyStudyStat.objects.update_or_create(
            date=study_date,
            defaults={
                'study_count': len(logs),
                'first_start_time': logs[0].start_time,
                'total_minutes': sum(max(0, log.duration_minutes) for log in logs),
            },
        )
    return stat


def rebuild_all_daily_stats():
    """Repair the complete derived table and remove rows without source logs."""
    study_dates = {
        local_study_date(start_time)
        for start_time in TimeLog.objects.filter(end_time__isnull=False).values_list(
            'start_time', flat=True
        ).iterator()
    }

    with transaction.atomic():
        if study_dates:
            DailyStudyStat.objects.exclude(date__in=study_dates).delete()
        else:
            DailyStudyStat.objects.all().delete()
        for study_date in sorted(study_dates):
            refresh_daily_stat(study_date)

    return len(study_dates)
