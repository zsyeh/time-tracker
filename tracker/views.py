# tracker/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
import json
import datetime
from .models import TimeLog
from functools import wraps

SECRET_TOKEN = "eH_"

def token_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        token = request.headers.get('Authorization')
        if token == SECRET_TOKEN:
            return view_func(request, *args, **kwargs)
        return JsonResponse({'status': 'error', 'msg': '鉴权失败，请检查你的令牌'}, status=403)
    return _wrapped_view

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

def dashboard_view(request):
    _execute_lazy_garbage_collection()
    now = _get_safe_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days_since_sunday = (today_start.weekday() + 1) % 7
    start_of_week_dt = today_start - datetime.timedelta(days=days_since_sunday)

    week_logs = TimeLog.objects.filter(
        start_time__gte=start_of_week_dt, 
        end_time__isnull=False
    )

    stats = {}
    daily_stats = {} 
    
    for log in week_logs:
        label = dict(TimeLog.CATEGORY_CHOICES).get(log.category, log.category)
        stats[label] = stats.get(label, 0) + log.duration_minutes
        
        local_start = timezone.localtime(log.start_time) if timezone.is_aware(log.start_time) else log.start_time
        log_date_str = str(local_start.date())
        daily_stats[log_date_str] = daily_stats.get(log_date_str, 0) + log.duration_minutes

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

    today_str = str(timezone.localtime(now).date() if timezone.is_aware(now) else now.date())

    context = {
        'chart_data': json.dumps(chart_data),
        'active_category': active_category,
        'active_elapsed': active_elapsed,
        'daily_stats': json.dumps(daily_stats),
        'recent_logs': json.dumps(recent_logs),
        'today_str': today_str,
    }
    return render(request, 'dashboard.html', context)

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
        return JsonResponse({'status': 'success', 'msg': f'结算成功: {int(duration_mins)} 分钟'})

    return JsonResponse({'status': 'error', 'msg': '未知指令'}, status=400)
