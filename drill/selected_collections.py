"""Navigation dispatch only; normal question-bank paths remain unchanged."""
from . import circuit_selected, signal_selected

CODES = {circuit_selected.CODE, signal_selected.CODE}


def filter_collection(queryset, request):
    module = signal_selected if request.query_params.get('collection') == signal_selected.CODE else circuit_selected
    return module.filter_collection(queryset, request)
