from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST
import json
import datetime
import csv
from .models import DailyStudyStat, TimeLog
from .schedule import get_summer_schedule

from .auth import token_required

VALID_CATEGORIES = {choice[0] for choice in TimeLog.CATEGORY_CHOICES}
CATEGORY_LABELS = dict(TimeLog.CATEGORY_CHOICES)

MAX_TASK_DURATION = datetime.timedelta(hours=6)

def _get_safe_now():
    return timezone.now()

def _execute_lazy_garbage_collection():
    active_log = TimeLog.objects.filter(end_time__isnull=True).first()
    if active_log and active_log.start_time:
        now = _get_safe_now()
        start = active_log.start_time
        
        if timezone.is_aware(now) and timezone.is_naive(start):
            start = timezone.make_aware(start)
        elif timezone.is_naive(now) and timezone.is_aware(start):
            now = timezone.make_aware(now)
            
        duration = now - start
        
        if duration > MAX_TASK_DURATION:
            active_log.delete()
            return True
    return False

def _build_period_summary(logs):
    total_minutes = 0
    category_totals = {}
    daily_totals = {}

    for log in logs:
        minutes = log.duration_minutes
        total_minutes += minutes
        label = CATEGORY_LABELS.get(log.category, log.category)
        category_totals[label] = category_totals.get(label, 0) + minutes
        local_start = timezone.localtime(log.start_time) if timezone.is_aware(log.start_time) else log.start_time
        day_key = str(local_start.date())
        daily_totals[day_key] = daily_totals.get(day_key, 0) + minutes

    top_category = None
    if category_totals:
        top_category = max(category_totals.items(), key=lambda item: item[1])[0]
    best_day = None
    best_day_minutes = 0
    if daily_totals:
        best_day, best_day_minutes = max(daily_totals.items(), key=lambda item: item[1])

    return {
        'total_minutes': total_minutes,
        'total_hours': round(total_minutes / 60, 2),
        'session_count': len(logs),
        'average_minutes': int(total_minutes / len(logs)) if logs else 0,
        'active_days': len(daily_totals),
        'best_day': best_day or '暂无',
        'best_day_minutes': best_day_minutes,
        'top_category': top_category or '暂无',
        'category_totals': [
            {'name': name, 'value': minutes}
            for name, minutes in sorted(category_totals.items(), key=lambda item: item[1], reverse=True)
        ],
    }

def _build_streak_summary(daily_totals, today_date):
    active_dates = {datetime.date.fromisoformat(day) for day, minutes in daily_totals.items() if minutes > 0}
    current_streak = 0
    cursor = today_date
    while cursor in active_dates:
        current_streak += 1
        cursor -= datetime.timedelta(days=1)

    longest_streak = 0
    running = 0
    previous = None
    for day in sorted(active_dates):
        if previous and day == previous + datetime.timedelta(days=1):
            running += 1
        else:
            running = 1
        longest_streak = max(longest_streak, running)
        previous = day

    return {
        'current_streak': current_streak,
        'longest_streak': longest_streak,
        'active_days': len(active_dates),
    }

def dashboard_view(request):
    _execute_lazy_garbage_collection()
    now = _get_safe_now()
    local_now = timezone.localtime(now) if timezone.is_aware(now) else now
    today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    days_since_sunday = (today_start.weekday() + 1) % 7
    start_of_week_dt = today_start - datetime.timedelta(days=days_since_sunday)

    week_logs = TimeLog.objects.filter(
        start_time__gte=start_of_week_dt, 
        end_time__isnull=False
    )
    completed_logs = list(TimeLog.objects.filter(end_time__isnull=False).order_by('-start_time'))
    month_start = now - datetime.timedelta(days=30)
    month_logs = [log for log in completed_logs if log.start_time >= month_start]

    stats = {}
    daily_stat_rows = list(DailyStudyStat.objects.all())
    daily_stats = {
        str(stat.date): stat.total_minutes
        for stat in daily_stat_rows
    }
    daily_metrics = {
        str(stat.date): {
            'study_count': stat.study_count,
            'first_start_time': (
                timezone.localtime(stat.first_start_time).strftime('%H:%M')
                if timezone.is_aware(stat.first_start_time)
                else stat.first_start_time.strftime('%H:%M')
            ),
        }
        for stat in daily_stat_rows
    }
    
    for log in week_logs:
        label = dict(TimeLog.CATEGORY_CHOICES).get(log.category, log.category)
        stats[label] = stats.get(label, 0) + log.duration_minutes

    chart_data = [{"name": k, "value": v} for k, v in stats.items()]

    active_log = TimeLog.objects.filter(end_time__isnull=True).first()
    active_category = active_log.category if active_log else None
    
    # 获取服务端运行总秒数，避免前端刷新归零
    active_elapsed = 0
    if active_log:
        active_start = timezone.make_aware(active_log.start_time) if timezone.is_naive(active_log.start_time) else active_log.start_time
        active_elapsed = int((now - active_start).total_seconds())

    # 获取近 7 日记录用于前端预览列表
    recent_logs_query = TimeLog.objects.filter(end_time__isnull=False).order_by('-start_time')[:50]
    recent_logs = []
    for log in recent_logs_query:
        label = dict(TimeLog.CATEGORY_CHOICES).get(log.category, log.category)
        local_st = timezone.localtime(log.start_time) if timezone.is_aware(log.start_time) else log.start_time
        recent_logs.append({
            'date': local_st.strftime('%m-%d %H:%M'),
            'category': label,
            'duration': log.duration_minutes,
            'note': log.note or '无'
        })

    today_str = str(local_now.date())

    context = {
        'chart_data': json.dumps(chart_data),
        'active_category': active_category,
        'active_elapsed': active_elapsed,
        'daily_stats': json.dumps(daily_stats),
        'daily_metrics': json.dumps(daily_metrics),
        'recent_logs': json.dumps(recent_logs),
        'month_summary': json.dumps(_build_period_summary(month_logs)),
        'all_time_summary': json.dumps(_build_period_summary(completed_logs)),
        'streak_summary': json.dumps(_build_streak_summary(daily_stats, local_now.date())),
        'today_str': today_str,
        'daily_target_minutes': settings.TRACKER_DAILY_TARGET_MINUTES,
        'weekly_target_minutes': settings.TRACKER_WEEKLY_TARGET_MINUTES,
        'exam_date': settings.TRACKER_EXAM_DATE,
        'summer_schedule': get_summer_schedule(),
    }
    return render(request, 'dashboard.html', context)


def daily_stats_view(request):
    stats = DailyStudyStat.objects.all()
    totals = stats.aggregate(
        study_count=Sum('study_count'),
        total_minutes=Sum('total_minutes'),
    )
    total_minutes = totals['total_minutes'] or 0
    overview = {
        'day_count': stats.count(),
        'study_count': totals['study_count'] or 0,
        'total_minutes': total_minutes,
        'total_hours': round(total_minutes / 60, 2),
    }

    paginator = Paginator(stats, 31)
    page_obj = paginator.get_page(request.GET.get('page'))
    daily_target_minutes = settings.TRACKER_DAILY_TARGET_MINUTES
    for stat in page_obj.object_list:
        stat.progress_percent = min(
            100,
            round(stat.total_minutes / daily_target_minutes * 100, 1),
        ) if daily_target_minutes else 0

    return render(
        request,
        'daily_stats.html',
        {
            'page_obj': page_obj,
            'overview': overview,
            'daily_target_minutes': daily_target_minutes,
        },
    )

@token_required
@require_POST
def api_action(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'msg': '数据解析失败'}, status=400)

    action = data.get('action')
    category = data.get('category')
    note = data.get('note', '')

    was_cleaned = _execute_lazy_garbage_collection()
    active_log = TimeLog.objects.filter(end_time__isnull=True).first()
    now = _get_safe_now()

    if action == 'start':
        if active_log:
            return JsonResponse({'status': 'error', 'msg': '已有任务运行中'}, status=400)

        if category not in VALID_CATEGORIES:
            return JsonResponse({'status': 'error', 'msg': '无效任务分类'}, status=400)
        
        msg_prefix = "前次任务超时 6 小时已作废。 " if was_cleaned else ""
        TimeLog.objects.create(category=category)
        return JsonResponse({'status': 'success', 'msg': f'{msg_prefix}已开启 {category}'})

    elif action == 'stop':
        if not active_log:
            msg = '当前无活动任务，或因超时已作废' if was_cleaned else '当前无活动任务'
            return JsonResponse({'status': 'error', 'msg': msg}, status=400)
        
        active_start = timezone.make_aware(active_log.start_time) if timezone.is_naive(active_log.start_time) else active_log.start_time
        duration_mins = (now - active_start).total_seconds() / 60.0
        
        # 物理拦截：不足25分钟直接销毁记录
        if duration_mins < 25:
            active_log.delete()
            return JsonResponse({'status': 'error', 'msg': f'时长不足25分钟 (仅 {int(duration_mins)}m)，已销毁记录'})
            
        active_log.end_time = now
        active_log.note = note
        active_log.save()
        local_start = timezone.localtime(active_log.start_time) if timezone.is_aware(active_log.start_time) else active_log.start_time
        local_end = timezone.localtime(active_log.end_time) if timezone.is_aware(active_log.end_time) else active_log.end_time
        return JsonResponse({
            'status': 'success',
            'msg': f'结算成功: {int(duration_mins)} 分钟',
            'session': {
                'id': active_log.pk,
                'category': active_log.category,
                'category_label': CATEGORY_LABELS.get(active_log.category, active_log.category),
                'start_time': local_start.isoformat(),
                'end_time': local_end.isoformat(),
                'duration_minutes': int(duration_mins),
                'summary': active_log.note,
            },
        })

    return JsonResponse({'status': 'error', 'msg': '未知指令'}, status=400)

@token_required
def export_logs_csv(request):
    try:
        days = int(request.GET.get('days', '90'))
    except ValueError:
        return JsonResponse({'status': 'error', 'msg': 'days 必须是数字'}, status=400)

    days = max(1, min(days, 3650))
    start_date = _get_safe_now() - datetime.timedelta(days=days)
    logs = TimeLog.objects.filter(
        start_time__gte=start_date,
        end_time__isnull=False,
    ).order_by('-start_time')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="time_logs.csv"'
    writer = csv.writer(response)
    writer.writerow(['start_time', 'end_time', 'category', 'category_label', 'duration_minutes', 'note'])

    for log in logs:
        start_time = timezone.localtime(log.start_time) if timezone.is_aware(log.start_time) else log.start_time
        end_time = timezone.localtime(log.end_time) if timezone.is_aware(log.end_time) else log.end_time
        writer.writerow([
            start_time.strftime('%Y-%m-%d %H:%M:%S'),
            end_time.strftime('%Y-%m-%d %H:%M:%S'),
            log.category,
            CATEGORY_LABELS.get(log.category, log.category),
            log.duration_minutes,
            log.note or '',
        ])

    return response
