import datetime

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Exists, Max, OuterRef, Prefetch, Q, Subquery
from django.db.models.functions import TruncDate
from django.http import Http404, HttpResponse, HttpResponseNotModified
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .cleaning import SOURCE_LABELS
from .models import (
    Question, QuestionAsset, QuestionAttempt, QuestionDocument, QuestionMarker,
    QuestionTopic, QuestionUserState,
)
from .serializers import (
    PaperGenerateSerializer, QuestionAttemptCreateSerializer,
    QuestionMarkerSelectionSerializer, QuestionSummarySerializer, QuestionUserStateSerializer,
)


def request_workspace(request):
    hostname = request.get_host().partition(':')[0].lower()
    return 'ei' if hostname in settings.EI_HOSTS else 'drill'


def workspace_questions(request):
    return Question.objects.filter(document__workspace=request_workspace(request))


def question_progress(queryset, user):
    latest = QuestionAttempt.objects.filter(
        user=user,
        question_id=OuterRef('pk'),
    ).order_by('-created_at', '-pk')
    user_state = QuestionUserState.objects.filter(user=user, question_id=OuterRef('pk'))
    return queryset.annotate(
        attempt_count=Count(
            'attempts',
            filter=Q(attempts__user=user, attempts__result__in=('done', 'correct', 'review')),
        ),
        state_change_count=Count('attempts', filter=Q(attempts__user=user)),
        latest_result=Subquery(latest.values('result')[:1]),
        is_favorite=Exists(user_state.filter(is_favorite=True)),
        review_later=Exists(user_state.filter(review_later=True)),
        saved_note=Subquery(user_state.values('note')[:1]),
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


def navigation_queryset(question, request):
    queryset = workspace_questions(request).filter(is_practiceable=True)
    document_id = request.query_params.get('document')
    topic_id = request.query_params.get('topic')
    source_category = request.query_params.get('source_category', '').strip()
    search = request.query_params.get('q', '').strip()
    marker = request.query_params.get('marker', '').strip()
    if document_id:
        queryset = queryset.filter(document_id=document_id)
    else:
        queryset = queryset.filter(document_id=question.document_id)
    if topic_id:
        queryset = queryset.filter(similarity_topic_id=topic_id)
    elif not source_category:
        queryset = queryset.filter(source_category=question.source_category)
    if source_category in {choice[0] for choice in Question.SOURCE_CATEGORY_CHOICES}:
        queryset = queryset.filter(source_category=source_category)
    if request.query_params.get('unattempted') == '1':
        latest_state = QuestionAttempt.objects.filter(
            user=request.user,
            question_id=OuterRef('pk'),
        ).order_by('-created_at', '-pk')
        queryset = queryset.annotate(
            navigation_latest_result=Subquery(latest_state.values('result')[:1]),
        ).filter(
            Q(navigation_latest_result__isnull=True) | Q(navigation_latest_result='reset'),
        )
    if search:
        queryset = queryset.filter(
            Q(source_label__icontains=search)
            | Q(display_label__icontains=search)
            | Q(prompt_text__icontains=search)
            | Q(similarity_topic__title__icontains=search)
            | Q(similarity_topic__display_title__icontains=search)
        )
    if marker in dict(QuestionMarker.MARKER_CHOICES):
        queryset = queryset.filter(markers__user=request.user, markers__code=marker)
    return queryset.order_by('document_id', 'question_order', 'pk')


class DrillCatalogView(APIView):
    def get(self, request):
        workspace = request_workspace(request)
        documents = QuestionDocument.objects.filter(workspace=workspace).annotate(
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
            document__workspace=workspace,
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
            for row in Question.objects.filter(
                document__workspace=workspace, is_practiceable=True,
            ).values(
                'source_category',
            ).annotate(count=Count('id'))
        }
        imported_count = Question.objects.filter(document__workspace=workspace).count()
        practiceable_count = Question.objects.filter(
            document__workspace=workspace, is_practiceable=True,
        ).count()
        available_titles = [
            document.display_title or document.title
            for document in documents
        ]
        missing_titles = []
        if workspace == 'drill' and not any('一元微分' in title for title in available_titles):
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
        queryset = workspace_questions(request).select_related('document', 'similarity_topic')
        if request.query_params.get('include_structure') != '1':
            queryset = queryset.filter(is_practiceable=True)
        document_id = request.query_params.get('document')
        topic_id = request.query_params.get('topic')
        source_category = request.query_params.get('source_category', '').strip()
        search = request.query_params.get('q', '').strip()
        marker = request.query_params.get('marker', '').strip()
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
        if marker in dict(QuestionMarker.MARKER_CHOICES):
            queryset = queryset.filter(markers__user=request.user, markers__code=marker)
        queryset = question_progress(queryset, request.user).order_by(
            'document_id', 'question_order',
        )
        paginator = PageNumberPagination()
        paginator.page_size = 24
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(QuestionSummarySerializer(page, many=True).data)


class DrillPaperGenerateView(APIView):
    """Generate an ephemeral, user-scoped paper without persisting duplicate rows."""

    def post(self, request):
        import secrets

        serializer = PaperGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        queryset = workspace_questions(request).filter(is_practiceable=True)
        if data.get('document'):
            queryset = queryset.filter(document_id=data['document'])
        if data.get('topic'):
            queryset = queryset.filter(similarity_topic_id=data['topic'])
        if data.get('source_category'):
            queryset = queryset.filter(source_category=data['source_category'])
        if data['unattempted']:
            attempted = QuestionAttempt.objects.filter(
                user=request.user,
                result__in=('done', 'correct', 'review'),
            ).values_list('question_id', flat=True)
            queryset = queryset.exclude(id__in=attempted)
        candidate_ids = list(queryset.values_list('id', flat=True))
        requested = data['count']
        if not candidate_ids:
            return Response({'detail': 'No questions match these filters.'}, status=400)
        selected_ids = secrets.SystemRandom().sample(candidate_ids, min(requested, len(candidate_ids)))
        questions = {
            item.pk: item for item in question_progress(
                workspace_questions(request).filter(pk__in=selected_ids).select_related('document', 'similarity_topic'),
                request.user,
            )
        }
        return Response({
            'requested_count': requested,
            'available_count': len(candidate_ids),
            'questions': [summary_payload(questions[pk]) for pk in selected_ids],
        })


class DrillQuestionDetailView(APIView):
    def get(self, request, question_uuid):
        assets = QuestionAsset.objects.only(
            'id', 'question_id', 'position', 'asset_type', 'width', 'height', 'mime_type', 'sha256',
        )
        question = get_object_or_404(
            question_progress(
                workspace_questions(request).select_related(
                    'document', 'topic', 'similarity_topic',
                ).prefetch_related(Prefetch('assets', queryset=assets)),
                request.user,
            ),
            uuid=question_uuid,
        )
        navigation = list(navigation_queryset(question, request).values_list('pk', 'uuid'))
        position = next((index for index, item in enumerate(navigation) if item[0] == question.pk), -1)
        previous_question_uuid = navigation[position - 1][1] if position > 0 else None
        next_question_uuid = navigation[position + 1][1] if position >= 0 and position + 1 < len(navigation) else None
        latest = QuestionAttempt.objects.filter(
            user=request.user, question=question,
        ).order_by('-created_at', '-pk').first()
        user_state = QuestionUserState.objects.filter(
            user=request.user, question=question,
        ).first()
        marker_codes = list(QuestionMarker.objects.filter(
            user=request.user, question=question,
        ).order_by('created_at', 'pk').values_list('code', flat=True))
        payload = summary_payload(question)
        payload.update({
            'prompt_text': question.prompt_text,
            'latex_text': question.latex_text,
            'content_mode': question.content_mode,
            'formula_source': 'tex' if question.latex_text else 'original_pdf_crop',
            'document_author': question.document.author,
            'document_attribution': question.document.attribution,
            'confidence': latest.confidence if latest else None,
            'note': user_state.note if user_state else (latest.note if latest else ''),
            'markers': marker_codes,
            'next_question_uuid': str(next_question_uuid) if next_question_uuid else None,
            'previous_question_uuid': str(previous_question_uuid) if previous_question_uuid else None,
            'breadcrumbs': topic_breadcrumbs(question.topic),
            'question_assets': [
                {
                    'id': asset.pk,
                    'url': f'/api/drill/assets/{asset.pk}/?v={asset.sha256[:16]}',
                    'width': asset.width,
                    'height': asset.height,
                    'position': asset.position,
                }
                for asset in question.assets.all() if asset.asset_type == 'question_crop'
            ],
            'answer_assets': [
                {
                    'id': asset.pk,
                    'url': f'/api/drill/assets/{asset.pk}/?v={asset.sha256[:16]}',
                    'width': asset.width,
                    'height': asset.height,
                    'position': asset.position,
                }
                for asset in question.assets.all() if asset.asset_type == 'answer_crop'
            ],
            'has_answer': any(asset.asset_type == 'answer_crop' for asset in question.assets.all()),
            'answer_markdown': question.answer_markdown,
            'answer_source': question.answer_source,
            'answer_confidence': question.answer_confidence,
            'answer_generated_at': question.answer_generated_at,
            'assets': [
                {
                    'id': asset.pk,
                    'url': f'/api/drill/assets/{asset.pk}/?v={asset.sha256[:16]}',
                    'width': asset.width,
                    'height': asset.height,
                    'position': asset.position,
                }
                for asset in question.assets.all() if asset.asset_type == 'question_crop'
            ],
        })
        return Response(payload)


class DrillSimilarQuestionView(APIView):
    def get(self, request, question_uuid):
        question = get_object_or_404(
            workspace_questions(request).select_related('similarity_topic'),
            uuid=question_uuid,
        )
        if question.similarity_topic_id is None:
            return Response({
                'topic': None,
                'kind': None,
                'counts': {'past_exam': 0, 'practice': 0},
                'results': [],
            })
        base = workspace_questions(request).filter(
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
        user_state = QuestionUserState.objects.filter(user=user, question=question).first()
        return {
            'attempt_count': attempt_count,
            'latest_result': latest_result,
            'state': state,
            'can_undo': latest is not None,
            'confidence': latest.confidence if latest else None,
            'note': user_state.note if user_state else (latest.note if latest else ''),
            'is_favorite': user_state.is_favorite if user_state else False,
            'review_later': user_state.review_later if user_state else False,
        }

    def post(self, request, question_uuid):
        serializer = QuestionAttemptCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = get_object_or_404(workspace_questions(request), uuid=question_uuid)
        attempt = QuestionAttempt.objects.create(
            user=request.user,
            question=question,
            result=serializer.validated_data['result'],
            confidence=serializer.validated_data.get('confidence'),
            note=serializer.validated_data.get('note'),
        )
        if serializer.validated_data.get('note') is not None:
            QuestionUserState.objects.update_or_create(
                user=request.user,
                question=question,
                defaults={'note': serializer.validated_data.get('note') or ''},
            )
        return Response({
            'id': attempt.pk,
            'result': attempt.result,
            'created_at': attempt.created_at,
            **self._payload(request.user, question),
        }, status=status.HTTP_201_CREATED)

    def delete(self, request, question_uuid):
        question = get_object_or_404(workspace_questions(request), uuid=question_uuid)
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


class DrillQuestionUserStateView(APIView):
    def post(self, request, question_uuid):
        serializer = QuestionUserStateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = get_object_or_404(
            workspace_questions(request), uuid=question_uuid, is_practiceable=True,
        )
        state, _ = QuestionUserState.objects.get_or_create(
            user=request.user,
            question=question,
        )
        for field, value in serializer.validated_data.items():
            setattr(state, field, value)
        state.save()
        return Response({
            'note': state.note,
            'is_favorite': state.is_favorite,
            'review_later': state.review_later,
            'updated_at': state.updated_at,
        })


class DrillQuestionMarkerView(APIView):
    def post(self, request, question_uuid):
        serializer = QuestionMarkerSelectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = get_object_or_404(
            workspace_questions(request), uuid=question_uuid, is_practiceable=True,
        )
        requested_codes = serializer.validated_data['codes']
        with transaction.atomic():
            current = QuestionMarker.objects.select_for_update().filter(
                user=request.user, question=question,
            )
            current.exclude(code__in=requested_codes).delete()
            existing = set(current.values_list('code', flat=True))
            QuestionMarker.objects.bulk_create([
                QuestionMarker(user=request.user, question=question, code=code)
                for code in requested_codes if code not in existing
            ])
        return Response({'markers': requested_codes})


class DrillCollectionView(APIView):
    def get(self, request):
        kind = request.query_params.get('kind', 'favorite')
        field = {'favorite': 'is_favorite', 'review_later': 'review_later'}.get(kind)
        if field is None:
            return Response({'detail': 'kind must be favorite or review_later.'}, status=400)
        states = QuestionUserState.objects.filter(
            user=request.user,
            question__is_practiceable=True,
            question__document__workspace=request_workspace(request),
            **{field: True},
        ).order_by('-updated_at')
        paginator = PageNumberPagination()
        paginator.page_size = 24
        state_page = paginator.paginate_queryset(states, request)
        question_ids = [state.question_id for state in state_page]
        questions = {
            item.pk: item
            for item in question_progress(
                workspace_questions(request).filter(pk__in=question_ids).select_related(
                    'document', 'similarity_topic',
                ),
                request.user,
            )
        }
        return Response({
            'count': paginator.page.paginator.count,
            'next': paginator.get_next_link(),
            'previous': paginator.get_previous_link(),
            'kind': kind,
            'results': [summary_payload(questions[pk]) for pk in question_ids if pk in questions],
        })


class DrillBookFeelView(APIView):
    def get(self, request):
        documents = QuestionDocument.objects.filter(
            workspace=request_workspace(request),
            questions__is_practiceable=True,
        ).annotate(
            question_count=Count('questions', filter=Q(questions__is_practiceable=True), distinct=True),
            last_practiced_at=Max(
                'questions__attempts__created_at',
                filter=Q(
                    questions__attempts__user=request.user,
                    questions__attempts__result__in=('done', 'correct', 'review'),
                ),
            ),
            recent_attempts=Count(
                'questions__attempts',
                filter=Q(
                    questions__attempts__user=request.user,
                    questions__attempts__result__in=('done', 'correct', 'review'),
                    questions__attempts__created_at__gte=timezone.now() - datetime.timedelta(days=7),
                ),
            ),
        ).distinct()
        today = timezone.localdate()
        books = []
        for document in documents:
            last_date = timezone.localtime(document.last_practiced_at).date() if document.last_practiced_at else None
            days_idle = (today - last_date).days if last_date else None
            books.append({
                'document_id': document.pk,
                'document': document.display_title or document.title,
                'question_count': document.question_count,
                'last_practiced_at': document.last_practiced_at,
                'days_idle': days_idle,
                'feel_score': -days_idle if days_idle is not None else None,
                'recent_attempts': document.recent_attempts,
            })
        books.sort(key=lambda item: (item['feel_score'] is None, item['feel_score'] or 0, item['document']))
        return Response({'books': books})


class DrillInsightView(APIView):
    def get(self, request):
        recent_attempts = QuestionAttempt.objects.filter(
            user=request.user,
            result__in=('done', 'correct', 'review'),
            question__is_practiceable=True,
            question__document__workspace=request_workspace(request),
        ).select_related('question__document', 'question__similarity_topic')[:30]
        saved_notes = QuestionUserState.objects.filter(
            user=request.user,
            question__is_practiceable=True,
            question__document__workspace=request_workspace(request),
        ).exclude(note='').select_related('question__document', 'question__similarity_topic').order_by('-updated_at')[:30]
        attempt_notes = QuestionAttempt.objects.filter(
            user=request.user,
            question__is_practiceable=True,
            question__document__workspace=request_workspace(request),
        ).exclude(note__isnull=True).exclude(note='').select_related(
            'question__document', 'question__similarity_topic',
        ).order_by('-created_at', '-pk')[:30]

        def question_identity(question):
            return {
                'uuid': str(question.uuid),
                'label': question.display_label or question.source_label or f'Question {question.question_order}',
                'document': question.document.display_title or question.document.title,
                'topic': (
                    question.similarity_topic.display_title or question.similarity_topic.title
                ) if question.similarity_topic else 'General',
            }

        note_candidates = [
            (item.updated_at, item.question, item.note)
            for item in saved_notes
        ] + [
            (item.created_at, item.question, item.note)
            for item in attempt_notes
        ]
        note_candidates.sort(key=lambda item: item[0], reverse=True)
        note_payload = []
        seen_question_ids = set()
        for updated_at, question, note in note_candidates:
            if question.pk in seen_question_ids:
                continue
            seen_question_ids.add(question.pk)
            note_payload.append({
                **question_identity(question),
                'note': note,
                'updated_at': updated_at,
            })
            if len(note_payload) == 30:
                break

        marker_counts = {
            row['code']: row['count']
            for row in QuestionMarker.objects.filter(
                user=request.user,
                question__is_practiceable=True,
                question__document__workspace=request_workspace(request),
            ).values('code').annotate(count=Count('question', distinct=True))
        }

        return Response({
            'recent_questions': [
                {
                    **question_identity(item.question),
                    'result': item.result,
                    'created_at': item.created_at,
                }
                for item in recent_attempts
            ],
            'recent_notes': note_payload,
            'marker_stats': [
                {'code': code, 'label': label, 'count': marker_counts.get(code, 0)}
                for code, label in QuestionMarker.MARKER_CHOICES
            ],
        })


class DrillHeatmapView(APIView):
    def get(self, request):
        scope = request.query_params.get('scope', 'past_exam')
        mode = request.query_params.get('mode', 'questions')
        scope_filters = {
            'past_exam': Q(source_category='past_exam'),
            'mock_exam': Q(source_category='mock_exam'),
            'all': Q(),
        }
        if scope not in scope_filters:
            return Response({'detail': 'scope must be past_exam, mock_exam, or all.'}, status=400)
        if mode not in {'topics', 'questions'}:
            return Response({'detail': 'mode must be topics or questions.'}, status=400)

        questions = list(
            workspace_questions(request).filter(
                scope_filters[scope], is_practiceable=True,
            ).select_related('document', 'similarity_topic').only(
                'id', 'uuid', 'document_id', 'document__title', 'document__display_title',
                'similarity_topic_id', 'similarity_topic__title',
                'similarity_topic__display_title', 'question_order', 'source_label',
                'display_label', 'exam_year', 'exam_variant',
            ).order_by('document_id', 'question_order')
        )
        attempt_filters = Q(
            question__is_practiceable=True,
            question__document__workspace=request_workspace(request),
        )
        if scope != 'all':
            attempt_filters &= Q(question__source_category=scope)
        progress = {}
        for row in QuestionAttempt.objects.filter(
            attempt_filters, user=request.user,
        ).values(
            'question_id', 'result',
        ).order_by('question_id', '-created_at', '-pk'):
            item = progress.setdefault(row['question_id'], {
                'latest_result': row['result'],
                'attempt_count': 0,
            })
            if row['result'] in {'done', 'correct', 'review'}:
                item['attempt_count'] += 1

        topic_metadata = {}
        if mode == 'topics' and questions:
            document_ids = {question.document_id for question in questions}
            topic_metadata = {
                row['id']: row
                for row in QuestionTopic.objects.filter(
                    document_id__in=document_ids,
                ).values('id', 'parent_id', 'title', 'display_title')
            }

        def topic_path(topic_id):
            result = []
            visited = set()
            while topic_id and topic_id not in visited:
                visited.add(topic_id)
                item = topic_metadata.get(topic_id)
                if item is None:
                    break
                result.append(item['display_title'] or item['title'])
                topic_id = item['parent_id']
            return ' / '.join(reversed(result)) or 'General'

        groups = []
        current = None
        unique_topic_ids = set()
        for question in questions:
            if current is None or current['document_id'] != question.document_id:
                current = {
                    'document_id': question.document_id,
                    'document': question.document.display_title or question.document.title,
                    'source_category': scope,
                    'questions': [],
                    'topics': [],
                    '_topics_by_id': {},
                }
                groups.append(current)
            question_progress_item = progress.get(question.pk, {
                'latest_result': None,
                'attempt_count': 0,
            })
            latest_result = question_progress_item['latest_result']
            attempt_count = question_progress_item['attempt_count']
            state = (
                'review' if latest_result == 'review'
                else 'mastered' if latest_result in {'done', 'correct'}
                else 'unattempted'
            )
            if mode == 'questions':
                current['questions'].append({
                    'uuid': str(question.uuid),
                    'order': question.question_order,
                    'label': question.display_label or question.source_label,
                    'topic': (
                        question.similarity_topic.display_title or question.similarity_topic.title
                    ) if question.similarity_topic else '',
                    'year': question.exam_year,
                    'variant': question.exam_variant,
                    'attempt_count': attempt_count,
                    'latest_result': latest_result,
                    'state': state,
                })
            topic = question.similarity_topic
            topic_id = topic.pk if topic else None
            unique_topic_ids.add(topic_id)
            if mode != 'topics':
                continue
            topic_cell = current['_topics_by_id'].get(topic_id)
            if topic_cell is None:
                topic_cell = {
                    'topic_id': topic_id,
                    'topic': (topic.display_title or topic.title) if topic else 'General',
                    'path': topic_path(topic_id),
                    'question_count': 0,
                    'attempted_question_count': 0,
                    'mastered_question_count': 0,
                    'review_question_count': 0,
                    'attempt_count': 0,
                }
                current['_topics_by_id'][topic_id] = topic_cell
                current['topics'].append(topic_cell)
            topic_cell['question_count'] += 1
            topic_cell['attempt_count'] += attempt_count
            if state != 'unattempted':
                topic_cell['attempted_question_count'] += 1
            if state == 'mastered':
                topic_cell['mastered_question_count'] += 1
            elif state == 'review':
                topic_cell['review_question_count'] += 1

        for group in groups:
            group.pop('_topics_by_id', None)
            for topic_cell in group['topics']:
                total = topic_cell['question_count']
                attempted = topic_cell['attempted_question_count']
                topic_cell['coverage_percent'] = round(attempted * 100 / total)
                topic_cell['intensity'] = (
                    0 if attempted == 0 else min(4, max(1, (attempted * 4 + total - 1) // total))
                )
                topic_cell['state'] = (
                    'review' if topic_cell['review_question_count']
                    else 'mastered' if attempted == total
                    else 'progress' if attempted
                    else 'unattempted'
                )
        return Response({
            'mode': mode,
            'question_count': len(questions),
            'topic_count': len(unique_topic_ids),
            'groups': groups,
            'levels': [0, 1, 2, 3, 4],
        })


class DrillActivityHeatmapView(APIView):
    """Return a compact, user-scoped GitHub-style activity calendar."""

    @staticmethod
    def activity_level(count):
        # Fixed bands keep colors comparable between the all-books view and each book.
        for level, minimum in reversed(tuple(enumerate((0, 1, 2, 3, 4, 6, 9, 13, 20)))):
            if count >= minimum:
                return level
        return 0

    def get(self, request):
        workspace = request_workspace(request)
        today = timezone.localdate()
        # Render 53 complete Sunday-to-Saturday columns, including the current week.
        calendar_end = today + datetime.timedelta(days=(5 - today.weekday()) % 7)
        calendar_start = calendar_end - datetime.timedelta(days=(53 * 7 - 1))
        current_timezone = timezone.get_current_timezone()
        range_start = timezone.make_aware(
            datetime.datetime.combine(calendar_start, datetime.time.min), current_timezone,
        )
        range_end = timezone.make_aware(
            datetime.datetime.combine(today + datetime.timedelta(days=1), datetime.time.min),
            current_timezone,
        )
        documents = list(
            QuestionDocument.objects.filter(workspace=workspace)
            .values('id', 'title', 'display_title')
            .order_by('id')
        )
        rows = QuestionAttempt.objects.filter(
            user=request.user,
            question__document__workspace=workspace,
            result__in=('done', 'correct', 'review'),
            created_at__gte=range_start,
            created_at__lt=range_end,
        ).annotate(
            activity_date=TruncDate('created_at', tzinfo=current_timezone),
        ).values(
            'activity_date', 'question__document_id',
        ).annotate(
            count=Count('id'),
        ).order_by()

        overall_counts = {}
        book_counts = {}
        for row in rows:
            day = row['activity_date']
            count = row['count']
            overall_counts[day] = overall_counts.get(day, 0) + count
            book_counts.setdefault(row['question__document_id'], {})[day] = count

        def calendar(counts):
            days = []
            total = 0
            active_days = 0
            maximum = 0
            for offset in range(53 * 7):
                day = calendar_start + datetime.timedelta(days=offset)
                count = counts.get(day, 0)
                total += count
                active_days += int(count > 0)
                maximum = max(maximum, count)
                days.append({
                    'date': day.isoformat(),
                    'count': count,
                    'level': self.activity_level(count),
                    'is_future': day > today,
                })
            return {
                'total_attempts': total,
                'active_days': active_days,
                'max_daily_count': maximum,
                'days': days,
            }

        return Response({
            'start_date': calendar_start.isoformat(),
            'end_date': calendar_end.isoformat(),
            'today': today.isoformat(),
            'levels': list(range(9)),
            'overall': calendar(overall_counts),
            'books': [
                {
                    'document_id': document['id'],
                    'document': document['display_title'] or document['title'],
                    **calendar(book_counts.get(document['id'], {})),
                }
                for document in documents
            ],
        })


class DrillProgressView(APIView):
    def get(self, request):
        workspace = request_workspace(request)
        attempts = QuestionAttempt.objects.filter(
            user=request.user,
            question__document__workspace=workspace,
        )
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
        aggregate['question_count'] = Question.objects.filter(
            document__workspace=workspace, is_practiceable=True,
        ).count()
        aggregate['past_exam_count'] = Question.objects.filter(
            document__workspace=workspace,
            source_category='past_exam', is_practiceable=True,
        ).count()
        return Response(aggregate)


class DrillAssetView(APIView):
    def get(self, request, asset_id):
        asset = get_object_or_404(
            QuestionAsset.objects.filter(
                question__document__workspace=request_workspace(request),
            ).only('image_data', 'mime_type', 'sha256'),
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
