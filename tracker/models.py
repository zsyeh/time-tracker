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
    note = models.CharField(max_length=255, null=True, blank=True)

    @property
    def duration_minutes(self):
        """计算离散时间差，返回标量分钟数"""
        if self.end_time:
            delta = self.end_time - self.start_time
            return int(delta.total_seconds() / 60)
        return 0

    def __str__(self):
        return f"{self.category} | {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}"
