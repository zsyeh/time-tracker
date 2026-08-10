import secrets

from django.contrib import admin, messages
from django.core.cache import cache
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from .forms import AdminInviteCodeForm

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
    change_list_template = 'admin/tracker/invitecode/change_list.html'
    list_display = (
        'name', 'created_by', 'availability', 'use_count', 'max_uses',
        'remaining_uses_display', 'visitor_count', 'last_used_at', 'expires_at',
    )
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'created_by__username', 'redemptions__user__username')
    readonly_fields = (
        'name', 'code_digest', 'created_by', 'max_uses', 'use_count',
        'last_used_at', 'created_at',
    )

    @admin.display(description='Status', boolean=True)
    def availability(self, obj):
        return obj.usable

    @admin.display(description='Remaining', ordering='use_count')
    def remaining_uses_display(self, obj):
        return obj.remaining_uses

    @admin.display(description='Visitors')
    def visitor_count(self, obj):
        return obj.redemptions.count()

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by').prefetch_related(
            'redemptions__user',
        )

    def get_urls(self):
        custom = [
            path(
                'dashboard/',
                self.admin_site.admin_view(self.invite_dashboard),
                name='tracker_invitecode_dashboard',
            ),
        ]
        return custom + super().get_urls()

    def invite_dashboard(self, request):
        if request.method == 'POST':
            form = AdminInviteCodeForm(request.POST)
            if form.is_valid():
                invite, raw_code = InviteCode.issue(
                    created_by=request.user,
                    **form.cleaned_data,
                )
                reveal_token = secrets.token_urlsafe(20)
                cache.set(
                    f'invite-admin-reveal:{request.user.pk}:{reveal_token}',
                    raw_code,
                    timeout=5 * 60,
                )
                messages.success(request, f'Invite “{invite.name}” was generated.')
                target = reverse('admin:tracker_invitecode_dashboard')
                return redirect(f'{target}?reveal={reveal_token}')
        else:
            form = AdminInviteCodeForm()

        raw_code = None
        reveal_token = request.GET.get('reveal', '')[:80]
        if reveal_token:
            reveal_key = f'invite-admin-reveal:{request.user.pk}:{reveal_token}'
            raw_code = cache.get(reveal_key)
            cache.delete(reveal_key)

        invitations = list(
            InviteCode.objects.select_related('created_by').prefetch_related(
                'redemptions__user',
            )[:100]
        )
        context = {
            **self.admin_site.each_context(request),
            'title': 'Invitation control',
            'opts': self.model._meta,
            'form': form,
            'raw_code': raw_code,
            'invitations': invitations,
            'invite_count': len(invitations),
            'available_count': sum(1 for invite in invitations if invite.usable),
            'remaining_count': sum(invite.remaining_uses for invite in invitations if invite.usable),
            'visitor_count': sum(invite.use_count for invite in invitations),
        }
        response = TemplateResponse(
            request,
            'admin/tracker/invitecode/dashboard.html',
            context,
        )
        response['Cache-Control'] = 'private, no-store, max-age=0'
        return response

    def has_add_permission(self, request):
        # Raw codes are generated once from the authenticated Settings screen.
        return False


@admin.register(InviteRedemption)
class InviteRedemptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'invite', 'redeemed_at')
    list_filter = ('redeemed_at', 'invite')
    search_fields = ('user__username', 'invite__name')
    readonly_fields = ('user', 'invite', 'redeemed_at')

    def has_add_permission(self, request):
        return False


@admin.register(SessionReview)
class SessionReviewAdmin(admin.ModelAdmin):
    list_display = ('session', 'user', 'reviewed_at')
    list_filter = ('reviewed_at',)
    readonly_fields = ('session', 'user', 'reviewed_at')
