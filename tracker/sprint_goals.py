"""Account-owned 20-day net-time goals; no surplus transfer between subjects/days."""
import datetime
from collections import defaultdict
from django.db.models import Q
from django.utils import timezone
from .models import TimeLog
from .time_intervals import study_seconds_between
from .user_preferences import preferences_snapshot

SUBJECTS = [('math','数学二',300,'Selected 严选题30道'),('major','892专业课',240,'20–30道，旧知识复测与新考点覆盖'),('english','英语二',111,'完形15分钟；阅读1–4各19分钟；新题型10分钟；翻译10分钟'),('training','政治',30,'基础学习30分钟')]
EXTRA_TAG = '冲刺额外任务'


def goal_config(user):
    return preferences_snapshot(user)['values']['timer.goal_plan']


def sprint_enabled(user):
    return goal_config(user)['mode'] == 'sprint20'


def build_sprint_progress(user, now=None, config=None):
    config = config or goal_config(user)
    if config['mode'] != 'sprint20':
        return None
    now = now or timezone.now()
    today = timezone.localtime(now).date()
    start = datetime.date.fromisoformat(config['start_date'])
    end = start + datetime.timedelta(days=19)
    tz = timezone.get_current_timezone()
    def boundary(day):
        return timezone.make_aware(datetime.datetime.combine(day,datetime.time.min),tz)
    first = min(start,today)
    logs = TimeLog.objects.filter(user=user,status__in=['completed','running'],start_time__lt=now).filter(
        Q(end_time__isnull=True)|Q(end_time__gte=boundary(first))).only('id','user_id','category','start_time','end_time','status','pause_intervals','task_path','title','encrypted_summary','encrypted_content').prefetch_related('tags')
    base, extra = defaultdict(int), defaultdict(int)
    for log in logs:
        # Explicit task names/tag only: general review and knowledge retests remain base study.
        names = (log.task_path or '')+' '+(log.title or '')
        is_extra = '错题订正' in names or (log.category=='english' and '作文' in names) or any(t.name==EXTRA_TAG for t in log.tags.all())
        cursor = max(first,timezone.localtime(log.start_time).date())
        last = min(today,timezone.localtime(log.end_time or now).date())
        while cursor <= last:
            if cursor==today or start<=cursor<=end:
                seconds = study_seconds_between(log,boundary(cursor),min(now,boundary(cursor+datetime.timedelta(days=1))))
                (extra if is_extra else base)[cursor,log.category] += seconds
            cursor += datetime.timedelta(days=1)
    def day_payload(day):
        rows=[]
        for key,label,target,task in SUBJECTS:
            b,e=base[day,key]/60,extra[day,key]/60
            rows.append(dict(subject=key,label=label,target_minutes=target,actual_minutes=round(b+e,2),base_minutes=round(b,2),extra_minutes=round(e,2),remaining_minutes=round(max(0,target-b),2),completion_percent=round(b/target*100,1),task=task))
        return dict(subjects=rows,credited_minutes=round(sum(min(r['base_minutes'],r['target_minutes']) for r in rows),2),actual_minutes=round(sum(r['actual_minutes'] for r in rows),2),extra_minutes=round(sum(r['extra_minutes'] for r in rows),2),complete=all(base[day,key]>=target*60 for key,_label,target,_task in SUBJECTS))
    daily = day_payload(today)
    days = [dict(date=(start+datetime.timedelta(days=i)).isoformat(),**day_payload(start+datetime.timedelta(days=i))) for i in range(20)]
    credited = round(sum(d['credited_minutes'] for d in days),2)
    return dict(name='考研最后20天冲刺',start_date=start.isoformat(),end_date=end.isoformat(),days=20,day_index=max(0,min(20,(today-start).days+1)),daily_target_minutes=681,today=dict(**daily,completion_percent=round(daily['credited_minutes']/681*100,1),remaining_minutes=round(681-daily['credited_minutes'],2)),cumulative=dict(target_minutes=13620,credited_minutes=credited,actual_minutes=round(sum(d['actual_minutes'] for d in days),2),extra_minutes=round(sum(d['extra_minutes'] for d in days),2),completion_percent=round(credited/13620*100,1),completed_days=sum(d['complete'] for d in days)),calendar=days,updated_at=now.isoformat())
