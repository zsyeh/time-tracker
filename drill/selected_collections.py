"""Navigation dispatch only; normal question-bank paths remain unchanged."""
from . import circuit_selected, signal_selected, analog_selected, digital_selected, communication_selected, core_selected
from django.db.models import Q

CODES = {'selected', circuit_selected.CODE, signal_selected.CODE, analog_selected.CODE, digital_selected.CODE, communication_selected.CODE, core_selected.CODE}


def filter_collection(queryset, request):
    code = request.query_params.get('collection')
    if code == 'selected':
        return queryset.filter(document__workspace='drill', is_practiceable=True).filter(
            Q(answer_source='daguan_answer_guide_pdf') | Q(document__relation_type='selected_question_book'))
    module = {signal_selected.CODE: signal_selected, analog_selected.CODE: analog_selected,
              digital_selected.CODE: digital_selected, communication_selected.CODE: communication_selected,
              core_selected.CODE: core_selected}.get(code, circuit_selected)
    return module.filter_collection(queryset, request)
