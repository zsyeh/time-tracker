"""Bounded capability endpoint for remote capacity-test orchestration."""

from __future__ import annotations

import json
import secrets
import threading
import time
from collections import deque

from django.conf import settings
from django.http import Http404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .loadtest import issue_run_token, normalize_run_id, verify_run_token
from .loadtest_fixtures import cleanup_run, prepare_finish_burst, provision_run
from .loadtest_metrics import sample_system_metrics


MINIMUM_KEY_LENGTH = 32


class SlidingWindowRateLimiter:
    """Small per-process limiter that avoids database/cache work under load."""

    def __init__(self):
        self._events = deque()
        self._lock = threading.Lock()

    def allow(self, limit):
        now = time.monotonic()
        cutoff = now - 1.0
        with self._lock:
            while self._events and self._events[0] <= cutoff:
                self._events.popleft()
            if len(self._events) >= limit:
                return False
            self._events.append(now)
            return True

    def reset(self):
        with self._lock:
            self._events.clear()


_RATE_LIMITER = SlidingWindowRateLimiter()


def _capabilities():
    return {
        'max_rps_per_worker': settings.STRESS_TEST_MAX_RPS,
        'max_users': settings.STRESS_TEST_MAX_USERS,
        'max_history_rows': settings.STRESS_TEST_MAX_HISTORY_ROWS,
        'run_ttl_seconds': settings.STRESS_TEST_RUN_TTL_SECONDS,
        'data_setup_enabled': settings.STRESS_TEST_ALLOW_DATA_SETUP,
        'network_capacity_mbps': settings.STRESS_TEST_NETWORK_CAPACITY_MBPS or None,
        'storage_benchmark': False,
        'remote_commands': False,
        'request_instrumentation': {
            'queue': 'Nginx proxy handoff to Django middleware entry; includes socket backlog/scheduling and requires the trusted proxy timestamp.',
            'app_wall': 'Django middleware entry until response construction completes.',
            'cpu': 'Linux request-thread user and system CPU time.',
            'database': 'Django execute_wrapper query count, write count, and wall time.',
        },
    }


class StressTestProbeView(APIView):
    """Expose fixed actions only; never execute caller-provided commands."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    http_method_names = ['post', 'options']

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store, max-age=0'
        response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        response['Referrer-Policy'] = 'no-referrer'
        return response

    @staticmethod
    def _require_capability(request):
        expected = settings.STRESS_TEST_KEY
        if not settings.STRESS_TEST_ENABLED or len(expected) < MINIMUM_KEY_LENGTH:
            raise Http404
        authorization = request.headers.get('Authorization', '')
        prefix = 'Bearer '
        provided = authorization[len(prefix):] if authorization.startswith(prefix) else ''
        if len(provided) > 256 or not secrets.compare_digest(provided, expected):
            raise Http404

    @staticmethod
    def _require_run(payload_data):
        run_token = str(payload_data.get('run_token', ''))
        capability = verify_run_token(run_token)
        if capability is None:
            raise Http404
        run_id = normalize_run_id(payload_data.get('run_id', capability['run_id']))
        if run_id != capability['run_id']:
            raise Http404
        return capability

    @staticmethod
    def _parse_body(request):
        try:
            content_length = int(request.META.get('CONTENT_LENGTH') or 0)
        except (TypeError, ValueError):
            content_length = settings.STRESS_TEST_MAX_BODY_BYTES + 1
        if content_length > settings.STRESS_TEST_MAX_BODY_BYTES:
            return None, Response(
                {'detail': 'Request body exceeds the stress probe limit.'},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        raw_body = request.stream.read(settings.STRESS_TEST_MAX_BODY_BYTES + 1)
        if len(raw_body) > settings.STRESS_TEST_MAX_BODY_BYTES:
            return None, Response(
                {'detail': 'Request body exceeds the stress probe limit.'},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        try:
            payload_data = json.loads(raw_body.decode('utf-8')) if raw_body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None, Response(
                {'detail': 'Valid JSON object expected.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(payload_data, dict):
            return None, Response(
                {'detail': 'JSON object expected.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return payload_data, None

    def post(self, request):
        self._require_capability(request)
        if not _RATE_LIMITER.allow(settings.STRESS_TEST_MAX_RPS):
            response = Response(
                {'detail': 'Stress probe rate limit reached.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
            response['Retry-After'] = '1'
            return response
        payload_data, error_response = self._parse_body(request)
        if error_response is not None:
            return error_response

        action = str(payload_data.get('action', 'sample')).strip().lower()
        request_id = str(payload_data.get('request_id', ''))[:64]
        payload = {
            'ok': True,
            'schema_version': 2,
            'action': action,
            'request_id': request_id,
            'server_time': timezone.now().isoformat(),
            'limits': _capabilities(),
        }
        try:
            if action in {'sample', 'preflight', 'metrics'}:
                include_metrics = (
                    action in {'preflight', 'metrics'}
                    or payload_data.get('sample_metrics') is True
                )
                if include_metrics:
                    payload['metrics'] = sample_system_metrics(
                        include_database=payload_data.get('sample_database') is True,
                    )
                return Response(payload)

            if action == 'begin':
                run_id = normalize_run_id(
                    payload_data.get('run_id') or f'run-{secrets.token_hex(8)}'
                )
                requested_rps = int(payload_data.get('max_rps', settings.STRESS_TEST_MAX_RPS))
                ttl_seconds = max(
                    60,
                    min(
                        int(payload_data.get('ttl_seconds', settings.STRESS_TEST_RUN_TTL_SECONDS)),
                        settings.STRESS_TEST_RUN_TTL_SECONDS,
                    ),
                )
                max_rps = max(1, min(requested_rps, settings.STRESS_TEST_MAX_RPS))
                payload['run'] = {
                    'run_id': run_id,
                    'run_token': issue_run_token(
                        run_id,
                        max_rps=max_rps,
                        ttl_seconds=ttl_seconds,
                    ),
                    'expires_in_seconds': ttl_seconds,
                    'max_rps_per_worker': max_rps,
                }
                payload['metrics'] = sample_system_metrics(include_database=True)
                return Response(payload)

            if action in {'provision', 'prepare_finish', 'cleanup'}:
                if action != 'cleanup' and not settings.STRESS_TEST_ALLOW_DATA_SETUP:
                    return Response(
                        {'detail': 'Isolated load-test data setup is disabled on this server.'},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                if action == 'cleanup':
                    # The long-lived key can recover an interrupted/expired run;
                    # deletion remains restricted to the exact loadtest prefix.
                    run_id = normalize_run_id(payload_data.get('run_id', ''))
                else:
                    capability = self._require_run(payload_data)
                    run_id = capability['run_id']
                if action == 'provision':
                    payload['fixtures'] = provision_run(
                        run_id,
                        user_count=int(payload_data.get('user_count', 8)),
                        seed=int(payload_data.get('seed', 20260815)),
                    )
                elif action == 'prepare_finish':
                    payload['fixtures'] = prepare_finish_burst(
                        run_id,
                        limit=int(payload_data.get('limit', settings.STRESS_TEST_MAX_USERS)),
                    )
                else:
                    payload['fixtures'] = cleanup_run(run_id)
                return Response(payload)
        except (TypeError, ValueError, RuntimeError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'detail': 'Unknown fixed stress-test action.'}, status=404)
