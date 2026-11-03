import re

from django.db import transaction
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .ei_selected_pdf_pages import COURSE_LABELS, pdf_page_catalog, pdf_page_rows
from .diagnostics import create_diagnosed_attempt
from .models import Question, QuestionUserState
from .notes import MAX_QUESTION_NOTE_LENGTH, merge_note_values
from .serializers import QuestionAttemptCreateSerializer
from .views import request_workspace


MAX_PAGE = 5000
MAX_SELECTED_PAGES = 500


def parse_page_expression(value):
    """Parse comma/space separated pages and inclusive ranges."""
    text = str(value or '').strip()
    if not text:
        return set()
    pages = set()
    normalized = text.replace('，', ',').replace('；', ',').replace(';', ',')
    for token in filter(None, re.split(r'[\s,]+', normalized)):
        match = re.fullmatch(r'(\d+)(?:\s*[-–—~]\s*(\d+))?', token)
        if not match:
            raise ValueError(f'无法识别页码“{token}”')
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start < 1 or end < 1 or start > MAX_PAGE or end > MAX_PAGE:
            raise ValueError(f'页码必须在 1–{MAX_PAGE} 之间')
        if end < start:
            raise ValueError(f'页码范围“{token}”顺序错误')
        if end - start + 1 > MAX_SELECTED_PAGES:
            raise ValueError('单个页码范围过大')
        pages.update(range(start, end + 1))
        if len(pages) > MAX_SELECTED_PAGES:
            raise ValueError(f'一次最多输入 {MAX_SELECTED_PAGES} 页')
    return pages


class PdfPageStatusView(APIView):
    """Preview and append attempts for EI questions selected by source PDF pages."""

    def _require_ei(self, request):
        if request_workspace(request) != 'ei':
            raise Http404

    def get(self, request):
        self._require_ei(request)
        return Response({
            'courses': pdf_page_catalog(),
            'results': [
                {'value': 'correct', 'label': 'Mastered'},
                {'value': 'review', 'label': 'Need to review'},
            ],
        })

    def post(self, request):
        self._require_ei(request)
        course = str(request.data.get('course') or '')
        result = str(request.data.get('result') or '')
        action = str(request.data.get('action') or 'preview')
        if course not in COURSE_LABELS:
            return Response({'detail': '请选择正确的科目'}, status=status.HTTP_400_BAD_REQUEST)
        if result not in {'correct', 'review'}:
            return Response({'detail': '请选择 Mastered 或 Need to review'}, status=status.HTTP_400_BAD_REQUEST)
        if action not in {'preview', 'apply'}:
            return Response({'detail': '未知操作'}, status=status.HTTP_400_BAD_REQUEST)
        note = str(request.data.get('note') or '').strip()
        if len(note) > MAX_QUESTION_NOTE_LENGTH:
            return Response({'detail': '题目笔记不能超过 20000 字符'}, status=status.HTTP_400_BAD_REQUEST)
        attempt_serializer = QuestionAttemptCreateSerializer(data={
            'result': result,
            'outcome': 'correct' if result == 'correct' else 'incorrect',
            'judgement_source': 'self',
            'error_codes': request.data.get('error_codes', []),
            'primary_error': request.data.get('primary_error'),
            'knowledge_level': request.data.get('knowledge_level'),
            'method_level': request.data.get('method_level'),
            'execution_level': request.data.get('execution_level'),
            'used_hint': request.data.get('used_hint'),
            'viewed_answer': request.data.get('viewed_answer'),
            'is_independent': request.data.get('is_independent'),
            'note': note,
        })
        attempt_serializer.is_valid(raise_exception=True)
        try:
            question_pages = parse_page_expression(request.data.get('question_pages'))
            paired_pages = parse_page_expression(request.data.get('paired_pages'))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if not question_pages and not paired_pages:
            return Response({'detail': '请至少输入一个题目册或题答对照册页码'}, status=status.HTTP_400_BAD_REQUEST)

        selected, question_hits, paired_hits = pdf_page_rows(course, question_pages, paired_pages)
        questions = Question.objects.filter(
            uuid__in=selected,
            document__workspace='ei',
            is_practiceable=True,
        ).select_related('document')
        matched = []
        stale_count = 0
        for question in questions:
            mapping = selected[str(question.uuid)]
            if question.fingerprint != mapping['row']['fingerprint']:
                stale_count += 1
                continue
            matched.append({
                'id': question.pk,
                'uuid': str(question.uuid),
                'label': question.display_label or question.source_label or f'题目 {question.question_order}',
                'book': question.document.display_title or question.document.title,
                'matched_by': mapping['matched_by'],
                'route': f'/practice/{question.uuid}?collection={course}_selected',
            })
        matched.sort(key=lambda item: (item['book'], item['label'], item['uuid']))

        created = 0
        if action == 'apply' and matched:
            # Attempts are append-only and now carry the same diagnosis dimensions,
            # training round and review-plan semantics as the normal question page.
            with transaction.atomic():
                locked = {
                    item.pk: item for item in Question.objects.select_for_update().filter(
                        pk__in=[row['id'] for row in matched], document__workspace='ei',
                    )
                }
                for item in matched:
                    if note:
                        state, _created = QuestionUserState.objects.select_for_update().get_or_create(
                            user=request.user, question=locked[item['id']],
                        )
                        merged = merge_note_values(state.note, note)
                        if merged != state.note:
                            state.note = merged
                            state.version += 1
                            state.save(update_fields=['note', 'version', 'updated_at'])
                    create_diagnosed_attempt(
                        request.user, locked[item['id']], attempt_serializer.validated_data,
                    )
            created = len(matched)

        return Response({
            'action': action,
            'course': course,
            'course_label': COURSE_LABELS[course],
            'result': result,
            'question_pages': sorted(question_pages),
            'paired_pages': sorted(paired_pages),
            'unmatched_question_pages': sorted(question_pages - question_hits),
            'unmatched_paired_pages': sorted(paired_pages - paired_hits),
            'stale_mapping_count': stale_count,
            'matched_count': len(matched),
            'created_count': created,
            'questions': [{key: value for key, value in item.items() if key != 'id'} for item in matched],
        }, status=status.HTTP_201_CREATED if action == 'apply' and created else status.HTTP_200_OK)
