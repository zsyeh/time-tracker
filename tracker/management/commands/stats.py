from django.core.management.base import BaseCommand
from django.utils import timezone
from tracker.models import TimeLog
from collections import defaultdict
import datetime

class Command(BaseCommand):
    help = 'Aggregates time logs and outputs proportional statistics.'

    def add_arguments(self, parser):
        # 允许传入 --days 参数以指定回溯天数，默认为 1（仅当日）
        parser.add_argument('--days', type=int, default=1, help='Number of days to analyze')

    def handle(self, *args, **options):
        days = options['days']
        now = timezone.now()
        # 设定统计时间窗口的起始零点
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=days-1)

        # 仅查询已闭合的时间区间 (end_time 不为空)
        logs = TimeLog.objects.filter(start_time__gte=start_date, end_time__isnull=False).order_by('-start_time')

        if not logs.exists():
            self.stdout.write(self.style.WARNING("未检索到有效的时间记录。"))
            return

        category_totals = defaultdict(int)
        total_minutes = 0

        # 1. 打印最近 10 条历史流水记录
        self.stdout.write(self.style.SUCCESS(f"\n=== 历史流水 (Recent History - Top 10) ==="))
        for log in list(logs)[:10]:
            start_str = log.start_time.strftime('%m-%d %H:%M')
            # 获取枚举对应的中文标签
            cat_display = dict(TimeLog.CATEGORY_CHOICES).get(log.category, log.category)
            self.stdout.write(f"[{start_str}] {cat_display:<6} : {log.duration_minutes:>3} min")

        # 2. 执行时间聚合计算
        for log in logs:
            category_totals[log.category] += log.duration_minutes
            total_minutes += log.duration_minutes

        if total_minutes == 0:
            return

        # 3. 渲染终端 ASCII 条形图与占比
        self.stdout.write(self.style.SUCCESS(f"\n=== 分块统计 (Time Allocation - Past {days} Days) ==="))
        self.stdout.write(f"总计追踪时间: {total_minutes / 60:.2f} h\n")

        # 按耗时降序排列
        sorted_cats = sorted(category_totals.items(), key=lambda item: item[1], reverse=True)

        for cat, mins in sorted_cats:
            cat_display = dict(TimeLog.CATEGORY_CHOICES).get(cat, cat)
            percentage = (mins / total_minutes) * 100
            
            # 计算 40 字符长度的进度条
            bar_length = int((percentage / 100) * 40)
            bar = '█' * bar_length + '-' * (40 - bar_length)
            
            # 格式化输出：标签 | 进度条 | 百分比 (绝对分钟数)
            self.stdout.write(f"{cat_display[:6]:<6} | {bar} | {percentage:>5.1f}% ({mins:>3} min)")
        
        self.stdout.write("\n")
