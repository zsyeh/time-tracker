"""Maintenance-only topic enrichment. Canonical questions and manifests stay intact."""
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone
from .cleaning import is_question_reference_topic
from .cockpit import syllabus_documents
from .core_selected import COURSES
from .models import Question, QuestionAsset, QuestionDocument, QuestionTopic
from .selected_collections import filter_collection

VERSION = 'selected-knowledge-v1'
EDIT_FIELDS = ('similarity_topic_id', 'topic_classification_source', 'topic_classification_confidence')
PLACEHOLDERS = {'', '严选题', '臻选题', '精选题', '未分类', '未归类', '待分类', '背诵简答',
                '简答题', '计算题', '选择题', '填空题', '判断题', 'general', 'unknown'}
PLACEHOLDER_PATTERN = re.compile(r'^(?:\d{4}年(?:真题|试题)(?:\s*[·•].*)?|课后题\s*[·•]\s*第\s*\d+\s*章)$')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      default=lambda item: item.isoformat() if hasattr(item, 'isoformat') else str(item))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def atomic_json(path, value, *, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive and path.exists():
        raise ValueError(f'Backup already exists: {path.name}')
    temporary = path.with_name(path.name + '.partial')
    with temporary.open('w') as target:
        os.chmod(temporary, 0o600)
        target.write(canonical(value) + '\n')
        target.flush(); os.fsync(target.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def placeholder(title):
    title = (title or '').strip()
    return title.lower() in PLACEHOLDERS or bool(PLACEHOLDER_PATTERN.fullmatch(title))


def selection_inventory():
    """Reuse math collection filters and the five real EI manifests, all tiers."""
    selected = {}
    math = filter_collection(Question.objects.filter(document__workspace='drill'),
                             SimpleNamespace(query_params={'collection':'selected'}))
    for pk in math.values_list('pk', flat=True): selected[pk] = ['math']
    registry = defaultdict(list)
    manifest_rows = []
    for course, _title, module in COURSES:
        for row in module.manifest()['questions']:
            registry[str(row['uuid'])].append((course, row['fingerprint']))
            manifest_rows.append((course, row['uuid'], row['fingerprint']))
    mismatches = []
    for pk, question_uuid, fingerprint in Question.objects.filter(
            document__workspace='ei', uuid__in=registry, is_practiceable=True).values_list('pk','uuid','fingerprint'):
        matches = registry[str(question_uuid)]
        if any(expected != fingerprint for _, expected in matches):
            mismatches.append(str(question_uuid)); continue
        selected[pk] = sorted({course for course, _ in matches})
    if mismatches:
        raise ValueError(f'Selected manifest fingerprint mismatch for {len(mismatches)} questions')
    return selected, digest(sorted(manifest_rows))


def topic_catalog():
    rows = list(QuestionTopic.objects.order_by('pk').values(
        'id','document_id','parent_id','title','display_title','level','sort_order'))
    indexed = {row['id']:row for row in rows}
    for row in rows:
        parts=[]; cursor=row; seen=set()
        while cursor and cursor['id'] not in seen:
            seen.add(cursor['id']); parts.append(cursor['display_title'] or cursor['title'])
            cursor=indexed.get(cursor['parent_id'])
        row['path']=' / '.join(reversed(parts))
    return rows


def protected_snapshot(ids, manifest_hash, topics):
    fields=[field.attname for field in Question._meta.concrete_fields if field.attname not in EDIT_FIELDS]
    return digest({'questions':list(Question.objects.filter(pk__in=ids).order_by('pk').values(*fields)),
        'assets':list(QuestionAsset.objects.filter(question_id__in=ids).order_by('pk').values(
            'id','question_id','position','asset_type','sha256','width','height','mime_type')),
        'documents':list(QuestionDocument.objects.order_by('pk').values()),
        'topics':topics,'manifest_hash':manifest_hash})


def build_export():
    selected, manifest_hash = selection_inventory()
    topics=topic_catalog(); topic_by_id={row['id']:row for row in topics}
    canonical_docs={code:doc.pk for code,doc in syllabus_documents().items()}
    docs={row['id']:row for row in QuestionDocument.objects.values('id','workspace','title','display_title')}
    assets=defaultdict(list)
    for row in QuestionAsset.objects.filter(question_id__in=selected).order_by('position','pk').values(
            'id','question_id','position','asset_type','sha256','width','height','mime_type'):
        assets[row['question_id']].append(row)
    pools={}; questions=[]; preserved=Counter()
    query=Question.objects.filter(pk__in=selected).order_by('pk').values(
        'id','uuid','document_id','topic_id',*EDIT_FIELDS,'question_order','source_label','display_label',
        'prompt_text','latex_text','fingerprint','content_mode')
    for row in query.iterator(chunk_size=200):
        topic=topic_by_id.get(row['similarity_topic_id'])
        current=(topic['display_title'] or topic['title']) if topic else ''
        doc=docs[row['document_id']]
        if not placeholder(current):
            preserved[doc['workspace']]+=1; continue
        courses=selected[row['id']]
        allowed_courses = courses
        # Historic electronics papers contain both analog and digital questions;
        # this widens classification candidates without touching curated membership.
        title = doc['display_title'] or doc['title']
        if doc['workspace']=='ei' and ('电子线路' in title or ('模电' in title and '数电' in title)):
            allowed_courses = ['analog', 'digital']
        pool_key='math:'+str(row['document_id']) if doc['workspace']=='drill' else 'ei:'+','.join(allowed_courses)
        if pool_key not in pools:
            allowed_docs=({row['document_id']} if doc['workspace']=='drill' else {
                canonical_docs[{'signal':'signals'}.get(course,course)] for course in allowed_courses})
            candidates=[{'topic_id':t['id'],'path':t['path'],'document_id':t['document_id']} for t in topics
                if t['document_id'] in allowed_docs and not placeholder(t['display_title'] or t['title'])
                and not is_question_reference_topic(t['display_title'] or t['title'])
                and (t['parent_id'] is not None or (t['display_title'] or t['title']) not in {
                    docs[t['document_id']]['title'],docs[t['document_id']]['display_title']})]
            if not candidates: raise ValueError(f'No existing knowledge topics for pool {pool_key}')
            pools[pool_key]=candidates
        before={field:row[field] for field in EDIT_FIELDS}
        item={'question_id':row['id'],'uuid':str(row['uuid']),'workspace':doc['workspace'],
            'document_id':row['document_id'],'document':doc['display_title'] or doc['title'],
            'question_order':row['question_order'],'fingerprint':row['fingerprint'],
            'original_topic_id':row['topic_id'],'before':before,'previous_topic':current,
            'source_label':row['source_label'],'display_label':row['display_label'],
            'prompt_text':row['prompt_text'],'latex_text':row['latex_text'],'content_mode':row['content_mode'],
            'pool':pool_key,'courses':courses,'assets':assets[row['id']]}
        item['content_hash']=digest({'version':VERSION,'question':item,'topics':pools[pool_key]})
        questions.append(item)
    return {'schema_version':1,'classification_version':VERSION,'generated_at':timezone.now().isoformat(),
        'manifest_hash':manifest_hash,'protected_hash':protected_snapshot(selected,manifest_hash,topics),
        'selected_ids':sorted(selected),'taxonomy_hash':digest(topics),'pools':pools,'questions':questions,
        'summary':{'selected_total':len(selected),'to_classify':len(questions),
            'by_workspace':dict(Counter(q['workspace'] for q in questions)),
            'preserved_meaningful':dict(preserved),'pool_sizes':{k:len(v) for k,v in pools.items()}}}


def read_results(path, export):
    with Path(path).open() as source:
        rows=[json.loads(line) for line in source if line.strip()]
    expected={q['question_id']:q for q in export['questions']}; results={}
    for row in rows:
        qid=row.get('question_id')
        if type(qid) is not int or qid not in expected or qid in results: raise ValueError('Unexpected or duplicate question ID')
        q=expected[qid]
        if row.get('uuid')!=q['uuid'] or row.get('workspace')!=q['workspace']:
            raise ValueError(f'Question identity mismatch for {qid}')
        if type(row.get('topic_id')) is not int:
            raise ValueError(f'Unresolved or invalid topic ID for {qid}')
        if row.get('content_hash')!=q['content_hash']: raise ValueError(f'Stale input for question {qid}')
        if row.get('model_id') not in {'gpt-6.1-terra','gpt-6.1-sol'}: raise ValueError('Unexpected model')
        if row.get('classification_version')!=VERSION: raise ValueError('Unexpected classification version')
        if row.get('topic_id') not in {t['topic_id'] for t in export['pools'][q['pool']]}:
            raise ValueError(f'Unresolved or unauthorized topic for question {qid}')
        results[qid]=row
    if set(results)!=set(expected): raise ValueError('Classification coverage is incomplete')
    return results


@transaction.atomic
def import_results(export, results_path, *, apply=False, backup_path=None, batch_id=''):
    results=read_results(results_path,export)
    selected, manifest_hash=selection_inventory(); topics=topic_catalog()
    if sorted(selected)!=export['selected_ids'] or manifest_hash!=export['manifest_hash']:
        raise ValueError('Selected collection changed; refresh export')
    if protected_snapshot(selected,manifest_hash,topics)!=export['protected_hash']:
        raise ValueError('Question/content/assets/taxonomy changed; refresh export')
    current={q.pk:q for q in Question.objects.select_for_update().filter(
        pk__in=results).only('pk','fingerprint',*EDIT_FIELDS)}
    if len(current)!=len(results): raise ValueError('Missing production question')
    if apply and (not backup_path or not batch_id or len(batch_id)>12):
        raise ValueError('Apply requires a backup path and a batch ID of at most 12 characters')
    previous=json.loads(Path(backup_path).read_text()) if backup_path and Path(backup_path).exists() else None
    if previous:
        if previous['export_hash']!=digest(export) or previous['results_hash']!=digest(results):
            raise ValueError('Existing backup belongs to a different input')
        if all({f:getattr(current[row['question_id']],f) for f in EDIT_FIELDS}==row['after'] for row in previous['rows']):
            return {'verified':True,'idempotent':True,'updated':0,'rows':len(results)}
        raise ValueError('Existing backup targets are no longer identical; refusing overwrite')
    changes=[]
    for q in export['questions']:
        record=current[q['question_id']]
        if {f:getattr(record,f) for f in EDIT_FIELDS}!=q['before']:
            raise ValueError(f'Knowledge classification changed for question {record.pk}')
        result=results[record.pk]; model='sol' if result['model_id']=='gpt-6.1-sol' else 'terra'
        after={'similarity_topic_id':result['topic_id'],'topic_classification_source':f'api-topic:{model}:{batch_id}',
               'topic_classification_confidence':None}
        changes.append({'question_id':record.pk,'fingerprint':record.fingerprint,'before':q['before'],
                        'after':after,'result':result})
    if apply:
        atomic_json(backup_path,{'schema_version':1,'batch_id':batch_id,'export_hash':digest(export),
            'results_hash':digest(results),'created_at':timezone.now().isoformat(),'rows':changes},exclusive=True)
        for change in changes:
            for field,value in change['after'].items(): setattr(current[change['question_id']],field,value)
        affected=Question.objects.bulk_update(list(current.values()),EDIT_FIELDS,batch_size=100)
        saved={row['id']:row for row in Question.objects.filter(pk__in=current).values('id',*EDIT_FIELDS)}
        if affected!=len(changes) or any(
            {field:saved[row['question_id']][field] for field in EDIT_FIELDS}!=row['after'] for row in changes):
            raise ValueError('Saved knowledge fields do not match; rolling back')
        if protected_snapshot(selected,manifest_hash,topic_catalog())!=export['protected_hash']:
            raise ValueError('Protected selected-bank data changed; rolling back')
    return {'verified':True,'mode':'apply' if apply else 'dry-run','rows':len(changes),
        'updated':len(changes) if apply else 0,'by_workspace':export['summary']['by_workspace'],
        'models':dict(Counter(row['model_id'] for row in results.values()))}


@transaction.atomic
def rollback_import(path):
    backup=json.loads(Path(path).read_text()); changes=backup['rows']
    current={q.pk:q for q in Question.objects.select_for_update().filter(
        pk__in=[row['question_id'] for row in changes]).only('pk','fingerprint',*EDIT_FIELDS)}
    for row in changes:
        q=current.get(row['question_id'])
        if q is None or q.fingerprint!=row['fingerprint'] or {f:getattr(q,f) for f in EDIT_FIELDS}!=row['after']:
            raise ValueError('Later edits or missing question prevent safe rollback')
    for row in changes:
        for field,value in row['before'].items(): setattr(current[row['question_id']],field,value)
    Question.objects.bulk_update(list(current.values()),EDIT_FIELDS,batch_size=100)
    return {'verified':True,'restored':len(changes),'batch_id':backup['batch_id']}
