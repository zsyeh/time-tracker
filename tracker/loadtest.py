"""Signed load-test capabilities and low-overhead request instrumentation.

The feature is inert unless STRESS_TEST_ENABLED is true.  A short-lived run
token authorizes instrumentation only; normal application authentication and
ownership checks continue to apply to every real API request.
"""

from __future__ import annotations

import base64
import binascii
import contextvars
from contextlib import contextmanager
import hashlib
import hmac
import json
import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from django.conf import settings
from django.db import connection
from django.http import JsonResponse

try:
    import resource
except ImportError:  # pragma: no cover - production is Linux.
    resource = None


RUN_ID_PATTERN = re.compile(r'^[a-z0-9][a-z0-9-]{7,39}$')
TOKEN_PREFIX = 'lt1'
TOKEN_HEADER = 'X-Load-Test-Run'
PROXY_START_HEADER = 'X-Load-Test-Proxy-Start'
LOADTEST_USER_PREFIX = 'loadtest_'
LOADTEST_USERNAME_PATTERN = re.compile(
    r'^loadtest_(?P<run_id>[a-z0-9][a-z0-9-]{7,39})_(?P<index>[0-9]{4,5})$',
)
_BULK_FIXTURE_MAINTENANCE = contextvars.ContextVar(
    'loadtest_bulk_fixture_maintenance', default=False,
)


def normalize_run_id(value: str) -> str:
    run_id = str(value or '').strip().lower()
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError('run_id must contain 8-40 lowercase letters, digits, or hyphens')
    return run_id


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def issue_run_token(run_id: str, *, max_rps: int, ttl_seconds: int) -> str:
    run_id = normalize_run_id(run_id)
    now = int(time.time())
    payload = {
        'run_id': run_id,
        'iat': now,
        'exp': now + max(60, int(ttl_seconds)),
        'max_rps': max(1, min(int(max_rps), settings.STRESS_TEST_MAX_RPS)),
        'version': 1,
    }
    encoded = _b64encode(json.dumps(payload, separators=(',', ':'), sort_keys=True).encode())
    signature = _b64encode(hmac.new(
        settings.STRESS_TEST_KEY.encode('utf-8'),
        f'{TOKEN_PREFIX}.{encoded}'.encode('ascii'),
        hashlib.sha256,
    ).digest())
    return f'{TOKEN_PREFIX}.{encoded}.{signature}'


def verify_run_token(raw_token: str) -> dict | None:
    if (
        not settings.STRESS_TEST_ENABLED
        or len(settings.STRESS_TEST_KEY) < 32
        or not raw_token
        or len(raw_token) > 1024
    ):
        return None
    try:
        prefix, encoded, provided_signature = raw_token.split('.', 2)
        if prefix != TOKEN_PREFIX:
            return None
        expected_signature = _b64encode(hmac.new(
            settings.STRESS_TEST_KEY.encode('utf-8'),
            f'{prefix}.{encoded}'.encode('ascii'),
            hashlib.sha256,
        ).digest())
        if not hmac.compare_digest(provided_signature, expected_signature):
            return None
        payload = json.loads(_b64decode(encoded).decode('utf-8'))
        normalize_run_id(payload.get('run_id', ''))
        if payload.get('version') != 1 or int(payload.get('exp', 0)) < int(time.time()):
            return None
        payload['max_rps'] = max(
            1,
            min(int(payload.get('max_rps', 1)), settings.STRESS_TEST_MAX_RPS),
        )
        return payload
    except (
        ValueError,
        TypeError,
        AttributeError,
        binascii.Error,
        json.JSONDecodeError,
        UnicodeDecodeError,
    ):
        return None


def is_loadtest_username(value: str, *, run_id: str | None = None) -> bool:
    matched = LOADTEST_USERNAME_PATTERN.fullmatch(str(value or ''))
    return bool(matched and (run_id is None or matched.group('run_id') == run_id))


def is_loadtest_user(user) -> bool:
    return bool(
        getattr(user, 'is_authenticated', False)
        and is_loadtest_username(user.get_username())
    )


@contextmanager
def suppress_fixture_maintenance():
    """Skip expensive per-row signal rebuilds only during isolated cleanup."""
    token = _BULK_FIXTURE_MAINTENANCE.set(True)
    try:
        yield
    finally:
        _BULK_FIXTURE_MAINTENANCE.reset(token)


def fixture_maintenance_suppressed():
    return _BULK_FIXTURE_MAINTENANCE.get()


class _RunRateLimiter:
    """Per-worker safety limit for signed real-API test traffic."""

    def __init__(self):
        self._events = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, run_id: str, limit: int) -> bool:
        now = time.monotonic()
        cutoff = now - 1.0
        with self._lock:
            events = self._events[run_id]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            if len(self._events) > 64:
                stale = [key for key, rows in self._events.items() if not rows or rows[-1] <= cutoff]
                for key in stale:
                    self._events.pop(key, None)
            return True

    def reset(self):
        with self._lock:
            self._events.clear()


_RUN_RATE_LIMITER = _RunRateLimiter()


@dataclass
class QueryTiming:
    count: int = 0
    write_count: int = 0
    total_ms: float = 0.0

    def __call__(self, execute, sql, params, many, context):
        started = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            self.count += 1
            self.total_ms += (time.perf_counter() - started) * 1000
            command = str(sql).lstrip().split(None, 1)[0].upper() if sql else ''
            if command in {'INSERT', 'UPDATE', 'DELETE', 'MERGE', 'REPLACE'}:
                self.write_count += 1


def _thread_usage():
    if resource is None:
        return None
    scope = getattr(resource, 'RUSAGE_THREAD', resource.RUSAGE_SELF)
    usage = resource.getrusage(scope)
    return usage.ru_utime, usage.ru_stime


def _proxy_queue_ms(request, app_started_epoch: float) -> float | None:
    raw_value = request.headers.get(PROXY_START_HEADER, '').strip()
    if raw_value.startswith('t='):
        raw_value = raw_value[2:]
    try:
        proxy_started = float(raw_value)
    except (TypeError, ValueError):
        return None
    value = (app_started_epoch - proxy_started) * 1000
    # A negative value or a very large value means the trusted Nginx header is
    # absent/misconfigured or came from a different clock domain.
    if value < -5 or value > 120_000:
        return None
    return max(0.0, value)


def _set_timing_headers(response, *, wall_ms, cpu_user_ms, cpu_system_ms,
                        queue_ms, query_timing):
    cpu_total_ms = None
    if cpu_user_ms is not None and cpu_system_ms is not None:
        cpu_total_ms = cpu_user_ms + cpu_system_ms
    values = {
        'X-Load-Test-App-Wall-Ms': wall_ms,
        'X-Load-Test-App-CPU-Ms': cpu_total_ms,
        'X-Load-Test-CPU-User-Ms': cpu_user_ms,
        'X-Load-Test-CPU-System-Ms': cpu_system_ms,
        'X-Load-Test-DB-Ms': query_timing.total_ms,
        'X-Load-Test-DB-Queries': query_timing.count,
        'X-Load-Test-DB-Writes': query_timing.write_count,
        'X-Load-Test-Queue-Ms': queue_ms,
    }
    for header, value in values.items():
        if value is not None:
            response[header] = f'{value:.3f}' if isinstance(value, float) else str(value)
    timing = [
        f'app;dur={wall_ms:.3f}',
        f'db;dur={query_timing.total_ms:.3f}',
    ]
    if cpu_total_ms is not None:
        timing.append(f'cpu;dur={cpu_total_ms:.3f}')
    if queue_ms is not None:
        timing.append(f'queue;dur={queue_ms:.3f}')
    response['Server-Timing'] = ', '.join(timing)
    response['Timing-Allow-Origin'] = 'none'
    response['Cache-Control'] = response.get('Cache-Control', 'private, no-store')


class LoadTestTimingMiddleware:
    """Instrument only requests carrying a valid short-lived run token."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        raw_token = request.headers.get(TOKEN_HEADER, '')
        capability = verify_run_token(raw_token)
        if capability is None:
            return self.get_response(request)
        request.loadtest_capability = capability
        if not _RUN_RATE_LIMITER.allow(capability['run_id'], capability['max_rps']):
            response = JsonResponse(
                {'detail': 'Signed load-test traffic exceeded the per-worker safety limit.'},
                status=429,
            )
            response['Retry-After'] = '1'
            response['X-Load-Test-Limited'] = '1'
            return response

        app_started_epoch = time.time()
        wall_started = time.perf_counter()
        usage_started = _thread_usage()
        query_timing = QueryTiming()
        with connection.execute_wrapper(query_timing):
            response = self.get_response(request)
        wall_ms = (time.perf_counter() - wall_started) * 1000
        usage_finished = _thread_usage()
        cpu_user_ms = cpu_system_ms = None
        if usage_started is not None and usage_finished is not None:
            cpu_user_ms = max(0.0, (usage_finished[0] - usage_started[0]) * 1000)
            cpu_system_ms = max(0.0, (usage_finished[1] - usage_started[1]) * 1000)
        queue_ms = _proxy_queue_ms(request, app_started_epoch)
        _set_timing_headers(
            response,
            wall_ms=wall_ms,
            cpu_user_ms=cpu_user_ms,
            cpu_system_ms=cpu_system_ms,
            queue_ms=queue_ms,
            query_timing=query_timing,
        )
        response['X-Load-Test-Run-Id'] = capability['run_id']
        return response
