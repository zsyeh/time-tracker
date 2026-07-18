from django.contrib import admin

from .models import DailyStudyStat, TimeLog


@admin.register(TimeLog)
class TimeLogAdmin(admin.ModelAdmin):
    list_display = ('category', 'start_time', 'end_time', 'duration_minutes')
    list_filter = ('category', 'start_time')


@admin.register(DailyStudyStat)
class DailyStudyStatAdmin(admin.ModelAdmin):
    list_display = ('date', 'study_count', 'first_start_time', 'total_minutes')
    ordering = ('-date',)
