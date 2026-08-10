from django.contrib import admin

from .models import (
    DailyStudyStat, GitHubNoteSync, InviteCode, InviteRedemption, KnowledgePoint,
    LaunchToken, LearningIssue, SessionReview, TimeLog,
)


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
    list_display = ('session', 'status', 'branch', 'attempts', 'markdown_path', 'synced_at')
    list_filter = ('status',)
    readonly_fields = ('session', 'attempts', 'last_error', 'markdown_path', 'synced_at')


admin.site.register(LearningIssue)
admin.site.register(KnowledgePoint)


@admin.register(LaunchToken)
class LaunchTokenAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'category', 'is_active', 'expires_at', 'usage_count')
    readonly_fields = ('token_digest', 'created_at', 'last_used_at', 'usage_count')


@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'is_active', 'use_count', 'max_uses', 'expires_at')
    list_filter = ('is_active', 'created_at')
    readonly_fields = ('code_digest', 'created_by', 'use_count', 'last_used_at', 'created_at')

    def has_add_permission(self, request):
        # Raw codes are generated once from the authenticated Settings screen.
        return False


@admin.register(InviteRedemption)
class InviteRedemptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'invite', 'redeemed_at')
    readonly_fields = ('user', 'invite', 'redeemed_at')

    def has_add_permission(self, request):
        return False


@admin.register(SessionReview)
class SessionReviewAdmin(admin.ModelAdmin):
    list_display = ('session', 'user', 'reviewed_at')
    list_filter = ('reviewed_at',)
    readonly_fields = ('session', 'user', 'reviewed_at')
