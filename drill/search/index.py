"""Projection building and idempotent, revision-aware queue processing."""
import datetime
import hashlib
import json
import time
from collections import Counter
from contextlib import contextmanager
from functools import lru_cache
from itertools import islice
from pathlib import Path
from django.db import connection, transaction
from django.db.models import F, Q
from django.utils import timezone
from drill.models import (Question, QuestionTopic, QuestionSearchDocument, QuestionSearchLexeme,
                          QuestionSearchDirty, QuestionSearchState)
from .normalize import (NORMALIZER_VERSION, SEPARATOR, LATIN_RE, aliases_hash, compact,
                        formula, formula_terms, identifier, text_terms)

SCHEMA_VERSION = 1
MANIFEST_NAMES = ('circuit', 'signal', 'analog', 'digital', 'communication')


@lru_cache(maxsize=1)
def manifest_data():
    result, digests = {}, []
    for name in MANIFEST_NAMES:
        path = Path(__file__).resolve().parent.parent/'data'/f'{name}_selected_v1.json'
        if not path.exists():
            continue
        raw = path.read_bytes()
        digests.append(hashlib.sha256(raw).hexdigest())
        data = json.loads(raw)
        buckets = {b['key']: b['title'] for b in data.get('buckets', [])}
        for row in data.get('questions', []):
            if row.get('status', 'included') == 'included':
                result.setdefault(row['uuid'], []).append({
                    'fingerprint': row['fingerprint'],
                    'text': [row.get('label', ''), buckets.get(row.get('bucket'), ''), *row.get('tags', [])],
                })
    return result, hashlib.sha256(''.join(digests).encode()).hexdigest()


def source_version():
    return hashlib.sha256(f'{NORMALIZER_VERSION}:{aliases_hash()}:{manifest_data()[1]}'.encode()).hexdigest()


def question_source(question):
    doc = question.document
    topics, seen = [], set()
    direct_topics=[]
    for topic in (question.topic, question.similarity_topic):
        if topic:
            direct_topics.extend([topic.title,topic.display_title,topic.normalized_title])
        while topic and topic.pk not in seen:
            seen.add(topic.pk)
            topics.extend([topic.title, topic.display_title, topic.normalized_title])
            topic = topic.parent
    try:
        anchor = question.source_anchor
    except Question.source_anchor.RelatedObjectDoesNotExist:
        anchor = None
    rows = manifest_data()[0].get(str(question.uuid), []) if doc.workspace == 'ei' else []
    reviewed = [text for row in rows if row['fingerprint'] == question.fingerprint for text in row['text']]
    mismatches = sum(row['fingerprint'] != question.fingerprint for row in rows)
    values = {
        'labels': [question.source_label, question.display_label, *( [anchor.label, anchor.key] if anchor else [])],
        'book': [doc.title, doc.display_title, doc.filename],
        'topics': [*topics, *reviewed], 'direct_topics':direct_topics,
        'body': [question.prompt_text], 'formula': [question.latex_text, question.prompt_text],
    }
    size = sum(len(value or '') for name, fields in values.items() if name != 'formula' for value in fields) + len(question.latex_text or '')
    if size > 100000:
        raise ValueError('SEARCH_SOURCE_TOO_LONG')
    identifiers = list(dict.fromkeys(identifier(v) for v in [str(question.uuid), question.source_label,
                                  *( [anchor.key] if anchor else [])] if v))
    # Every live field that changes membership/order is hashed as well as indexed text.
    membership = {name: getattr(question, name) for name in (
        'document_id','topic_id','similarity_topic_id','question_order','content_mode','fingerprint',
        'is_past_exam','source_category','record_kind','is_practiceable','subject','exam_year','exam_variant',
        'answer_source','question_type','syllabus_scope')}
    membership['relation_type'] = doc.relation_type
    membership['workspace'] = doc.workspace
    try:
        membership['final_type'] = question.exam_type.question_type
    except Question.exam_type.RelatedObjectDoesNotExist:
        membership['final_type'] = None
    raw = {'values': values, 'identifiers': identifiers, 'membership': membership, 'version': source_version()}
    return values, identifiers, hashlib.sha256(json.dumps(raw, ensure_ascii=False, sort_keys=True).encode()).hexdigest(), {
        'has_prompt': bool(question.prompt_text.strip()), 'has_latex': bool(question.latex_text.strip()),
        'has_anchor': bool(anchor), 'has_reviewed_metadata': bool(reviewed), 'manifest_mismatches': mismatches, 'source_codepoints': size,
    }


def projection(question):
    values, identifiers, digest, coverage = question_source(question)
    terms, refs, lexemes = {}, {}, {}
    workspace = question.document.workspace
    def add_ref(kind, term, display, target, target_key=''):
        if not term:
            return
        key = (workspace, kind, term[:120], target_key)
        refs[key] = dict(zip(('workspace','kind','term','target_key'), key))
        lexemes[key] = {'display': display, 'target': target}
    norms = {}
    for name, bit in [('labels',1),('book',2),('topics',4),('body',8),('formula',16),('direct_topics',64)]:
        norm = SEPARATOR.join(dict.fromkeys((formula(v) if name == 'formula' else compact(v)) for v in values[name] if v))
        if name=='direct_topics':
            coverage['direct_topics_norm']=norm
        else:
            norms[name+'_norm']=norm
        for value in values[name]:
            for term in (formula_terms(value) if name == 'formula' else text_terms(value)):
                terms[term] = terms.get(term, 0) | bit
            if name != 'formula':
                for token in set(LATIN_RE.findall(compact(value))):
                    if 3 <= len(token) <= 48:
                        add_ref('latin', token, token, {})
    for value in identifiers:
        terms['id:'+value] = terms.get('id:'+value, 0) | 32
    for value in values['book']:
        add_ref('book', compact(value), value, {'document': question.document_id}, str(question.document_id))
    for topic in (question.topic, question.similarity_topic):
        if topic:
            add_ref('topic', compact(topic.display_title or topic.title), topic.display_title or topic.title,
                    {'topic': topic.pk}, str(topic.pk))
    return {'workspace': workspace, 'schema_version': SCHEMA_VERSION, 'source_hash': digest, **norms,
            'identifiers': identifiers, 'terms': terms, 'lexeme_refs': list(refs.values()),
            'coverage': coverage, 'indexed_at': timezone.now()}, lexemes


def enqueue(question_ids, *, bump=True):
    ids = list(set(question_ids))
    with transaction.atomic():
        workspaces = sorted(set(Question.objects.filter(pk__in=ids).values_list('document__workspace', flat=True)))
        if bump:
            bump_generations(workspaces)
        for pk in ids:
            obj, created = QuestionSearchDirty.objects.get_or_create(question_id=pk)
            if not created:
                QuestionSearchDirty.objects.filter(pk=pk).update(revision=F('revision')+1, attempts=0,
                    next_retry_at=None, last_error_code='', enqueued_at=timezone.now())


def bump_generations(workspaces):
    for workspace in sorted(set(workspaces)):
        QuestionSearchState.objects.get_or_create(workspace=workspace)
        QuestionSearchState.objects.filter(workspace=workspace).update(generation=F('generation')+1)


def refs_counter(refs):
    return Counter(tuple(ref[k] for k in ('workspace','kind','term','target_key')) for ref in refs)


def sync_lexemes(old_refs, new_refs, metadata):
    old, new = refs_counter(old_refs), refs_counter(new_refs)
    if connection.vendor == 'postgresql':
        # One statement per delta kind, not one round trip per vocabulary word.
        added, removed, same = [], [], []
        for key in sorted(old.keys() | new.keys()):
            row = dict(zip(('workspace','kind','term','target_key'), key))
            delta = new[key]-old[key]
            if delta > 0:
                added.append({**row, **metadata[key], 'frequency': delta})
            elif delta < 0:
                removed.append({**row, 'frequency': -delta})
            else:
                same.append({**row, **metadata[key]})
        with connection.cursor() as cursor:
            if added:
                cursor.execute("""INSERT INTO drill_questionsearchlexeme
                    (workspace,kind,term,target_key,display,target,document_frequency,schema_version)
                    SELECT workspace,kind,term,target_key,display,target,frequency,1
                    FROM jsonb_to_recordset(%s::jsonb) AS x(workspace text,kind text,term text,target_key text,display text,target jsonb,frequency integer)
                    ORDER BY workspace,kind,term,target_key
                    ON CONFLICT(workspace,kind,term,target_key) DO UPDATE SET
                    document_frequency=drill_questionsearchlexeme.document_frequency+EXCLUDED.document_frequency,
                    display=EXCLUDED.display,target=EXCLUDED.target""", [json.dumps(added,ensure_ascii=False)])
            if removed:
                records = "jsonb_to_recordset(%s::jsonb) AS x(workspace text,kind text,term text,target_key text,frequency integer)"
                predicate = "l.workspace=x.workspace AND l.kind=x.kind AND l.term=x.term AND l.target_key=x.target_key"
                payload=json.dumps(removed,ensure_ascii=False)
                cursor.execute('UPDATE drill_questionsearchlexeme l SET document_frequency=l.document_frequency-x.frequency FROM '+records+' WHERE '+predicate,[payload])
                cursor.execute('DELETE FROM drill_questionsearchlexeme l USING '+records+' WHERE '+predicate+' AND l.document_frequency=0',[payload])
            if same:
                cursor.execute("""UPDATE drill_questionsearchlexeme l SET display=x.display,target=x.target
                    FROM jsonb_to_recordset(%s::jsonb) AS x(workspace text,kind text,term text,target_key text,display text,target jsonb)
                    WHERE l.workspace=x.workspace AND l.kind=x.kind AND l.term=x.term AND l.target_key=x.target_key""",[json.dumps(same,ensure_ascii=False)])
        return
    for key in sorted(old.keys() | new.keys()):
        lookup = dict(zip(('workspace','kind','term','target_key'), key))
        delta = new[key]-old[key]
        if delta > 0:
            obj, created = QuestionSearchLexeme.objects.get_or_create(**lookup,
                defaults={**metadata[key], 'document_frequency': delta})
            if not created:
                QuestionSearchLexeme.objects.filter(pk=obj.pk).update(document_frequency=F('document_frequency')+delta, **metadata[key])
        elif delta < 0:
            # Atomic decrement obtains the row lock before deciding to delete;
            # concurrent source deletion must not leave a zero-frequency row.
            rows = QuestionSearchLexeme.objects.filter(**lookup)
            rows.update(document_frequency=F('document_frequency')+delta)
            rows.filter(document_frequency=0).delete()
        elif key in metadata:
            QuestionSearchLexeme.objects.filter(**lookup).update(**metadata[key])


def index_question(pk, revision=0, statement_timeout_ms=None):
    with transaction.atomic():
        if statement_timeout_ms is not None and connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('statement_timeout', %s, true)", [str(statement_timeout_ms)])
        question = Question.objects.select_related('document','topic','similarity_topic','source_anchor','exam_type').get(pk=pk)
        values, lexemes = projection(question)
        old = QuestionSearchDocument.objects.select_for_update().filter(pk=pk).first()
        sync_lexemes(old.lexeme_refs if old else [], values['lexeme_refs'], lexemes)
        QuestionSearchDocument.objects.update_or_create(question_id=pk, defaults=values)
        bump_generations([values['workspace'], *( [old.workspace] if old else [])])
        dirty = QuestionSearchDirty.objects.filter(question_id=pk)
        dirty.filter(revision=revision).delete()
    return values


def index_batch(question_ids):
    """Full rebuild only: bounded atomic batch under the caller's worker lock.

    Per-question source hashes and captured dirty revisions retain the incremental
    worker semantics. Aggregated lexical deltas count each question exactly once;
    a single publication generation represents this batch's atomic commit.
    """
    ids=sorted(set(question_ids))
    if not ids:
        return 0
    with transaction.atomic():
        revisions=dict(QuestionSearchDirty.objects.filter(pk__in=ids).values_list('pk','revision'))
        questions=list(Question.objects.filter(pk__in=ids).select_related(
            'document','topic','similarity_topic','source_anchor','exam_type').order_by('pk'))
        old_rows=QuestionSearchDocument.objects.select_for_update().filter(pk__in=ids).in_bulk()
        old_refs,new_refs,metadata,rows,spaces=[],[],{},[],set()
        for question in questions:
            values,lexemes=projection(question)
            old=old_rows.get(question.pk)
            if old:
                old_refs.extend(old.lexeme_refs)
                spaces.add(old.workspace)
            new_refs.extend(values['lexeme_refs'])
            metadata.update(lexemes)
            spaces.add(values['workspace'])
            rows.append(QuestionSearchDocument(question_id=question.pk,**values))
        if rows:
            sync_lexemes(old_refs,new_refs,metadata)
            fields=[field.name for field in QuestionSearchDocument._meta.concrete_fields if not field.primary_key]
            QuestionSearchDocument.objects.bulk_create(rows,batch_size=500,update_conflicts=True,
                unique_fields=['question'],update_fields=fields)
            bump_generations(spaces)
        # Never clear a revision created after our source read. Bounded chunks
        # also stay within SQLite's conservative bind parameter limit.
        pairs=list(revisions.items())
        for start in range(0,len(pairs),200):
            match=Q(pk__in=[])
            for pk,revision in pairs[start:start+200]:
                match |= Q(pk=pk,revision=revision)
            QuestionSearchDirty.objects.filter(match).delete()
        return len(rows)


@contextmanager
def worker_lock():
    acquired = True
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_try_advisory_lock(8612042201)')
            acquired = cursor.fetchone()[0]
    try:
        yield acquired
    finally:
        if acquired and connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_unlock(8612042201)')


def process_queue(batch_size=100, max_seconds=20):
    started, completed, failed = time.monotonic(), 0, 0
    with worker_lock() as acquired:
        if not acquired:
            return {'completed': 0, 'failed': 0, 'locked': True}
        rows = QuestionSearchDirty.objects.filter(attempts__lt=5).filter(
            Q(next_retry_at__isnull=True) | Q(next_retry_at__lte=timezone.now())).order_by('enqueued_at').values_list('pk','revision','attempts')[:batch_size]
        for pk, revision, attempts in list(rows):
            if time.monotonic()-started >= max_seconds:
                break
            try:
                remaining = max_seconds - (time.monotonic() - started)
                index_question(pk, revision, max(1, int(remaining * 1000)))
                completed += 1
            except Question.DoesNotExist:
                QuestionSearchDirty.objects.filter(pk=pk, revision=revision).delete()
            except Exception as exc:
                code = str(exc) if isinstance(exc, ValueError) and str(exc).startswith('SEARCH_') else type(exc).__name__
                QuestionSearchDirty.objects.filter(pk=pk, revision=revision).update(attempts=attempts+1,
                    last_error_code=code[:64], next_retry_at=timezone.now()+datetime.timedelta(seconds=(30,60,120,300,900)[min(attempts,4)]))
                failed += 1
    quarantine = QuestionSearchDirty.objects.filter(attempts__gte=5).count()
    oldest = QuestionSearchDirty.objects.order_by('enqueued_at').values_list('enqueued_at', flat=True).first()
    return {'completed': completed, 'failed': failed, 'locked': False, 'quarantined': quarantine,
            'oldest_seconds': int((timezone.now()-oldest).total_seconds()) if oldest else 0}


def verify_workspace(workspace, enqueue_mismatch=False):
    start_state, _ = QuestionSearchState.objects.get_or_create(workspace=workspace)
    start_generation = start_state.generation
    mismatches, refs, maximum = [], Counter(), 0
    source=Question.objects.filter(document__workspace=workspace).select_related(
        'document','topic','similarity_topic','source_anchor','exam_type').iterator(chunk_size=500)
    while batch:=list(islice(source,500)):
        projected=QuestionSearchDocument.objects.filter(pk__in=[question.pk for question in batch]).only(
            'question_id','workspace','schema_version','source_hash','lexeme_refs').in_bulk()
        for question in batch:
            values, _ = projection(question)
            maximum = max(maximum, len(values['terms']))
            row = projected.get(question.pk)
            if not row or row.workspace != workspace or row.schema_version != SCHEMA_VERSION or row.source_hash != values['source_hash']:
                mismatches.append(question.pk)
            if row:
                refs.update(refs_counter(row.lexeme_refs))
    actual = { (l.workspace,l.kind,l.term,l.target_key): l.document_frequency for l in QuestionSearchLexeme.objects.filter(workspace=workspace) }
    lexemes_ok = dict(refs) == actual
    if enqueue_mismatch and mismatches:
        enqueue(mismatches)
    dirty = QuestionSearchDirty.objects.filter(question__document__workspace=workspace).count()
    state, _ = QuestionSearchState.objects.get_or_create(workspace=workspace)
    valid = not mismatches and lexemes_ok and not dirty and not state.rebuilding
    if valid:
        promoted = QuestionSearchState.objects.filter(pk=state.pk, generation=start_generation,rebuilding=False).update(ready=True, schema_version=SCHEMA_VERSION,
            aliases_hash=aliases_hash(), manifest_hash=manifest_data()[1], build_source_version=source_version(), last_completed_at=timezone.now())
        valid = bool(promoted)
    elif not state.ready:
        QuestionSearchState.objects.filter(pk=state.pk).update(ready=False)
    return {'workspace': workspace, 'valid': valid, 'mismatch_ids': mismatches, 'lexemes_ok': lexemes_ok,
            'pending': dirty, 'maximum_terms': maximum}
