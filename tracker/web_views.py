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

from .models import LaunchToken
from .services import ActiveSessionConflict, normalize_subject, start_session


@lru_cache(maxsize=1)
def _frontend_html():
    index_path = settings.FRONTEND_DIST / 'index.html'
    if not index_path.exists():
        return ''
    return index_path.read_text(encoding='utf-8')


@login_required
@never_cache
def spa_view(request):
    html = _frontend_html()
    if not html:
        return render(request, 'frontend_missing.html', status=503)
    response = HttpResponse(html)
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
@never_cache
def direct_start_view(request, subject):
    try:
        session, _ = start_session(request.user, subject)
    except ValueError as exc:
        raise Http404 from exc
    except ActiveSessionConflict as exc:
        return redirect(f'/?conflict={exc.session.pk}')
    return redirect(f'/?active={session.pk}')


def _consume_launch_token(raw_token):
    digest = LaunchToken.digest(raw_token)
    with transaction.atomic():
        token = LaunchToken.objects.select_for_update().filter(token_digest=digest).first()
        if token is None or not token.usable:
            raise Http404
        try:
            session, reused = start_session(token.user, token.category)
        except ActiveSessionConflict as exc:
            return token, exc.session, False, True
        token.last_used_at = timezone.now()
        token.usage_count += 1
        token.save(update_fields=('last_used_at', 'usage_count'))
    return token, session, reused, False


def _protect_launch_response(response):
    response['Cache-Control'] = 'private, no-store, max-age=0'
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    response['Referrer-Policy'] = 'no-referrer'
    return response


@never_cache
def launch_browser_view(request, raw_token):
    token, session, reused, conflict = _consume_launch_token(raw_token)
    response = render(
        request,
        'launch_result.html',
        {
            'subject': token.get_category_display(),
            'started_at': timezone.localtime(session.start_time),
            'reused': reused,
            'conflict': conflict,
        },
        status=409 if conflict else 200,
    )
    return _protect_launch_response(response)


class LaunchDeviceView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request, raw_token):
        token, session, reused, conflict = _consume_launch_token(raw_token)
        response = Response(
            {
                'status': 'conflict' if conflict else ('existing' if reused else 'started'),
                'subject': token.category,
                'session_id': session.pk,
                'started_at': session.start_time.isoformat(),
            },
            status=status.HTTP_409_CONFLICT if conflict else status.HTTP_200_OK,
        )
        return _protect_launch_response(response)
