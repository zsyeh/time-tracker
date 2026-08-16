"""Isolated, deterministic test users and histories for real-API load tests."""

from __future__ import annotations

import datetime
import random
from importlib import import_module

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY, get_user_model
from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone

from .loadtest import (
    LOADTEST_USER_PREFIX,
    is_loadtest_username,
    normalize_run_id,
    suppress_fixture_maintenance,
)
from .models import LearningIssue, SessionReview, SessionShare, TimeLog


PROFILE_ROWS = {
    'new': 8,
    'six_month': 360,
    'one_year': 730,
    'heavy': 1460,
}
PROFILE_ORDER = tuple(PROFILE_ROWS)
FINISH_BURST_TASK_PATH = 'Capacity model › 22:00 finish burst'


def username_prefix(run_id: str) -> str:
    return f'{LOADTEST_USER_PREFIX}{normalize_run_id(run_id)}_'


def _delete_auth_sessions(user_ids):
    wanted = {str(user_id) for user_id in user_ids}
    session_keys = []
    for session in Session.objects.all().iterator(chunk_size=200):
        try:
            if str(session.get_decoded().get(SESSION_KEY, '')) in wanted:
                session_keys.append(session.session_key)
        except Exception:
            continue
    if session_keys:
        Session.objects.filter(session_key__in=session_keys).delete()
    return len(session_keys)


def cleanup_run(run_id: str):
    run_id = normalize_run_id(run_id)
    prefix = username_prefix(run_id)
    User = get_user_model()
    candidates = User.objects.filter(
        **{f'{User.USERNAME_FIELD}__startswith': prefix},
    ).values_list('pk', User.USERNAME_FIELD)
    user_ids = [
        user_id for user_id, username in candidates
        if is_loadtest_username(username, run_id=run_id)
    ]
    users = User.objects.filter(pk__in=user_ids)
    auth_sessions = _delete_auth_sessions(user_ids)
    deleted_users = len(user_ids)
    if user_ids:
        with suppress_fixture_maintenance():
            users.delete()
    return {
        'run_id': normalize_run_id(run_id),
        'deleted_users': deleted_users,
        'deleted_auth_sessions': auth_sessions,
    }


def _create_auth_session(user):
    engine = import_module(settings.SESSION_ENGINE)
    store = engine.SessionStore()
    store[SESSION_KEY] = str(user.pk)
    store[BACKEND_SESSION_KEY] = 'django.contrib.auth.backends.ModelBackend'
    store[HASH_SESSION_KEY] = user.get_session_auth_hash()
    store.create()
    return store.session_key


def _history_rows(user, profile, rng, *, remaining_limit):
    target = min(PROFILE_ROWS[profile], remaining_limit)
    if target <= 0:
        return []
    now = timezone.now()
    lookback_days = {
        'new': 7,
        'six_month': 183,
        'one_year': 366,
        'heavy': 730,
    }[profile]
    rows = []
    subjects = ('math', 'english', 'major', 'training')
    for index in range(target):
        # Completed history must never be timestamped in the future. Starting
        # at yesterday also avoids overlap with a later finish-burst fixture.
        day_offset = 1 + int(index * max(0, lookback_days - 1) / max(1, target - 1))
        hour = 7 + (index % 4) * 3
        minute = rng.randrange(0, 50)
        local_day = timezone.localtime(now).date() - datetime.timedelta(days=day_offset)
        local_start = datetime.datetime.combine(
            local_day,
            datetime.time(hour=min(hour, 21), minute=minute),
        )
        start_time = timezone.make_aware(local_start, timezone.get_current_timezone())
        duration = 80 + rng.randrange(0, 75)
        details = (
            '# Load test Markdown\n\n'
            'Representative history content with **formatting**, a table, and formula.\n\n'
            '| Metric | Value |\n|---|---:|\n| sample | 1 |\n\n'
            '$$\\int_0^1 x^2\\,dx = \\frac{1}{3}$$\n'
        )
        if profile == 'heavy' and index == 0:
            details += '\n'.join(f'- Historical note line {line}' for line in range(1500))
        rows.append(TimeLog(
            user=user,
            category=subjects[index % len(subjects)],
            task_path=f'Capacity model › {profile}',
            chapter=f'History {index // 20 + 1}',
            topic=f'Representative task {index % 20 + 1}',
            start_time=start_time,
            end_time=start_time + datetime.timedelta(minutes=duration),
            status='completed',
            efficiency_grade=('A', 'B', 'C')[index % 3],
            learning_mode=('theory', 'exercise', 'review')[index % 3],
            title=f'Load test {profile} session {index + 1}',
            details=details if index < 4 else 'Representative load-test Markdown body.',
            review_count=1 if index < 6 else 0,
            last_reviewed_at=now - datetime.timedelta(days=index % 30) if index < 6 else None,
        ))
    return rows


@transaction.atomic
def provision_run(run_id: str, *, user_count: int, seed: int):
    run_id = normalize_run_id(run_id)
    user_count = max(1, min(int(user_count), settings.STRESS_TEST_MAX_USERS))
    required_history_rows = sum(
        PROFILE_ROWS[PROFILE_ORDER[index]] if index < len(PROFILE_ORDER) else 1
        for index in range(user_count)
    )
    if settings.STRESS_TEST_MAX_HISTORY_ROWS < required_history_rows:
        raise ValueError(
            'STRESS_TEST_MAX_HISTORY_ROWS is too small for the requested users: '
            f'{required_history_rows} rows are required to preserve the new, '
            'six-month, one-year, and heavy-history fixture profiles.'
        )
    cleanup_run(run_id)
    prefix = username_prefix(run_id)
    User = get_user_model()
    if User.USERNAME_FIELD != 'username':
        raise RuntimeError('The load-test fixture builder currently requires a username user model.')

    users = []
    for index in range(user_count):
        user = User(username=f'{prefix}{index + 1:04d}', is_active=True)
        user.set_unusable_password()
        users.append(user)
    User.objects.bulk_create(users, batch_size=200)
    candidate_users = User.objects.filter(username__startswith=prefix).order_by('username')
    users = [
        user for user in candidate_users
        if is_loadtest_username(user.username, run_id=run_id)
    ]

    rng = random.Random(seed)
    history_rows = []
    remaining = settings.STRESS_TEST_MAX_HISTORY_ROWS
    profiles = {}
    for index, user in enumerate(users):
        # The first four users provide the required data-age archetypes.  Extra
        # VUs stay light so provisioning thousands of rows is not multiplied by
        # the requested concurrency.
        profile = PROFILE_ORDER[index] if index < len(PROFILE_ORDER) else 'new'
        profiles[user.pk] = profile
        rows = _history_rows(user, profile, rng, remaining_limit=remaining)
        history_rows.extend(rows)
        remaining -= len(rows)
    TimeLog.objects.bulk_create(history_rows, batch_size=500)

    detail_by_user = {}
    recent_sessions = TimeLog.objects.filter(
        user__in=users,
        status='completed',
    ).order_by('user_id', '-start_time')
    for session in recent_sessions.iterator(chunk_size=500):
        detail_by_user.setdefault(session.user_id, session)

    reviews = []
    issues = []
    for user in users:
        detail = detail_by_user.get(user.pk)
        if detail:
            reviews.append(SessionReview(
                session=detail,
                user=user,
                reviewed_at=timezone.now() - datetime.timedelta(days=1),
            ))
            issues.append(LearningIssue(
                user=user,
                study_session=detail,
                category=detail.category,
                topic='Representative load-test issue',
                issue_type='concept_error',
                description='Synthetic issue used only for capacity testing.',
                solution='Synthetic resolution.',
            ))
    SessionReview.objects.bulk_create(reviews, batch_size=200)
    LearningIssue.objects.bulk_create(issues, batch_size=200)

    public_share_token = None
    first_detail = detail_by_user.get(users[0].pk) if users else None
    if first_detail:
        _, public_share_token = SessionShare.issue(session=first_detail)

    credentials = []
    for user in users:
        detail = detail_by_user.get(user.pk)
        credentials.append({
            'username': user.username,
            'session_key': _create_auth_session(user),
            'profile': profiles[user.pk],
            'detail_id': detail.pk if detail else None,
            'detail_uuid': str(detail.uuid) if detail else None,
        })
    return {
        'run_id': run_id,
        'users': credentials,
        'history_rows': len(history_rows),
        'profile_rows': PROFILE_ROWS,
        'public_share_token': public_share_token,
        'warning': 'Credentials are ephemeral test-only capabilities and must not be written to reports.',
    }


@transaction.atomic
def prepare_finish_burst(run_id: str, *, limit: int):
    run_id = normalize_run_id(run_id)
    prefix = username_prefix(run_id)
    User = get_user_model()
    candidate_users = User.objects.filter(
        **{f'{User.USERNAME_FIELD}__startswith': prefix},
    ).order_by(User.USERNAME_FIELD)
    users = [
        user for user in candidate_users
        if is_loadtest_username(user.get_username(), run_id=run_id)
    ][:max(1, min(int(limit), settings.STRESS_TEST_MAX_USERS))]
    if not users:
        raise ValueError('No isolated users exist for this run_id.')
    with suppress_fixture_maintenance():
        # Each DAU/window stage starts from the same fixture state. Otherwise
        # completed synthetic bursts would accumulate and make later stages a
        # different history-size workload.
        TimeLog.objects.filter(
            user__in=users,
            task_path=FINISH_BURST_TASK_PATH,
        ).delete()
        TimeLog.objects.filter(user__in=users, status='running').delete()
    start_time = timezone.now() - datetime.timedelta(hours=2)
    rows = [TimeLog(
        user=user,
        category=('math', 'english', 'major')[index % 3],
        task_path=FINISH_BURST_TASK_PATH,
        topic='Prepared finish burst session',
        start_time=start_time - datetime.timedelta(seconds=index % 30),
        status='running',
    ) for index, user in enumerate(users)]
    TimeLog.objects.bulk_create(rows, batch_size=500)
    sessions = TimeLog.objects.filter(user__in=users, status='running').select_related('user')
    return {
        'run_id': run_id,
        'sessions': [
            {'username': row.user.username, 'session_id': row.pk, 'session_uuid': str(row.uuid)}
            for row in sessions.order_by('user__username')
        ],
    }
