"""Final answer formats and audit metadata. Review status never gates reads."""
from collections import defaultdict

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
