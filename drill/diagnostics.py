"""Shared EI/Drill attempt diagnosis and remediation calculations."""

import datetime
from collections import Counter, defaultdict

from django.db import transaction
from django.utils import timezone

from .cockpit import course_for_title
from .models import QuestionAttempt, QuestionAttemptError, QuestionReviewPlan, TopicMastery


DEFAULT_REVIEW_DAYS = [0, 1, 3, 7]
EFFECTIVE_OUTCOMES = {'correct', 'incorrect'}


def infer_stage(user, question, now):
    previous = list(QuestionAttempt.objects.filter(
        user=user, question=question,
    ).exclude(result='reset').exclude(outcome='unknown').order_by('created_at', 'pk'))
    attempt_round = len(previous) + 1
    if not previous:
        return 'first', attempt_round
    previous_day = timezone.localtime(previous[-1].created_at).date()
    current_day = timezone.localtime(now).date()
    if previous_day == current_day:
        return 'same_day_redo', attempt_round
    if previous_day == current_day - datetime.timedelta(days=1):
        return 'next_day_redo', attempt_round
    return 'review', attempt_round


def create_diagnosed_attempt(user, question, data, *, now=None):
    """Create one append-only attempt using the same diagnosis semantics as the question page."""
    now = now or timezone.now()
    training_stage, attempt_round = infer_stage(user, question, now)
    attempt = QuestionAttempt.objects.create(
        user=user,
        question=question,
        result=data['result'],
        confidence=data.get('confidence'),
        note=data.get('note'),
        time_spent_seconds=data.get('time_spent_seconds'),
        started_at=data.get('started_at'),
        outcome=data.get('outcome', 'unknown'),
        knowledge_level=data.get('knowledge_level'),
        method_level=data.get('method_level'),
        execution_level=data.get('execution_level'),
        used_hint=data.get('used_hint'),
        viewed_answer=data.get('viewed_answer'),
        is_independent=data.get('is_independent'),
        judgement_source=data.get('judgement_source', 'unknown'),
        training_stage=training_stage,
        attempt_round=attempt_round,
        correction_note='',
        knowledge_note='',
        first_step_note='',
        submission_key=data.get('submission_key'),
        created_at=now,
    )
    primary_error = data.get('primary_error')
    QuestionAttemptError.objects.bulk_create([
        QuestionAttemptError(attempt=attempt, code=code, is_primary=code == primary_error)
        for code in data.get('error_codes', [])
    ])
    update_review_plan(attempt)
    return attempt


def update_review_plan(attempt):
    """Update D0/D1/D3/D7 without rewriting any historical attempt."""
    if attempt.outcome not in EFFECTIVE_OUTCOMES:
        return None
    failed_independent = not (attempt.outcome == 'correct' and attempt.is_independent is True)
    plan = QuestionReviewPlan.objects.select_for_update().filter(
        user=attempt.user, question=attempt.question,
    ).first()
    if plan is None and not failed_independent:
        return None
    if plan is None:
        plan = QuestionReviewPlan.objects.create(
            user=attempt.user, question=attempt.question,
            schedule_days=DEFAULT_REVIEW_DAYS, step=0, status='active',
        )
    schedule = plan.schedule_days or DEFAULT_REVIEW_DAYS
    plan.schedule_days = schedule
    plan.last_attempt = attempt
    if failed_independent:
        plan.status = 'active'
        # A failed review remains at its current checkpoint.
        delay = schedule[min(plan.step, len(schedule) - 1)]
        plan.next_review_at = attempt.created_at + datetime.timedelta(days=delay)
    else:
        plan.step += 1
        if plan.step >= len(schedule):
            plan.status = 'completed'
            plan.next_review_at = None
        else:
            plan.status = 'active'
            plan.next_review_at = attempt.created_at + datetime.timedelta(days=schedule[plan.step])
    plan.save()
    return plan


def rebuild_review_plan(user, question):
    """Rebuild mutable scheduling state from immutable remaining attempts."""
    QuestionReviewPlan.objects.filter(user=user, question=question).delete()
    plan = None
    attempts = QuestionAttempt.objects.filter(
        user=user, question=question,
    ).exclude(result='reset').order_by('created_at', 'pk')
    for attempt in attempts:
        plan = update_review_plan(attempt) or plan
    return plan


def rebuild_topic_mastery(user, question):
    """Recompute system evidence while preserving an explicit manual grade."""
    if not question.similarity_topic_id:
        return None
    mastery = TopicMastery.objects.select_for_update().filter(
        user=user, topic_id=question.similarity_topic_id,
    ).first()
    if mastery is None:
        return None
    from .cockpit import apply_mastery_grade

    mastery.system_grade = 'D'
    mastery.grade = mastery.manual_grade or 'D'
    mastery.last_reviewed_at = None
    mastery.next_review_at = None
    mastery.correct_streak = 0
    mastery.independent_last_time = None
    mastery.retention_score = {'A': 100, 'B': 72, 'C': 35, 'D': 0}[mastery.grade]
    mastery.review_count = 0
    attempts = QuestionAttempt.objects.filter(
        user=user,
        question__similarity_topic_id=question.similarity_topic_id,
        question__document__workspace='ei',
        result__in=('correct', 'review'),
    ).order_by('created_at', 'pk')
    for attempt in attempts:
        if attempt.result == 'review':
            grade = 'C'
        elif mastery.system_grade == 'D':
            grade = 'C'
        elif mastery.system_grade == 'C':
            grade = 'B'
        elif mastery.system_grade == 'B' and mastery.correct_streak >= 1:
            grade = 'A'
        else:
            grade = mastery.system_grade
        apply_mastery_grade(
            mastery, grade, independent=attempt.result == 'correct',
            reviewed=True, now=attempt.created_at,
        )
    mastery.grade = mastery.manual_grade or mastery.system_grade
    mastery.save()
    return mastery


def attempt_payload(attempt):
    errors = list(attempt.error_tags.order_by('-is_primary', 'code').values('code', 'is_primary'))
    return {
        'id': attempt.pk,
        'result': attempt.result,
        'outcome': attempt.outcome,
        'knowledge_level': attempt.knowledge_level,
        'method_level': attempt.method_level,
        'execution_level': attempt.execution_level,
        'used_hint': attempt.used_hint,
        'viewed_answer': attempt.viewed_answer,
        'is_independent': attempt.is_independent,
        'judgement_source': attempt.judgement_source,
        'training_stage': attempt.training_stage,
        'attempt_round': attempt.attempt_round,
        'correction_note': attempt.correction_note,
        'knowledge_note': attempt.knowledge_note,
        'first_step_note': attempt.first_step_note,
        'time_spent_seconds': attempt.time_spent_seconds,
        'started_at': attempt.started_at,
        'created_at': attempt.created_at,
        'errors': errors,
        'primary_error': next((row['code'] for row in errors if row['is_primary']), None),
    }


def review_plan_payload(plan):
    if not plan:
        return None
    schedule = plan.schedule_days or DEFAULT_REVIEW_DAYS
    return {
        'status': plan.status,
        'step': plan.step,
        'checkpoint': f"D{schedule[min(plan.step, len(schedule) - 1)]}" if plan.status == 'active' else 'complete',
        'schedule_days': schedule,
        'next_review_at': plan.next_review_at,
    }


def _course_label(question, workspace):
    title = question.document.display_title or question.document.title
    if workspace == 'ei':
        code, label = course_for_title(title)
        if code:
            return code, label
    return str(question.document_id), title


def diagnostic_dashboard(user, workspace, start_date, end_date):
    attempts = list(QuestionAttempt.objects.filter(
        user=user, question__document__workspace=workspace,
    ).exclude(result='reset').select_related(
        'question__document', 'question__similarity_topic', 'question__topic',
    ).prefetch_related('error_tags').order_by('question_id', 'created_at', 'pk'))
    start_at = timezone.make_aware(datetime.datetime.combine(start_date, datetime.time.min))
    end_at = timezone.make_aware(datetime.datetime.combine(end_date + datetime.timedelta(days=1), datetime.time.min))

    by_question = defaultdict(list)
    for attempt in attempts:
        if attempt.outcome in EFFECTIVE_OUTCOMES:
            by_question[attempt.question_id].append(attempt)

    # Activity and ability evidence deliberately use different populations.
    # Legacy attempts are valid proof that a question was completed, but they
    # do not prove whether it was independent or whether an answer was viewed.
    first_activity_date = {}
    for attempt in attempts:
        first_activity_date.setdefault(
            attempt.question_id, timezone.localtime(attempt.created_at).date(),
        )
    activity = []
    period_activity_rows = []
    day = start_date
    while day <= end_date:
        rows = [
            row for row in attempts
            if timezone.localtime(row.created_at).date() == day
        ]
        period_activity_rows.extend(rows)
        question_ids = {row.question_id for row in rows}
        diagnosed_ids = {
            row.question_id for row in rows if row.outcome in EFFECTIVE_OUTCOMES
        }
        activity.append({
            'date': day.isoformat(),
            'daily_unique_questions': len(question_ids),
            'submissions': len(rows),
            'new_questions': sum(first_activity_date.get(question_id) == day for question_id in question_ids),
            'review_questions': sum(first_activity_date.get(question_id) != day for question_id in question_ids),
            'diagnosed_questions': len(diagnosed_ids),
            'legacy_unknown_questions': len(question_ids - diagnosed_ids),
        })
        day += datetime.timedelta(days=1)

    first_rows = []
    second_independent_rows = []
    recurrence_questions = []
    for rows in by_question.values():
        first = rows[0]
        if start_at <= first.created_at < end_at:
            first_rows.append(first)
        if not (first.outcome == 'correct' and first.is_independent is True):
            independent_redos = [row for row in rows[1:] if row.is_independent is True]
            if independent_redos and start_at <= independent_redos[0].created_at < end_at:
                second_independent_rows.append(independent_redos[0])
        diagnosed = []
        repeated = False
        seen = set()
        for row in rows:
            primary = next((tag.code for tag in row.error_tags.all() if tag.is_primary), None)
            if primary:
                diagnosed.append(row)
                if primary in seen:
                    repeated = True
                seen.add(primary)
        if len(diagnosed) >= 2 and any(start_at <= row.created_at < end_at for row in diagnosed[1:]):
            recurrence_questions.append((rows[0].question, repeated))

    period = [row for row in attempts if start_at <= row.created_at < end_at]
    diagnosed_period = [row for row in period if any(tag.is_primary for tag in row.error_tags.all())]
    primary_codes = [
        next(tag.code for tag in row.error_tags.all() if tag.is_primary)
        for row in diagnosed_period
    ]
    method_failures = sum(code in {'B2', 'B3'} for code in primary_codes)
    today = timezone.localdate()
    today_activity = next((row for row in activity if row['date'] == today.isoformat()), {
        'new_questions': 0, 'review_questions': 0,
        'daily_unique_questions': 0, 'submissions': 0,
    })

    trend = []
    for offset in range(6, -1, -1):
        day = today - datetime.timedelta(days=offset)
        day_first = [row for row in first_rows if timezone.localtime(row.created_at).date() == day]
        day_second = [row for row in second_independent_rows if timezone.localtime(row.created_at).date() == day]
        trend.append({
            'date': day.isoformat(),
            'first_sample': len(day_first),
            'first_independent_correct': sum(row.outcome == 'correct' and row.is_independent is True for row in day_first),
            'second_sample': len(day_second),
            'second_independent_correct': sum(row.outcome == 'correct' for row in day_second),
        })

    course_map = {}
    for row in period:
        if row.outcome not in EFFECTIVE_OUTCOMES:
            continue
        code, label = _course_label(row.question, workspace)
        bucket = course_map.setdefault(code, {
            'code': code, 'label': label, 'attempts': [], 'knowledge_gap': 0,
            'method_failure': 0, 'execution_error': 0,
        })
        bucket['attempts'].append(row)
        primary = next((tag.code for tag in row.error_tags.all() if tag.is_primary), None)
        bucket['knowledge_gap'] += primary == 'A'
        bucket['method_failure'] += primary in {'B2', 'B3'}
        bucket['execution_error'] += primary in {'C1', 'C2', 'C3'}

    courses = []
    for bucket in course_map.values():
        rows = bucket.pop('attempts')
        course_first = [row for row in first_rows if _course_label(row.question, workspace)[0] == bucket['code']]
        course_second = [row for row in second_independent_rows if _course_label(row.question, workspace)[0] == bucket['code']]
        diagnosed = bucket['knowledge_gap'] + bucket['method_failure'] + bucket['execution_error']
        courses.append({
            **bucket,
            'question_count': len({row.question_id for row in rows}),
            'first_sample': len(course_first),
            'first_independent_accuracy': _rate(sum(row.outcome == 'correct' and row.is_independent is True for row in course_first), len(course_first)),
            'knowledge_gap_rate': _rate(bucket['knowledge_gap'], diagnosed),
            'method_failure_rate': _rate(bucket['method_failure'], diagnosed),
            'execution_error_rate': _rate(bucket['execution_error'], diagnosed),
            'redo_sample': len(course_second),
            'redo_pass_rate': _rate(sum(row.outcome == 'correct' for row in course_second), len(course_second)),
        })

    due_count = QuestionReviewPlan.objects.filter(
        user=user, question__document__workspace=workspace, status='active',
        next_review_at__lte=timezone.now(),
    ).count()
    error_counts = Counter(primary_codes)
    topic_errors = Counter()
    for row in diagnosed_period:
        topic = row.question.similarity_topic or row.question.topic
        topic_label = (topic.display_title or topic.title) if topic else '未分类'
        topic_errors[topic_label] += 1

    last7_start = timezone.make_aware(datetime.datetime.combine(today - datetime.timedelta(days=7), datetime.time.min))
    previous7_start = last7_start - datetime.timedelta(days=7)
    topic_windows = defaultdict(lambda: {'current': [], 'previous': []})
    for row in attempts:
        if row.outcome not in EFFECTIVE_OUTCOMES or row.is_independent is not True:
            continue
        topic = row.question.similarity_topic or row.question.topic
        label = (topic.display_title or topic.title) if topic else '未分类'
        if last7_start <= row.created_at:
            topic_windows[label]['current'].append(row)
        elif previous7_start <= row.created_at < last7_start:
            topic_windows[label]['previous'].append(row)
    topic_trends = []
    for label, windows in topic_windows.items():
        if not windows['current'] or not windows['previous']:
            continue
        current_rate = _rate(sum(row.outcome == 'correct' for row in windows['current']), len(windows['current']))
        previous_rate = _rate(sum(row.outcome == 'correct' for row in windows['previous']), len(windows['previous']))
        topic_trends.append({
            'topic': label,
            'current_rate': current_rate,
            'previous_rate': previous_rate,
            'change': round(current_rate - previous_rate, 1),
            'current_sample': len(windows['current']),
            'previous_sample': len(windows['previous']),
        })
    return {
        'workspace': workspace,
        'range': {'start': start_date, 'end': end_date},
        'today': {
            'new_questions': today_activity['new_questions'],
            'review_questions': today_activity['review_questions'],
            'completed_questions': today_activity['daily_unique_questions'],
            'submissions': today_activity['submissions'],
            'first_sample': sum(
                row.training_stage == 'first'
                for row in first_rows
                if timezone.localtime(row.created_at).date() == today
            ),
            'first_independent_correct': sum(
                row.training_stage == 'first' and row.outcome == 'correct' and row.is_independent is True
                for row in first_rows
                if timezone.localtime(row.created_at).date() == today
            ),
        },
        'period_activity': {
            'daily_unique_questions': sum(row['daily_unique_questions'] for row in activity),
            'submissions': len(period_activity_rows),
            'unique_questions': len({row.question_id for row in period_activity_rows}),
            'diagnosed_attempts': sum(row.outcome in EFFECTIVE_OUTCOMES for row in period_activity_rows),
            'legacy_unknown_attempts': sum(row.outcome == 'unknown' for row in period_activity_rows),
        },
        'activity': activity,
        'metrics': {
            'first_independent_accuracy': _metric(first_rows, lambda row: row.outcome == 'correct' and row.is_independent is True),
            'second_independent_accuracy': _metric(second_independent_rows, lambda row: row.outcome == 'correct'),
            'pending_redo_count': QuestionReviewPlan.objects.filter(user=user, question__document__workspace=workspace, status='active').count(),
            'error_recurrence_rate': {
                'value': _rate(sum(repeated for _question, repeated in recurrence_questions), len(recurrence_questions)),
                'sample': len(recurrence_questions),
            },
            'method_start_failure_rate': {
                'value': _rate(method_failures, len(diagnosed_period)),
                'sample': len(diagnosed_period),
            },
        },
        'error_distribution': [{'code': code, 'count': error_counts.get(code, 0)} for code in ('A', 'B1', 'B2', 'B3', 'C1', 'C2', 'C3', 'D')],
        'due_count': due_count,
        'trend': trend,
        'courses': sorted(courses, key=lambda row: row['label']),
        'repeated_topics': [{'topic': label, 'diagnosed_errors': count} for label, count in topic_errors.most_common(8)],
        'topic_trends': sorted(topic_trends, key=lambda row: -abs(row['change']))[:8],
        'notice': 'Rates only use attempts with explicit diagnosis evidence. Historical unknown fields are excluded.',
    }


def _rate(numerator, denominator):
    return round(numerator * 100 / denominator, 1) if denominator else None


def _metric(rows, predicate):
    numerator = sum(predicate(row) for row in rows)
    return {'value': _rate(numerator, len(rows)), 'numerator': numerator, 'sample': len(rows)}
