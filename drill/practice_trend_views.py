from __future__ import annotations

import datetime
import math
from zoneinfo import ZoneInfo
from types import SimpleNamespace

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import Http404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import QuestionAttempt
from .views import request_workspace, workspace_questions
from .selected_collections import filter_collection
from .exam_types import type_group


VALID_RESULTS = ("done", "correct", "review")
ALLOWED_RANGES = (7, 14, 30, 50, 90)
DEFAULT_DEADLINE = datetime.date(2026, 11, 21)
ORIGINAL_DEADLINE = datetime.date(2026, 11, 22)
PROJECTS = {
    "drill": {
        "label": "Drill 数学",
        "targets": {"minimum": 21, "standard": 24, "sprint": 29},
    },
    "ei": {
        "label": "EI 专业课",
        "question_target": 307,
        "targets": {"minimum": 9, "standard": 11, "sprint": 13},
    },
}


def _date_bounds(first_day, day_after_last, tz):
    return (
        timezone.make_aware(datetime.datetime.combine(first_day, datetime.time.min), tz),
        timezone.make_aware(datetime.datetime.combine(day_after_last, datetime.time.min), tz),
    )


def _parse_int(value, default, *, minimum, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if minimum <= parsed <= maximum else default


def _parse_deadline(value):
    if not value:
        return DEFAULT_DEADLINE
    try:
        parsed = datetime.date.fromisoformat(value)
    except ValueError:
        return DEFAULT_DEADLINE
    return parsed


def _sum_days(counts, first_day, last_day):
    if last_day < first_day:
        return 0
    return sum(
        counts.get(first_day + datetime.timedelta(days=offset), 0)
        for offset in range((last_day - first_day).days + 1)
    )


def _coverage_history(questions, user, tz, today):
    """Replay still-existing evidence; reset subtracts coverage and Undo deletes evidence.

    Repeated valid submissions change workload, never coverage. The initial state
    before a window is retained by replaying older evidence as well.
    """
    by_id = {row['pk']: row for row in questions}
    states = {}
    daily = {}
    first_day = None
    events = QuestionAttempt.objects.filter(user=user, question_id__in=by_id).order_by(
        'created_at', 'pk',
    ).values_list('question_id', 'result', 'created_at').iterator(chunk_size=2000)
    for question_id, result, created_at in events:
        day = timezone.localtime(created_at, tz).date()
        before = states.get(question_id) in VALID_RESULTS
        after = result in VALID_RESULTS
        # Current inventory follows the same latest evidence as the heatmap,
        # including imported records with a future timestamp. Such records do
        # not establish observed history or enter historical net-growth rates.
        states[question_id] = result
        if day > today:
            continue
        first_day = min(first_day, day) if first_day else day
        item = daily.setdefault(day, {'net': 0, 'added': 0, 'removed': 0})
        if after != before:
            item['net'] += 1 if after else -1
            item['added' if after else 'removed'] += 1
    groups = {name: {'total': 0, 'covered': 0, 'mastered': 0, 'review': 0, 'remaining': 0}
              for name in ('small', 'large', 'short_answer', 'unknown')}
    for row in questions:
        group = groups[type_group(row['final_question_type'])]
        state = states.get(row['pk'])
        group['total'] += 1
        group['covered'] += state in VALID_RESULTS
        group['mastered'] += state in ('done', 'correct')
        group['review'] += state == 'review'
        group['remaining'] += state not in VALID_RESULTS
    return groups, daily, max((today - first_day).days, 0) if first_day else 0


def _forecast(label, average, completed, target, remaining, deadline, today,
              today_net, *, window_days=None, history_days=0, scope_available=True):
    days_remaining = max((deadline - today).days + 1, 0)
    history_sufficient = window_days is None or history_days >= window_days
    rate = max(average, 0)
    today_capacity = max(rate - today_net, 0) if days_remaining and rate > 0 else 0
    projected_added = math.floor(today_capacity + rate * max(days_remaining - 1, 0) + 1e-9)
    projected_total = completed + projected_added
    if not scope_available:
        status = 'empty_scope'
    elif not remaining:
        status = 'complete'
    elif not days_remaining:
        status = 'past_deadline'
    elif not history_sufficient:
        status = 'insufficient_history'
    elif average <= 0:
        status = 'no_positive_rate'
    else:
        status = 'ready'
    estimate = None
    if status == 'complete':
        estimate = today
    elif status == 'ready':
        estimate = today + datetime.timedelta(days=max(math.ceil((remaining - today_capacity) / rate), 0))
    unavailable = status in ('insufficient_history', 'empty_scope')
    return {
        'label': label, 'average': round(average, 1),
        'window_days': window_days, 'available_history_days': history_days,
        'history_sufficient': history_sufficient, 'status': status,
        'today_net_coverage': today_net, 'today_remaining_capacity': round(today_capacity, 2),
        'projected_added': None if unavailable else projected_added,
        'projected_total': None if unavailable else projected_total,
        'projected_toward_goal': None if unavailable else min(target, projected_total),
        'shortfall': None if unavailable else max(target - projected_total, 0),
        'on_track': None if unavailable else (status == 'complete' or (status == 'ready' and projected_total >= target)),
        'estimated_completion_date': estimate,
    }


class PracticeTrendView(APIView):
    """Per-user, per-workspace daily practice trend using saved attempts only."""

    def get(self, request):
        workspace = request_workspace(request)
        if workspace not in PROJECTS:
            raise Http404
        project = PROJECTS[workspace]
        range_days = _parse_int(
            request.query_params.get("days"), 30, minimum=min(ALLOWED_RANGES), maximum=max(ALLOWED_RANGES),
        )
        if range_days not in ALLOWED_RANGES:
            range_days = 30
        daily_target = _parse_int(
            request.query_params.get("target"), project["targets"]["standard"], minimum=1, maximum=500,
        )
        deadline = _parse_deadline(request.query_params.get("deadline"))

        tz = ZoneInfo("Asia/Shanghai")
        today = timezone.localdate(timezone=tz)
        graph_start = today - datetime.timedelta(days=range_days - 1)
        query_start = min(graph_start - datetime.timedelta(days=6), today - datetime.timedelta(days=30))
        query_start_at, tomorrow_at = _date_bounds(query_start, today + datetime.timedelta(days=1), tz)

        base = QuestionAttempt.objects.filter(
            user=request.user,
            question__document__workspace=workspace,
            result__in=VALID_RESULTS,
        )
        daily_rows = (
            base.filter(created_at__gte=query_start_at, created_at__lt=tomorrow_at)
            .annotate(day=TruncDate("created_at", tzinfo=tz))
            .values("day")
            .annotate(unique_questions=Count("question_id", distinct=True), submissions=Count("id"))
            .order_by("day")
        )
        daily_counts = {row["day"]: row["unique_questions"] for row in daily_rows}
        daily_submissions = {row["day"]: row["submissions"] for row in daily_rows}

        points = []
        for offset in range(range_days):
            day = graph_start + datetime.timedelta(days=offset)
            rolling_total = _sum_days(daily_counts, day - datetime.timedelta(days=6), day)
            points.append({
                "date": day,
                "count": daily_counts.get(day, 0),
                "submissions": daily_submissions.get(day, 0),
                "moving_average_7": round(rolling_total / 7, 1),
                "target": daily_target,
                "is_today": day == today,
                "is_complete_day": day < today,
            })

        # Comparative windows deliberately exclude the unfinished current day.
        last7_start, last7_end = today - datetime.timedelta(days=7), today - datetime.timedelta(days=1)
        previous7_start, previous7_end = today - datetime.timedelta(days=14), today - datetime.timedelta(days=8)
        last14_start = today - datetime.timedelta(days=14)
        last7 = _sum_days(daily_counts, last7_start, last7_end)
        previous7 = _sum_days(daily_counts, previous7_start, previous7_end)
        last14 = _sum_days(daily_counts, last14_start, last7_end)
        growth_percent = None if previous7 == 0 else round((last7 - previous7) * 100 / previous7, 1)

        active_dates = set(
            base.annotate(day=TruncDate("created_at", tzinfo=tz))
            .values_list("day", flat=True).distinct()
        )
        streak = 0
        cursor = today if today in active_dates else today - datetime.timedelta(days=1)
        while cursor in active_dates:
            streak += 1
            cursor -= datetime.timedelta(days=1)

        eligible = workspace_questions(request).filter(is_practiceable=True)
        if workspace == 'drill':
            # Exactly the selected/all heatmap predicate, not a copied manifest.
            scope_request = SimpleNamespace(query_params={'collection': 'selected'})
            eligible = filter_collection(eligible, scope_request)
        questions = list(eligible.values('pk', 'final_question_type'))
        breakdown, coverage_daily, history_days = _coverage_history(questions, request.user, tz, today)
        completed_distinct = sum(group['covered'] for group in breakdown.values())
        mastered = sum(group['mastered'] for group in breakdown.values())
        review = sum(group['review'] for group in breakdown.values())
        available_questions = len(questions)
        question_target = available_questions if workspace == 'drill' else project['question_target']
        remaining = max(question_target - completed_distinct, 0)
        net_counts = {day: value['net'] for day, value in coverage_daily.items()}
        today_coverage = coverage_daily.get(today, {'net': 0, 'added': 0, 'removed': 0})
        for item in points:
            coverage = coverage_daily.get(item['date'], {'net': 0, 'added': 0, 'removed': 0})
            item.update(net_coverage=coverage['net'], new_coverage=coverage['added'], removed_coverage=coverage['removed'])
        net7 = _sum_days(net_counts, last7_start, last7_end)
        net14 = _sum_days(net_counts, last14_start, last7_end)

        graph_start_at, _ = _date_bounds(graph_start, today + datetime.timedelta(days=1), tz)
        period = base.filter(created_at__gte=graph_start_at, created_at__lt=tomorrow_at).aggregate(
            submissions=Count("id"),
            different_questions=Count("question_id", distinct=True),
        )

        days_remaining = max((deadline - today).days + 1, 0)
        required_daily = math.ceil(remaining / days_remaining) if remaining and days_remaining else (0 if not remaining else None)
        average7 = last7 / 7
        average14 = last14 / 14
        if not available_questions:
            required_daily = None
        for group in breakdown.values():
            group['required_daily'] = (math.ceil(group['remaining'] / days_remaining)
                                       if days_remaining and available_questions else None)
        scenarios = [
            _forecast('最近7天净覆盖速度', net7 / 7, completed_distinct, question_target, remaining,
                      deadline, today, today_coverage['net'], window_days=7, history_days=history_days, scope_available=bool(available_questions)),
            _forecast('最近14天净覆盖速度', net14 / 14, completed_distinct, question_target, remaining,
                      deadline, today, today_coverage['net'], window_days=14, history_days=history_days, scope_available=bool(available_questions)),
        ]


        return Response({
            "workspace": workspace,
            "project_label": project["label"],
            "timezone": "Asia/Shanghai",
            "today": today,
            "range_days": range_days,
            "allowed_ranges": ALLOWED_RANGES,
            "daily_target": daily_target,
            "target_options": project["targets"],
            "question_target": question_target,
            "goal": {
                "metric": "current_coverage", "total": question_target,
                "status": "active" if available_questions else "empty_scope",
                "scope": {"collection": "selected" if workspace == "drill" else "all", "scope": "all"},
                "covered": completed_distinct, "mastered": mastered, "review": review,
                "remaining": remaining, "type_breakdown": breakdown,
                "coverage_percent": round(completed_distinct * 100 / question_target, 1) if question_target else None,
                "mastery_percent": round(mastered * 100 / question_target, 1) if question_target else None,
                "mastery_denominator": "goal_total",
            },
            "available_questions": available_questions,
            "points": points,
            "period": {
                "submissions": period["submissions"] or 0,
                "different_questions": period["different_questions"] or 0,
                "daily_unique_total": sum(item["count"] for item in points),
            },
            "summary": {
                "today": daily_counts.get(today, 0),
                "today_submissions": daily_submissions.get(today, 0),
                "last7": last7,
                "average7": round(average7, 1),
                "last14": last14,
                "average14": round(average14, 1),
                "previous7": previous7,
                "growth_percent": growth_percent,
                "last30": _sum_days(daily_counts, today - datetime.timedelta(days=29), today),
                "streak": streak,
                "target_days_last7": sum(
                    daily_counts.get(last7_start + datetime.timedelta(days=offset), 0) >= daily_target
                    for offset in range(7)
                ),
                "completed_distinct": completed_distinct,
                "remaining": remaining,
                "today_net_coverage": today_coverage['net'],
                "today_new_coverage": today_coverage['added'],
                "today_removed_coverage": today_coverage['removed'],
                "net_coverage_last7": net7, "net_coverage_last14": net14,
            },
            "comparison_windows": {
                "last7": {"start": last7_start, "end": last7_end},
                "previous7": {"start": previous7_start, "end": previous7_end},
                "excludes_today": True,
            },
            "prediction": {
                "deadline": deadline,
                "original_deadline": ORIGINAL_DEADLINE,
                "deadline_passed": deadline < today,
                "forecast_basis": "net_coverage",
                "today_handling": "max(rate - today_net_coverage, 0) + rate * future_complete_days",
                "history_available_days": history_days,
                "days_remaining_including_today": days_remaining,
                "remaining_determinable": bool(available_questions),
                "remaining": remaining,
                "required_daily": required_daily,
                "scenarios": scenarios,
                "notice": "按现有速度估算，不构成完成承诺。",
            },
        })
