import json
from django.core.management.base import BaseCommand, CommandError
from drill.search.index import process_queue


class Command(BaseCommand):
    help = 'Process public search dirty queue; bounded work and retry-safe revisions.'
    def add_arguments(self,parser):
        parser.add_argument('--batch-size',type=int,default=100)
        parser.add_argument('--max-seconds',type=float,default=20)
    def handle(self,*args,**options):
        if not 1<=options['batch_size']<=2000 or not 0<options['max_seconds']<=300:
            raise CommandError('Invalid work budget')
        result=process_queue(options['batch_size'],options['max_seconds'])
        self.stdout.write(json.dumps(result))
        if result['failed'] or result.get('quarantined') or result.get('oldest_seconds', 0)>300:
            raise CommandError('Search rows failed; inspect error codes and quarantine count, not source bodies.')
