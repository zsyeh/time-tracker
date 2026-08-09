from django.core.management.base import BaseCommand

from tracker.learning_log import sync_session_note
from tracker.models import GitHubNoteSync


class Command(BaseCommand):
    help = 'Push pending completed-session Markdown documents to GitHub.'

    def add_arguments(self, parser):
        parser.add_argument('--session-id', type=int)
        parser.add_argument('--limit', type=int, default=20)

    def handle(self, *args, **options):
        limit = max(1, min(options['limit'], 100))
        queryset = GitHubNoteSync.objects.filter(status='pending').select_related('session')
        if options['session_id']:
            queryset = queryset.filter(session_id=options['session_id'])

        synced = 0
        pending = 0
        for record in queryset.order_by('created_at')[:limit]:
            result = sync_session_note(record.session)
            if result['status'] == 'pushed':
                synced += 1
            else:
                pending += 1
                self.stderr.write(
                    f"Session {record.session_id} remains pending: {result.get('error', result['status'])}"
                )
        self.stdout.write(f'GitHub note sync: {synced} pushed, {pending} pending')
