import secrets
import time
from urllib.parse import urlencode

from allauth.account.adapter import get_adapter
from allauth.core.internal.ratelimit import parse_rates, truncate_ip
from django.conf import settings
from django.contrib import admin, messages
from django.core.cache import cache
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from .forms import AdminInviteCodeForm, LoginRateLimitResetForm, RegistrationPolicyForm

from .models import (
    DailyStudyStat, GitHubNoteSync, InviteCode, InviteRedemption, KnowledgePoint,
    LaunchToken, LearningIssue, SessionReview, SiteConfiguration, TimeLog,
    SessionShare, UserDataEncryptionPreference,
)


LOGIN_RATE_ACTIONS = ('login', 'login_failed')


def _rate_cache_key(action, network_address):
    return f'allauth:rl:{action}:ip:{truncate_ip(network_address)}'


def _rate_window_label(seconds):
    if seconds % 3600 == 0:
        return f'{int(seconds / 3600)} hour'
    if seconds % 60 == 0:
        return f'{int(seconds / 60)} minutes'
    return f'{int(seconds)} seconds'


def login_rate_status(network_address):
    now = time.time()
    rows = []
    for action in LOGIN_RATE_ACTIONS:
        history = cache.get(_rate_cache_key(action, network_address), [])
        for rate in parse_rates(settings.ACCOUNT_RATE_LIMITS.get(action)):
            if rate.per != 'ip':
                continue
            used = sum(timestamp > now - rate.duration for timestamp in history)
            rows.append({
                'action': action,
                'limit': rate.amount,
                'window': _rate_window_label(rate.duration),
                'used': used,
                'remaining': max(0, rate.amount - used),
            })
    return rows


def clear_login_rate_limits(network_address):
    for action in LOGIN_RATE_ACTIONS:
        cache.delete(_rate_cache_key(action, network_address))


@admin.register(TimeLog)
class TimeLogAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'category', 'status', 'start_time', 'end_time',
        'duration_minutes', 'disturbance_count',
    )
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
    list_display = (
        'name', 'user', 'category', 'is_active', 'is_paused',
        'available_from', 'available_until', 'expires_at', 'usage_count',
    )
    readonly_fields = (
        'token_digest', 'disturbance_token_digest', 'created_at',
        'last_used_at', 'usage_count',
    )


@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    change_list_template = 'admin/tracker/invitecode/change_list.html'
    list_display = (
        'name', 'created_by', 'availability', 'use_count', 'max_uses',
        'remaining_uses_display', 'visitor_count', 'is_self_service',
        'issued_local_date', 'last_used_at', 'expires_at',
    )
    list_filter = ('is_active', 'is_self_service', 'created_at')
    search_fields = ('name', 'created_by__username', 'redemptions__user__username')
    readonly_fields = (
        'name', 'code_digest', 'created_by', 'max_uses', 'use_count',
        'is_self_service', 'issued_local_date', 'last_used_at', 'created_at',
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
            path(
                'auth-recovery/',
                self.admin_site.admin_view(self.auth_recovery),
                name='tracker_auth_recovery',
            ),
        ]
        return custom + super().get_urls()

    def auth_recovery(self, request):
        current_network = get_adapter().get_client_ip(request)
        initial_network = request.GET.get('network', '').strip() or current_network
        form = LoginRateLimitResetForm(
            request.POST or None,
            initial={'network_address': initial_network},
        )
        selected_network = initial_network
        if request.method == 'POST' and form.is_valid():
            selected_network = form.cleaned_data['network_address'] or current_network
            if request.POST.get('scope') == 'all':
                cache.clear()
                messages.success(request, 'All temporary authentication limits were reset.')
            else:
                clear_login_rate_limits(selected_network)
                messages.success(request, f'Login limits for {selected_network} were reset.')
            target = reverse('admin:tracker_auth_recovery')
            return redirect(f'{target}?{urlencode({"network": selected_network})}')

        context = {
            **self.admin_site.each_context(request),
            'title': 'Authentication recovery',
            'opts': self.model._meta,
            'form': form,
            'current_network': current_network,
            'selected_network': selected_network,
            'rate_status': login_rate_status(selected_network),
        }
        response = TemplateResponse(
            request,
            'admin/tracker/invitecode/auth_recovery.html',
            context,
        )
        response['Cache-Control'] = 'private, no-store, max-age=0'
        return response

    def invite_dashboard(self, request):
        configuration = SiteConfiguration.load()
        policy_form = RegistrationPolicyForm(
            initial={
                'registration_open': configuration.registration_open,
                'math_visualization_enabled': configuration.math_visualization_enabled,
            },
        )
        if request.method == 'POST' and request.POST.get('action') == 'registration_policy':
            policy_form = RegistrationPolicyForm(request.POST)
            form = AdminInviteCodeForm()
            if policy_form.is_valid():
                configuration.registration_open = policy_form.cleaned_data['registration_open']
                configuration.math_visualization_enabled = policy_form.cleaned_data['math_visualization_enabled']
                configuration.updated_by = request.user
                configuration.save(update_fields=(
                    'registration_open', 'math_visualization_enabled', 'updated_by', 'updated_at',
                ))
                state = 'open' if configuration.registration_open else 'invite-only'
                math_state = 'enabled' if configuration.math_visualization_enabled else 'disabled'
                messages.success(request, f'Registration is now {state}. Math visualization is {math_state}.')
                return redirect(reverse('admin:tracker_invitecode_dashboard'))
        elif request.method == 'POST':
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
            'policy_form': policy_form,
            'configuration': configuration,
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


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    list_display = ('registration_open', 'math_visualization_enabled', 'updated_by', 'updated_at')
    readonly_fields = ('singleton_key', 'updated_by', 'updated_at')
    fields = ('registration_open', 'math_visualization_enabled', 'singleton_key', 'updated_by', 'updated_at')

    def has_add_permission(self, request):
        return not SiteConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.singleton_key = 1
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


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


@admin.register(SessionShare)
class SessionShareAdmin(admin.ModelAdmin):
    list_display = ('session', 'is_active', 'created_at', 'expires_at', 'revoked_at')
    list_filter = ('is_active', 'created_at', 'expires_at')
    readonly_fields = ('session', 'token_digest', 'created_at', 'expires_at', 'revoked_at', 'is_active')

    def has_add_permission(self, request):
        return False


@admin.register(UserDataEncryptionPreference)
class UserDataEncryptionPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'enabled', 'updated_at')
    list_filter = ('enabled', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('user', 'enabled', 'updated_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
