"""Rehearse all candidate imports against metadata in an EMPTY disposable DB.

Run using manage.py shell in an isolated PostgreSQL container; no production
connection, credentials, asset bytes, or learning records are required.
"""
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from drill.models import Question, QuestionAsset, QuestionDocument, QuestionExamType, QuestionTopic

if os.environ.get('EXAM_TYPE_REHEARSAL_ONLY') != '1' or settings.DATABASES['default']['HOST'] != '127.0.0.1':
    raise RuntimeError('Only run in the explicitly isolated rehearsal database')
if Question.objects.exists() or QuestionDocument.objects.exists():
    raise RuntimeError('Rehearsal requires an empty database')

root=Path('/audit')
rows=[json.loads(line) for line in (root/'deploy-20261110/current-snapshot.jsonl').open()]
docs={}; topics={}; questions=[]; assets=[]
for row in rows:
    doc_key=(row['source_system'],row['document_filename'],row['document_title'])
    if doc_key not in docs:
        docs[doc_key]=QuestionDocument.objects.create(source_id=len(docs)+1,workspace=row['source_system'],
            filename=row['document_filename'],title=row['document_title'],page_count=1,
            sha256=hashlib.sha256(repr(doc_key).encode()).hexdigest())
    doc=docs[doc_key]
    topic_key=(doc.pk,row['topic_title'])
    if row['topic_title'] and topic_key not in topics:
        topics[topic_key]=QuestionTopic.objects.create(source_id=len(topics)+1,document=doc,
            title=row['topic_title'],level=0,sort_order=len(topics)+1)
    q=Question(id=row['question_id'],uuid=row['uuid'],document=doc,
        similarity_topic=topics.get(topic_key),question_order=row['question_id'],
        source_label=row['source_label'],display_label=row['display_label'],
        prompt_text=row['prompt_text'],latex_text=row['latex_text'],content_mode=row['content_mode'],
        question_type=row['legacy_type'],question_type_source=row['legacy_source'],
        question_type_human_verified=row['legacy_human_verified'],
        fingerprint=hashlib.sha256(row['uuid'].encode()).hexdigest())
    questions.append(q)
    for position,asset in enumerate(row.get('assets') or []):
        assets.append(QuestionAsset(question_id=q.pk,source_id=len(assets)+1,position=position,
            asset_type=asset['type'],sha256=asset['sha256'],width=asset['width'],height=asset['height'],image_data=b''))
Question.objects.bulk_create(questions,batch_size=200)
QuestionAsset.objects.bulk_create(assets,batch_size=200)
source=root/'production-terra/import-candidates.jsonl'
counts=['drill=5837','ei=2798']
call_command('import_exam_types',input=source,expected_workspace_count=counts)
for index in (1,2):
    call_command('import_exam_types',input=source,apply=True,batch_id=f'rehearsal_full_{index}',
        expected_workspace_count=counts,backup=root/f'deploy-20261110/rehearsal-rollback-{index}.json')
    assert QuestionExamType.objects.count()==8635
    assert QuestionExamType.objects.filter(review_required=True).count()==4357
    assert QuestionExamType.objects.filter(question_type='unknown').count()==901
call_command('import_exam_types',rollback=root/'deploy-20261110/rehearsal-rollback-2.json')
assert QuestionExamType.objects.count()==8635
call_command('import_exam_types',rollback=root/'deploy-20261110/rehearsal-rollback-1.json')
assert QuestionExamType.objects.count()==0
original={row['question_id']:row['legacy_type'] for row in rows}
assert all(original[qid]==label for qid,label in Question.objects.values_list('pk','question_type'))
print(json.dumps({'rehearsal':'passed','rows':len(rows),'workspaces':dict(Counter(r['source_system'] for r in rows)),
    'idempotent_import':True,'rollback_verified':True,'legacy_types_preserved':True}))
