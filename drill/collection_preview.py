"""Read-only, owner-scoped collection projection over existing question lists.

Every request reads one snapshot: ordered thin identities, its version, and at
most 50 hydrated previews. No persisted collection, duplicated learning state,
cross-user cache, answer text or image binary is introduced.
"""
import datetime
import hashlib
import json
import uuid
from dataclasses import dataclass

from django.db.models import Count, F, Max, OuterRef, Subquery, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .exam_types import filter_exam_type
from .models import (
    ExamPaper, ExamPaperItem, Question, QuestionAsset, QuestionAttempt,
    QuestionAttemptError, QuestionErratum, QuestionReviewPlan, QuestionRevision,
    QuestionRevisionAsset, QuestionSearchState, QuestionUserState,
)
from .search.service import order_question_scope, question_list_scope, read_snapshot


PAGE_SIZE = 50
SOURCES = {'practice', 'heatmap', 'attempts', 'notes', 'favorite', 'review_later',
           'selected', 'diagnostics', 'paper', 'errata', 'navigation'}
# Controls change the requested window, never the collection identity. Unknown
# filters remain bound into the version too, so a context cannot be reused under
# a different URL silently. Only existing adapters define filter semantics.
WINDOW_KEYS = {'offset', 'limit', 'collection_version', 'locate_entry', 'locate_uuid',
               'fallback_index', 'page', 'questions_page', 'notes_page'}


@dataclass(frozen=True)
class Entry:
    entry_id: str
    question_id: int
    question_uuid: str
    row_id: int
    revision_id: int | None = None


def _integer(params, key, default=None, minimum=0):
    raw = params.get(key)
    if raw in (None, ''):
        return default
    try:
        value = int(raw)
        if value < minimum or value > 2**63 - 1:
            raise ValueError
        return value
    except (ValueError, TypeError):
        raise ValidationError({key: f'Use an integer greater than or equal to {minimum}.'})


def _uuid(raw, key):
    try:
        return str(uuid.UUID(str(raw)))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError({key: 'Use a question or paper UUID.'})


def _question_entries(queryset):
    return [Entry(f'question:{value}', pk, str(value), pk)
            for pk, value in queryset.values_list('pk', 'uuid')]


def _related_entries(queryset, prefix, *, revision=False):
    fields = ['pk', 'question_id', 'question__uuid']
    if revision:
        fields.append('question_revision_id')
    return [Entry(f'{prefix}:{row[0]}', row[1], str(row[2]), row[0], row[3] if revision else None)
            for row in queryset.values_list(*fields)]


def _heatmap_entries(request):
    from .views import request_workspace, workspace_questions
    from .selected_collections import filter_collection
    params = request.query_params
    scope, mode, collection = params.get('scope', 'past_exam'), params.get('mode', 'questions'), params.get('collection', '')
    if scope not in {'all', 'past_exam', 'mock_exam'} or mode not in {'questions', 'topics'}:
        raise ValidationError({'detail': 'Invalid heatmap scope or mode.'})
    if collection not in {'', 'selected', 'core_selected'}:
        raise ValidationError({'collection': 'Use selected, core_selected, or omit.'})
    if collection == 'selected' and request_workspace(request) != 'drill':
        raise Http404
    if collection == 'core_selected' and request_workspace(request) != 'ei':
        raise Http404
    queryset = workspace_questions(request).filter(is_practiceable=True)
    if scope != 'all':
        queryset = queryset.filter(source_category=scope)
    if collection:
        queryset = filter_collection(queryset, request)
    # Topic cards open a question subset; the matrix's quick-state highlighting
    # deliberately does not remove other cells or reorder their positions.
    for name, field in [('document', 'document_id'), ('topic', 'similarity_topic_id')]:
        if params.get(name):
            queryset = queryset.filter(**{field: _integer(params, name, minimum=1)})
    queryset = filter_exam_type(queryset, params).order_by('document_id', 'question_order', 'pk')
    return _question_entries(queryset)


def _selected_entries(request):
    from .views import request_workspace, workspace_questions
    from . import circuit_selected, signal_selected, analog_selected, digital_selected, communication_selected, core_selected
    from .selected_collections import filter_collection
    modules = {module.CODE: module for module in (circuit_selected, signal_selected,
        analog_selected, digital_selected, communication_selected, core_selected)}
    code = request.query_params.get('collection', '')
    if code == 'selected':
        if request_workspace(request) != 'drill':
            raise Http404
        return _question_entries(filter_exam_type(filter_collection(workspace_questions(request), request),
            request.query_params).order_by('document_id', 'question_order', 'pk'))
    if code not in modules:
        raise ValidationError({'collection': 'Choose an existing selected collection.'})
    if request_workspace(request) != 'ei':
        raise Http404
    module = modules[code]
    data = module.manifest()
    records = {row['uuid']: row for row in data['questions']}
    bucket_order = {bucket['key']: index for index, bucket in enumerate(data['buckets'])}
    queryset = filter_exam_type(module.filter_collection(workspace_questions(request), request, force=True),
        request.query_params).order_by('document_id', 'question_order', 'pk')
    # Exactly the selected page's visual order: manifest bucket order, then
    # existing source order within each bucket. Match fingerprint as that view does.
    rows = [(bucket_order[records[str(value)]['bucket']], Entry(f'question:{value}', pk, str(value), pk))
            for pk, value, fingerprint in queryset.values_list('pk', 'uuid', 'fingerprint')
            if str(value) in records and records[str(value)]['fingerprint'] == fingerprint
            and records[str(value)]['bucket'] in bucket_order]
    rows.sort(key=lambda pair: pair[0])
    return [entry for _bucket, entry in rows]


def _navigation_entries(request, workspace):
    """One finite pass through the existing Next button order, without writes."""
    from urllib.parse import parse_qs, urlsplit
    from .views import (workspace_questions, navigation_queryset,
                        insight_filtered_querysets, SELECTED_COLLECTIONS, filter_collection)
    params = request.query_params
    mode = params.get('navigation_mode', 'sequential')
    if mode not in {'sequential', 'review', 'overdue', 'unattempted'}:
        raise ValidationError({'navigation_mode': 'Unknown next-question mode.'})
    anchor = get_object_or_404(Question.objects.only('pk', 'uuid', 'document_id', 'question_order',
        'source_category'), uuid=_uuid(params.get('navigation_anchor'), 'navigation_anchor'),
        document__workspace=workspace)
    origin = params.get('navigation_from', '')
    ordered_ids = None
    if origin == 'collection' and params.get('collection') in {'favorite', 'review_later'}:
        flag = 'is_favorite' if params['collection'] == 'favorite' else 'review_later'
        ordered_ids = list(QuestionUserState.objects.filter(user=request.user,
            question__is_practiceable=True, question__document__workspace=workspace,
            **{flag: True}).order_by('-updated_at', '-pk').values_list('question_id', flat=True))
    elif origin == 'insight':
        path = urlsplit(params.get('insight_return', ''))
        if path.path == '/insight' and not path.netloc and not path.scheme:
            filters = {key: values[-1] for key, values in parse_qs(path.query).items()}
            filtered = insight_filtered_querysets(request, filters)
            if not isinstance(filtered, Response) and params.get('insight_list') in {'attempts', 'notes'}:
                ordered_ids = list(dict.fromkeys(filtered[0 if params['insight_list'] == 'attempts' else 1]
                    .values_list('question_id', flat=True)))
    if ordered_ids is not None:
        queryset = workspace_questions(request).filter(pk__in=ordered_ids, is_practiceable=True)
    elif mode == 'unattempted':
        queryset = navigation_queryset(anchor, request)
    else:
        queryset = workspace_questions(request).filter(is_practiceable=True)
        queryset = (filter_collection(queryset, request) if params.get('collection') in SELECTED_COLLECTIONS
                    else queryset.filter(source_category=anchor.source_category))
        queryset = filter_exam_type(queryset, params)
    latest = QuestionAttempt.objects.filter(user=request.user, question_id=OuterRef('pk')).order_by('-created_at', '-pk')
    rows = list(queryset.annotate(_result=Subquery(latest.values('result')[:1]),
        _at=Subquery(latest.values('created_at')[:1])).order_by('document_id', 'question_order', 'pk')
        .values_list('pk', 'uuid', 'document_id', 'question_order', '_result', '_at'))
    cutoff = timezone.now() - datetime.timedelta(days=5)
    def eligible(row):
        if row[0] == anchor.pk or mode == 'sequential': return True
        if mode == 'unattempted': return row[4] in (None, 'reset')
        return row[4] == 'review' and row[5] is not None and ((row[5] <= cutoff) if mode == 'overdue' else (row[5] > cutoff))
    if ordered_ids is not None:
        by_id = {row[0]: row for row in rows}
        rows = [by_id[pk] for pk in ordered_ids if pk in by_id]
        if anchor.pk not in by_id:
            rows = []  # Legacy list navigation has no next when the current item left the list.
        rows = [row for row in rows if eligible(row)]
        if mode == 'unattempted' and rows:
            index = next(i for i, row in enumerate(rows) if row[0] == anchor.pk)
            rows = rows[index:] + rows[:index]
    else:
        key = (anchor.document_id, anchor.question_order, anchor.pk)
        selected_missing = (mode == 'unattempted' and params.get('collection') in SELECTED_COLLECTIONS
                            and not any(row[0] == anchor.pk for row in rows))
        rows = [row for row in rows if row[0] != anchor.pk and eligible(row)]
        if not selected_missing:
            rows = ([row for row in rows if (row[2], row[3], row[0]) > key]
                    + [row for row in rows if (row[2], row[3], row[0]) <= key])
        rows.insert(0, (anchor.pk, anchor.uuid, anchor.document_id, anchor.question_order, None, None))
    if not rows:
        rows = [(anchor.pk, anchor.uuid, anchor.document_id, anchor.question_order, None, None)]
    return [Entry(f'question:{row[1]}', row[0], str(row[1]), row[0]) for row in rows]


def _entries(request, source, workspace):
    """Reuse source membership/order; never turn history rows into unique UUIDs."""
    params = request.query_params
    search_version = None
    if source == 'navigation':
        entries = _navigation_entries(request, workspace)
    elif source == 'practice':
        queryset, plan, _state, search_version, hybrid, sort = question_list_scope(request)
        entries = _question_entries(order_question_scope(filter_exam_type(queryset, params), plan, hybrid, sort))
    elif source == 'heatmap':
        entries = _heatmap_entries(request)
    elif source == 'selected':
        entries = _selected_entries(request)
    elif source in {'attempts', 'notes'}:
        from .views import insight_filtered_querysets
        for name in ('document', 'topic'):
            if params.get(name):
                _integer(params, name, minimum=1)
        filtered = insight_filtered_querysets(request, params)
        if isinstance(filtered, Response):
            raise ValidationError(filtered.data)
        entries = _related_entries(filtered[0 if source == 'attempts' else 1], 'attempt' if source == 'attempts' else 'note')
    elif source in {'favorite', 'review_later'}:
        flag = 'is_favorite' if source == 'favorite' else 'review_later'
        entries = _related_entries(QuestionUserState.objects.filter(user=request.user,
            question__is_practiceable=True, question__document__workspace=workspace,
            **{flag: True}).order_by('-updated_at', '-pk'), source)
    elif source == 'diagnostics':
        queryset = QuestionReviewPlan.objects.filter(user=request.user, question__document__workspace=workspace)
        codes = {value for value in params.get('error', '').split(',') if value}
        if not codes <= {value for value, _label in QuestionAttemptError.ERROR_CHOICES}:
            raise ValidationError({'error': 'Unknown diagnosis code.'})
        if codes:
            queryset = queryset.filter(question_id__in=QuestionAttemptError.objects.filter(
                attempt__user=request.user, attempt__question__document__workspace=workspace,
                code__in=codes).values('attempt__question_id'))
        queue = params.get('queue', '')
        if queue == 'due':
            queryset = queryset.filter(status='active', next_review_at__lte=timezone.now())
        elif queue == 'active':
            queryset = queryset.filter(status='active')
        elif queue:
            raise ValidationError({'queue': 'Use due or active.'})
        entries = _related_entries(queryset.order_by('next_review_at', 'pk'), 'diagnostic')
    elif source == 'paper':
        paper = get_object_or_404(ExamPaper, user=request.user, uuid=_uuid(params.get('paper'), 'paper'))
        # A paper is owner-private. A mixed/corrupt workspace cannot make another
        # workspace's items visible; revision and current question must agree.
        queryset = ExamPaperItem.objects.filter(paper=paper, question__document__workspace=workspace,
            question_revision__question_id=F('question_id')).order_by('position', 'pk')
        if not queryset.exists() and paper.items.exists():
            raise Http404
        entries = _related_entries(queryset, 'paper', revision=True)
    else:  # Errata are already workspace-public, unlike attempts and saved notes.
        queryset = QuestionErratum.objects.filter(question__document__workspace=workspace)
        if params.get('question'):
            queryset = queryset.filter(question__uuid=_uuid(params['question'], 'question'))
        entries = _related_entries(queryset.order_by('-created_at', '-pk'), 'erratum')
    if search_version is None:
        state = QuestionSearchState.objects.filter(workspace=workspace).values(
            'schema_version', 'aliases_hash', 'generation').first()
        search_version = f"{state['schema_version']}:{state['aliases_hash'][:16]}:{state['generation']}" if state else 'legacy:0'
    return entries, search_version


def _version(request, source, workspace, entries, search_version):
    params = request.query_params
    scope = {key: params.getlist(key) for key in sorted(params) if key not in WINDOW_KEYS}
    # A cached second batch must also expire when another device changes a
    # member's mastery/favorite/note without changing collection membership.
    # Fixed owner/workspace aggregates avoid per-question queries or a new
    # counter table. Counts catch deletes of non-max rows; timestamps and the
    # existing state version sum catch updates (including same-timestamp edits).
    owner_scope = {'user': request.user, 'question__document__workspace': workspace}
    learning_revision = [
        QuestionUserState.objects.filter(**owner_scope).aggregate(
            count=Count('pk'), updated=Max('updated_at'), versions=Sum('version')),
        QuestionAttempt.objects.filter(**owner_scope).aggregate(
            count=Count('pk'), latest=Max('pk'), created=Max('created_at')),
        QuestionReviewPlan.objects.filter(**owner_scope).aggregate(
            count=Count('pk'), updated=Max('updated_at')),
    ]
    payload = [1, request.user.pk, workspace, source, scope, search_version, learning_revision,
               [(row.entry_id, row.question_uuid, row.revision_id) for row in entries]]
    return hashlib.sha256(json.dumps(payload, default=str, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def _asset(row, *, position=None):
    return {'id': row['id'], 'url': f"/api/drill/assets/{row['id']}/?v={row['sha256'][:16]}",
            'width': row['width'], 'height': row['height'],
            'position': row['position'] if position is None else position}


def _state(result):
    return 'mastered' if result in {'done', 'correct'} else 'review' if result == 'review' else 'unattempted'


def _hydrate(request, source, workspace, entries, offset):
    if not entries:
        return []
    ids = {row.question_id for row in entries}
    latest = QuestionAttempt.objects.filter(user=request.user, question_id=OuterRef('pk')).order_by('-created_at', '-pk')
    if source == 'notes':
        # Insight's existing note column reports the latest completed attempt,
        # whereas Practice reports the latest state change (including reset).
        latest = latest.filter(result__in=('done', 'correct', 'review'))
    # Explicit metadata-only fields. Neither current nor revision answers are
    # read, and image_data is excluded from every asset query below.
    questions = {row['id']: row for row in Question.objects.filter(pk__in=ids,
        document__workspace=workspace).annotate(_latest=Subquery(latest.values('result')[:1]),
        _latest_at=Subquery(latest.values('created_at')[:1])).values(
        'id', 'uuid', 'source_label', 'display_label', 'prompt_text', 'latex_text',
        'document__title', 'document__display_title', 'similarity_topic__title',
        'similarity_topic__display_title', 'topic__title', 'topic__display_title', '_latest', '_latest_at')}
    state_fields = ['question_id', 'is_favorite', 'review_later']
    if source in {'attempts', 'notes'}:
        state_fields.append('note')
    states = {row['question_id']: row for row in QuestionUserState.objects.filter(
        user=request.user, question_id__in=ids).values(*state_fields)}
    assets = {pk: [] for pk in ids}
    for row in QuestionAsset.objects.filter(question_id__in=ids, asset_type='question_crop').order_by(
            'position', 'source_id', 'pk').values('id', 'question_id', 'sha256', 'width', 'height', 'position'):
        assets[row['question_id']].append(_asset(row))
    from drill_sources.models import SourceQuestionAnchor
    source_pages = set()
    for row in SourceQuestionAnchor.objects.filter(question_id__in=[pk for pk in ids if not assets[pk]],
            source_question__document__workspace=workspace, asset__question_id=F('source_question_id'),
            asset__asset_type='question_crop', source_question__document_id=F('question__document_id')).values(
            'question_id', 'asset__id', 'asset__sha256', 'asset__width', 'asset__height', 'asset__position'):
        assets[row['question_id']].append(_asset({key.removeprefix('asset__'): value
            for key, value in row.items() if key.startswith('asset__')}))
        source_pages.add(row['question_id'])
    attempts = {}
    if source == 'attempts':
        attempts = {row['id']: row for row in QuestionAttempt.objects.filter(user=request.user,
            pk__in=[entry.row_id for entry in entries]).values('id', 'result', 'created_at')}
    revisions, revision_assets, revision_source_pages = {}, {}, set()
    if source == 'paper':
        revision_ids = {entry.revision_id for entry in entries}
        revisions = {row['id']: row for row in QuestionRevision.objects.filter(pk__in=revision_ids).values(
            'id', 'question_id', 'document_title', 'topic_title', 'source_label', 'display_label', 'prompt_text', 'latex_text')}
        for row in QuestionRevisionAsset.objects.filter(revision_id__in=revision_ids, asset_type='question_crop',
                asset__question__document__workspace=workspace).order_by('revision_id', 'position', 'pk').values(
                'revision_id', 'position', 'asset__id', 'asset__sha256', 'asset__width', 'asset__height', 'asset__question_id'):
            value = {key.removeprefix('asset__'): item for key, item in row.items() if key.startswith('asset__')}
            revision_assets.setdefault(row['revision_id'], []).append(_asset(value, position=row['position']))
            if row['asset__question_id'] != revisions[row['revision_id']]['question_id']:
                revision_source_pages.add(row['revision_id'])
    results = []
    for index, entry in enumerate(entries, offset):
        question = questions[entry.question_id]
        state = states.get(entry.question_id, {})
        item = {'entry_id': entry.entry_id, 'index': index, 'question_uuid': entry.question_uuid,
                'label': question['display_label'] or question['source_label'],
                'document': question['document__display_title'] or question['document__title'],
                'topic': question['similarity_topic__display_title'] or question['similarity_topic__title']
                         or question['topic__display_title'] or question['topic__title'] or '',
                'state': _state(question['_latest']),
                'review_overdue': question['_latest'] == 'review' and question['_latest_at'] is not None
                    and question['_latest_at'] <= timezone.now() - datetime.timedelta(days=5),
                'is_favorite': state.get('is_favorite', False),
                'review_later': state.get('review_later', False),
                'preview': {'question_markdown': question['prompt_text'] or question['latex_text'],
                            'assets': assets[entry.question_id], 'source_page': entry.question_id in source_pages}}
        if source == 'attempts':
            item['attempt'] = attempts[entry.row_id]
            item['attempt']['created_at'] = item['attempt']['created_at'].isoformat()
            item['state'] = _state(item['attempt']['result'])
        if source in {'attempts', 'notes'}:
            item['note_excerpt'] = (state.get('note') or '')[:160]
        if source == 'paper':
            revision = revisions[entry.revision_id]
            item.update(label=revision['display_label'] or revision['source_label'],
                        document=revision['document_title'], topic=revision['topic_title'])
            item['preview'] = {'question_markdown': revision['prompt_text'] or revision['latex_text'],
                               'assets': revision_assets.get(entry.revision_id, []),
                               'source_page': entry.revision_id in revision_source_pages}
        results.append(item)
    return results


def _neighbor(entries, index):
    if index is None or not 0 <= index < len(entries):
        return None
    entry = entries[index]
    return {'entry_id': entry.entry_id, 'question_uuid': entry.question_uuid, 'index': index}


class CollectionPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        patch_vary_headers(response, ['Cookie'])
        return response

    def get(self, request):
        from .views import request_workspace
        params = request.query_params
        source = params.get('source', 'practice')
        if source not in SOURCES:
            raise ValidationError({'source': 'Unknown collection source.'})
        if _integer(params, 'limit', PAGE_SIZE, minimum=1) != PAGE_SIZE:
            raise ValidationError({'limit': 'Preview batches contain 50 entries.'})
        offset = _integer(params, 'offset', 0)
        fallback = _integer(params, 'fallback_index')
        locate_entry = params.get('locate_entry', '')
        if len(locate_entry) > 100:
            raise ValidationError({'locate_entry': 'Entry identity is too long.'})
        locate_uuid = _uuid(params['locate_uuid'], 'locate_uuid') if params.get('locate_uuid') else ''
        workspace = request_workspace(request)
        with read_snapshot():
            entries, search_version = _entries(request, source, workspace)
            version = _version(request, source, workspace, entries, search_version)
            if params.get('collection_version') and params['collection_version'] != version:
                return Response({'code': 'COLLECTION_CHANGED', 'collection_version': version,
                    'detail': 'The collection changed. Refresh and locate the selected entry again.'}, status=409)
            located_index = None
            notice = None
            if locate_entry:
                located_index = next((index for index, entry in enumerate(entries) if entry.entry_id == locate_entry), None)
            elif locate_uuid:
                located_index = next((index for index, entry in enumerate(entries) if entry.question_uuid == locate_uuid), None)
            if (locate_entry or locate_uuid) and located_index is None:
                notice = 'ENTRY_NOT_FOUND'
                if fallback is not None and entries:
                    located_index = min(fallback, len(entries) - 1)
                    notice = 'ENTRY_REMOVED_USING_NEAREST'
            if located_index is not None:
                offset = (located_index // PAGE_SIZE) * PAGE_SIZE
            elif offset >= len(entries):
                offset = ((len(entries) - 1) // PAGE_SIZE) * PAGE_SIZE if entries else 0
            payload = {'count': len(entries), 'offset': offset, 'limit': PAGE_SIZE,
                       'has_more': offset + PAGE_SIZE < len(entries), 'collection_version': version,
                       'located': _neighbor(entries, located_index),
                       'previous_entry': _neighbor(entries, located_index - 1) if located_index is not None else None,
                       'next_entry': _neighbor(entries, located_index + 1) if located_index is not None else None,
                       'results': _hydrate(request, source, workspace, entries[offset:offset + PAGE_SIZE], offset)}
            if notice:
                payload['notice'] = notice
            elif source == 'paper':
                payload['notice'] = 'PAPER_REVISION_PREVIEW_CANONICAL_PRACTICE_IS_SEPARATE'
            return Response(payload)
