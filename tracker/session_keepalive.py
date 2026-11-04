"""Keep active remembered sessions valid without a database write per page view."""

from django.conf import settings
from django.utils import timezone


class SessionKeepaliveMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = int(timezone.now().timestamp())
            last_refresh = request.session.get('_keepalive_at', 0)
            if not isinstance(last_refresh, int) or now - last_refresh >= 24 * 60 * 60:
                request.session['_keepalive_at'] = now
                request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        return self.get_response(request)
