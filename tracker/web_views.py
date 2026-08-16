from functools import lru_cache

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import LaunchToken, TimeLog
from .services import ActiveSessionConflict, is_long_session, normalize_subject, start_session


@lru_cache(maxsize=4)
def _read_frontend_html(index_path, mtime_ns, size):
    """Cache a deployed SPA index while still noticing atomic rebuilds."""

    return index_path.read_text(encoding='utf-8')


def _frontend_html():
    index_path = settings.FRONTEND_DIST / 'index.html'
    try:
        metadata = index_path.stat()
    except OSError:
        return ''
    return _read_frontend_html(index_path, metadata.st_mtime_ns, metadata.st_size)


# Existing tests and operational checks use this public cache reset hook.
_frontend_html.cache_clear = _read_frontend_html.cache_clear


@login_required
@never_cache
def spa_view(request, **_route):
    html = _frontend_html()
    if not html:
        return render(request, 'frontend_missing.html', status=503)
    response = HttpResponse(html)
    response['Cache-Control'] = 'private, no-store'
    return response


@never_cache
def public_spa_view(request, **_route):
    """Serve only the anonymous Vue share shell; data still comes from its capability API."""

    html = _frontend_html()
    if not html:
        return render(request, 'frontend_missing.html', status=503)
    response = HttpResponse(html)
    response['Cache-Control'] = 'no-store, max-age=0'
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    response['Referrer-Policy'] = 'no-referrer'
    response['Content-Security-Policy'] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; font-src 'self' data:; connect-src 'self'; "
        "object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    )
    return response


def root_spa_view(request):
    """Select the independently built SPA by hostname at the shared root URI."""

    from drill.web_views import drill_spa_view, is_drill_host

    if is_drill_host(request):
        return drill_spa_view(request)
    return spa_view(request)


@login_required
@never_cache
def direct_start_view(request, subject):
    try:
        session, _ = start_session(request.user, subject)
    except ValueError as exc:
        raise Http404 from exc
    except ActiveSessionConflict as exc:
        return redirect(f'/today?conflict={exc.session.pk}')
    return redirect(f'/today?active={session.pk}')


def _token_block_reason(token, *, check_launch_limit=False):
    if not token.credential_valid:
        raise Http404
    if check_launch_limit and token.max_uses is not None and token.usage_count >= token.max_uses:
        raise Http404
    if token.is_paused:
        return 'paused'
    if not token.within_schedule:
        return 'outside_schedule'
    return None


def _consume_launch_token(raw_token):
    digest = LaunchToken.digest(raw_token)
    with transaction.atomic():
        token = LaunchToken.objects.select_for_update().filter(token_digest=digest).first()
        if token is None:
            raise Http404
        blocked = _token_block_reason(token, check_launch_limit=True)
        if blocked:
            return token, None, False, False, blocked
        try:
            session, reused = start_session(token.user, token.category)
        except ActiveSessionConflict as exc:
            return token, exc.session, False, True, None
        token.last_used_at = timezone.now()
        token.usage_count += 1
        token.save(update_fields=('last_used_at', 'usage_count'))
    return token, session, reused, False, None


def _record_disturbance(raw_token):
    digest = LaunchToken.digest(raw_token)
    with transaction.atomic():
        token = LaunchToken.objects.select_for_update().filter(
            disturbance_token_digest=digest,
        ).first()
        if token is None:
            raise Http404
        blocked = _token_block_reason(token)
        if blocked:
            return token, None, blocked, False

        session = TimeLog.objects.select_for_update().filter(
            user=token.user,
            status='running',
        ).first()
        if session is None:
            return token, None, 'no_active_session', False

        now = timezone.now()
        if is_long_session(session.start_time, now):
            session.delete()
            return token, None, 'stale_session_discarded', False

        disturbance_count = session.disturbance_count + 1
        # This operational counter does not affect duration aggregates. Bypass the
        # TimeLog save signals so a Shortcut ping stays one small indexed update.
        TimeLog.objects.filter(pk=session.pk).update(
            disturbance_count=disturbance_count,
            last_disturbance_at=now,
            updated_at=now,
        )
        session.disturbance_count = disturbance_count
        session.last_disturbance_at = now
        session.updated_at = now
        return token, session, 'recorded', True


def _protect_launch_response(response):
    response['Cache-Control'] = 'private, no-store, max-age=0'
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    response['Referrer-Policy'] = 'no-referrer'
    return response


@never_cache
def launch_browser_view(request, raw_token):
    token, session, reused, conflict, blocked = _consume_launch_token(raw_token)
    response = render(
        request,
        'launch_result.html',
        {
            'subject': token.get_category_display(),
            'started_at': timezone.localtime(session.start_time) if session else None,
            'reused': reused,
            'conflict': conflict,
            'blocked': blocked,
            'available_from': token.available_from,
            'available_until': token.available_until,
        },
        status=409 if conflict else 200,
    )
    return _protect_launch_response(response)


class LaunchCapabilityView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        return _protect_launch_response(response)


class LaunchDeviceView(LaunchCapabilityView):

    def post(self, request, raw_token):
        token, session, reused, conflict, blocked = _consume_launch_token(raw_token)
        if blocked:
            return Response({
                'status': blocked,
                'started': False,
                'available_from': token.available_from.strftime('%H:%M'),
                'available_until': token.available_until.strftime('%H:%M'),
                'timezone': settings.TIME_ZONE,
            })
        response = Response(
            {
                'status': 'conflict' if conflict else ('existing' if reused else 'started'),
                'subject': token.category,
                'session_id': session.pk,
                'started_at': session.start_time.isoformat(),
            },
            status=status.HTTP_409_CONFLICT if conflict else status.HTTP_200_OK,
        )
        return response


class LaunchDisturbanceView(LaunchCapabilityView):

    def post(self, request, raw_token):
        token, session, event_status, recorded = _record_disturbance(raw_token)
        payload = {
            'status': event_status,
            'recorded': recorded,
            'subject': token.category,
        }
        if event_status == 'outside_schedule':
            payload.update({
                'available_from': token.available_from.strftime('%H:%M'),
                'available_until': token.available_until.strftime('%H:%M'),
                'timezone': settings.TIME_ZONE,
            })
        if session is not None:
            payload.update({
                'disturbance_count': session.disturbance_count,
                'recorded_at': session.last_disturbance_at.isoformat(),
            })
        return Response(payload)
