from __future__ import annotations

import datetime
import hashlib
import random

from django.db import transaction
from django.db.models import OuterRef, Q, Subquery
from django.http import Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Question, QuestionAttempt, SignalFormulaMastery
from .analog_selected import manifest as analog_manifest
from .circuit_selected import manifest as circuit_manifest
from .communication_selected import manifest as communication_manifest
from .digital_selected import manifest as digital_manifest
from .four_subject_formula_library import (
    CYCLE as FOUR_CYCLE,
    DEFAULT_WEAK_KEYS as FOUR_DEFAULT_WEAK_KEYS,
    FORMULA_BY_KEY as FOUR_FORMULA_BY_KEY,
    FORMULA_COUNTS as FOUR_FORMULA_COUNTS,
    FORMULA_LIBRARY as FOUR_FORMULA_LIBRARY,
)
from .signal_formula_library import (
    CYCLE,
    FORMULA_BY_KEY,
    FORMULA_LIBRARY,
    FOURIER_DAILY_KEYS,
    START_DATE,
)
from .signal_selected import manifest as signal_manifest
from .views import request_workspace


START = datetime.date.fromisoformat(START_DATE)
DEFAULT_WEAK_KEYS = (
    "C2_right_exponential",
    "C3_frequency_shift",
    "E4_unilateral_z",
)

FOUR_MANIFESTS = {
    "circuit": circuit_manifest,
    "analog": analog_manifest,
    "digital": digital_manifest,
    "communication": communication_manifest,
}


def _formula_payload(entry, mastery=None):
    return {
        **entry,
        "formulas": list(entry["formulas"]),
        "tags": list(entry["tags"]),
        "mastery": None if mastery is None else {
            "grade": mastery.grade,
            "last_reviewed_on": mastery.last_reviewed_on,
            "next_review_on": mastery.next_review_on,
            "due_dates": mastery.due_dates,
            "review_count": mastery.review_count,
        },
    }


def _review_date(request):
    value = request.query_params.get("date", "").strip()
    if not value:
        return timezone.localdate()
    try:
        result = datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise Http404("Invalid review date") from exc
    if result < START:
        raise Http404("Formula review starts on 2026-10-30")
    return result


def _rotated(entries, seed):
    result = list(entries)
    random.Random(seed).shuffle(result)
    return result


def _daily_formula_selection(review_date, masteries):
    cycle_index = (review_date - START).days % len(CYCLE)
    plan = CYCLE[cycle_index]
    due_keys = []
    date_text = review_date.isoformat()
    for key, mastery in masteries.items():
        if mastery.next_review_on and mastery.next_review_on <= review_date:
            due_keys.append(key)
        elif date_text in mastery.due_dates:
            due_keys.append(key)

    topic_entries = [entry for entry in FORMULA_LIBRARY if entry["section"] in plan["sections"]]
    fourier_entries = [FORMULA_BY_KEY[key] for key in FOURIER_DAILY_KEYS]
    seed = review_date.toordinal()
    recall = []

    # Every day starts with at least two Fourier pairs or properties.
    due_fourier = [FORMULA_BY_KEY[key] for key in due_keys if key in FOURIER_DAILY_KEYS]
    for entry in [*_rotated(due_fourier, seed), *_rotated(fourier_entries, seed + 11)]:
        if entry not in recall:
            recall.append(entry)
        if len([item for item in recall if item["key"] in FOURIER_DAILY_KEYS]) >= 2:
            break

    due_entries = [FORMULA_BY_KEY[key] for key in due_keys if key in FORMULA_BY_KEY]
    for entry in [*_rotated(due_entries, seed + 17), *_rotated(topic_entries, seed + 23)]:
        if entry not in recall:
            recall.append(entry)
        if len(recall) == 5:
            break

    if len(recall) < 5:
        for entry in _rotated(FORMULA_LIBRARY, seed + 29):
            if entry not in recall:
                recall.append(entry)
            if len(recall) == 5:
                break

    core = []
    for entry in [*_rotated(due_entries, seed + 31), *_rotated(topic_entries, seed + 37)]:
        if entry not in core:
            core.append(entry)
        if len(core) == 5:
            break

    weak = [
        FORMULA_BY_KEY[key]
        for key, mastery in masteries.items()
        if mastery.grade == "C" and key in FORMULA_BY_KEY
    ]
    if not weak:
        weak = [FORMULA_BY_KEY[key] for key in DEFAULT_WEAK_KEYS]

    return cycle_index, plan, recall, core, weak[:3], due_keys


def _four_daily_formula_selection(review_date, masteries):
    cycle_index = (review_date - START).days % len(FOUR_CYCLE)
    plan = FOUR_CYCLE[cycle_index]
    subject = plan["subject"]
    date_text = review_date.isoformat()
    due_keys = [
        key for key, mastery in masteries.items()
        if key in FOUR_FORMULA_BY_KEY and (
            (mastery.next_review_on and mastery.next_review_on <= review_date)
            or date_text in mastery.due_dates
        )
    ]
    due_entries = [FOUR_FORMULA_BY_KEY[key] for key in due_keys]
    current = [entry for entry in FOUR_FORMULA_LIBRARY if entry["subject"] == subject]
    cross = [entry for entry in FOUR_FORMULA_LIBRARY if entry["subject"] != subject]
    seed = review_date.toordinal()

    # Three current-subject items, one cross-subject item, then one historical
    # weak/due item (or a documented default weak point when no history exists).
    recall = []
    for entry in [
        *_rotated([item for item in due_entries if item["subject"] == subject], seed + 3),
        *_rotated(current, seed + 5),
    ]:
        if entry not in recall:
            recall.append(entry)
        if len(recall) == 3:
            break
    cross_candidates = [item for item in due_entries if item["subject"] != subject]
    for entry in [*_rotated(cross_candidates, seed + 7), *_rotated(cross, seed + 11)]:
        if entry not in recall:
            recall.append(entry)
            break
    historical = [
        FOUR_FORMULA_BY_KEY[key]
        for key, mastery in masteries.items()
        if key in FOUR_FORMULA_BY_KEY and mastery.grade == "C"
    ]
    defaults = [FOUR_FORMULA_BY_KEY[key] for key in FOUR_DEFAULT_WEAK_KEYS]
    for entry in [*_rotated(historical, seed + 13), *defaults, *_rotated(current, seed + 17)]:
        if entry not in recall:
            recall.append(entry)
            break

    core = []
    for entry in [
        *_rotated([item for item in due_entries if item["subject"] == subject], seed + 19),
        *_rotated(current, seed + 23),
    ]:
        if entry not in core:
            core.append(entry)
        if len(core) == 5:
            break

    weak = historical
    if not weak:
        weak = [entry for entry in defaults if entry["subject"] == subject]
        weak.extend(entry for entry in _rotated(current, seed + 29) if entry not in weak)
    return cycle_index, plan, recall, core, weak[:3], due_keys


def _application_questions(user, review_date, buckets):
    data = signal_manifest()
    records = [row for row in data["questions"] if row["bucket"] in buckets]
    records_by_uuid = {row["uuid"]: row for row in records}
    latest = QuestionAttempt.objects.filter(
        user=user,
        question_id=OuterRef("pk"),
    ).order_by("-created_at", "-pk")
    questions = Question.objects.filter(
        document__workspace="ei",
        is_practiceable=True,
        uuid__in=records_by_uuid,
    ).annotate(latest_result=Subquery(latest.values("result")[:1])).select_related("document")

    rows = []
    for question in questions:
        record = records_by_uuid[str(question.uuid)]
        if question.fingerprint != record["fingerprint"]:
            continue
        state = (
            "mastered" if question.latest_result in {"done", "correct"}
            else "review" if question.latest_result == "review"
            else "unattempted"
        )
        stable = hashlib.sha256(f"{review_date}:{question.uuid}".encode()).hexdigest()
        rows.append((question, record, state, stable))

    state_rank = {"review": 0, "unattempted": 1, "mastered": 2}
    basic = sorted(
        rows,
        key=lambda row: (
            state_rank[row[2]],
            0 if row[1]["tier"] in {"foundation", "core"} else 1,
            0 if row[1]["kind"] == "calculation" else 1,
            row[3],
        ),
    )
    first = basic[0] if basic else None
    comprehensive = sorted(
        [row for row in rows if first is None or row[0].pk != first[0].pk],
        key=lambda row: (
            state_rank[row[2]],
            0 if row[1].get(data.get("combination_key", "combined_z_initial")) else 1,
            0 if row[1]["tier"] in {"core", "advanced"} else 1,
            row[3],
        ),
    )
    selected = [row for row in (first, comprehensive[0] if comprehensive else None) if row]
    result = []
    for index, (question, record, state, _stable) in enumerate(selected):
        result.append({
            "kind": "基础题" if index == 0 else "综合题",
            "uuid": str(question.uuid),
            "label": question.display_label or question.source_label,
            "book": question.document.display_title or question.document.title,
            "bucket": record["bucket"],
            "tier": record["tier"],
            "state": state,
            "reason": record["reason"],
            "route": f"/practice/{question.uuid}?collection=signal_selected&bucket={record['bucket']}",
        })
    return result


def _four_application_questions(user, review_date, plan):
    data = FOUR_MANIFESTS[plan["subject"]]()
    records = data["questions"]
    records_by_uuid = {row["uuid"]: row for row in records}
    latest = QuestionAttempt.objects.filter(
        user=user,
        question_id=OuterRef("pk"),
    ).order_by("-created_at", "-pk")
    questions = Question.objects.filter(
        document__workspace="ei",
        is_practiceable=True,
        uuid__in=records_by_uuid,
    ).annotate(latest_result=Subquery(latest.values("result")[:1])).select_related("document")
    rows = []
    for question in questions:
        record = records_by_uuid[str(question.uuid)]
        if question.fingerprint != record["fingerprint"]:
            continue
        state = (
            "mastered" if question.latest_result in {"done", "correct"}
            else "review" if question.latest_result == "review"
            else "unattempted"
        )
        stable = hashlib.sha256(f"four:{review_date}:{question.uuid}".encode()).hexdigest()
        rows.append((question, record, state, stable))
    state_rank = {"review": 0, "unattempted": 1, "mastered": 2}
    ordered = sorted(rows, key=lambda row: (
        state_rank[row[2]],
        0 if row[1].get("tier") in {"foundation", "core"} else 1,
        0 if row[1].get("kind") == "calculation" else 1,
        row[3],
    ))
    result = []
    for index, (question, record, state, _stable) in enumerate(ordered[:2]):
        reason = record.get("reason", [])
        if isinstance(reason, str):
            reason = [reason]
        result.append({
            "kind": "基础题" if index == 0 else "综合题",
            "uuid": str(question.uuid),
            "label": question.display_label or question.source_label,
            "book": question.document.display_title or question.document.title,
            "bucket": record.get("bucket", ""),
            "tier": record.get("tier", "core"),
            "state": state,
            "reason": reason,
            "route": f"/practice/{question.uuid}?collection={plan['collection']}&bucket={record.get('bucket', '')}",
        })
    return result


class SignalFormulaReviewView(APIView):
    """Daily deterministic 892 formula review backed by the canonical signal collection."""

    def get(self, request):
        if request_workspace(request) != "ei":
            raise Http404
        review_date = _review_date(request)
        track = request.query_params.get("track", "signal").strip().lower()
        if track not in {"signal", "four"}:
            raise Http404("Unknown formula review track")
        masteries = {
            item.formula_key: item
            for item in SignalFormulaMastery.objects.filter(user=request.user)
        }
        if track == "four":
            cycle_index, plan, recall, core, weak, due_keys = _four_daily_formula_selection(
                review_date, masteries,
            )
            day_number = (review_date - START).days + 1
            applications = _four_application_questions(request.user, review_date, plan)
            return Response({
                "track": "four",
                "track_title": "四科循环",
                "date": review_date,
                "day_number": day_number,
                "cycle_day": cycle_index + 1,
                "title": f"892 四科公式循环｜第 {day_number} 日｜今日：{plan['title']}",
                "topic": plan["title"],
                "subject": plan["subject"],
                "return_route": plan["route"],
                "duration_minutes": 25,
                "recall": [_formula_payload(entry, masteries.get(entry["key"])) for entry in recall],
                "core": [_formula_payload(entry, masteries.get(entry["key"])) for entry in core],
                "applications": applications,
                "mistakes": list(plan["mistakes"]),
                "weak_review": [_formula_payload(entry, masteries.get(entry["key"])) for entry in weak],
                "due_keys": due_keys,
                "has_history": any(key in FOUR_FORMULA_BY_KEY for key in masteries),
                "formula_count": len(FOUR_FORMULA_LIBRARY),
                "formula_counts": FOUR_FORMULA_COUNTS,
                "answer_policy": "默写答案逐题揭示；应用题复用今日科目的严选原题和既有答题记录。",
            })
        cycle_index, plan, recall, core, weak, due_keys = _daily_formula_selection(
            review_date, masteries,
        )
        day_number = (review_date - START).days + 1
        applications = _application_questions(request.user, review_date, plan["buckets"])
        return Response({
            "track": "signal",
            "track_title": "信号循环",
            "date": review_date,
            "day_number": day_number,
            "cycle_day": cycle_index + 1,
            "title": f"892 信号与系统｜第 {day_number} 天｜{plan['title']}",
            "topic": plan["title"],
            "subject": "signal",
            "return_route": "/signal-selected",
            "duration_minutes": 20,
            "recall": [_formula_payload(entry, masteries.get(entry["key"])) for entry in recall],
            "core": [_formula_payload(entry, masteries.get(entry["key"])) for entry in core],
            "applications": applications,
            "mistakes": list(plan["mistakes"]),
            "weak_review": [_formula_payload(entry, masteries.get(entry["key"])) for entry in weak],
            "due_keys": due_keys,
            "has_history": bool(masteries),
            "formula_count": len(FORMULA_LIBRARY),
            "answer_policy": "默写答案逐题揭示；严选应用题沿用原题答案与原答题记录。",
        })

    @transaction.atomic
    def post(self, request):
        if request_workspace(request) != "ei":
            raise Http404
        formula_key = str(request.data.get("formula_key", "")).strip()
        grade = str(request.data.get("grade", "")).upper().strip()
        formula_bank = FORMULA_BY_KEY if formula_key in FORMULA_BY_KEY else FOUR_FORMULA_BY_KEY
        if formula_key not in formula_bank:
            return Response({"detail": "Unknown formula"}, status=status.HTTP_400_BAD_REQUEST)
        if grade not in {"A", "B", "C"}:
            return Response({"detail": "Grade must be A, B, or C"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            review_date = datetime.date.fromisoformat(
                str(request.data.get("date") or timezone.localdate().isoformat()),
            )
        except ValueError:
            return Response({"detail": "Invalid review date"}, status=status.HTTP_400_BAD_REQUEST)
        if review_date < START:
            return Response({"detail": "Review date predates the formula plan"}, status=status.HTTP_400_BAD_REQUEST)

        mastery, created = SignalFormulaMastery.objects.select_for_update().get_or_create(
            user=request.user,
            formula_key=formula_key,
            defaults={
                "grade": grade,
                "last_reviewed_on": review_date,
                "review_count": 0,
            },
        )
        future_due = {
            datetime.date.fromisoformat(value)
            for value in mastery.due_dates
            if datetime.date.fromisoformat(value) > review_date
        }
        if grade == "C":
            future_due.update(review_date + datetime.timedelta(days=days) for days in (1, 3, 7))
        elif grade == "B":
            future_due.add(review_date + datetime.timedelta(days=4))
        elif formula_key in FOUR_FORMULA_BY_KEY:
            future_due.update(review_date + datetime.timedelta(days=days) for days in (4, 7))
        else:
            # A extends with repeated successful reviews while keeping explicit future C checks.
            interval = min(28, 12 + max(0, mastery.review_count - 1) * 4)
            future_due.add(review_date + datetime.timedelta(days=interval))

        mastery.grade = grade
        mastery.last_reviewed_on = review_date
        mastery.due_dates = [value.isoformat() for value in sorted(future_due)]
        mastery.next_review_on = min(future_due) if future_due else None
        mastery.review_count += 1
        mastery.save(update_fields=(
            "grade", "last_reviewed_on", "due_dates", "next_review_on", "review_count", "updated_at",
        ))
        return Response(_formula_payload(formula_bank[formula_key], mastery))
