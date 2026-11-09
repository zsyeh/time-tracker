import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from drill.selected_topic_classification import atomic_json, build_export, import_results, rollback_import

class Command(BaseCommand):
    help='Export missing selected knowledge topics, or safely import/rollback local API results.'
    def add_arguments(self, parser):
        parser.add_argument('action',choices=['export','import','rollback'])
        parser.add_argument('--export',type=Path,required=False)
        parser.add_argument('--results',type=Path)
        parser.add_argument('--backup',type=Path)
        parser.add_argument('--batch-id',default='')
        parser.add_argument('--apply',action='store_true')
    def handle(self,*args,**options):
        try:
            if options['action']=='export':
                if not options['export']: raise ValueError('--export is required')
                data=build_export(); atomic_json(options['export'],data); report=data['summary']
            elif options['action']=='rollback':
                if not options['backup'] or not options['apply']: raise ValueError('Rollback requires --backup and --apply')
                report=rollback_import(options['backup'])
            else:
                if not options['export'] or not options['results']: raise ValueError('--export and --results are required')
                report=import_results(json.loads(options['export'].read_text()),options['results'],
                    apply=options['apply'],backup_path=options['backup'],batch_id=options['batch_id'])
            self.stdout.write(json.dumps(report,ensure_ascii=False))
        except (ValueError,KeyError) as error: raise CommandError(str(error)) from error
