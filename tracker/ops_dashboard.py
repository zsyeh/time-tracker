"""Small, superuser-only operations console for this single-VPS deployment."""

from __future__ import annotations

import http.client
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.db import connection
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST


WEB_SERVICE = 'time-tracker-web.service'
NGINX_SERVICE = 'nginx.service'
DEPLOY_SCRIPT = Path(__file__).resolve().parent.parent / 'deploy' / 'scripts' / 'deploy-native.sh'


def is_dashboard_host(request):
    hostname = request.get_host().partition(':')[0].lower()
    return hostname in settings.DASH_HOSTS


def _require_dashboard_host(request):
    if not is_dashboard_host(request) and not settings.DEBUG:
        raise Http404


def _login_redirect(request):
    target = request.get_full_path() if request.path == '/' else '/'
    query = urlencode({'next': target, 'site': 'dash'})
    return redirect(f'{settings.DRILL_AUTH_ORIGIN}/drill-auth/start?{query}')


def _systemd_state(unit):
    result = subprocess.run(
        ('systemctl', 'is-active', unit),
        capture_output=True,
        text=True,
        timeout=2,
        check=False,
    )
    value = result.stdout.strip() or 'unknown'
    return {'healthy': result.returncode == 0 and value == 'active', 'detail': value}


def _local_http(host, path, expected):
    started = time.perf_counter()
    try:
        client = http.client.HTTPConnection('127.0.0.1', 8000, timeout=2)
        client.request('GET', path, headers={'Host': host, 'X-Forwarded-Proto': 'https'})
        response = client.getresponse()
        response.read(1024)
        client.close()
        latency = round((time.perf_counter() - started) * 1000)
        return response.status in expected, f'HTTP {response.status} · {latency} ms'
    except (OSError, http.client.HTTPException) as exc:
        return False, exc.__class__.__name__


def _referenced_assets(index_path, prefix):
    try:
        html = index_path.read_text(encoding='utf-8')
    except OSError:
        return False, 'build index missing'
    paths = re.findall(rf'/static/{re.escape(prefix)}/([^"\']+\.(?:js|css))', html)
    missing = [path for path in paths if not (settings.STATIC_ROOT / prefix / path).is_file()]
    if not paths:
        return False, 'no JS/CSS references'
    if missing:
        return False, f'{len(missing)} deployed asset(s) missing'
    return True, f'{len(paths)} deployed assets verified'


def _database_state():
    started = time.perf_counter()
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return {'healthy': True, 'detail': f'connected · {round((time.perf_counter() - started) * 1000)} ms'}
    except Exception as exc:  # Database backends expose different exception classes.
        return {'healthy': False, 'detail': exc.__class__.__name__}


def _memory_metrics():
    values = {}
    try:
        for line in Path('/proc/meminfo').read_text(encoding='ascii').splitlines():
            key, raw = line.split(':', 1)
            values[key] = int(raw.strip().split()[0]) * 1024
    except (OSError, ValueError):
        return {'used': 'Unavailable', 'available': 'Unavailable', 'percent': 0}
    total = values.get('MemTotal', 0)
    available = values.get('MemAvailable', 0)
    used = max(total - available, 0)
    return {
        'used': _human_bytes(used),
        'available': _human_bytes(available),
        'percent': round((used / total) * 100) if total else 0,
    }


def _recent_oom_incident():
    """Report the latest kernel OOM kill without marking recovered services down."""

    result = _run_checked((
        'journalctl', '-k', '--since=-24 hours', '--no-pager', '-o', 'short-iso',
        '--grep=Out of memory: Killed process', '-n', '1',
    ), timeout=3)
    if result.returncode != 0:
        return {'detected': False, 'detail': 'Kernel incident history unavailable'}
    events = [
        line.strip() for line in result.stdout.splitlines()
        if 'Out of memory: Killed process' in line
    ]
    if not events:
        return {'detected': False, 'detail': 'No kernel OOM kills in the last 24 hours'}
    return {'detected': True, 'detail': events[-1][-220:]}


def _build_metrics():
    builds = []
    for name, path in (
        ('Timer', settings.FRONTEND_DIST / 'index.html'),
        ('Drill / EI', settings.DRILL_FRONTEND_DIST / 'index.html'),
    ):
        try:
            metadata = path.stat()
            built_at = datetime.fromtimestamp(metadata.st_mtime).astimezone()
            detail = built_at.strftime('%Y-%m-%d %H:%M:%S %Z')
            healthy = metadata.st_size > 0
        except OSError:
            detail = 'Build index missing'
            healthy = False
        builds.append({'name': name, 'healthy': healthy, 'detail': detail})
    return builds


def _human_bytes(value):
    size = float(value)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size < 1024 or unit == 'TB':
            return f'{size:.1f} {unit}' if unit in {'GB', 'TB'} else f'{size:.0f} {unit}'
        size /= 1024
    return f'{size:.1f} TB'


def _service_rows():
    web = _systemd_state(WEB_SERVICE)
    nginx = _systemd_state(NGINX_SERVICE)
    services = []
    for name, host, path, expected, index_path, prefix in (
        ('Timer', 'timer.ehzsy.site', '/accounts/login/', {200}, settings.FRONTEND_DIST / 'index.html', 'app'),
        ('Drill', 'drill.ehzsy.site', '/', {302}, settings.DRILL_FRONTEND_DIST / 'index.html', 'drill'),
        ('EI / 892', 'ei.ehzsy.site', '/', {302}, settings.DRILL_FRONTEND_DIST / 'index.html', 'drill'),
    ):
        route_ok, route_detail = _local_http(host, path, expected)
        assets_ok, asset_detail = _referenced_assets(index_path, prefix)
        services.append({
            'name': name,
            'host': host,
            'url': f'https://{host}/',
            'healthy': web['healthy'] and nginx['healthy'] and route_ok and assets_ok,
            'detail': f'{route_detail} · {asset_detail}',
        })
    services.extend([
        {'name': 'Django / Gunicorn', 'host': WEB_SERVICE, 'url': '', **web},
        {'name': 'Nginx', 'host': NGINX_SERVICE, 'url': '', **nginx},
        {'name': 'PostgreSQL', 'host': connection.settings_dict.get('NAME', 'database'), 'url': '', **_database_state()},
    ])
    return services


@never_cache
def operations_dashboard(request):
    _require_dashboard_host(request)
    if not request.user.is_authenticated:
        return _login_redirect(request)
    if not request.user.is_superuser:
        return HttpResponseForbidden('Administrator access required.')

    disk = shutil.disk_usage(settings.BASE_DIR)
    memory = _memory_metrics()
    load = os.getloadavg()
    context = {
        'services': _service_rows(),
        'all_healthy': False,
        'disk': {
            'used': _human_bytes(disk.used),
            'free': _human_bytes(disk.free),
            'percent': round((disk.used / disk.total) * 100) if disk.total else 0,
        },
        'memory': memory,
        'load': f'{load[0]:.2f} / {load[1]:.2f} / {load[2]:.2f}',
        'cores': os.cpu_count() or 1,
        'builds': _build_metrics(),
        'oom_incident': _recent_oom_incident(),
        'checked_at': datetime.now().astimezone(),
    }
    context['all_healthy'] = all(item['healthy'] for item in context['services'])
    return render(request, 'operations/dashboard.html', context)


def _run_checked(arguments, timeout=30):
    return subprocess.run(arguments, capture_output=True, text=True, timeout=timeout, check=False)


def _schedule_restart():
    unit_name = f'time-tracker-dashboard-restart-{int(time.time())}'
    return _run_checked((
        'systemd-run', f'--unit={unit_name}', '--on-active=2s',
        '/bin/systemctl', 'restart', WEB_SERVICE,
    ), timeout=5)


def _schedule_safe_deploy():
    unit_name = f'time-tracker-dashboard-deploy-{int(time.time())}'
    return _run_checked((
        'systemd-run', f'--unit={unit_name}', '--collect',
        '/bin/sh', str(DEPLOY_SCRIPT),
    ), timeout=5)


@require_POST
@never_cache
def dashboard_action(request):
    _require_dashboard_host(request)
    if not request.user.is_authenticated:
        return _login_redirect(request)
    if not request.user.is_superuser:
        return HttpResponseForbidden('Administrator access required.')

    action = request.POST.get('action', '')
    if action == 'reload_nginx':
        check = _run_checked(('nginx', '-t'), timeout=5)
        result = check if check.returncode else _run_checked(('systemctl', 'reload', NGINX_SERVICE), timeout=5)
        label = 'Nginx configuration reloaded'
    elif action == 'restart_web':
        result = _schedule_restart()
        label = 'Web service restart scheduled'
    elif action == 'repair_assets':
        result = _run_checked((sys.executable, str(settings.BASE_DIR / 'manage.py'), 'collectstatic', '--noinput'), timeout=60)
        if result.returncode == 0:
            result = _schedule_restart()
        label = 'Static assets repaired and web restart scheduled'
    elif action == 'safe_deploy':
        result = _schedule_safe_deploy()
        label = 'Safe frontend rebuild and deployment queued'
    else:
        raise Http404

    if result.returncode == 0:
        messages.success(request, label)
    else:
        messages.error(request, f'Action failed: {(result.stderr or result.stdout).strip()[-240:]}')
    return redirect('/')
