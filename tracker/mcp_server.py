"""ChatGPT-compatible MCP tools for the study time tracker."""

import datetime
import json
import re
from typing import Any, Dict, List, Optional

import uvicorn
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from .models import TimeLog


CATEGORY_LABELS = dict(TimeLog.CATEGORY_CHOICES)
VALID_CATEGORIES = set(CATEGORY_LABELS)
MAX_TASK_DURATION = datetime.timedelta(hours=6)
MAX_REPORT_LENGTH = 10_000
URL_KEY_PATTERN = re.compile(r'^[A-Za-z0-9_-]{24,128}$')

READ_ONLY = {
    'readOnlyHint': True,
    'openWorldHint': False,
    'destructiveHint': False,
}
BOUNDED_WRITE = {
    'readOnlyHint': False,
    'openWorldHint': False,
    'destructiveHint': False,
}
BOUNDED_DESTRUCTIVE_WRITE = {
    'readOnlyHint': False,
    'openWorldHint': False,
    'destructiveHint': True,
}


class SearchHit(BaseModel):
    id: str
    title: str
    url: str


class SearchResponse(BaseModel):
    results: List[SearchHit]


class FetchResponse(BaseModel):
    id: str
    title: str
    text: str
    url: str
    metadata: Dict[str, str]


def mcp_path() -> str:
    """Build the configured endpoint path."""
    key = settings.MCP_URL_KEY
    return f'/{key}/mcp' if key else '/mcp'


def validate_mcp_configuration() -> None:
    key = settings.MCP_URL_KEY
    if key and not URL_KEY_PATTERN.fullmatch(key):
        raise ValueError(
            'MCP_URL_KEY must contain 24-128 letters, digits, underscores, or hyphens.'
        )
    if not key and not settings.MCP_ALLOW_UNAUTHENTICATED:
        raise ValueError(
            'MCP is locked: configure MCP_URL_KEY, or explicitly set '
            'MCP_ALLOW_UNAUTHENTICATED=true for a trusted private tunnel.'
        )


def _local(value: datetime.datetime) -> datetime.datetime:
    return timezone.localtime(value) if timezone.is_aware(value) else value


def _serialize_log(log: TimeLog, now: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    current = now or timezone.now()
    active = log.end_time is None
    elapsed = current - log.start_time if active else log.end_time - log.start_time
    return {
        'id': log.pk,
        'category': log.category,
        'category_label': CATEGORY_LABELS.get(log.category, log.category),
        'start_time': _local(log.start_time).isoformat(),
        'end_time': _local(log.end_time).isoformat() if log.end_time else None,
        'duration_minutes': max(0, int(elapsed.total_seconds() / 60)),
        'active': active,
        'report': log.note or '',
    }


def _period_start(days: int) -> datetime.datetime:
    local_now = _local(timezone.now())
    return local_now.replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(
        days=days - 1
    )


def _validate_range(days: int, limit: Optional[int] = None) -> None:
    if not 1 <= days <= 3650:
        raise ValueError('days must be between 1 and 3650')
    if limit is not None and not 1 <= limit <= 200:
        raise ValueError('limit must be between 1 and 200')


def get_tracker_status() -> Dict[str, Any]:
    """Return the active task plus today's and this week's study progress."""
    now = timezone.now()
    local_now = _local(now)
    today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - datetime.timedelta(days=(today_start.weekday() + 1) % 7)
    completed = TimeLog.objects.filter(end_time__isnull=False)
    today_logs = list(completed.filter(start_time__gte=today_start))
    week_logs = list(completed.filter(start_time__gte=week_start))
    active = TimeLog.objects.filter(end_time__isnull=True).order_by('start_time').first()
    return {
        'server_time': local_now.isoformat(),
        'active_task': _serialize_log(active, now) if active else None,
        'today': {
            'minutes': sum(log.duration_minutes for log in today_logs),
            'sessions': len(today_logs),
            'target_minutes': settings.TRACKER_DAILY_TARGET_MINUTES,
        },
        'week': {
            'minutes': sum(log.duration_minutes for log in week_logs),
            'sessions': len(week_logs),
            'target_minutes': settings.TRACKER_WEEKLY_TARGET_MINUTES,
        },
        'categories': [
            {'id': value, 'label': label}
            for value, label in TimeLog.CATEGORY_CHOICES
        ],
        'rules': {
            'minimum_session_minutes': 25,
            'maximum_session_hours': 6,
        },
    }


def list_recent_sessions(days: int = 7, limit: int = 50) -> Dict[str, Any]:
    """List completed study sessions in a recent time window."""
    _validate_range(days, limit)
    logs = TimeLog.objects.filter(
        start_time__gte=_period_start(days),
        end_time__isnull=False,
    ).order_by('-start_time')[:limit]
    items = [_serialize_log(log) for log in logs]
    return {'days': days, 'count': len(items), 'sessions': items}


def get_study_summary(days: int = 7) -> Dict[str, Any]:
    """Aggregate completed study time by category and day."""
    _validate_range(days)
    logs = list(TimeLog.objects.filter(
        start_time__gte=_period_start(days),
        end_time__isnull=False,
    ).order_by('-start_time'))
    by_category: Dict[str, int] = {}
    by_day: Dict[str, int] = {}
    total = 0
    for log in logs:
        minutes = log.duration_minutes
        total += minutes
        label = CATEGORY_LABELS.get(log.category, log.category)
        by_category[label] = by_category.get(label, 0) + minutes
        day = _local(log.start_time).date().isoformat()
        by_day[day] = by_day.get(day, 0) + minutes
    return {
        'days': days,
        'total_minutes': total,
        'total_hours': round(total / 60, 2),
        'session_count': len(logs),
        'average_minutes': int(total / len(logs)) if logs else 0,
        'category_totals': [
            {'name': name, 'minutes': minutes}
            for name, minutes in sorted(by_category.items(), key=lambda item: item[1], reverse=True)
        ],
        'daily_totals': [
            {'date': day, 'minutes': minutes}
            for day, minutes in sorted(by_day.items(), reverse=True)
        ],
    }


def _discard_stale_active(now: datetime.datetime) -> bool:
    active = TimeLog.objects.filter(end_time__isnull=True).order_by('start_time').first()
    if active and now - active.start_time > MAX_TASK_DURATION:
        active.delete()
        return True
    return False


def start_task(category: str) -> Dict[str, Any]:
    """Start one study task. Category must be math, english, major, or training."""
    if category not in VALID_CATEGORIES:
        raise ValueError(f'Invalid category. Allowed values: {sorted(VALID_CATEGORIES)}')
    now = timezone.now()
    with transaction.atomic():
        stale_discarded = _discard_stale_active(now)
        active = TimeLog.objects.filter(end_time__isnull=True).order_by('start_time').first()
        if active:
            raise ValueError(
                f'{CATEGORY_LABELS.get(active.category, active.category)} is already running '
                f'(session {active.pk}). Stop it before starting another task.'
            )
        log = TimeLog.objects.create(category=category, start_time=now)
    return {
        'status': 'started',
        'stale_task_discarded': stale_discarded,
        'task': _serialize_log(log, now),
    }


def stop_task(report: str) -> Dict[str, Any]:
    """End the active task and save the supplied completion summary/report."""
    report = report.strip()
    if not report:
        raise ValueError('report is required when ending a task')
    if len(report) > MAX_REPORT_LENGTH:
        raise ValueError(f'report must not exceed {MAX_REPORT_LENGTH} characters')
    now = timezone.now()
    with transaction.atomic():
        stale_discarded = _discard_stale_active(now)
        active = TimeLog.objects.filter(end_time__isnull=True).order_by('start_time').first()
        if not active:
            suffix = ' The stale task exceeded 6 hours and was discarded.' if stale_discarded else ''
            raise ValueError(f'No active task.{suffix}')
        duration_minutes = int((now - active.start_time).total_seconds() / 60)
        task = _serialize_log(active, now)
        if duration_minutes < 25:
            active.delete()
            return {
                'status': 'discarded',
                'reason': 'Session was shorter than the 25-minute minimum.',
                'duration_minutes': duration_minutes,
                'task': task,
            }
        active.end_time = now
        active.note = report
        active.save(update_fields=['end_time', 'note'])
    return {'status': 'completed', 'task': _serialize_log(active, now)}


def search(query: str) -> Dict[str, List[Dict[str, str]]]:
    """Search tracker knowledge. This exact shape enables ChatGPT knowledge retrieval."""
    query = query.strip()
    results = [
        {'id': 'status:current', 'title': '当前任务与目标进度', 'url': ''},
        {'id': 'summary:7', 'title': '最近 7 天学习汇总', 'url': ''},
        {'id': 'summary:30', 'title': '最近 30 天学习汇总', 'url': ''},
    ]
    logs = TimeLog.objects.filter(end_time__isnull=False)
    if query:
        category_ids = [
            key for key, label in CATEGORY_LABELS.items()
            if query.lower() in key.lower() or query in label
        ]
        logs = logs.filter(Q(note__icontains=query) | Q(category__in=category_ids))
    for log in logs.order_by('-start_time')[:17]:
        local_start = _local(log.start_time)
        results.append({
            'id': f'session:{log.pk}',
            'title': (
                f'{local_start:%Y-%m-%d %H:%M} '
                f'{CATEGORY_LABELS.get(log.category, log.category)} {log.duration_minutes} 分钟'
            ),
            'url': '',
        })
    return {'results': results[:20]}


def fetch(id: str) -> Dict[str, Any]:
    """Fetch one result returned by search using the required ChatGPT connector shape."""
    if id == 'status:current':
        payload = get_tracker_status()
        title = '当前任务与目标进度'
    elif id.startswith('summary:'):
        try:
            days = int(id.split(':', 1)[1])
        except ValueError as exc:
            raise ValueError('Invalid summary id') from exc
        payload = get_study_summary(days)
        title = f'最近 {days} 天学习汇总'
    elif id.startswith('session:'):
        try:
            pk = int(id.split(':', 1)[1])
            log = TimeLog.objects.get(pk=pk, end_time__isnull=False)
        except (ValueError, TimeLog.DoesNotExist) as exc:
            raise ValueError('Session not found') from exc
        payload = _serialize_log(log)
        title = f"{payload['start_time']} {payload['category_label']}"
    else:
        raise ValueError('Unknown document id')
    return {
        'id': id,
        'title': title,
        'text': json.dumps(payload, ensure_ascii=False, indent=2),
        'url': '',
        'metadata': {'source': 'jkxx-study-tracker'},
    }


async def _mcp_search(query: str) -> SearchResponse:
    """Search study records and tracker summaries."""
    payload = await sync_to_async(search, thread_sensitive=True)(query)
    return SearchResponse.model_validate(payload)


async def _mcp_fetch(id: str) -> FetchResponse:
    """Fetch a tracker document returned by search."""
    payload = await sync_to_async(fetch, thread_sensitive=True)(id)
    return FetchResponse.model_validate(payload)


async def _mcp_get_tracker_status() -> Dict[str, Any]:
    """Get the active task and today's and this week's progress."""
    return await sync_to_async(get_tracker_status, thread_sensitive=True)()


async def _mcp_list_recent_sessions(days: int = 7, limit: int = 50) -> Dict[str, Any]:
    """List completed sessions from the requested number of recent days."""
    return await sync_to_async(list_recent_sessions, thread_sensitive=True)(days, limit)


async def _mcp_get_study_summary(days: int = 7) -> Dict[str, Any]:
    """Summarize completed study sessions by category and date."""
    return await sync_to_async(get_study_summary, thread_sensitive=True)(days)


async def _mcp_start_task(category: str) -> Dict[str, Any]:
    """Start one task in math, english, major, or training."""
    return await sync_to_async(start_task, thread_sensitive=True)(category)


async def _mcp_stop_task(report: str) -> Dict[str, Any]:
    """End the active task and save its completion summary/report."""
    return await sync_to_async(stop_task, thread_sensitive=True)(report)


def create_mcp_server() -> FastMCP:
    """Build a stateless MCP server suitable for ChatGPT and other HTTP clients."""
    server = FastMCP(
        name='jkxx Study Tracker',
        instructions=(
            '查询学习记录和目标进度；按用户明确意图开启任务；结束任务前收集本次总结报告。'
            '任务分类仅可使用 math、english、major、training。'
        ),
        host=settings.MCP_HOST,
        port=settings.MCP_PORT,
        streamable_http_path=mcp_path(),
        stateless_http=True,
        json_response=True,
    )
    server.tool(name='search', annotations=READ_ONLY)(_mcp_search)
    server.tool(name='fetch', annotations=READ_ONLY)(_mcp_fetch)
    server.tool(name='get_tracker_status', annotations=READ_ONLY)(_mcp_get_tracker_status)
    server.tool(name='list_recent_sessions', annotations=READ_ONLY)(_mcp_list_recent_sessions)
    server.tool(name='get_study_summary', annotations=READ_ONLY)(_mcp_get_study_summary)
    server.tool(name='start_task', annotations=BOUNDED_WRITE)(_mcp_start_task)
    server.tool(name='stop_task', annotations=BOUNDED_DESTRUCTIVE_WRITE)(_mcp_stop_task)
    return server


mcp = create_mcp_server()


def run_mcp_server() -> None:
    """Run MCP without access logs, which would otherwise expose the URL key."""
    uvicorn.run(
        mcp.streamable_http_app(),
        host=mcp.settings.host,
        port=mcp.settings.port,
        log_level=mcp.settings.log_level.lower(),
        access_log=False,
    )


if __name__ == '__main__':
    validate_mcp_configuration()
    run_mcp_server()
