import datetime
from collections import defaultdict

from django.conf import settings
from django.utils import timezone

from .models import TimeLog


FIVE_HOUR_MINUTES = 300


def _local(value):
    return timezone.localtime(value) if timezone.is_aware(value) else value


def _streak(dates, today):
    dates = set(dates)
    current = 0
    cursor = today
    while cursor in dates:
        current += 1
        cursor -= datetime.timedelta(days=1)

    longest = 0
    running = 0
    previous = None
    for day in sorted(dates):
        running = running + 1 if previous and day == previous + datetime.timedelta(days=1) else 1
        longest = max(longest, running)
        previous = day
    return current, longest


def build_dashboard_overview(user, days=180):
    days = max(7, min(int(days), 366))
    now = timezone.now()
    local_today = _local(now).date()
    first_day = local_today - datetime.timedelta(days=days - 1)
    try:
        configured_heatmap_start = datetime.date.fromisoformat(
            settings.TRACKER_HEATMAP_START_DATE
        )
    except (TypeError, ValueError):
        configured_heatmap_start = datetime.date(2026, 5, 23)
    heatmap_first_day = max(first_day, configured_heatmap_start)
    boundary = timezone.make_aware(
        datetime.datetime.combine(first_day, datetime.time.min),
        timezone.get_current_timezone(),
    )
    sessions = list(
        TimeLog.objects.filter(
            user=user,
            status='completed',
            start_time__gte=boundary,
        ).only(
            'id', 'category', 'start_time', 'end_time', 'status',
        ).order_by('start_time')
    )
    active = TimeLog.objects.filter(user=user, status='running').first()

    daily = defaultdict(lambda: {'minutes': 0, 'sessions': 0, 'first_start': None})
    by_subject = defaultdict(int)
    by_week = defaultdict(int)
    by_month = defaultdict(int)
    today_by_subject = defaultdict(int)
    for session in sessions:
        local_start = _local(session.start_time)
        day = local_start.date()
        row = daily[day]
        row['minutes'] += session.duration_minutes
        row['sessions'] += 1
        start_label = local_start.strftime('%H:%M')
        if row['first_start'] is None or start_label < row['first_start']:
            row['first_start'] = start_label
        by_subject[session.category] += session.duration_minutes
        by_week[day - datetime.timedelta(days=day.weekday())] += session.duration_minutes
        by_month[day.replace(day=1)] += session.duration_minutes
        if day == local_today:
            today_by_subject[session.category] += session.duration_minutes

    active_dates = {day for day, row in daily.items() if row['minutes'] > 0}
    five_hour_dates = {day for day, row in daily.items() if row['minutes'] >= FIVE_HOUR_MINUTES}
    current_streak, longest_streak = _streak(active_dates, local_today)
    current_five_hour_streak, longest_five_hour_streak = _streak(five_hour_dates, local_today)

    heatmap = []
    heatmap_day_count = max(0, (local_today - heatmap_first_day).days + 1)
    for offset in range(heatmap_day_count):
        day = heatmap_first_day + datetime.timedelta(days=offset)
        row = daily.get(day, {'minutes': 0, 'sessions': 0, 'first_start': None})
        minutes = row['minutes']
        if minutes == 0:
            level = 0
        elif minutes < 120:
            level = 1
        elif minutes < FIVE_HOUR_MINUTES:
            level = 2
        else:
            level = 4
        heatmap.append({
            'date': day.isoformat(),
            'minutes': minutes,
            'sessions': row['sessions'],
            'first_start': row['first_start'],
            'level': level,
            'five_hour_goal': minutes >= FIVE_HOUR_MINUTES,
        })

    today_row = daily.get(local_today, {'minutes': 0, 'sessions': 0, 'first_start': None})
    total_minutes = sum(row['minutes'] for row in daily.values())
    start_minutes = []
    for row in daily.values():
        if row['first_start']:
            hour, minute = map(int, row['first_start'].split(':'))
            start_minutes.append(hour * 60 + minute)
    average_start = None
    if start_minutes:
        mean = round(sum(start_minutes) / len(start_minutes))
        average_start = f'{mean // 60:02d}:{mean % 60:02d}'

    try:
        exam_date = datetime.date.fromisoformat(settings.TRACKER_EXAM_DATE)
    except (TypeError, ValueError):
        exam_date = datetime.date(2026, 12, 26)
    return {
        'server_time': _local(now).isoformat(),
        'range_days': days,
        'calendar': {
            'today': local_today.isoformat(),
            'exam_date': exam_date.isoformat(),
            'days_until_exam': max(0, (exam_date - local_today).days),
            'heatmap_start_date': heatmap_first_day.isoformat(),
        },
        'today': today_row,
        'active_session': serialize_session(active, now) if active else None,
        'summary': {
            'total_minutes': total_minutes,
            'session_count': len(sessions),
            'active_days': len(active_dates),
            'five_hour_days': len(five_hour_dates),
            'current_streak': current_streak,
            'longest_streak': longest_streak,
            'current_five_hour_streak': current_five_hour_streak,
            'longest_five_hour_streak': longest_five_hour_streak,
            'average_start_time': average_start,
        },
        'subject_totals': [
            {'subject': subject, 'minutes': minutes}
            for subject, minutes in sorted(by_subject.items(), key=lambda item: item[1], reverse=True)
        ],
        'today_subject_totals': [
            {'subject': subject, 'minutes': today_by_subject.get(subject, 0)}
            for subject in ('math', 'english', 'major', 'training')
        ],
        'weekly_totals': [
            {'week_start': day.isoformat(), 'minutes': minutes}
            for day, minutes in sorted(by_week.items())
        ],
        'monthly_totals': [
            {'month': day.strftime('%Y-%m'), 'minutes': minutes}
            for day, minutes in sorted(by_month.items())
        ],
        'heatmap': heatmap,
        'daily_start_times': [
            {'date': row['date'], 'first_start': row['first_start']}
            for row in heatmap
            if row['first_start']
        ],
    }


def serialize_session(session, now=None):
    if not session:
        return None
    end = session.end_time or now or timezone.now()
    return {
        'id': session.pk,
        'subject': session.category,
        'subject_label': session.get_category_display(),
        'chapter': session.chapter,
        'topic': session.topic,
        'status': session.status,
        'learning_mode': session.learning_mode,
        'start_time': _local(session.start_time).isoformat(),
        'end_time': _local(session.end_time).isoformat() if session.end_time else None,
        'duration_minutes': max(0, int((end - session.start_time).total_seconds() / 60)),
        'title': session.title or '',
        'details': session.details,
        'breakthrough': session.breakthrough,
        'problems': session.problems,
        'next_action': session.next_action,
    }
