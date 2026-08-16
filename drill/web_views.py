from functools import lru_cache

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache


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


@login_required
@never_cache
def drill_spa_view(request, **_route):
    if not is_drill_host(request) and not settings.DEBUG:
        raise Http404
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

