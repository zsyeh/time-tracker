from django.test import SimpleTestCase

from .web_views import _safe_drill_target


class PracticeNavigationTargetTests(SimpleTestCase):
    def test_practice_deep_links_survive_authentication(self):
        for path in ('/diagnostics?days=30', '/diagnostic-queue', '/selected-pdf-pages'):
            with self.subTest(path=path):
                self.assertEqual(_safe_drill_target(path, site='drill'), path)

    def test_external_target_is_still_rejected(self):
        self.assertEqual(_safe_drill_target('https://example.com/diagnostics'), '/practice')
