from functools import lru_cache
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .models import DrillLoginHandoff


@lru_cache(maxsize=4)
def _read_drill_html(index_path, mtime_ns, size):
    return index_path.read_text(encoding='utf-8')


def _drill_html():
    index_path = settings.DRILL_FRONTEND_DIST / 'index.html'
    try:
        metadata = index_path.stat()
    except OSError:
        return ''
    return _read_drill_html(index_path, metadata.st_mtime_ns, metadata.st_size)


def is_drill_host(request):
    hostname = request.get_host().partition(':')[0].lower()
    return hostname in settings.DRILL_HOSTS


@never_cache
def site_icon_redirect(request, icon_kind='touch'):
    if is_drill_host(request):
        filename = (
            'drill-favicon-32.png'
            if icon_kind == 'favicon'
            else 'drill-icon-180.png'
        )
        return redirect(f'/static/drill/{filename}?v=img9392')
    return redirect('/static/tracker/img9387-icon-180.png')


def _safe_drill_target(value):
    parsed = urlsplit(value or '')
    if parsed.scheme or parsed.netloc or not parsed.path.startswith('/') or parsed.path.startswith('//'):
        return '/practice'
    path = parsed.path
    allowed = path in {'/', '/practice', '/heatmap'} or path.startswith('/practice/')
    if not allowed:
        return '/practice'
    return path + (f'?{parsed.query}' if parsed.query else '')


def _timer_handoff_url(target_path):
    return f'{settings.DRILL_AUTH_ORIGIN}/drill-auth/start?{urlencode({"next": target_path})}'


@never_cache
def drill_spa_view(request, **_route):
    if not is_drill_host(request) and not settings.DEBUG:
        raise Http404
    if not request.user.is_authenticated:
        target_path = _safe_drill_target(request.get_full_path())
        if settings.DEBUG:
            return redirect(f'{settings.LOGIN_URL}?{urlencode({"next": target_path})}')
        return redirect(_timer_handoff_url(target_path))
    html = _drill_html()
    if not html:
        return render(request, 'frontend_missing.html', status=503)
    response = HttpResponse(html)
    response['Cache-Control'] = 'private, no-store'
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    response['Content-Security-Policy'] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self' data:; connect-src 'self'; "
        "object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
    )
    return response


@login_required
@never_cache
def drill_login_start(request):
    hostname = request.get_host().partition(':')[0].lower()
    if hostname != settings.DRILL_AUTH_HOST and not settings.DEBUG:
        raise Http404
    target_path = _safe_drill_target(request.GET.get('next', '/practice'))
    _, raw_token = DrillLoginHandoff.issue(user=request.user, target_path=target_path)
    return redirect(f'{settings.DRILL_ORIGIN}/drill-auth/complete/{raw_token}')


@never_cache
def drill_login_complete(request, raw_token):
    if not is_drill_host(request) and not settings.DEBUG:
        raise Http404
    if len(raw_token) > 128:
        raise Http404
    with transaction.atomic():
        handoff = DrillLoginHandoff.objects.select_for_update().select_related('user').filter(
            token_digest=DrillLoginHandoff.digest(raw_token),
            expires_at__gt=timezone.now(),
            user__is_active=True,
        ).first()
        if handoff is None:
            raise Http404
        user = handoff.user
        target_path = _safe_drill_target(handoff.target_path)
        handoff.delete()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    response = redirect(target_path)
    response['Cache-Control'] = 'no-store, max-age=0'
    response['Referrer-Policy'] = 'no-referrer'
    return response
