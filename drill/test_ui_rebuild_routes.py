"""Refresh and authenticated recovery regression for the shared UI rebuild."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from .models import ExamBlueprint, ExamPaper
from .recovery import valid_location


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver', 'drill.ehzsy.site', 'ei.ehzsy.site', 'timer.ehzsy.site'])
class RebuildRouteTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('route-owner')
        self.other = get_user_model().objects.create_user('route-other')
        self.client.force_login(self.user)

    def test_progress_and_settings_refresh_on_prefix_and_workspace_host(self):
        for workspace in ('drill', 'ei'):
            for route in ('progress', 'settings'):
                # Nginx strips /drill or /ei and forwards the workspace host.
                for path, host in ((f'/{route}', f'{workspace}.ehzsy.site'),):
                    with self.subTest(path=path, host=host):
                        response = self.client.get(path, HTTP_HOST=host)
                        self.assertEqual(response.status_code, 200)
                        self.assertIn(b'/static/drill/', response.content)
                        self.assertIn('no-store', response['Cache-Control'])
        response = self.client.get('/settings', HTTP_HOST='timer.ehzsy.site')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'/static/app/', response.content)

    def test_refresh_keeps_authentication_required(self):
        self.client.logout()
        for path in ('/settings', '/progress'):
            self.assertEqual(self.client.get(path, HTTP_HOST='drill.ehzsy.site').status_code, 302)

    def test_recovery_new_pages_and_papers_are_workspace_and_owner_scoped(self):
        blueprint = ExamBlueprint.objects.create(code='route-test', title='Route', subject='math2', mode='standard', version=999, duration_minutes=120, total_score=100)
        paper = ExamPaper.objects.create(user=self.user, blueprint=blueprint, seed=1, mode='standard')
        for route in ('settings', 'progress', 'selected-pdf-pages'):
            self.assertTrue(valid_location('drill', f'/drill/{route}', self.user))
            self.assertTrue(valid_location('ei', f'/ei/{route}', self.user))
        self.assertTrue(valid_location('drill', f'/drill/papers/{paper.uuid}/review', self.user))
        self.assertFalse(valid_location('drill', f'/drill/papers/{paper.uuid}', self.other))
        self.assertFalse(valid_location('ei', f'/ei/papers/{paper.uuid}', self.user))
        self.assertFalse(valid_location('drill', '/ei/settings', self.user))
        self.assertFalse(valid_location('drill', 'https://example.com/drill/settings', self.user))
