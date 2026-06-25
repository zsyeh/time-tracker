from django.contrib import admin
from .models import TimeLog

@admin.register(TimeLog)
class TimeLogAdmin(admin.ModelAdmin):
    list_display = ('category', 'start_time', 'end_time', 'duration_minutes')
    list_filter = ('category', 'start_time')
