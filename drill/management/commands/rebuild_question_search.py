import json
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from drill.models import Question, QuestionSearchDirty, QuestionSearchState
from drill.search.index import (index_batch, projection, source_version, aliases_hash, manifest_data,
                                verify_workspace, worker_lock)


class Command(BaseCommand):
    help = 'Rebuild disposable public question search. Keep DRILL_SEARCH_BACKEND=legacy until verified.'

    def add_arguments(self,parser):
        parser.add_argument('--workspace',choices=('drill','ei','all'),default='all')
        parser.add_argument('--batch-size',type=int,default=500)
        parser.add_argument('--resume',action='store_true')
        parser.add_argument('--verify',action='store_true')
        parser.add_argument('--dry-run',action='store_true')

    def handle(self,*args,**options):
        if options['batch_size']<1 or options['batch_size']>2000:
            raise CommandError('batch-size must be 1..2000')
        spaces=('drill','ei') if options['workspace']=='all' else (options['workspace'],)
        with worker_lock() as locked:
            if not locked:
                raise CommandError('Search worker is already running; retry after it finishes.')
            for workspace in spaces:
                qs=Question.objects.filter(document__workspace=workspace).select_related('document','topic','similarity_topic','source_anchor','exam_type').order_by('pk')
                if options['dry_run']:
                    count,max_terms,mismatch,max_source=0,0,0,0
                    for question in qs.iterator(chunk_size=options['batch_size']):
                        values,_=projection(question);count+=1;max_terms=max(max_terms,len(values['terms']))
                        mismatch+=values['coverage']['manifest_mismatches']
                        max_source=max(max_source,values['coverage']['source_codepoints'])
                    self.stdout.write(json.dumps({'workspace':workspace,'dry_run':True,'questions':count,'maximum_terms':max_terms,'manifest_mismatches':mismatch,'maximum_source_codepoints':max_source}))
                    continue
                state,_=QuestionSearchState.objects.get_or_create(workspace=workspace)
                version=source_version()
                if options['resume'] and state.build_source_version and state.build_source_version!=version:
                    raise CommandError('Build inputs changed. Restart without --resume under legacy mode.')
                last=state.rebuild_last_pk if options['resume'] else 0
                QuestionSearchState.objects.filter(pk=state.pk).update(ready=False,rebuilding=True,
                    build_source_version=version,rebuild_last_pk=last,aliases_hash=aliases_hash(),manifest_hash=manifest_data()[1])
                completed=0
                while True:
                    ids=list(qs.filter(pk__gt=last).values_list('pk',flat=True)[:options['batch_size']])
                    if not ids:
                        break
                    try:
                        completed+=index_batch(ids)
                    except Exception as exc:
                        # Never print source text or private exception details.
                        raise CommandError(f'Batch {ids[0]}..{ids[-1]}: {type(exc).__name__}; rebuild remains resumable.') from exc
                    last=ids[-1]
                    QuestionSearchState.objects.filter(pk=state.pk).update(rebuild_last_pk=last)
                    self.stdout.write(json.dumps({'workspace':workspace,'completed':completed,'last_pk':last}))
                QuestionSearchState.objects.filter(pk=state.pk).update(rebuilding=False)
                if options['verify']:
                    result=verify_workspace(workspace)
                    self.stdout.write(json.dumps(result))
                    if not result['valid']:
                        raise CommandError('Search verification failed; drain/reconcile dirty entries before enabling hybrid.')
