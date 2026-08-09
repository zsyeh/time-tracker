from django.contrib import admin
from django.urls import include, path

from tracker.api_views import (
    DashboardOverviewView,
    KnowledgePointDetailView,
    KnowledgePointListCreateView,
    LaunchTokenActionView,
    LaunchTokenListCreateView,
    LearningIssueDetailView,
    LearningIssueListCreateView,
    SessionAbandonView,
    SessionDetailView,
    SessionFinishView,
    SessionListCreateView,
    auth_logout,
    auth_session,
    export_csv,
    export_json,
    export_markdown,
)
from tracker.web_views import LaunchDeviceView, direct_start_view, launch_browser_view, spa_view


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('start/<str:subject>', direct_start_view, name='direct_start'),
    path('launch/<str:raw_token>', launch_browser_view, name='launch_browser'),
    path('api/launch/<str:raw_token>/start', LaunchDeviceView.as_view(), name='launch_device'),
    path('api/auth/session/', auth_session, name='auth_session'),
    path('api/auth/logout/', auth_logout, name='auth_logout'),
    path('api/sessions/', SessionListCreateView.as_view(), name='session_list'),
    path('api/sessions/<int:pk>/', SessionDetailView.as_view(), name='session_detail'),
    path('api/sessions/<int:pk>/finish/', SessionFinishView.as_view(), name='session_finish'),
    path('api/sessions/<int:pk>/abandon/', SessionAbandonView.as_view(), name='session_abandon'),
    path('api/dashboard/overview/', DashboardOverviewView.as_view(), name='dashboard_overview'),
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
    path('', spa_view, name='dashboard'),
]
