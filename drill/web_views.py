from functools import lru_cache
import ipaddress
import json
import re
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from allauth.account.internal.flows.login import get_authentication_records
from allauth.mfa.webauthn.forms import ReauthenticateWebAuthnForm
from allauth.mfa.webauthn.internal import auth as webauthn_auth

from .models import DrillLoginHandoff, QuestionAsset
from .sharing import (
    public_share, public_share_context, public_share_url, share_contains_asset, share_markdown,
)


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


def dedicated_private_workspace(request):
    """Dedicated local containers follow the requested LAN IP, not a saved IP."""
    hostname = urlsplit('//' + request.get_host()).hostname or ''
    try:
        private = ipaddress.ip_address(hostname).is_private
    except ValueError:
        private = hostname == 'localhost'
    if not private:
        return None
    disabled = {'disabled.invalid'}
    if settings.EI_HOSTS == disabled and settings.DRILL_HOSTS != disabled:
        return 'drill'
    if settings.DRILL_HOSTS == disabled and settings.EI_HOSTS != disabled:
        return 'ei'
    return None


def practice_site(request):
    hostname = (urlsplit('//' + request.get_host()).hostname or '').lower()
    if hostname in settings.EI_HOSTS:
        return 'ei'
    if hostname in settings.DRILL_HOSTS:
        return 'drill'
    return dedicated_private_workspace(request)


def handoff_site(request):
    hostname = request.get_host().partition(':')[0].lower()
    if hostname in settings.DASH_HOSTS:
        return 'dash'
    return practice_site(request)


def is_practice_host(request):
    return practice_site(request) is not None


def is_drill_host(request):
    return practice_site(request) == 'drill'


def _public_share_headers(response):
    response['Cache-Control'] = 'no-store, max-age=0'
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    response['Referrer-Policy'] = 'no-referrer'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@never_cache
def public_drill_share_view(request, raw_token):
    workspace = practice_site(request)
    if workspace is None:
        raise Http404
    share = public_share(raw_token, workspace)
    context = public_share_context(request, share, raw_token)
    context.update({
        'is_authenticated': request.user.is_authenticated,
        'markdown_url': public_share_url(request, workspace, raw_token, '/content.md'),
    })
    response = render(request, 'drill/public_share.html', context)
    response['Content-Security-Policy'] = (
        "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    )
    response['Link'] = f'<{context["markdown_url"]}>; rel="alternate"; type="text/plain"'
    return _public_share_headers(response)


@never_cache
def public_drill_share_markdown_view(request, raw_token):
    workspace = practice_site(request)
    if workspace is None:
        raise Http404
    share = public_share(raw_token, workspace)
    context = public_share_context(request, share, raw_token)
    # A number of AI/web readers reject the still-uncommon text/markdown MIME
    # even though the body is ordinary UTF-8 text. Keep Markdown syntax while
    # advertising the broadly supported plain-text representation.
    response = HttpResponse(share_markdown(context), content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = 'inline; filename="shared-study-content.md"'
    return _public_share_headers(response)


@never_cache
def public_drill_share_asset_view(request, raw_token, asset_id):
    workspace = practice_site(request)
    if workspace is None:
        raise Http404
    share = public_share(raw_token, workspace)
    if not share_contains_asset(share, asset_id):
        raise Http404
    asset = get_object_or_404(QuestionAsset.objects.only('image_data', 'mime_type', 'sha256'), pk=asset_id)
    response = HttpResponse(bytes(asset.image_data), content_type=asset.mime_type)
    response['ETag'] = f'"{asset.sha256}"'
    response['Content-Disposition'] = f'inline; filename="shared-question-{asset_id}.png"'
    return _public_share_headers(response)


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


def _safe_drill_target(value, site='drill'):
    parsed = urlsplit(value or '')
    if parsed.scheme or parsed.netloc or not parsed.path.startswith('/') or parsed.path.startswith('//'):
        return '/' if site == 'dash' else '/practice'
    path = parsed.path
    if site == 'dash':
        return path + (f'?{parsed.query}' if parsed.query else '') if path == '/' else '/'
    allowed = path in {
        '/', '/practice', '/activity', '/book-activity', '/heatmap', '/selected-heatmap', '/paper', '/papers', '/favorites', '/review-later',
        '/feel', '/insight', '/errata', '/cockpit', '/circuit-selected', '/signal-selected', '/signal-formulas', '/analog-selected', '/digital-selected', '/communication-selected', '/core-heatmap',
        '/diagnostics', '/diagnostic-queue', '/selected-pdf-pages',
    } or path.startswith('/practice/') or path.startswith('/papers/')
    if not allowed:
        return '/practice'
    return path + (f'?{parsed.query}' if parsed.query else '')


def _safe_ip_target(value):
    """Allow only known UI paths on the fixed IP origin."""
    parsed = urlsplit(value or '')
    if parsed.scheme or parsed.netloc or not parsed.path.startswith('/') or parsed.path.startswith('//'):
        return '/'
    path = parsed.path
    timer_paths = {'/', '/today', '/trends', '/sessions', '/issues', '/settings'}
    prefixed_ui = ('/drill', '/ei')
    allowed = path in timer_paths or any(
        path == prefix or path.startswith(prefix + '/') for prefix in prefixed_ui
    )
    if not allowed:
        return '/'
    return path + (f'?{parsed.query}' if parsed.query else '')


def _is_ip_entry_request(request):
    return request.META.get('HTTP_X_TIME_TRACKER_EXTERNAL_HOST', '').split(':', 1)[0] == settings.IP_AUTH_EXTERNAL_HOST


def _target_origin(site):
    if site == 'dash':
        return settings.DASH_ORIGIN
    return settings.EI_ORIGIN if site == 'ei' else settings.DRILL_ORIGIN


def _timer_handoff_url(target_path, site):
    return f'{settings.DRILL_AUTH_ORIGIN}/drill-auth/start?{urlencode({"next": target_path, "site": site})}'


@never_cache
@require_http_methods(['GET', 'POST'])
def ip_login_start(request):
    """Verify a fresh Timer Passkey assertion before issuing an IP session."""
    target_path = _safe_ip_target(request.GET.get('next', '/'))
    hostname = request.get_host().partition(':')[0].lower()
    if _is_ip_entry_request(request):
        canonical = f'{settings.DRILL_AUTH_ORIGIN}/ip-auth/start?{urlencode({"next": target_path})}'
        return redirect(canonical)
    if hostname != settings.DRILL_AUTH_HOST and not settings.DEBUG:
        raise Http404
    if not request.user.is_authenticated:
        return redirect(f'{settings.LOGIN_URL}?{urlencode({"next": request.get_full_path()})}')
    return _verify_passkey_handoff(request, target_path, 'ip')


def _verify_passkey_handoff(request, target_path, target_site):
    """Require one current WebAuthn assertion for an explicit Passkey handoff."""
    if request.method == 'GET':
        used_at = request.session.get('handoff_used_passkey_at', 0)
        if not isinstance(used_at, (int, float)):
            used_at = 0
        now = timezone.now().timestamp()
        fresh = next((record for record in reversed(get_authentication_records(request, request.user))
                      if record.get('method') == 'mfa'
                      and record.get('type') == 'webauthn'
                      and record.get('passwordless') is True
                      and isinstance(record.get('at'), (int, float))
                      and used_at < record['at'] <= now
                      and now - record['at'] <= 120), None)
        if fresh is not None:
            request.session['handoff_used_passkey_at'] = fresh['at']
            return _issue_verified_handoff(request, target_path, target_site)

    has_passkey = bool(webauthn_auth.get_credentials(request.user))
    form = ReauthenticateWebAuthnForm(request.POST or None, user=request.user)
    if request.method == 'POST' and has_passkey and form.is_valid():
        form.save()
        return _issue_verified_handoff(request, target_path, target_site)
    js_data = {'request_options': webauthn_auth.begin_authentication(request.user)} if has_passkey else None
    action = ('/ip-auth/start?' + urlencode({'next': target_path}) if target_site == 'ip'
              else '/drill-auth/start?' + urlencode({'site': target_site, 'next': target_path, 'verify': '1'}))
    response = render(request, 'account/ip_passkey_verify.html', {
        'form': form, 'js_data': js_data, 'has_passkey': has_passkey,
        'target_path': target_path, 'target_site': target_site, 'action': action,
    })
    response['Cache-Control'] = 'private, no-store'
    return response


def _issue_ip_login_handoff(request, target_path):
    _, raw_token = DrillLoginHandoff.issue(
        user=request.user,
        target_path=target_path,
        target_site='ip',
        lifetime_seconds=90,
    )
    response = redirect(f'{settings.IP_AUTH_CALLBACK_ORIGIN}/ip-auth/complete#{raw_token}')
    response['Cache-Control'] = 'no-store, max-age=0'
    response['Referrer-Policy'] = 'no-referrer'
    return response


def _issue_verified_handoff(request, target_path, target_site):
    if target_site == 'ip':
        return _issue_ip_login_handoff(request, target_path)
    _, raw_token = DrillLoginHandoff.issue(
        user=request.user, target_path=target_path, target_site=target_site,
    )
    response = redirect(f'{_target_origin(target_site)}/drill-auth/complete/{raw_token}')
    response['Cache-Control'] = 'no-store, max-age=0'
    response['Referrer-Policy'] = 'no-referrer'
    return response


@never_cache
@ensure_csrf_cookie
@require_http_methods(['GET', 'POST'])
def ip_login_complete(request):
    """Consume the fragment-delivered token with a same-origin CSRF POST."""
    if not _is_ip_entry_request(request):
        raise Http404
    if request.method == 'GET':
        response = render(request, 'account/ip_handoff_complete.html')
        response['Cache-Control'] = 'no-store, max-age=0'
        response['Referrer-Policy'] = 'no-referrer'
        response['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'none'"
        )
        return response

    origin = request.META.get('HTTP_ORIGIN', '').rstrip('/')
    if origin != settings.IP_AUTH_CALLBACK_ORIGIN:
        return JsonResponse({'detail': '非法登录来源。'}, status=403)
    try:
        payload = json.loads(request.body or b'{}')
    except (TypeError, ValueError):
        return JsonResponse({'detail': '登录请求格式无效。'}, status=400)
    raw_token = str(payload.get('token', ''))
    if len(raw_token) > 128 or not re.fullmatch(r'drill_[A-Za-z0-9_-]{32,128}', raw_token):
        return JsonResponse({'detail': '登录凭证无效或已过期。'}, status=400)
    with transaction.atomic():
        handoff = DrillLoginHandoff.objects.select_for_update().select_related('user').filter(
            token_digest=DrillLoginHandoff.digest(raw_token),
            target_site='ip',
            expires_at__gt=timezone.now(),
            user__is_active=True,
        ).first()
        if handoff is None:
            return JsonResponse({'detail': '登录凭证无效、已使用或已过期。'}, status=400)
        user = handoff.user
        target_path = _safe_ip_target(handoff.target_path)
        handoff.delete()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return JsonResponse({'redirect': target_path})


@never_cache
def drill_spa_view(request, **_route):
    site = practice_site(request)
    if site is None and not settings.DEBUG:
        raise Http404
    site = site or 'drill'
    if not request.user.is_authenticated:
        target_path = _safe_drill_target(request.get_full_path())
        if settings.DEBUG or dedicated_private_workspace(request):
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
@require_http_methods(['GET', 'POST'])
def drill_login_start(request):
    hostname = request.get_host().partition(':')[0].lower()
    if hostname != settings.DRILL_AUTH_HOST and not settings.DEBUG:
        raise Http404
    target_site = request.GET.get('site', 'drill')
    if target_site not in {'drill', 'ei', 'dash'}:
        raise Http404
    target_path = _safe_drill_target(request.GET.get('next', '/practice'), target_site)
    if request.GET.get('verify') == '1':
        return _verify_passkey_handoff(request, target_path, target_site)
    _, raw_token = DrillLoginHandoff.issue(
        user=request.user,
        target_path=target_path,
        target_site=target_site,
    )
    return redirect(f'{_target_origin(target_site)}/drill-auth/complete/{raw_token}')


@never_cache
def drill_login_complete(request, raw_token):
    site = handoff_site(request)
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
        target_path = _safe_drill_target(handoff.target_path, site)
        handoff.delete()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    response = redirect(target_path)
    response['Cache-Control'] = 'no-store, max-age=0'
    response['Referrer-Policy'] = 'no-referrer'
    return response
