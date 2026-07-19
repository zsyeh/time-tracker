from functools import wraps
from hmac import compare_digest

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.cache import patch_vary_headers


AUTHORIZATION_HEADER = 'Authorization'
AUTH_GATE_PATHS = {'/', '/daily-stats/'}


def request_has_valid_token(request):
    supplied_token = request.headers.get(AUTHORIZATION_HEADER, '')
    expected_token = str(settings.TRACKER_API_TOKEN or '')
    if not supplied_token or not expected_token:
        return False
    try:
        supplied_bytes = str(supplied_token).encode('utf-8')
        expected_bytes = expected_token.encode('utf-8')
    except UnicodeEncodeError:
        return False
    return compare_digest(supplied_bytes, expected_bytes)


def prevent_auth_response_caching(response):
    response['Cache-Control'] = 'private, no-store'
    response['X-Frame-Options'] = getattr(settings, 'X_FRAME_OPTIONS', 'DENY') or 'DENY'
    patch_vary_headers(response, (AUTHORIZATION_HEADER,))
    return response


def empty_forbidden_response():
    return prevent_auth_response_caching(HttpResponse(status=403))


def token_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request_has_valid_token(request):
            return empty_forbidden_response()
        return view_func(request, *args, **kwargs)

    return _wrapped_view


class TrackerAuthorizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request_has_valid_token(request):
            if request.method == 'GET' and request.path in AUTH_GATE_PATHS:
                response = HttpResponse(
                    render_to_string('auth_gate.html'),
                    status=403,
                )
            else:
                response = HttpResponse(status=403)
            return prevent_auth_response_caching(response)

        response = self.get_response(request)
        return prevent_auth_response_caching(response)
