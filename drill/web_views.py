from functools import lru_cache
import re
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
    html = _read_drill_html(index_path, metadata.st_mtime_ns, metadata.st_size)
    asset_version = str(metadata.st_mtime_ns)
    return re.sub(
        r'(/static/drill/assets/[^"\']+?)(?:\?[^"\']*)?(?=["\'])',
        rf'\1?v={asset_version}',
        html,
    )


def practice_site(request):
    hostname = request.get_host().partition(':')[0].lower()
    if hostname in settings.EI_HOSTS:
        return 'ei'
    if hostname in settings.DRILL_HOSTS:
        return 'drill'
    return None


def is_practice_host(request):
    return practice_site(request) is not None


def is_drill_host(request):
    return practice_site(request) == 'drill'


@never_cache
def site_icon_redirect(request, icon_kind='touch'):
    if is_practice_host(request):
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
    allowed = path in {
        '/', '/practice', '/activity', '/book-activity', '/heatmap', '/paper', '/favorites', '/review-later',
        '/feel', '/insight',
    } or path.startswith('/practice/')
    if not allowed:
        return '/practice'
    return path + (f'?{parsed.query}' if parsed.query else '')


def _practice_origin(site):
    return settings.EI_ORIGIN if site == 'ei' else settings.DRILL_ORIGIN


def _timer_handoff_url(target_path, site):
    return f'{settings.DRILL_AUTH_ORIGIN}/drill-auth/start?{urlencode({"next": target_path, "site": site})}'


@never_cache
def drill_spa_view(request, **_route):
    site = practice_site(request)
    if site is None and not settings.DEBUG:
        raise Http404
    site = site or 'drill'
    if not request.user.is_authenticated:
        target_path = _safe_drill_target(request.get_full_path())
        if settings.DEBUG:
            return redirect(f'{settings.LOGIN_URL}?{urlencode({"next": target_path})}')
        return redirect(_timer_handoff_url(target_path, site))
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
    target_site = request.GET.get('site', 'drill')
    if target_site not in {'drill', 'ei'}:
        raise Http404
    _, raw_token = DrillLoginHandoff.issue(
        user=request.user,
        target_path=target_path,
        target_site=target_site,
    )
    return redirect(f'{_practice_origin(target_site)}/drill-auth/complete/{raw_token}')


@never_cache
def drill_login_complete(request, raw_token):
    site = practice_site(request)
    if site is None and not settings.DEBUG:
        raise Http404
    site = site or 'drill'
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
        if handoff.target_site != site:
            raise Http404
        user = handoff.user
        target_path = _safe_drill_target(handoff.target_path)
        handoff.delete()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    response = redirect(target_path)
    response['Cache-Control'] = 'no-store, max-age=0'
    response['Referrer-Policy'] = 'no-referrer'
    return response
