"""DRF render timing that is active only for signed capacity-test requests."""

from __future__ import annotations

import time

from rest_framework.renderers import JSONRenderer


class LoadTestJSONRenderer(JSONRenderer):
    """Measure JSON encoding, without changing the rendered representation."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        context = renderer_context or {}
        request = context.get('request')
        if not getattr(request, 'loadtest_capability', None):
            return super().render(data, accepted_media_type, renderer_context)
        started = time.perf_counter()
        rendered = super().render(data, accepted_media_type, renderer_context)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response = context.get('response')
        if response is not None:
            response['X-Load-Test-JSON-Render-Ms'] = f'{elapsed_ms:.3f}'
        return rendered
