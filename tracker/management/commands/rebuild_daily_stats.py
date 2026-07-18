from django.core.management.base import BaseCommand

from tracker.daily_stats import rebuild_all_daily_stats


class Command(BaseCommand):
    help = 'Rebuild all denormalized daily study statistics from TimeLog records.'

    def handle(self, *args, **options):
        rebuilt_days = rebuild_all_daily_stats()
        self.stdout.write(
            self.style.SUCCESS(f'Rebuilt daily statistics for {rebuilt_days} day(s).')
        )
