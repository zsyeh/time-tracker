from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .daily_stats import local_study_date, refresh_daily_stat
from .models import TimeLog


@receiver(pre_save, sender=TimeLog)
def remember_previous_study_date(sender, instance, **kwargs):
    if not instance.pk:
        return
    previous_start = sender.objects.filter(pk=instance.pk).values_list(
        'start_time', flat=True
    ).first()
    if previous_start:
        instance._previous_study_date = local_study_date(previous_start)


@receiver(post_save, sender=TimeLog)
def refresh_stats_after_save(sender, instance, raw=False, **kwargs):
    if raw:
        return
    current_date = local_study_date(instance.start_time)
    previous_date = getattr(instance, '_previous_study_date', None)
    refresh_daily_stat(current_date)
    if previous_date and previous_date != current_date:
        refresh_daily_stat(previous_date)


@receiver(post_delete, sender=TimeLog)
def refresh_stats_after_delete(sender, instance, **kwargs):
    if instance.start_time:
        refresh_daily_stat(local_study_date(instance.start_time))
