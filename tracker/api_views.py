import csv
import datetime
import json
import re
import secrets
from io import StringIO

from django.contrib.auth import logout
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .analytics import build_dashboard_overview
from .learning_log import dispatch_github_note_sync
from .models import InviteCode, KnowledgePoint, LaunchToken, LearningIssue, SessionReview, TimeLog
from .runtime_settings import runtime_config, save_runtime_config
from .serializers import (
    FinishSessionSerializer,
    InviteCodeCreateSerializer,
    InviteCodeSerializer,
    KnowledgePointSerializer,
    LaunchTokenCreateSerializer,
    LaunchTokenSerializer,
    LearningIssueSerializer,
    RuntimeSettingsSerializer,
    StartSessionSerializer,
    StudySessionSerializer,
    StudySessionSummarySerializer,
)
from .services import (
    MAXIMUM_SESSION_HOURS,
    MINIMUM_SESSION_MINUTES,
    ActiveSessionConflict,
    abandon_session,
    finish_session,
    normalize_subject,
    start_session,
)


def _local(value):
    return timezone.localtime(value) if timezone.is_aware(value) else value


def _filtered_sessions(request):
    queryset = TimeLog.objects.filter(user=request.user)
    subject = request.query_params.get('subject')
    if subject:
        try:
            queryset = queryset.filter(category=normalize_subject(subject))
        except ValueError:
            return queryset.none()
    status_value = request.query_params.get('status')
    if status_value:
        queryset = queryset.filter(status=status_value)
    date_from = parse_date(request.query_params.get('date_from', ''))
    date_to = parse_date(request.query_params.get('date_to', ''))
    if date_from:
        queryset = queryset.filter(start_time__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(start_time__date__lte=date_to)
    search = request.query_params.get('search', '').strip()
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search)
            | Q(details__icontains=search)
            | Q(chapter__icontains=search)
            | Q(topic__icontains=search)
            | Q(breakthrough__icontains=search)
            | Q(problems__icontains=search)
            | Q(next_action__icontains=search)
        )
    return queryset.order_by('-start_time')


@api_view(['GET'])
@ensure_csrf_cookie
def auth_session(request):
    return Response({
        'authenticated': request.user.is_authenticated,
        'user': {
            'id': request.user.pk,
            'username': request.user.get_username(),
            'is_staff': request.user.is_staff,
            'is_superuser': request.user.is_superuser,
        } if request.user.is_authenticated else None,
        'csrf_token': get_token(request),
    })


@api_view(['POST'])
def auth_logout(request):
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


class SessionListCreateView(APIView):
    def get(self, request):
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(_filtered_sessions(request), request)
        serializer_class = (
            StudySessionSummarySerializer
            if request.query_params.get('compact') == '1'
            else StudySessionSerializer
        )
        return paginator.get_paginated_response(serializer_class(page, many=True).data)

    def post(self, request):
        serializer = StartSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        subject = values.pop('subject')
        try:
            session, reused = start_session(request.user, subject, **values)
        except ActiveSessionConflict as exc:
            return Response(
                {
                    'detail': 'Another subject is active. Finish or discard it first.',
                    'active_session': StudySessionSerializer(exc.session).data,
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            {'reused': reused, 'session': StudySessionSerializer(session).data},
            status=status.HTTP_200_OK if reused else status.HTTP_201_CREATED,
        )


class SessionDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = StudySessionSerializer

    def get_queryset(self):
        return TimeLog.objects.filter(user=self.request.user)


class SessionFinishView(APIView):
    def post(self, request, pk):
        session = get_object_or_404(TimeLog, pk=pk, user=request.user)
        serializer = FinishSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            session, changed, discard_reason = finish_session(session, serializer.validated_data)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if discard_reason:
            return Response({
                'changed': changed,
                'discarded': True,
                'discard_reason': discard_reason,
                'minimum_minutes': MINIMUM_SESSION_MINUTES,
                'maximum_hours': MAXIMUM_SESSION_HOURS,
                'session': None,
            })
        github_note = dispatch_github_note_sync(session.pk) if changed else {'status': 'unchanged'}
        return Response({
            'changed': changed,
            'discarded': False,
            'discard_reason': None,
            'minimum_minutes': MINIMUM_SESSION_MINUTES,
            'maximum_hours': MAXIMUM_SESSION_HOURS,
            'session': StudySessionSerializer(session).data,
            'github_note': github_note,
        })


class SessionAbandonView(APIView):
    def post(self, request, pk):
        session = get_object_or_404(TimeLog, pk=pk, user=request.user)
        deleted = abandon_session(session)
        return Response({'deleted': deleted})


class SessionReviewView(APIView):
    """Record a deduplicated review visit and return its per-session trend."""

    window_days = 90

    def _payload(self, session, created=False):
        boundary = timezone.now() - datetime.timedelta(days=self.window_days - 1)
        daily = list(
            SessionReview.objects.filter(session=session, reviewed_at__gte=boundary)
            .annotate(date=TruncDate('reviewed_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
        return {
            'session_id': session.pk,
            'total': session.review_count,
            'last_reviewed_at': session.last_reviewed_at,
            'review_days': len(daily),
            'window_days': self.window_days,
            'created': created,
            'daily': [
                {'date': item['date'].isoformat(), 'count': item['count']}
                for item in daily
            ],
        }

    def get(self, request, pk):
        session = get_object_or_404(TimeLog, pk=pk, user=request.user)
        return Response(self._payload(session))

    def post(self, request, pk):
        with transaction.atomic():
            session = get_object_or_404(
                TimeLog.objects.select_for_update(), pk=pk, user=request.user,
            )
            if session.status != 'completed':
                return Response(
                    {'detail': 'Only completed sessions can be reviewed.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            now = timezone.now()
            cutoff = now - datetime.timedelta(minutes=10)
            recent = SessionReview.objects.filter(
                session=session, user=request.user, reviewed_at__gte=cutoff,
            ).exists()
            created = not recent
            if created:
                SessionReview.objects.create(session=session, user=request.user, reviewed_at=now)
                session.review_count += 1
                session.last_reviewed_at = now
                session.save(update_fields=('review_count', 'last_reviewed_at', 'updated_at'))
        return Response(self._payload(session, created=created))


class DashboardOverviewView(APIView):
    def get(self, request):
        try:
            days = int(request.query_params.get('days', 180))
        except ValueError:
            return Response({'detail': 'days must be an integer'}, status=400)
        days = max(7, min(days, 366))
        version = cache.get(f'dashboard-version:{request.user.pk}', 1)
        config = runtime_config()
        # Keep a payload schema version in the key so a zero-downtime frontend
        # deployment never receives an older cached response shape.
        cache_key = f'dashboard-overview:v5:{request.user.pk}:{days}:{version}:{config["fingerprint"]}'
        payload = cache.get(cache_key)
        if payload is None:
            payload = build_dashboard_overview(request.user, days, config=config['values'])
            cache.set(cache_key, payload, timeout=60)
        return Response(payload)


class RuntimeSettingsView(APIView):
    """Read and atomically persist the allow-listed local instance settings."""

    def get(self, request):
        return Response(runtime_config())

    def put(self, request):
        serializer = RuntimeSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = {
            key: value.isoformat() if hasattr(value, 'isoformat') else value
            for key, value in serializer.validated_data.items()
        }
        try:
            payload = save_runtime_config(values)
        except OSError:
            return Response(
                {'detail': 'The local settings file is not writable.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(payload)


class InviteCodeListCreateView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        queryset = InviteCode.objects.select_related('created_by').all()[:100]
        return Response(InviteCodeSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = InviteCodeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invite, raw_code = InviteCode.issue(
            created_by=request.user,
            **serializer.validated_data,
        )
        payload = InviteCodeSerializer(invite).data
        payload.update({
            'raw_code': raw_code,
            'signup_url': request.build_absolute_uri('/accounts/signup/'),
        })
        return Response(payload, status=status.HTTP_201_CREATED)


class InviteCodeActionView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk, action):
        invite = get_object_or_404(InviteCode, pk=pk)
        if action != 'revoke':
            return Response({'detail': 'Unsupported action.'}, status=status.HTTP_400_BAD_REQUEST)
        invite.is_active = False
        invite.save(update_fields=('is_active',))
        return Response(InviteCodeSerializer(invite).data)


def _search_snippet(query, *values, length=180):
    text = next(
        (str(value) for value in values if value and query.casefold() in str(value).casefold()),
        next((str(value) for value in values if value), ''),
    )
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) <= length:
        return text
    match_at = text.casefold().find(query.casefold())
    start = max(0, match_at - 55) if match_at >= 0 else 0
    start = min(start, max(0, len(text) - length))
    excerpt = text[start:start + length].strip()
    return f"{'…' if start else ''}{excerpt}{'…' if start + length < len(text) else ''}"


class GlobalSearchView(APIView):
    """Return bounded cross-feature search summaries without full session bodies."""

    def get(self, request):
        query = request.query_params.get('q', '').strip()[:120]
        if not query:
            return Response({'query': '', 'results': []})
        try:
            limit = int(request.query_params.get('limit', 16))
        except ValueError:
            return Response({'detail': 'limit must be an integer'}, status=400)
        limit = max(1, min(limit, 24))

        session_filter = (
            Q(title__icontains=query)
            | Q(details__icontains=query)
            | Q(chapter__icontains=query)
            | Q(topic__icontains=query)
            | Q(breakthrough__icontains=query)
            | Q(problems__icontains=query)
            | Q(next_action__icontains=query)
        )
        sessions = TimeLog.objects.filter(
            user=request.user,
            status='completed',
        ).filter(session_filter).only(
            'id', 'category', 'title', 'details', 'chapter', 'topic',
            'breakthrough', 'problems', 'next_action', 'start_time',
        ).order_by('-start_time')[:limit]

        issue_filter = (
            Q(topic__icontains=query)
            | Q(description__icontains=query)
            | Q(solution__icontains=query)
        )
        issues = LearningIssue.objects.filter(user=request.user).filter(issue_filter).only(
            'id', 'category', 'topic', 'issue_type', 'description', 'solution',
            'resolved', 'updated_at',
        ).order_by('-updated_at')[:limit]

        results = []
        for session in sessions:
            results.append({
                'kind': 'session',
                'record_id': session.pk,
                'title': session.title or session.topic or session.chapter or 'Untitled session',
                'snippet': _search_snippet(
                    query, session.title, session.details, session.topic, session.chapter,
                    session.breakthrough, session.problems, session.next_action,
                ),
                'subject': session.category,
                'subject_label': session.get_category_display(),
                'occurred_at': _local(session.start_time).isoformat(),
                '_sort': session.start_time,
            })
        for issue in issues:
            results.append({
                'kind': 'issue',
                'record_id': issue.pk,
                'title': issue.topic or issue.get_issue_type_display(),
                'snippet': _search_snippet(query, issue.topic, issue.description, issue.solution),
                'subject': issue.category,
                'subject_label': issue.get_category_display(),
                'occurred_at': _local(issue.updated_at).isoformat(),
                '_sort': issue.updated_at,
            })
        results.sort(key=lambda item: item['_sort'], reverse=True)
        for item in results:
            item.pop('_sort', None)
        return Response({'query': query, 'results': results[:limit]})


class LearningIssueListCreateView(generics.ListCreateAPIView):
    serializer_class = LearningIssueSerializer

    def get_queryset(self):
        return LearningIssue.objects.filter(user=self.request.user).select_related('study_session')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class LearningIssueDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = LearningIssueSerializer

    def get_queryset(self):
        return LearningIssue.objects.filter(user=self.request.user)


class KnowledgePointListCreateView(generics.ListCreateAPIView):
    serializer_class = KnowledgePointSerializer
    pagination_class = None

    def get_queryset(self):
        return KnowledgePoint.objects.filter(user=self.request.user).select_related('parent')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class KnowledgePointDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = KnowledgePointSerializer

    def get_queryset(self):
        return KnowledgePoint.objects.filter(user=self.request.user)


class LaunchTokenListCreateView(APIView):
    def get(self, request):
        tokens = LaunchToken.objects.filter(user=request.user)
        return Response(LaunchTokenSerializer(tokens, many=True).data)

    def post(self, request):
        serializer = LaunchTokenCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        values['category'] = normalize_subject(values.pop('subject'))
        token, raw_token = LaunchToken.issue(user=request.user, **values)
        data = LaunchTokenSerializer(token).data
        data.update({
            'raw_token': raw_token,
            'launch_url': request.build_absolute_uri(f'/launch/{raw_token}'),
            'warning': 'This URL is displayed once. Save it now.',
        })
        return Response(data, status=status.HTTP_201_CREATED)


class LaunchTokenActionView(APIView):
    def post(self, request, pk, action):
        token = get_object_or_404(LaunchToken, pk=pk, user=request.user)
        if action == 'revoke':
            token.is_active = False
            token.save(update_fields=('is_active',))
            return Response(LaunchTokenSerializer(token).data)
        if action == 'regenerate':
            raw_token = secrets.token_urlsafe(32)
            token.token_digest = LaunchToken.digest(raw_token)
            token.is_active = True
            token.usage_count = 0
            token.last_used_at = None
            token.save(update_fields=('token_digest', 'is_active', 'usage_count', 'last_used_at'))
            data = LaunchTokenSerializer(token).data
            data.update({
                'raw_token': raw_token,
                'launch_url': request.build_absolute_uri(f'/launch/{raw_token}'),
                'warning': 'The new URL is displayed once. The previous URL is now invalid.',
            })
            return Response(data)
        if action == 'delete':
            token.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({'detail': 'unknown action'}, status=status.HTTP_404_NOT_FOUND)


def _session_export_rows(request):
    return list(
        _filtered_sessions(request).filter(status='completed').prefetch_related('issues')
    )


@api_view(['GET'])
def export_csv(request):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'session_id', 'user_id', 'date', 'start_time', 'end_time', 'duration_minutes',
        'subject', 'chapter', 'topic', 'learning_mode', 'difficulty', 'energy_level',
        'focus_level', 'confidence_before', 'confidence_after', 'status', 'title', 'details',
        'breakthrough', 'problems', 'next_action', 'issues_json',
    ])
    for session in _session_export_rows(request):
        issues = [
            {
                'type': issue.issue_type,
                'description': issue.description,
                'solution': issue.solution,
                'resolved': issue.resolved,
            }
            for issue in session.issues.all()
        ]
        local_start = _local(session.start_time)
        writer.writerow([
            session.pk, session.user_id, local_start.date().isoformat(), local_start.isoformat(),
            _local(session.end_time).isoformat(), session.duration_minutes, session.category,
            session.chapter, session.topic, session.learning_mode, session.difficulty,
            session.energy_level, session.focus_level, session.confidence_before,
            session.confidence_after, session.status, session.title or '', session.details,
            session.breakthrough, session.problems, session.next_action,
            json.dumps(issues, ensure_ascii=False),
        ])
    response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="learning-sessions.csv"'
    return response


@api_view(['GET'])
def export_json(request):
    data = []
    for session in _session_export_rows(request):
        item = StudySessionSerializer(session).data
        item['user_ref'] = f'user-{session.user_id}'
        item['issues'] = LearningIssueSerializer(session.issues.all(), many=True).data
        data.append(item)
    response = HttpResponse(
        json.dumps({'sessions': data}, ensure_ascii=False, indent=2),
        content_type='application/json; charset=utf-8',
    )
    response['Content-Disposition'] = 'attachment; filename="learning-sessions.json"'
    return response


@api_view(['GET'])
def export_markdown(request):
    lines = ['# Study session export', '']
    current_day = None
    for session in _session_export_rows(request):
        local_start = _local(session.start_time)
        day = local_start.date().isoformat()
        if day != current_day:
            lines.extend([f'## {day}', ''])
            current_day = day
        lines.extend([
            f"### {session.get_category_display()} · {session.duration_minutes} minutes",
            '',
            f'- Time: {local_start:%H:%M}–{_local(session.end_time):%H:%M}',
            f'- Chapter: {session.chapter or "Not provided"}',
            f'- Topic: {session.topic or "Not provided"}',
            f'- Mode: {session.learning_mode or "Not provided"}',
            '',
            f'### {session.title or "Untitled session"}',
            '',
            session.details,
            '',
        ])
    response = HttpResponse('\n'.join(lines), content_type='text/markdown; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="learning-sessions.md"'
    return response
