from .circuit_selected_views import CircuitSelectedView
from .digital_selected import filter_collection, manifest, review_manifest


class DigitalSelectedView(CircuitSelectedView):
    def selection_manifest(self):
        return manifest()

    def selection_review(self):
        return review_manifest()

    def selection_queryset(self, queryset, request):
        return filter_collection(queryset, request, force=True)
