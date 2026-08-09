from django.contrib import admin

from .models import DailyStudyStat, GitHubNoteSync, KnowledgePoint, LaunchToken, LearningIssue, TimeLog


@admin.register(TimeLog)
class TimeLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'status', 'start_time', 'end_time', 'duration_minutes')
    list_filter = ('user', 'category', 'status', 'start_time')
    search_fields = ('title', 'details', 'chapter', 'topic')


@admin.register(DailyStudyStat)
class DailyStudyStatAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'study_count', 'first_start_time', 'total_minutes')
    ordering = ('-date',)


@admin.register(GitHubNoteSync)
class GitHubNoteSyncAdmin(admin.ModelAdmin):
    list_display = ('session', 'status', 'attempts', 'markdown_path', 'synced_at')
    list_filter = ('status',)
    readonly_fields = ('session', 'attempts', 'last_error', 'markdown_path', 'synced_at')


admin.site.register(LearningIssue)
admin.site.register(KnowledgePoint)


@admin.register(LaunchToken)
class LaunchTokenAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'category', 'is_active', 'expires_at', 'usage_count')
    readonly_fields = ('token_digest', 'created_at', 'last_used_at', 'usage_count')
