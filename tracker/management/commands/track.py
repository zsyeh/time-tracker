from django.core.management.base import BaseCommand
from django.utils import timezone

from tracker.models import TimeLog
from tracker.services import (
    MINIMUM_SESSION_MINUTES,
    ActiveSessionConflict,
    get_service_user,
    is_short_session,
    start_session,
)

class Command(BaseCommand):
    help = 'Terminal-based execution for time tracking state machine.'

    def add_arguments(self, parser):
        # 定义终端命令的位置参数
        parser.add_argument('action', type=str, choices=['start', 'stop'], help='State transition vector')
        parser.add_argument('category', type=str, nargs='?', default=None, help='Task identifier')

    def handle(self, *args, **options):
        action = options['action']
        category = options['category']

        owner = get_service_user()
        active_log = TimeLog.objects.filter(user=owner, status='running').first()

        if action == 'start':
            if active_log:
                self.stderr.write(f"Refused: [{active_log.category}] is currently running.")
                return
            
            if not category:
                self.stderr.write("Syntax Error: Category parameter is mandatory for 'start' action.")
                return
            
            # 验证类别是否在枚举范围内
            valid_categories = [choice[0] for choice in TimeLog.CATEGORY_CHOICES]
            if category not in valid_categories:
                self.stderr.write(f"Invalid category. Allowed: {valid_categories}")
                return

            try:
                start_session(owner, category)
            except ActiveSessionConflict as exc:
                self.stderr.write(f"Refused: [{exc.session.category}] is currently running.")
                return
            self.stdout.write(f"Process [START] -> {category}")

        elif action == 'stop':
            if not active_log:
                self.stderr.write("Refused: No active task detected in memory.")
                return

            end_time = timezone.now()
            if is_short_session(active_log.start_time, end_time):
                active_log.delete()
                self.stdout.write(
                    f'Process [DISCARD] -> session shorter than {MINIMUM_SESSION_MINUTES} min'
                )
                return
            active_log.end_time = end_time
            active_log.status = 'completed'
            active_log.note = active_log.note or 'Completed through the command line; review pending.'
            active_log.breakthrough = active_log.breakthrough or 'Not provided'
            active_log.problems = active_log.problems or 'Not provided'
            active_log.next_action = active_log.next_action or 'Not provided'
            active_log.save()
            self.stdout.write(f"Process [STOP] -> {active_log.category} | Delta: {active_log.duration_minutes} min")
