"""Validate and transactionally import offline original exam-form labels."""

import json
import os
import re
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Prefetch

from drill.models import Question, QuestionAsset, QuestionExamType
from drill.exam_types import audit_reasons, digest_for_question


ALLOWED = {
    'drill': {'choice', 'fill', 'large', 'unknown'},
    'ei': {'judgment', 'choice', 'fill', 'short_answer', 'large', 'unknown'},
}
LEGACY = {'single_choice': 'choice', 'fill_blank': 'fill', 'solution': 'large'}
FIELDS = ('source_system', 'question_type', 'subquestion_count', 'classification_source',
          'model_id', 'classification_version', 'content_hash', 'review_required',
          'reason', 'evidence_missing', 'review_reasons', 'batch_id')


class Command(BaseCommand):
    help='Dry-run by default; --apply requires a verified backup file and migrated schema.'

    def add_arguments(self, parser):
        parser.add_argument('--input',type=Path)
        parser.add_argument('--apply',action='store_true')
        parser.add_argument('--batch-id',default='')
        parser.add_argument('--backup',type=Path)
        parser.add_argument('--rollback',type=Path)
        parser.add_argument('--expected-workspace-count', action='append', default=[], metavar='WORKSPACE=COUNT')

    @transaction.atomic
    def handle(self,*args,**options):
        for key in ('input','backup','rollback'):
            if options.get(key):options[key]=Path(options[key])
        if options['rollback']:
            self.rollback(options['rollback'])
            return
        if not options['input'] or not options['input'].is_file():
            raise CommandError('--input must name a JSONL file')
        if options['apply'] and (not options['backup'] or not re.fullmatch('[A-Za-z0-9_-]{8,64}',options['batch_id'])):
            raise CommandError('--apply requires --backup and a safe --batch-id')
        rows=[];seen=set()
        with options['input'].open(encoding='utf-8') as source:
            for line_no,line in enumerate(source,1):
                if not line.strip():continue
                try:row=json.loads(line)
                except json.JSONDecodeError as error:raise CommandError(f'Invalid JSONL line {line_no}') from error
                key=(row.get('source_system'),row.get('question_id'))
                if key in seen:raise CommandError(f'Duplicate question on line {line_no}')
                seen.add(key)
                if key[0] not in ALLOWED or row.get('question_type') not in ALLOWED[key[0]]:
                    raise CommandError(f'Invalid workspace or type on line {line_no}')
                if not isinstance(key[1],int) or key[1]<1 or not re.fullmatch('[a-f0-9]{64}',str(row.get('content_hash',''))):
                    raise CommandError(f'Invalid ID or content hash on line {line_no}')
                count=row.get('subquestion_count')
                if count is not None and (not isinstance(count,int) or not 1<=count<=100):
                    raise CommandError(f'Invalid subquestion count on line {line_no}')
                if not row.get('reason') or not row.get('classification_version'):
                    raise CommandError(f'Missing audit fields on line {line_no}')
                reasons=row.get('review_reasons',[])
                if not isinstance(reasons,list) or any(not isinstance(item,str) for item in reasons):
                    raise CommandError(f'Invalid review reasons on line {line_no}')
                if not isinstance(row.get('review_required'),bool):
                    raise CommandError(f'Invalid review flag on line {line_no}')
                rows.append(row)
        if not rows:raise CommandError('No import rows')
        expected={}
        for item in options['expected_workspace_count']:
            try:
                workspace,count=item.split('='); expected[workspace]=int(count)
                if workspace not in ALLOWED or int(count)<0:raise ValueError
            except ValueError as error:raise CommandError('Expected counts must be WORKSPACE=COUNT') from error
        actual=dict(Counter(row['source_system'] for row in rows))
        if expected and actual!=expected:
            raise CommandError(f'Workspace count mismatch: expected {expected}, found {actual}')
        ids=[row['question_id'] for row in rows]
        if options['apply']:
            list(Question.objects.filter(pk__in=ids).order_by('pk').select_for_update().values_list('pk',flat=True))
        assets=QuestionAsset.objects.only('id','question_id','position','asset_type','sha256')
        for start in range(0,len(ids),200):
            chunk=Question.objects.filter(pk__in=ids[start:start+200]).select_related(
                'document','similarity_topic').prefetch_related(Prefetch('assets',queryset=assets))
            questions={q.pk:q for q in chunk}
            for row in rows[start:start+200]:
                question=questions.get(row['question_id'])
                if not question or question.document.workspace!=row['source_system']:
                    raise CommandError(f'Missing or cross-workspace question {row["question_id"]}')
                if digest_for_question(question)!=row['content_hash']:
                    raise CommandError(f'Stale question content {row["question_id"]}; re-export before importing')
                row['review_reasons']=audit_reasons(question,row)
                row['review_required']=bool(row['review_required'] or row['review_reasons'])
        table_exists=QuestionExamType._meta.db_table in connection.introspection.table_names()
        if options['apply'] and not table_exists:
            raise CommandError('Migration 0032_questionexamtype must be applied before --apply')
        existing={r.question_id:r for r in QuestionExamType.objects.filter(question_id__in=ids)} if table_exists else {}
        counts=Counter((r['source_system'],r['question_type']) for r in rows)
        summary={'mode':'apply' if options['apply'] else 'dry_run','rows':len(rows),
                 'new':len(rows)-len(existing),'updates':len(existing),
                 'table_exists':table_exists,
                 'workspace_counts':actual,
                 'review_required':sum(bool(r['review_required']) for r in rows),
                 'review_reasons':dict(Counter(reason for row in rows for reason in row['review_reasons'])),
                 'types':{f'{w}:{label}':count for (w,label),count in sorted(counts.items())}}
        if not options['apply']:
            self.stdout.write(json.dumps(summary,ensure_ascii=False));return
        backup=options['backup'].expanduser().resolve()
        if backup.exists():raise CommandError('Backup path already exists')
        backup.parent.mkdir(parents=True,exist_ok=True)
        payload={'batch_id':options['batch_id'],'rows':[
            {'question_id':qid,'previous':{field:getattr(previous,field) for field in FIELDS} if previous else None}
            for qid,previous in ((qid,existing.get(qid)) for qid in ids)
        ]}
        temp=backup.with_name(backup.name+'.tmp')
        with temp.open('x',encoding='utf-8') as target:
            os.chmod(temp,0o600)
            json.dump(payload,target,ensure_ascii=False)
            target.flush();os.fsync(target.fileno())
        os.replace(temp,backup)
        with transaction.atomic():
            for start in range(0,len(rows),200):
                objects=[]
                for row in rows[start:start+200]:
                    values={field:row.get(field,'') for field in FIELDS if field!='batch_id'}
                    values['model_id']=values['model_id'] or ''
                    values['batch_id']=options['batch_id']
                    objects.append(QuestionExamType(question_id=row['question_id'],**values))
                QuestionExamType.objects.bulk_create(objects,update_conflicts=True,
                    unique_fields=['question'],update_fields=[*FIELDS,'updated_at'],batch_size=200)
            saved={r.question_id:r for r in QuestionExamType.objects.filter(question_id__in=ids)}
            if len(saved)!=len(rows) or any(
                any(getattr(saved[row['question_id']],field)!=row.get(field,'')
                    for field in FIELDS if field not in ('batch_id','model_id'))
                or saved[row['question_id']].model_id!=(row.get('model_id') or '')
                or saved[row['question_id']].batch_id!=options['batch_id'] for row in rows
            ):
                raise CommandError('Post-import integrity check failed; transaction rolled back')
        self.stdout.write(json.dumps({**summary,'backup':str(backup)},ensure_ascii=False))

    def rollback(self,path):
        path=path.expanduser().resolve()
        if not path.is_file():raise CommandError('Rollback backup is missing')
        payload=json.loads(path.read_text(encoding='utf-8'))
        batch_id=payload['batch_id']
        rows=payload['rows']
        ids=[row['question_id'] for row in rows]
        list(Question.objects.filter(pk__in=ids).order_by('pk').select_for_update().values_list('pk',flat=True))
        current={r.question_id:r for r in QuestionExamType.objects.select_for_update().filter(question_id__in=ids)}
        if len(current)!=len(ids) or any(current[qid].batch_id!=batch_id for qid in ids):
            raise CommandError('Rows changed since this batch; rollback refused')
        with transaction.atomic():
            for row in rows:
                previous=row['previous']
                if previous is None:QuestionExamType.objects.filter(question_id=row['question_id']).delete()
                else:QuestionExamType.objects.filter(question_id=row['question_id']).update(**previous)
        self.stdout.write(json.dumps({'rolled_back':len(rows),'batch_id':batch_id}))
