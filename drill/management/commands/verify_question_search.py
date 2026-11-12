import json
from django.core.management.base import BaseCommand,CommandError
from drill.search.index import verify_workspace


class Command(BaseCommand):
    help = 'Verify hashes, projection coverage and lexeme frequencies; no source data changes.'
    def add_arguments(self,parser):
        parser.add_argument('--workspace',choices=('drill','ei','all'),default='all')
        parser.add_argument('--enqueue-mismatch',action='store_true')
    def handle(self,*args,**options):
        valid=True
        for workspace in (('drill','ei') if options['workspace']=='all' else (options['workspace'],)):
            result=verify_workspace(workspace,options['enqueue_mismatch']);valid &= result['valid']
            self.stdout.write(json.dumps(result))
        if not valid:
            raise CommandError('Search projection is not fully verified.')
