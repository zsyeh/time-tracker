from __future__ import annotations

import datetime
import math
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Count, OuterRef, Subquery
from django.db.models.functions import TruncDate
from django.http import Http404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Question, QuestionAttempt
from .views import request_workspace


VALID_RESULTS = ("done", "correct", "review")
ALLOWED_RANGES = (7, 14, 30, 50, 90)
DEFAULT_DEADLINE = datetime.date(2026, 11, 22)
PROJECTS = {
    "drill": {
        "label": "Drill 数学",
        "question_target": 690,
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


def _forecast(label, average, completed, target, remaining, days_remaining, required_daily):
    projected_added = round(average * days_remaining)
    projected_total = completed + projected_added
    shortfall = max(target - projected_total, 0)
    return {
        "label": label,
        "average": round(average, 1),
        "projected_added": projected_added,
        "projected_total": projected_total,
        "projected_toward_goal": min(target, projected_total),
        "shortfall": shortfall,
        "on_track": remaining == 0 or (days_remaining > 0 and average >= required_daily),
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

        tz = ZoneInfo(settings.TIME_ZONE)
        today = timezone.localdate()
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

        latest = QuestionAttempt.objects.filter(
            user=request.user,
            question_id=OuterRef("pk"),
        ).order_by("-created_at", "-pk")
        eligible = Question.objects.filter(
            document__workspace=workspace,
            is_practiceable=True,
        )
        completed_distinct = eligible.annotate(
            latest_result=Subquery(latest.values("result")[:1]),
        ).filter(latest_result__in=VALID_RESULTS).count()
        available_questions = eligible.count()
        question_target = project["question_target"]
        remaining = max(question_target - completed_distinct, 0)

        graph_start_at, _ = _date_bounds(graph_start, today + datetime.timedelta(days=1), tz)
        period = base.filter(created_at__gte=graph_start_at, created_at__lt=tomorrow_at).aggregate(
            submissions=Count("id"),
            different_questions=Count("question_id", distinct=True),
        )

        days_remaining = max((deadline - today).days + 1, 0)
        required_daily = math.ceil(remaining / days_remaining) if remaining and days_remaining else (0 if not remaining else None)
        average7 = last7 / 7
        average14 = last14 / 14
        scenarios = [
            _forecast("最近7天速度", average7, completed_distinct, question_target, remaining, days_remaining, required_daily or 0),
            _forecast("最近14天速度", average14, completed_distinct, question_target, remaining, days_remaining, required_daily or 0),
            _forecast("当前目标速度", daily_target, completed_distinct, question_target, remaining, days_remaining, required_daily or 0),
        ]

        return Response({
            "workspace": workspace,
            "project_label": project["label"],
            "timezone": settings.TIME_ZONE,
            "today": today,
            "range_days": range_days,
            "allowed_ranges": ALLOWED_RANGES,
            "daily_target": daily_target,
            "target_options": project["targets"],
            "question_target": question_target,
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
            },
            "comparison_windows": {
                "last7": {"start": last7_start, "end": last7_end},
                "previous7": {"start": previous7_start, "end": previous7_end},
                "excludes_today": True,
            },
            "prediction": {
                "deadline": deadline,
                "days_remaining_including_today": days_remaining,
                "remaining_determinable": True,
                "remaining": remaining,
                "required_daily": required_daily,
                "scenarios": scenarios,
                "notice": "按现有速度估算，不构成完成承诺。",
            },
        })
