from .circuit_selected_views import CircuitSelectedView
from .communication_selected import filter_collection, manifest, review_manifest


class CommunicationSelectedView(CircuitSelectedView):
    def get(self, request):
        response = super().get(request)
        response.data['coverage_notes'] = self.selection_manifest().get('coverage_notes', [])
        return response

    def selection_manifest(self):
        return manifest()

    def selection_review(self):
        return review_manifest()

    def selection_queryset(self, queryset, request):
        return filter_collection(queryset, request, force=True)
