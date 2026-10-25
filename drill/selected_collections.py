"""Navigation dispatch only; normal question-bank paths remain unchanged."""
from . import circuit_selected, signal_selected, analog_selected

CODES = {circuit_selected.CODE, signal_selected.CODE, analog_selected.CODE}


def filter_collection(queryset, request):
    code = request.query_params.get('collection')
    module = {signal_selected.CODE: signal_selected, analog_selected.CODE: analog_selected}.get(code, circuit_selected)
    return module.filter_collection(queryset, request)
