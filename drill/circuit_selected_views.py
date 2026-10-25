from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import Http404

from .circuit_selected import aggregate_progress, filter_collection, manifest, material_annotations, review_manifest
from .models import Question
from .views import question_progress, request_workspace
from drill_sources.models import SourceQuestionAnchor


class CircuitSelectedView(APIView):
    """A virtual book: existing questions, original images, original progress."""
    def selection_manifest(self):
        return manifest()

    def selection_review(self):
        return review_manifest()

    def selection_queryset(self, queryset, request):
        return filter_collection(queryset, request, force=True)

    def get(self, request):
        if request_workspace(request) != 'ei':
            raise Http404
        data = self.selection_manifest()
        records = {q['uuid']: q for q in data['questions']}
        questions = question_progress(material_annotations(self.selection_queryset(
            Question.objects.all(), request,
        )), request.user).select_related('document').order_by('document_id', 'question_order', 'pk')
        indexed = set(SourceQuestionAnchor.objects.filter(
            question__uuid__in=records,
        ).values_list('question__uuid', flat=True))
        items = []
        for q in questions:
            row = records[str(q.uuid)]
            if q.fingerprint != row['fingerprint']:
                continue
            ready = bool((q.cs_prompt or q.prompt_text) and (q.cs_answer or q.answer_markdown) and not q.cs_erratum)
            items.append({
                'uuid': str(q.uuid), 'label': q.display_label or q.source_label,
                'document_id': q.document_id, 'book': q.document.display_title or q.document.title,
                'bucket': row['bucket'], 'tier': row['tier'], 'kind': row['kind'],
                'tags': row['tags'], 'reason': row['reason'],
                'combined': row.get(data.get('combination_key', 'combined_first_order_thevenin'), False),
                'state': 'mastered' if q.latest_result in {'done', 'correct'} else 'review' if q.latest_result == 'review' else 'unattempted',
                'attempt_count': q.attempt_count, 'ready': ready,
                'question_mode': '独立裁图' if q.cs_prompt else '原页定位' if q.uuid in indexed else '文字题',
                'answer_mode': '本题答案' if q.cs_answer or q.answer_markdown else '整卷答案待核对',
                'has_open_erratum': q.cs_erratum,
                'scope_note': '原真题书部分超纲，未逐小问重新核定' if q.source_category == 'past_exam' else '',
            })
        groups = []
        for bucket in data['buckets']:
            rows = [q for q in items if q['bucket'] == bucket['key']]
            groups.append({**bucket, 'questions': rows, 'progress': aggregate_progress(rows)})
        review = self.selection_review()['records']
        return Response({
            'title': data['title'], 'basis': data['basis'], 'groups': groups,
            'progress': aggregate_progress(items), 'ready_count': sum(q['ready'] for q in items),
            'inventory_count': data['inventory_count'], 'selected_count': len(records),
            'review_count': sum(q['status'] == 'review' for q in review),
            'excluded_count': sum(q['status'] == 'excluded' for q in review),
            'review_items': [q for q in review if q['status'] == 'review'],
        })
