from django.db.models import Count, OuterRef, Prefetch, Q, Subquery
from django.http import Http404, HttpResponse, HttpResponseNotModified
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Question, QuestionAsset, QuestionAttempt, QuestionDocument, QuestionTopic
from .serializers import QuestionAttemptCreateSerializer, QuestionSummarySerializer


def question_progress(queryset, user):
    latest = QuestionAttempt.objects.filter(
        user=user,
        question_id=OuterRef('pk'),
    ).order_by('-created_at')
    return queryset.annotate(
        attempt_count=Count('attempts', filter=Q(attempts__user=user)),
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
        result.append({'id': cursor.pk, 'title': cursor.title, 'level': cursor.level})
        cursor = cursor.parent
    return list(reversed(result))


class DrillCatalogView(APIView):
    def get(self, request):
        documents = QuestionDocument.objects.annotate(
            question_count=Count('questions'),
            past_exam_count=Count('questions', filter=Q(questions__is_past_exam=True)),
            attempted_count=Count(
                'questions',
                filter=Q(questions__attempts__user=request.user),
                distinct=True,
            ),
        ).filter(question_count__gt=0)
        topics = QuestionTopic.objects.filter(
            similar_questions__isnull=False,
            level__lte=4,
        ).annotate(
            question_count=Count('similar_questions'),
        ).select_related('document').order_by('document_id', 'sort_order')
        return Response({
            'documents': [
                {
                    'id': item.pk,
                    'title': item.title,
                    'question_count': item.question_count,
                    'past_exam_count': item.past_exam_count,
                    'attempted_count': item.attempted_count,
                }
                for item in documents
            ],
            'topics': [
                {
                    'id': item.pk,
                    'document_id': item.document_id,
                    'title': item.title,
                    'question_count': item.question_count,
                }
                for item in topics
            ],
        })


class DrillQuestionListView(APIView):
    def get(self, request):
        queryset = Question.objects.select_related('document', 'similarity_topic')
        document_id = request.query_params.get('document')
        topic_id = request.query_params.get('topic')
        search = request.query_params.get('q', '').strip()
        if document_id:
            queryset = queryset.filter(document_id=document_id)
        if topic_id:
            queryset = queryset.filter(similarity_topic_id=topic_id)
        if request.query_params.get('past_exam') == '1':
            queryset = queryset.filter(is_past_exam=True)
        if request.query_params.get('unattempted') == '1':
            queryset = queryset.exclude(attempts__user=request.user)
        if search:
            queryset = queryset.filter(
                Q(source_label__icontains=search)
                | Q(prompt_text__icontains=search)
                | Q(similarity_topic__title__icontains=search)
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
            return Response({'topic': None, 'results': []})
        queryset = question_progress(
            Question.objects.filter(
                similarity_topic_id=question.similarity_topic_id,
            ).exclude(pk=question.pk).select_related('document', 'similarity_topic'),
            request.user,
        ).order_by('attempt_count', 'document_id', 'question_order')[:24]
        return Response({
            'topic': question.similarity_topic.title,
            'results': QuestionSummarySerializer(queryset, many=True).data,
        })


class DrillQuestionAttemptView(APIView):
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
            'attempt_count': QuestionAttempt.objects.filter(
                user=request.user,
                question=question,
            ).count(),
        }, status=status.HTTP_201_CREATED)


class DrillHeatmapView(APIView):
    def get(self, request):
        questions = question_progress(
            Question.objects.filter(is_past_exam=True).select_related(
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
                    'document': question.document.title,
                    'questions': [],
                }
                groups.append(current)
            current['questions'].append({
                'uuid': str(question.uuid),
                'order': question.question_order,
                'label': question.source_label,
                'topic': question.similarity_topic.title if question.similarity_topic else '',
                'year': question.exam_year,
                'variant': question.exam_variant,
                'attempt_count': question.attempt_count,
                'latest_result': question.latest_result,
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
            total_attempts=Count('id'),
            attempted_questions=Count('question', distinct=True),
            correct_attempts=Count('id', filter=Q(result='correct')),
            review_attempts=Count('id', filter=Q(result='review')),
            past_exam_questions=Count(
                'question',
                filter=Q(question__is_past_exam=True),
                distinct=True,
            ),
        )
        aggregate['question_count'] = Question.objects.count()
        aggregate['past_exam_count'] = Question.objects.filter(is_past_exam=True).count()
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

