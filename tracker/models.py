from django.db import models
from django.utils import timezone


class TimeLog(models.Model):
    # 统一枚举值与前端 payload 严格对应
    CATEGORY_CHOICES = [
        ('math', '数学'),
        ('english', '英语'),
        ('major', '专业课'),
        ('training', '训练'), 
    ]
    
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    # A completed session can carry the longer summary/report submitted from
    # ChatGPT through MCP. Existing short notes remain fully compatible.
    note = models.TextField(null=True, blank=True)

    @property
    def duration_minutes(self):
        """计算离散时间差，返回标量分钟数"""
        if self.end_time:
            delta = self.end_time - self.start_time
            return int(delta.total_seconds() / 60)
        return 0

    def __str__(self):
        return f"{self.category} | {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}"


class DailyStudyStat(models.Model):
    """Denormalized statistics for completed study logs on one local day."""

    date = models.DateField(unique=True)
    study_count = models.PositiveIntegerField(default=0)
    first_start_time = models.DateTimeField()
    total_minutes = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('-date',)

    @property
    def average_minutes(self):
        if not self.study_count:
            return 0
        return int(self.total_minutes / self.study_count)

    def __str__(self):
        return f"{self.date} | {self.study_count} sessions"
