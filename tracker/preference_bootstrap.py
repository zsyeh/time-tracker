"""Per-request, non-secret account preferences; never cache this personalized HTML."""
from django.utils.html import json_script
from .user_preferences import preferences_snapshot


def preferences_bootstrap_script(user):
    authenticated = bool(user and user.is_authenticated)
    payload = {'user_id': str(user.pk) if authenticated else None,
               'snapshot': preferences_snapshot(user) if authenticated else None}
    return json_script(payload, 'learning-user-preferences')


def inject_preferences_bootstrap(html, user):
    script = str(preferences_bootstrap_script(user))
    # Before the external synchronous appearance bootstrap and application CSS.
    return html.replace('<head>', '<head>\n' + script, 1)
