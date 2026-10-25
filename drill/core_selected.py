"""Union of the five reviewed-priority manifests, never a second question bank."""
from functools import lru_cache
from django.http import Http404
from . import circuit_selected,signal_selected,analog_selected,digital_selected,communication_selected
from .circuit_selected import filter_collection as filter_reviewed_collection

CODE='core_selected'
COURSES=[('circuit','电路',circuit_selected),('signal','信号',signal_selected),
         ('analog','模电',analog_selected),('digital','数电',digital_selected),
         ('communication','通信',communication_selected)]


@lru_cache(maxsize=1)
def manifest():
    questions=[];buckets=[];seen=set()
    for course,title,module in COURSES:
        data=module.manifest()
        for bucket in data['buckets']:
            buckets.append({**bucket,'key':course+':'+bucket['key']})
        for row in data['questions']:
            if row['tier']!='core' or row['uuid'] in seen:continue
            seen.add(row['uuid'])
            questions.append({**row,'bucket':course+':'+row['bucket'],'course':course,'course_title':title})
    return dict(schema_version=1,questions=questions,buckets=buckets,kinds=['analysis','design','calculation','concept'])


def filter_collection(queryset,request,*,force=False):
    if not force and request.query_params.get('collection')!=CODE:return queryset
    data=manifest();course=request.query_params.get('course','')
    if course and course not in {c[0] for c in COURSES}:raise Http404('Unknown course')
    if course:data={**data,'questions':[q for q in data['questions'] if q['course']==course]}
    queryset=filter_reviewed_collection(queryset,request,force=True,data=data,code=CODE)
    scope=request.query_params.get('scope','all')
    if scope not in {'all','past_exam','mock_exam'}:raise Http404('Unknown scope')
    if scope!='all':queryset=queryset.filter(source_category=scope)
    return queryset
