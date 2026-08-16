from django.db import transaction
from django.db.models import Count, OuterRef, Prefetch, Q, Subquery
from django.http import Http404, HttpResponse, HttpResponseNotModified
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .cleaning import SOURCE_LABELS
from .models import Question, QuestionAsset, QuestionAttempt, QuestionDocument, QuestionTopic
from .serializers import QuestionAttemptCreateSerializer, QuestionSummarySerializer


def question_progress(queryset, user):
    latest = QuestionAttempt.objects.filter(
        user=user,
        question_id=OuterRef('pk'),
    ).order_by('-created_at', '-pk')
    return queryset.annotate(
        attempt_count=Count(
            'attempts',
            filter=Q(attempts__user=user, attempts__result__in=('done', 'correct', 'review')),
        ),
        state_change_count=Count('attempts', filter=Q(attempts__user=user)),
        latest_result=Subquery(latest.values('result')[:1]),
    )


def summary_payload(question):
    return QuestionSummarySerializer(question).data


def topic_breadcrumbs(topic):
    result = []
    visited = set()
    cursor = topic
    while cursor is not None and cursor.pk not in visited:
        visited.add(cursor.pk)
        result.append({
            'id': cursor.pk,
            'title': cursor.display_title or cursor.title,
            'level': cursor.level,
        })
        cursor = cursor.parent
    return list(reversed(result))


class DrillCatalogView(APIView):
    def get(self, request):
        documents = QuestionDocument.objects.annotate(
            imported_count=Count('questions', distinct=True),
            question_count=Count(
                'questions', filter=Q(questions__is_practiceable=True), distinct=True,
            ),
            past_exam_count=Count(
                'questions',
                filter=Q(questions__source_category='past_exam', questions__is_practiceable=True),
                distinct=True,
            ),
            attempted_count=Count(
                'questions',
                filter=Q(
                    questions__is_practiceable=True,
                    questions__attempts__user=request.user,
                    questions__attempts__result__in=('done', 'correct', 'review'),
                ),
                distinct=True,
            ),
        ).filter(question_count__gt=0)
        topics = QuestionTopic.objects.filter(
            similar_questions__is_practiceable=True,
            level__lte=4,
        ).annotate(
            question_count=Count(
                'similar_questions',
                filter=Q(similar_questions__is_practiceable=True),
            ),
        ).select_related(
            'document', 'parent', 'parent__parent', 'parent__parent__parent',
        ).order_by('document_id', 'sort_order')
        category_counts = {
            row['source_category']: row['count']
            for row in Question.objects.filter(is_practiceable=True).values(
                'source_category',
            ).annotate(count=Count('id'))
        }
        imported_count = Question.objects.count()
        practiceable_count = Question.objects.filter(is_practiceable=True).count()
        available_titles = [
            document.display_title or document.title
            for document in documents
        ]
        missing_titles = []
        if not any('一元微分' in title for title in available_titles):
            missing_titles.append('一元微分 / Single-variable differentiation')
        return Response({
            'summary': {
                'imported_count': imported_count,
                'practiceable_count': practiceable_count,
                'outline_count': imported_count - practiceable_count,
                'categories': [
                    {
                        'value': value,
                        'label': label,
                        'count': category_counts.get(value, 0),
                    }
                    for value, label in SOURCE_LABELS.items()
                ],
            },
            'coverage': {
                'available': available_titles,
                'missing': missing_titles,
                'source_archive_checked': True,
            },
            'documents': [
                {
                    'id': item.pk,
                    'title': item.display_title or item.title,
                    'author': item.author,
                    'attribution': item.attribution,
                    'question_count': item.question_count,
                    'imported_count': item.imported_count,
                    'past_exam_count': item.past_exam_count,
                    'attempted_count': item.attempted_count,
                }
                for item in documents
            ],
            'topics': [
                {
                    'id': item.pk,
                    'document_id': item.document_id,
                    'title': item.display_title or item.title,
                    'path': ' / '.join(
                        crumb['title'] for crumb in topic_breadcrumbs(item)
                    ),
                    'level': item.level,
                    'question_count': item.question_count,
                }
                for item in topics
            ],
        })


class DrillQuestionListView(APIView):
    def get(self, request):
        queryset = Question.objects.select_related('document', 'similarity_topic')
        if request.query_params.get('include_structure') != '1':
            queryset = queryset.filter(is_practiceable=True)
        document_id = request.query_params.get('document')
        topic_id = request.query_params.get('topic')
        source_category = request.query_params.get('source_category', '').strip()
        search = request.query_params.get('q', '').strip()
        if document_id:
            queryset = queryset.filter(document_id=document_id)
        if topic_id:
            queryset = queryset.filter(similarity_topic_id=topic_id)
        valid_categories = {choice[0] for choice in Question.SOURCE_CATEGORY_CHOICES}
        if source_category in valid_categories:
            queryset = queryset.filter(source_category=source_category)
        if request.query_params.get('past_exam') == '1':
            queryset = queryset.filter(source_category='past_exam')
        if request.query_params.get('unattempted') == '1':
            latest_state = QuestionAttempt.objects.filter(
                user=request.user,
                question_id=OuterRef('pk'),
            ).order_by('-created_at', '-pk')
            queryset = queryset.annotate(
                filter_latest_result=Subquery(latest_state.values('result')[:1]),
            ).filter(
                Q(filter_latest_result__isnull=True) | Q(filter_latest_result='reset'),
            )
        if search:
            queryset = queryset.filter(
                Q(source_label__icontains=search)
                | Q(display_label__icontains=search)
                | Q(prompt_text__icontains=search)
                | Q(similarity_topic__title__icontains=search)
                | Q(similarity_topic__display_title__icontains=search)
            )
        queryset = question_progress(queryset, request.user).order_by(
            'document_id', 'question_order',
        )
        paginator = PageNumberPagination()
        paginator.page_size = 24
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(QuestionSummarySerializer(page, many=True).data)


class DrillQuestionDetailView(APIView):
    def get(self, request, question_uuid):
        assets = QuestionAsset.objects.only(
            'id', 'question_id', 'position', 'width', 'height', 'mime_type', 'sha256',
        )
        question = get_object_or_404(
            question_progress(
                Question.objects.select_related(
                    'document', 'topic', 'similarity_topic',
                ).prefetch_related(Prefetch('assets', queryset=assets)),
                request.user,
            ),
            uuid=question_uuid,
        )
        payload = summary_payload(question)
        payload.update({
            'prompt_text': question.prompt_text,
            'latex_text': question.latex_text,
            'content_mode': question.content_mode,
            'formula_source': 'tex' if question.latex_text else 'original_pdf_crop',
            'document_author': question.document.author,
            'document_attribution': question.document.attribution,
            'breadcrumbs': topic_breadcrumbs(question.topic),
            'assets': [
                {
                    'id': asset.pk,
                    'url': f'/api/drill/assets/{asset.pk}/',
                    'width': asset.width,
                    'height': asset.height,
                    'position': asset.position,
                }
                for asset in question.assets.all()
            ],
        })
        return Response(payload)


class DrillSimilarQuestionView(APIView):
    def get(self, request, question_uuid):
        question = get_object_or_404(
            Question.objects.select_related('similarity_topic'),
            uuid=question_uuid,
        )
        if question.similarity_topic_id is None:
            return Response({
                'topic': None,
                'kind': None,
                'counts': {'past_exam': 0, 'practice': 0},
                'results': [],
            })
        base = Question.objects.filter(
            similarity_topic_id=question.similarity_topic_id,
            is_practiceable=True,
        ).exclude(pk=question.pk)
        counts = base.aggregate(
            past_exam=Count('id', filter=Q(source_category='past_exam')),
            practice=Count('id', filter=~Q(source_category='past_exam')),
        )
        kind = request.query_params.get('kind', '').strip()
        if kind == 'past_exam':
            base = base.filter(source_category='past_exam')
        elif kind == 'practice':
            base = base.exclude(source_category='past_exam')
        else:
            return Response({
                'topic': question.similarity_topic.display_title or question.similarity_topic.title,
                'kind': None,
                'counts': counts,
                'results': [],
            })
        queryset = question_progress(
            base.select_related('document', 'similarity_topic'), request.user,
        ).order_by('attempt_count', 'document_id', 'question_order')[:24]
        return Response({
            'topic': question.similarity_topic.display_title or question.similarity_topic.title,
            'kind': kind,
            'counts': counts,
            'results': QuestionSummarySerializer(queryset, many=True).data,
        })


class DrillQuestionAttemptView(APIView):
    @staticmethod
    def _payload(user, question):
        latest = QuestionAttempt.objects.filter(
            user=user,
            question=question,
        ).order_by('-created_at', '-pk').first()
        attempt_count = QuestionAttempt.objects.filter(
            user=user,
            question=question,
            result__in=('done', 'correct', 'review'),
        ).count()
        latest_result = latest.result if latest else None
        if latest_result == 'review':
            state = 'review'
        elif latest_result in {'done', 'correct'}:
            state = 'mastered'
        else:
            state = 'unattempted'
        return {
            'attempt_count': attempt_count,
            'latest_result': latest_result,
            'state': state,
            'can_undo': latest is not None,
        }

    def post(self, request, question_uuid):
        serializer = QuestionAttemptCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = get_object_or_404(Question, uuid=question_uuid)
        attempt = QuestionAttempt.objects.create(
            user=request.user,
            question=question,
            result=serializer.validated_data['result'],
        )
        return Response({
            'id': attempt.pk,
            'result': attempt.result,
            'created_at': attempt.created_at,
            **self._payload(request.user, question),
        }, status=status.HTTP_201_CREATED)

    def delete(self, request, question_uuid):
        question = get_object_or_404(Question, uuid=question_uuid)
        with transaction.atomic():
            latest = QuestionAttempt.objects.select_for_update().filter(
                user=request.user,
                question=question,
            ).order_by('-created_at', '-pk').first()
            if latest is None:
                return Response(
                    {'detail': 'There is no question-state change to undo.'},
                    status=status.HTTP_409_CONFLICT,
                )
            latest.delete()
        return Response(self._payload(request.user, question))


class DrillHeatmapView(APIView):
    def get(self, request):
        questions = question_progress(
            Question.objects.filter(
                source_category='past_exam', is_practiceable=True,
            ).select_related(
                'document', 'similarity_topic',
            ),
            request.user,
        ).order_by('document_id', 'question_order')
        groups = []
        current = None
        for question in questions:
            if current is None or current['document_id'] != question.document_id:
                current = {
                    'document_id': question.document_id,
                    'document': question.document.display_title or question.document.title,
                    'questions': [],
                }
                groups.append(current)
            current['questions'].append({
                'uuid': str(question.uuid),
                'order': question.question_order,
                'label': question.display_label or question.source_label,
                'topic': (
                    question.similarity_topic.display_title or question.similarity_topic.title
                ) if question.similarity_topic else '',
                'year': question.exam_year,
                'variant': question.exam_variant,
                'attempt_count': question.attempt_count,
                'latest_result': question.latest_result,
                'state': (
                    'review' if question.latest_result == 'review'
                    else 'mastered' if question.latest_result in {'done', 'correct'}
                    else 'unattempted'
                ),
            })
        return Response({
            'question_count': sum(len(group['questions']) for group in groups),
            'groups': groups,
            'levels': [0, 1, 2, 3, 4],
        })


class DrillProgressView(APIView):
    def get(self, request):
        attempts = QuestionAttempt.objects.filter(user=request.user)
        aggregate = attempts.aggregate(
            total_attempts=Count('id', filter=Q(result__in=('done', 'correct', 'review'))),
            attempted_questions=Count(
                'question',
                filter=Q(
                    result__in=('done', 'correct', 'review'),
                    question__is_practiceable=True,
                ),
                distinct=True,
            ),
            correct_attempts=Count('id', filter=Q(result='correct')),
            review_attempts=Count('id', filter=Q(result='review')),
            past_exam_questions=Count(
                'question',
                filter=Q(
                    result__in=('done', 'correct', 'review'),
                    question__source_category='past_exam',
                    question__is_practiceable=True,
                ),
                distinct=True,
            ),
        )
        aggregate['question_count'] = Question.objects.filter(is_practiceable=True).count()
        aggregate['past_exam_count'] = Question.objects.filter(
            source_category='past_exam', is_practiceable=True,
        ).count()
        return Response(aggregate)


class DrillAssetView(APIView):
    def get(self, request, asset_id):
        asset = get_object_or_404(
            QuestionAsset.objects.only('image_data', 'mime_type', 'sha256'),
            pk=asset_id,
        )
        etag = f'"{asset.sha256}"'
        if request.headers.get('If-None-Match') == etag:
            response = HttpResponseNotModified()
        else:
            response = HttpResponse(bytes(asset.image_data), content_type=asset.mime_type)
        response['ETag'] = etag
        response['Cache-Control'] = 'private, max-age=31536000, immutable'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
