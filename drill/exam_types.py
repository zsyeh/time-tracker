"""Final answer formats and audit metadata. Review status never gates reads."""
import hashlib
import json

from django.db.models import Case, CharField, F, Value, When
from django.db.models.functions import Coalesce
from rest_framework.exceptions import ValidationError

LEGACY = {'single_choice': 'choice', 'fill_blank': 'fill', 'solution': 'large'}
SMALL = ('choice', 'fill', 'judgment')
TYPES = (*SMALL, 'short_answer', 'large', 'unknown')
GROUPS = ('small', 'large', 'short_answer', 'unknown')


def with_exam_type(queryset):
    return queryset.annotate(final_question_type=Coalesce(
        F('exam_type__question_type'),
        Case(*[When(question_type=old, then=Value(new)) for old, new in LEGACY.items()],
             default=Value('unknown'), output_field=CharField()),
        output_field=CharField(),
    ))


def type_group(label):
    return 'small' if label in SMALL else label if label in GROUPS else 'unknown'


def filter_exam_type(queryset, params):
    queryset = with_exam_type(queryset)
    group = params.get('type_group', '')
    label = params.get('exam_type', '')
    if group and group not in GROUPS:
        raise ValidationError({'type_group': 'Use small, large, short_answer, or unknown.'})
    if label and label not in TYPES:
        raise ValidationError({'exam_type': 'Invalid final question type.'})
    if group:
        queryset = queryset.filter(final_question_type__in=SMALL if group == 'small' else [group])
    if label:
        queryset = queryset.filter(final_question_type=label)
    return queryset


def type_statistics(items):
    stats = {key: {'total': 0, 'attempted': 0, 'mastered': 0, 'review': 0} for key in GROUPS}
    for item in items:
        group = type_group(item.get('question_type') or item.get('final_question_type', 'unknown'))
        row = stats[group]
        state = item.get('state') or {'done': 'mastered', 'correct': 'mastered', 'review': 'review'}.get(item.get('latest_result'), 'unattempted')
        row['total'] += 1
        row['attempted'] += state != 'unattempted'
        row['mastered'] += state == 'mastered'
        row['review'] += state == 'review'
    return stats


def queryset_type_statistics(queryset, user):
    """Count formats inside the current scope, before the format selector."""
    from django.db.models import OuterRef, Subquery
    from .models import QuestionAttempt
    latest = QuestionAttempt.objects.filter(user=user, question_id=OuterRef('pk')).order_by('-created_at', '-pk')
    items = with_exam_type(queryset).annotate(
        latest_result=Subquery(latest.values('result')[:1]),
    ).order_by().values('pk', 'final_question_type', 'latest_result').distinct()
    return type_statistics(items)


def audit_reasons(question, record):
    reasons = []
    if record['question_type'] == 'unknown':
        reasons.append('unknown_type')
    old = LEGACY.get(question.question_type)
    if old and old != record['question_type']:
        reasons.append('legacy_type_conflict')
    if not (question.prompt_text or question.latex_text):
        reasons.append('no_text_prompt')
    # Older caches retained the combined flag, not the raw model flag.
    if record.get('review_required') and not reasons:
        reasons.append('record_requested_review')
    return list(dict.fromkeys([*reasons, *record.get('review_reasons', [])]))


def digest_for_question(question):
    assets = (question.assets.all() if 'assets' in getattr(question, '_prefetched_objects_cache', {})
              else question.assets.only('pk', 'position', 'asset_type', 'sha256'))
    assets = sorted(assets, key=lambda a: (a.position, a.pk))
    evidence={
        'question_id':question.pk, 'source_system':question.document.workspace,
        'source_label':question.source_label or '', 'display_label':question.display_label or '',
        'prompt_text':question.prompt_text or '', 'latex_text':question.latex_text or '',
        'document_title':question.document.title or '',
        'topic_title':(question.similarity_topic.display_title or question.similarity_topic.title) if question.similarity_topic else '',
        'legacy_type':question.question_type or '', 'legacy_source':question.question_type_source or '',
        'legacy_human_verified':bool(question.question_type_human_verified),
        'content_mode':question.content_mode or '',
        'question_asset_count':sum(a.asset_type=='question_crop' for a in assets),
        'question_asset_hashes':[a.sha256 for a in assets if a.asset_type=='question_crop'],
    }
    raw=json.dumps({'version':'exam-form-v1','evidence':evidence},ensure_ascii=False,sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()
