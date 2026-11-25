"""Net study intervals; pauses are never credited, including across midnight."""
from django.utils import timezone
from django.utils.dateparse import parse_datetime


def study_seconds_between(session, start, end):
    begin = max(session.start_time, start)
    finish = min(session.end_time or end, end)
    if finish <= begin:
        return 0
    spans = []
    for item in session.pause_intervals or []:
        try:
            a = parse_datetime(item['start'])
            b = parse_datetime(item['end']) if item.get('end') else finish
            if not a or not b or timezone.is_naive(a) or timezone.is_naive(b):
                continue
            a, b = max(begin, a), min(finish, b)
            if b > a:
                spans.append((a, b))
        except (KeyError, TypeError, ValueError):
            continue
    merged = []
    for a, b in sorted(spans):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return max(0, int((finish-begin).total_seconds() - sum((b-a).total_seconds() for a,b in merged)))
