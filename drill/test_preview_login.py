from urllib.parse import urlencode
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from .models import DrillLoginHandoff
from .web_views import _safe_drill_target


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'])
class PreviewLoginCompatibilityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='preview-login-fixture')
        self.client.force_login(self.user)

    def test_long_preview_context_survives_postgresql_handoff_storage(self):
        path = '/preview?' + urlencode({'list': '{"q":"' + '极限' * 80 + '","returnTo":"/practice"}'})
        self.assertGreater(len(path), 500)
        self.assertEqual(_safe_drill_target(path), path)
        handoff, _token = DrillLoginHandoff.issue(user=self.user, target_path=path)
        handoff.refresh_from_db()
        self.assertEqual(handoff.target_path, path)

    def test_preview_allows_image_blobs_without_relaxing_script_policy(self):
        response = self.client.get('/preview')
        self.assertEqual(response.status_code, 200)
        policy = response['Content-Security-Policy']
        self.assertIn("img-src 'self' data: blob:", policy)
        self.assertIn("script-src 'self';", policy)
        self.assertNotIn("script-src 'self' blob:", policy)

    def test_oversized_and_control_character_targets_are_rejected(self):
        for value in ('/preview?list=' + 'x' * 16384, '/preview?x=\nsecret', '/practice\\admin'):
            self.assertEqual(_safe_drill_target(value), '/practice')
