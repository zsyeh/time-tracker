"""Reviewed, virtual circuit collection. Never copy questions or user progress."""
from functools import lru_cache
import json
from pathlib import Path

from django.db.models import Exists, OuterRef, Q, Subquery
from django.http import Http404

from .models import QuestionAsset, QuestionAttempt, QuestionErratum

CODE = 'circuit_selected'


@lru_cache(maxsize=1)
def manifest():
    data = json.loads((Path(__file__).parent / 'data/circuit_selected_v1.json').read_text())
    assert data['schema_version'] == 1
    assert len({q['uuid'] for q in data['questions']}) == len(data['questions'])
    return data


@lru_cache(maxsize=1)
def review_manifest():
    return json.loads((Path(__file__).parent / 'data/circuit_selected_review_v1.json').read_text())


def collection_records(params, data=None):
    data = manifest() if data is None else data
    rows = data['questions']
    bucket = params.get('bucket', '')
    tier = params.get('tier', '')
    kind = params.get('kind', '')
    if bucket and bucket not in {b['key'] for b in data['buckets']}:
        raise Http404('Unknown circuit bucket')
    if tier and tier not in {'core', 'advanced', 'foundation', 'cross'}:
        raise Http404('Unknown practice tier')
    if kind and kind not in set(data.get('kinds', ['concept', 'calculation'])):
        raise Http404('Unknown exercise kind')
    return [r for r in rows if (not bucket or r['bucket'] == bucket)
            and (not tier or r['tier'] == tier) and (not kind or r['kind'] == kind)
            and (params.get('combined') != '1' or r.get(data.get('combination_key', 'combined_first_order_thevenin'), False))]


def material_annotations(queryset):
    return queryset.annotate(
        cs_prompt=Exists(QuestionAsset.objects.filter(question_id=OuterRef('pk'), asset_type='question_crop')),
        cs_answer=Exists(QuestionAsset.objects.filter(question_id=OuterRef('pk'), asset_type='answer_crop')),
        cs_erratum=Exists(QuestionErratum.objects.filter(question_id=OuterRef('pk'), status__in=['open', 'reviewing'])),
    )


def filter_collection(queryset, request, *, force=False, data=None, code=CODE):
    """Apply only when explicitly requested; retain all normal bank behaviour."""
    if not force and request.query_params.get('collection') != code:
        return queryset
    from .views import request_workspace
    if request_workspace(request) != 'ei':
        raise Http404
    rows = collection_records(request.query_params, data=data)
    # Check fingerprints as well as UUIDs: stale manifests cannot select a
    # reused ID or a different book/workspace. IDs are canonical, never clones.
    queryset = queryset.filter(document__workspace='ei', is_practiceable=True,
                              uuid__in=[r['uuid'] for r in rows],
                              fingerprint__in=[r['fingerprint'] for r in rows]).exclude(syllabus_scope='out_of_scope')
    if request.query_params.get('material') == 'ready':
        queryset = material_annotations(queryset).filter(cs_erratum=False).filter(
            Q(cs_prompt=True) | ~Q(prompt_text=''),
        ).filter(Q(cs_answer=True) | ~Q(answer_markdown=''))
    state = request.query_params.get('state', '')
    if state not in {'', 'unattempted', 'review', 'mastered'}:
        raise Http404('Unknown practice state')
    if state:
        latest = QuestionAttempt.objects.filter(user=request.user, question_id=OuterRef('pk')).order_by('-created_at', '-pk')
        queryset = queryset.annotate(cs_latest_result=Subquery(latest.values('result')[:1]))
        if state == 'mastered':
            queryset = queryset.filter(cs_latest_result__in=['done', 'correct'])
        elif state == 'review':
            queryset = queryset.filter(cs_latest_result='review')
        else:
            queryset = queryset.filter(Q(cs_latest_result__isnull=True) | Q(cs_latest_result='reset'))
    return queryset


def aggregate_progress(items):
    mastered = sum(q['state'] == 'mastered' for q in items)
    attempted = sum(q['state'] in {'mastered', 'review'} for q in items)
    return {'total': len(items), 'attempted': attempted, 'mastered': mastered,
            'unattempted': len(items) - attempted}
