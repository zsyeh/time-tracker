"""Private, idempotent paper grading import; never creates global attempts/timers.

Paper items are the exam attempt. Global mastery remains independent; targeted
review_later flags and append-only notes expose weaknesses without overwriting it.
"""
import hashlib
import json
import uuid
from collections import Counter
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import DrillContentShare, ExamPaper, QuestionUserState, QuestionAttempt

SUBJECTS = ('电路原理', '模拟电子技术', '数字电子技术', '信号与系统', '通信原理')

@transaction.atomic
def import_grading(*, user, share_token, data, apply=False):
    share = DrillContentShare.objects.get(token_digest=DrillContentShare.digest(share_token), owner=user,
                                        workspace='ei', is_active=True, revoked_at__isnull=True)
    paper = ExamPaper.objects.select_for_update().get(pk=share.paper_id, user=user, blueprint__subject='ei')
    items = list(paper.items.select_related('section', 'question').order_by('position'))
    rows = data['items']
    if len(rows) != len(items) or {r['position'] for r in rows} != {i.position for i in items}:
        raise ValueError('Every paper item must be supplied exactly once.')
    if set(data['weaknesses']) != set(SUBJECTS) or not all(isinstance(v, str) for v in data['weaknesses'].values()):
        raise ValueError('Exactly five subject texts are required.')
    digest = hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    previous = paper.generation_options.get('grading', {})
    if previous.get('import_digest') == digest:
        return {'unchanged': True, 'paper_id': paper.pk, 'paper_uuid': str(paper.uuid), 'score': previous['score']}
    if previous:
        raise ValueError('Existing grading differs: review it explicitly before replacing it.')
    by_position = {r['position']: r for r in rows}
    courses = {name: {'subject': name, 'score': Decimal(0), 'maximum': Decimal(0)} for name in SUBJECTS}
    total = Decimal(0); counts = Counter(); review_count = 0
    report_items = []; changed_states = 0
    marker = f'[892批阅 {paper.uuid} {data["exam_date"]}]'
    for item in items:
        row = by_position[item.position]
        if str(item.question.uuid) != row['question_uuid']:
            raise ValueError(f'Question mapping mismatch at {item.position}')
        raw = Decimal(str(row['raw_score']))
        if not raw.is_finite() or not 0 <= raw <= 5 or row['status'] not in ('correct','incorrect','partial','incomplete'):
            raise ValueError('Invalid grade.')
        earned = (item.score * raw / 5).quantize(Decimal('.01'))
        course = next((name for name in SUBJECTS if item.section.title.startswith(name)), None)
        if course is None: raise ValueError('Unknown course.')
        total += earned; courses[course]['score'] += earned; courses[course]['maximum'] += item.score
        counts[row['status']] += 1
        report_items.append({**row, 'subject': course, 'earned': float(earned), 'maximum': float(item.score),
                             'question_id': item.question_id, 'item_id': item.pk})
        if apply:
            # Import scores can be partial even on fill blanks; UI self-scoring rules stay unchanged.
            item.self_score = earned
            item.result = 'correct' if row['status']=='correct' else ('incorrect' if row['status']=='incorrect' else 'review')
            if item.user_answer and item.user_answer != row['user_answer']:
                report_items[-1]['previous_user_answer'] = item.user_answer
            else: item.user_answer = row['user_answer']
            note = f'{marker}\n{row["note"]}'
            if marker not in item.self_note:
                item.self_note = (item.self_note.rstrip()+'\n\n'+note).strip()
            item.submitted_at = timezone.now()  # import time; not an invented examination timestamp
            item.save(update_fields=['self_score','result','user_answer','self_note','submitted_at'])
        if apply and row.get('confirm_mastered'):
            if row['status'] != 'correct': raise ValueError('Explicit mastery requires correct status.')
            key = uuid.uuid5(uuid.NAMESPACE_URL, f'exam-grading:{paper.uuid}:{item.position}:mastery')
            QuestionAttempt.objects.get_or_create(submission_key=key, defaults={
                'user': user, 'question': item.question, 'result':'correct', 'outcome':'correct',
                'judgement_source':'self', 'correction_note':row['note'],
            })
        if row['status'] != 'correct':
            review_count += 1
            if apply:
                state, _ = QuestionUserState.objects.select_for_update().get_or_create(user=user, question=item.question)
                note = f'{marker}\n{row["priority"]} · {row["note"]}'
                if marker not in state.note:
                    state.note = (state.note.rstrip()+'\n\n'+note).strip()
                state.review_later = True
                state.version += 1
                state.save(update_fields=['note','review_later','version','updated_at']); changed_states += 1
    maximum = sum(i.score for i in items)
    grading = {**{k:v for k,v in data.items() if k!='items'}, 'schema_version':1,
               'import_digest':digest,'imported_at':timezone.now().isoformat(), 'official':False,
               'score':float(total),'maximum':float(maximum),'counts':dict(counts),'items':report_items,
               'subjects':[{**c,'score':float(c['score']),'maximum':float(c['maximum'])} for c in courses.values()]}
    if apply:
        paper.generation_options = {**paper.generation_options,'grading':grading}
        paper.status = 'completed'; paper.completed_at = timezone.now()
        paper.save(update_fields=['generation_options','status','completed_at'])
    return {'unchanged':False,'paper_id':paper.pk,'paper_uuid':str(paper.uuid),'score':float(total),
            'counts':dict(counts),'review_flags':review_count,'states_updated':changed_states,
            'explicit_mastery_records':sum(bool(r.get('confirm_mastered')) for r in rows),'timing_sessions_created':0,'applied':apply,'subjects':grading['subjects']}
