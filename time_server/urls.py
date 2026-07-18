"""
URL configuration for time_server project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from tracker.views import api_action, daily_stats_view, dashboard_view, export_logs_csv

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard_view, name='dashboard'),      # 根目录直接指向面板
    path('daily-stats/', daily_stats_view, name='daily_stats'),
    path('api/action/', api_action, name='api_action'), # 按钮操作 API
    path('api/export.csv', export_logs_csv, name='export_logs_csv'),
]
