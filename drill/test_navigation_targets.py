from django.test import SimpleTestCase
from django.urls import resolve

from .web_views import _safe_drill_target


class PracticeNavigationTargetTests(SimpleTestCase):
    def test_practice_deep_links_survive_authentication(self):
        for path in ('/preview', '/preview?list=%7B%7D', '/progress', '/progress?days=30', '/diagnostics?days=30', '/diagnostic-queue', '/selected-pdf-pages'):
            with self.subTest(path=path):
                self.assertEqual(_safe_drill_target(path, site='drill'), path)

    def test_external_target_is_still_rejected(self):
        self.assertEqual(_safe_drill_target('https://example.com/diagnostics'), '/practice')

    def test_progress_is_a_valid_recovery_location_for_both_workspaces(self):
        from .recovery import valid_location
        for workspace in ('drill', 'ei'):
            with self.subTest(workspace=workspace):
                self.assertTrue(valid_location(workspace, f'/{workspace}/progress?days=30'))

    def test_progress_refresh_resolves_to_explicit_spa_route(self):
        self.assertEqual(resolve('/progress').url_name, 'drill_progress_page')

    def test_preview_is_a_valid_recovery_and_refresh_route(self):
        from .recovery import valid_location
        for workspace in ('drill', 'ei'):
            self.assertTrue(valid_location(workspace, f'/{workspace}/preview?list=%7B%7D'))
        self.assertEqual(resolve('/preview').url_name, 'drill_collection_preview_page')
