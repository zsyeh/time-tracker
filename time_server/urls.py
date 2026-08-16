from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from allauth.account.views import signup_by_passkey
from allauth.mfa.webauthn.views import signup_webauthn

from tracker.api_views import (
    CompletionOptionsView,
    DashboardOverviewView,
    GlobalSearchView,
    InviteCodeActionView,
    InviteCodeListCreateView,
    KnowledgePointDetailView,
    KnowledgePointListCreateView,
    LaunchTokenActionView,
    LaunchTokenListCreateView,
    LearningIssueDetailView,
    LearningIssueListCreateView,
    RuntimeSettingsView,
    StudyTagDetailView,
    StudyTagListCreateView,
    TaskPresetDetailView,
    TaskPresetListCreateView,
    UserDataEncryptionView,
    SessionAbandonView,
    SessionDetailView,
    SessionFinishView,
    SessionListCreateView,
    SessionReviewView,
    SessionShareView,
    SessionUuidDetailView,
    PublicSessionShareView,
    auth_logout,
    auth_session,
    export_csv,
    export_json,
    export_markdown,
)
from tracker.public_views import contact_view, guide_view, legal_view
from tracker.stress_probe import StressTestProbeView
from tracker.web_views import (
    LaunchDeviceView, LaunchDisturbanceView, direct_start_view,
    launch_browser_view, public_spa_view, spa_view,
)


urlpatterns = [
    path(
        'icon-180.png',
        RedirectView.as_view(
            url='/static/tracker/img9387-icon-180.png',
            permanent=False,
        ),
        name='apple_touch_icon',
    ),
    path('admin/', admin.site.urls),
    # django-allauth normally exposes Passkey signup only alongside mandatory
    # email verification. This private instance uses its invite form instead.
    path('accounts/signup/passkey/', signup_by_passkey, name='account_signup_by_passkey'),
    path('accounts/2fa/webauthn/signup/', signup_webauthn, name='mfa_signup_webauthn'),
    path('accounts/', include('allauth.urls')),
    path('guide/', guide_view, name='guide'),
    path('legal/', legal_view, name='legal'),
    path('contact/', contact_view, name='contact'),
    path('start/<str:subject>', direct_start_view, name='direct_start'),
    path('launch/<str:raw_token>', launch_browser_view, name='launch_browser'),
    path('api/launch/<str:raw_token>/start', LaunchDeviceView.as_view(), name='launch_device'),
    path(
        'api/disturbance/<str:raw_token>/record',
        LaunchDisturbanceView.as_view(),
        name='launch_disturbance',
    ),
    path('api/auth/session/', auth_session, name='auth_session'),
    path('api/auth/logout/', auth_logout, name='auth_logout'),
    path('api/stress-test/probe/', StressTestProbeView.as_view(), name='stress_test_probe'),
    path('api/sessions/', SessionListCreateView.as_view(), name='session_list'),
    path('api/sessions/<int:pk>/', SessionDetailView.as_view(), name='session_detail'),
    path('api/sessions/<int:pk>/finish/', SessionFinishView.as_view(), name='session_finish'),
    path('api/sessions/<int:pk>/abandon/', SessionAbandonView.as_view(), name='session_abandon'),
    path('api/sessions/<int:pk>/reviews/', SessionReviewView.as_view(), name='session_reviews'),
    path('api/sessions/<uuid:session_uuid>/reviews/', SessionReviewView.as_view(), name='session_uuid_reviews'),
    path('api/sessions/<uuid:session_uuid>/share/', SessionShareView.as_view(), name='session_share'),
    path('api/sessions/<uuid:session_uuid>/', SessionUuidDetailView.as_view(), name='session_uuid_detail'),
    path('api/public/shares/<str:raw_token>/', PublicSessionShareView.as_view(), name='public_session_share'),
    path('api/dashboard/overview/', DashboardOverviewView.as_view(), name='dashboard_overview'),
    path('api/settings/runtime/', RuntimeSettingsView.as_view(), name='runtime_settings'),
    path('api/settings/data-encryption/', UserDataEncryptionView.as_view(), name='data_encryption_settings'),
    path('api/study-tags/', StudyTagListCreateView.as_view(), name='study_tag_list'),
    path('api/study-tags/<int:pk>/', StudyTagDetailView.as_view(), name='study_tag_detail'),
    path('api/task-presets/', TaskPresetListCreateView.as_view(), name='task_preset_list'),
    path('api/task-presets/<int:pk>/', TaskPresetDetailView.as_view(), name='task_preset_detail'),
    path('api/completion-options/', CompletionOptionsView.as_view(), name='completion_options'),
    path('api/invite-codes/', InviteCodeListCreateView.as_view(), name='invite_code_list'),
    path('api/invite-codes/<int:pk>/<str:action>/', InviteCodeActionView.as_view(), name='invite_code_action'),
    path('api/search/', GlobalSearchView.as_view(), name='global_search'),
    path('api/issues/', LearningIssueListCreateView.as_view(), name='issue_list'),
    path('api/issues/<int:pk>/', LearningIssueDetailView.as_view(), name='issue_detail'),
    path('api/knowledge/', KnowledgePointListCreateView.as_view(), name='knowledge_list'),
    path('api/knowledge/<int:pk>/', KnowledgePointDetailView.as_view(), name='knowledge_detail'),
    path('api/launch-tokens/', LaunchTokenListCreateView.as_view(), name='launch_token_list'),
    path(
        'api/launch-tokens/<int:pk>/<str:action>/',
        LaunchTokenActionView.as_view(),
        name='launch_token_action',
    ),
    path('api/export/csv/', export_csv, name='export_csv'),
    path('api/export/json/', export_json, name='export_json'),
    path('api/export/markdown/', export_markdown, name='export_markdown'),
    # Explicit SPA history fallbacks keep Django API/Auth/device endpoints out
    # of the catchment while allowing direct browser refreshes.
    path('today', spa_view, name='spa_today'),
    path('trends', spa_view, name='spa_trends'),
    path('sessions', spa_view, name='spa_sessions'),
    path('sessions/<uuid:session_uuid>', spa_view, name='spa_session_detail'),
    path('issues', spa_view, name='spa_issues'),
    path('settings', spa_view, name='spa_settings'),
    path('share/<str:raw_token>', public_spa_view, name='spa_public_share'),
    path('', spa_view, name='dashboard'),
]
