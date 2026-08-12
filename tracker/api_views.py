import csv
import datetime
import json
import re
import secrets
from io import StringIO

from django.contrib.auth import logout
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import Http404, HttpResponse
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
from .data_encryption import (
    DataEncryptionError,
    encryption_status,
    set_user_encryption,
    user_encryption_enabled,
)
from .learning_log import dispatch_github_note_sync
from .models import (
    InviteCode, KnowledgePoint, LaunchToken, LearningIssue, SessionReview,
    SessionShare, SiteConfiguration, TimeLog,
)
from .runtime_settings import runtime_config, save_runtime_config
from .serializers import (
    FinishSessionSerializer,
    InviteCodeCreateSerializer,
    InviteCodeSerializer,
    KnowledgePointSerializer,
    LaunchTokenCreateSerializer,
    LaunchTokenConfigureSerializer,
    LaunchTokenSerializer,
    LearningIssueSerializer,
    PublicSharedSessionSerializer,
    RuntimeSettingsSerializer,
    SessionShareCreateSerializer,
    StartSessionSerializer,
    StudySessionSerializer,
    StudySessionSummarySerializer,
    UserDataEncryptionSerializer,
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
        if user_encryption_enabled(request.user.pk):
            needle = search.casefold()
            matched_ids = [
                session.pk
                for session in queryset.iterator(chunk_size=200)
                if any(needle in str(getattr(session, field) or '').casefold() for field in (
                    'title', 'details', 'chapter', 'topic', 'breakthrough',
                    'problems', 'next_action',
                ))
            ]
            queryset = queryset.filter(pk__in=matched_ids)
        else:
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
        queryset = _filtered_sessions(request)
        # Long Markdown belongs to the resource detail response. `full=1`
        # remains available for compatibility with clients that explicitly need
        # the historical list payload.
        serializer_class = (
            StudySessionSerializer
            if request.query_params.get('full') == '1'
            else StudySessionSummarySerializer
        )
        if serializer_class is StudySessionSummarySerializer:
            queryset = queryset.defer(
                'encrypted_content', 'details', 'breakthrough', 'problems',
                'next_action', 'learning_mode', 'difficulty', 'energy_level',
                'focus_level', 'confidence_before', 'confidence_after',
            )
        page = paginator.paginate_queryset(queryset, request)
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


class SessionUuidDetailView(SessionDetailView):
    lookup_field = 'uuid'
    lookup_url_kwarg = 'session_uuid'


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
            'session_uuid': str(session.uuid),
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

    def _session(self, request, *, pk=None, session_uuid=None, lock=False):
        queryset = TimeLog.objects.select_for_update() if lock else TimeLog.objects.all()
        lookup = {'uuid': session_uuid} if session_uuid is not None else {'pk': pk}
        return get_object_or_404(queryset, user=request.user, **lookup)

    def get(self, request, pk=None, session_uuid=None):
        session = self._session(request, pk=pk, session_uuid=session_uuid)
        return Response(self._payload(session))

    def post(self, request, pk=None, session_uuid=None):
        with transaction.atomic():
            session = self._session(
                request, pk=pk, session_uuid=session_uuid, lock=True,
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


def _share_payload(share):
    if share is None:
        return {
            'status': 'private',
            'is_shared': False,
            'is_active': False,
            'created_at': None,
            'expires_at': None,
            'revoked_at': None,
        }
    if share.usable:
        share_status = 'active'
    elif share.revoked_at is not None or not share.is_active:
        share_status = 'revoked'
    else:
        share_status = 'expired'
    return {
        'status': share_status,
        'is_shared': True,
        'is_active': share.usable,
        'created_at': share.created_at,
        'expires_at': share.expires_at,
        'revoked_at': share.revoked_at,
    }


class SessionShareView(APIView):
    """Manage one active, hashed public capability for an owned session."""

    def _session(self, request, *, lock=False, session_uuid=None):
        queryset = TimeLog.objects.select_for_update() if lock else TimeLog.objects.all()
        return get_object_or_404(queryset, user=request.user, uuid=session_uuid)

    def get(self, request, session_uuid):
        session = self._session(request, session_uuid=session_uuid)
        share = session.shares.order_by('-created_at').first()
        return Response(_share_payload(share))

    def post(self, request, session_uuid):
        serializer = SessionShareCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            session = self._session(request, lock=True, session_uuid=session_uuid)
            if session.status != 'completed':
                return Response(
                    {'detail': 'Only completed sessions can be shared.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            existing = session.shares.filter(is_active=True).first()
            if existing and existing.usable:
                return Response(
                    {'detail': 'This session already has an active share. Revoke it before creating another.'},
                    status=status.HTTP_409_CONFLICT,
                )
            if existing:
                existing.revoke()
            share, raw_token = SessionShare.issue(
                session=session,
                expires_at=serializer.validated_data.get('expires_at'),
            )
        payload = _share_payload(share)
        payload['share_url'] = request.build_absolute_uri(f'/share/{raw_token}')
        payload['warning'] = 'This URL is shown once because only its hash is stored.'
        return Response(payload, status=status.HTTP_201_CREATED)

    def delete(self, request, session_uuid):
        with transaction.atomic():
            session = self._session(request, lock=True, session_uuid=session_uuid)
            share = session.shares.filter(is_active=True).first()
            if share is None:
                return Response(_share_payload(session.shares.order_by('-created_at').first()))
            share.revoke()
        return Response(_share_payload(share))


class PublicSessionShareView(APIView):
    """Anonymous, read-only, minimal projection of a valid share capability."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        # Apply capability protections to success and error responses alike so
        # an expired/revoked token is never cached by a browser or intermediary.
        response['Cache-Control'] = 'no-store, max-age=0'
        response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        response['Referrer-Policy'] = 'no-referrer'
        return response

    def get(self, request, raw_token):
        if len(raw_token) > 128:
            raise Http404
        share = get_object_or_404(
            SessionShare.objects.select_related('session'),
            token_digest=SessionShare.digest(raw_token),
            is_active=True,
            revoked_at__isnull=True,
            session__status='completed',
        )
        if not share.usable:
            raise Http404
        return Response(PublicSharedSessionSerializer(share.session).data)


class DashboardOverviewView(APIView):
    def get(self, request):
        try:
            days = int(request.query_params.get('days', 180))
        except ValueError:
            return Response({'detail': 'days must be an integer'}, status=400)
        days = max(7, min(days, 366))
        version = cache.get(f'dashboard-version:{request.user.pk}', 1)
        config = runtime_config(user=request.user)
        math_visualization_enabled = SiteConfiguration.math_visualization_is_enabled()
        # Keep a payload schema version in the key so a zero-downtime frontend
        # deployment never receives an older cached response shape.
        cache_key = f'dashboard-overview:v6:{request.user.pk}:{days}:{version}:{config["fingerprint"]}:{int(math_visualization_enabled)}'
        payload = cache.get(cache_key)
        if payload is None:
            payload = build_dashboard_overview(request.user, days, config=config['values'])
            payload['features'] = {
                'math_visualization': math_visualization_enabled,
            }
            cache.set(cache_key, payload, timeout=60)
        return Response(payload)


class RuntimeSettingsView(APIView):
    """Read and atomically persist the allow-listed local instance settings."""

    def get(self, request):
        return Response(runtime_config(user=request.user))

    def put(self, request):
        if not request.user.is_superuser:
            return Response(
                {'detail': 'Only the instance superuser can synchronize local environment settings.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = RuntimeSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = {
            key: value.isoformat() if hasattr(value, 'isoformat') else value
            for key, value in serializer.validated_data.items()
        }
        try:
            payload = save_runtime_config(values, user=request.user)
        except OSError:
            return Response(
                {'detail': 'The local settings file is not writable.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(payload)


class UserDataEncryptionView(APIView):
    """Read or change the current user's transparent at-rest storage policy."""

    def get(self, request):
        return Response(encryption_status(request.user))

    def put(self, request):
        serializer = UserDataEncryptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = set_user_encryption(
                request.user,
                serializer.validated_data['enabled'],
            )
        except DataEncryptionError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(payload)


class InviteCodeListCreateView(APIView):
    def _queryset(self, request):
        queryset = InviteCode.objects.select_related('created_by').prefetch_related(
            'redemptions__user',
        )
        if not request.user.is_staff:
            queryset = queryset.filter(created_by=request.user)
        return queryset

    def get(self, request):
        queryset = self._queryset(request)[:100]
        return Response(InviteCodeSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = InviteCodeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)
        if not request.user.is_staff:
            local_day = timezone.localdate()
            fields.update({
                'max_uses': 1,
                'expires_at': None,
                'is_self_service': True,
                'issued_local_date': local_day,
            })
            if InviteCode.objects.filter(
                created_by=request.user,
                is_self_service=True,
                issued_local_date=local_day,
            ).exists():
                return Response(
                    {'detail': 'Your one-time invite for today has already been generated.'},
                    status=status.HTTP_409_CONFLICT,
                )
        try:
            with transaction.atomic():
                invite, raw_code = InviteCode.issue(
                    created_by=request.user,
                    **fields,
                )
        except IntegrityError:
            return Response(
                {'detail': 'Your one-time invite for today has already been generated.'},
                status=status.HTTP_409_CONFLICT,
            )
        payload = InviteCodeSerializer(invite).data
        payload.update({
            'raw_code': raw_code,
            'signup_url': request.build_absolute_uri('/accounts/signup/'),
        })
        return Response(payload, status=status.HTTP_201_CREATED)


class InviteCodeActionView(APIView):
    def post(self, request, pk, action):
        queryset = InviteCode.objects.all()
        if not request.user.is_staff:
            queryset = queryset.filter(created_by=request.user)
        invite = get_object_or_404(queryset, pk=pk)
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
        encrypted_search = user_encryption_enabled(request.user.pk)
        session_queryset = TimeLog.objects.filter(
            user=request.user,
            status='completed',
        ).order_by('-start_time')
        if encrypted_search:
            needle = query.casefold()
            sessions = [
                session
                for session in session_queryset.iterator(chunk_size=200)
                if any(needle in str(getattr(session, field) or '').casefold() for field in (
                    'title', 'details', 'chapter', 'topic', 'breakthrough',
                    'problems', 'next_action',
                ))
            ][:limit]
        else:
            sessions = session_queryset.filter(session_filter).only(
                'id', 'uuid', 'user', 'category', 'title', 'details', 'chapter', 'topic',
                'breakthrough', 'problems', 'next_action', 'start_time',
                'encrypted_summary', 'encrypted_content',
            )[:limit]

        issue_filter = (
            Q(topic__icontains=query)
            | Q(description__icontains=query)
            | Q(solution__icontains=query)
        )
        issue_queryset = LearningIssue.objects.filter(user=request.user).order_by('-updated_at')
        if encrypted_search:
            needle = query.casefold()
            issues = [
                issue
                for issue in issue_queryset.iterator(chunk_size=200)
                if any(needle in str(getattr(issue, field) or '').casefold() for field in (
                    'topic', 'description', 'solution',
                ))
            ][:limit]
        else:
            issues = issue_queryset.filter(issue_filter).only(
                'id', 'user', 'category', 'topic', 'issue_type', 'description', 'solution',
                'resolved', 'updated_at', 'encrypted_content',
            )[:limit]

        results = []
        for session in sessions:
            results.append({
                'kind': 'session',
                'record_id': session.pk,
                'session_uuid': str(session.uuid),
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
        token, raw_token, disturbance_token = LaunchToken.issue_with_disturbance(
            user=request.user,
            **values,
        )
        data = LaunchTokenSerializer(token).data
        data.update(_launch_uri_payload(request, raw_token, disturbance_token))
        return Response(data, status=status.HTTP_201_CREATED)


def _launch_uri_payload(request, raw_token=None, disturbance_token=None):
    payload = {
        'shortcuts_create_url': 'shortcuts://create-shortcut',
        'warning': 'Capability URLs are displayed once. Save them in Shortcuts now.',
    }
    if raw_token:
        payload.update({
            'raw_token': raw_token,
            'launch_url': request.build_absolute_uri(f'/launch/{raw_token}'),
            'shortcut_start_url': request.build_absolute_uri(
                f'/api/launch/{raw_token}/start',
            ),
        })
    if disturbance_token:
        payload.update({
            'raw_disturbance_token': disturbance_token,
            'disturbance_url': request.build_absolute_uri(
                f'/api/disturbance/{disturbance_token}/record',
            ),
        })
    return payload


class LaunchTokenActionView(APIView):
    def post(self, request, pk, action):
        token = get_object_or_404(LaunchToken, pk=pk, user=request.user)
        if action in {'pause', 'resume'}:
            if not token.is_active:
                return Response(
                    {'detail': 'A revoked token must be regenerated before it can be resumed.'},
                    status=status.HTTP_409_CONFLICT,
                )
            token.is_paused = action == 'pause'
            token.save(update_fields=('is_paused',))
            return Response(LaunchTokenSerializer(token).data)
        if action == 'revoke':
            token.is_active = False
            token.is_paused = False
            token.save(update_fields=('is_active', 'is_paused'))
            return Response(LaunchTokenSerializer(token).data)
        if action == 'regenerate':
            raw_token = secrets.token_urlsafe(32)
            token.token_digest = LaunchToken.digest(raw_token)
            token.is_active = True
            token.is_paused = False
            token.usage_count = 0
            token.last_used_at = None
            token.save(update_fields=(
                'token_digest', 'is_active', 'is_paused', 'usage_count', 'last_used_at',
            ))
            data = LaunchTokenSerializer(token).data
            data.update(_launch_uri_payload(request, raw_token=raw_token))
            data['warning'] = 'The new start URLs are displayed once. Previous start URLs are now invalid.'
            return Response(data)
        if action == 'regenerate-disturbance':
            if not token.is_active:
                return Response(
                    {'detail': 'Regenerate the start URI to reactivate this capability first.'},
                    status=status.HTTP_409_CONFLICT,
                )
            raw_token = secrets.token_urlsafe(32)
            token.disturbance_token_digest = LaunchToken.digest(raw_token)
            token.save(update_fields=('disturbance_token_digest',))
            data = LaunchTokenSerializer(token).data
            data.update(_launch_uri_payload(request, disturbance_token=raw_token))
            data['warning'] = 'The new disturbance URL is displayed once. The previous disturbance URL is now invalid.'
            return Response(data)
        if action == 'delete':
            token.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({'detail': 'unknown action'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, pk, action):
        if action != 'configure':
            return Response({'detail': 'unknown action'}, status=status.HTTP_404_NOT_FOUND)
        token = get_object_or_404(LaunchToken, pk=pk, user=request.user)
        serializer = LaunchTokenConfigureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(token, field, value)
        token.save(update_fields=tuple(serializer.validated_data))
        return Response(LaunchTokenSerializer(token).data)


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
        'breakthrough', 'problems', 'next_action', 'disturbance_count',
        'last_disturbance_at', 'issues_json',
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
            session.disturbance_count,
            _local(session.last_disturbance_at).isoformat() if session.last_disturbance_at else '',
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
            f'- Disturbances: {session.disturbance_count}',
            (
                f'- Last disturbance: {_local(session.last_disturbance_at).isoformat()}'
                if session.last_disturbance_at else '- Last disturbance: None'
            ),
            '',
            f'### {session.title or "Untitled session"}',
            '',
            session.details,
            '',
        ])
    response = HttpResponse('\n'.join(lines), content_type='text/markdown; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="learning-sessions.md"'
    return response
