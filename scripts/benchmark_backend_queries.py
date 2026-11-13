"""Read-only admin benchmark: python manage.py shell < scripts/benchmark_backend_queries.py.

Reports view/render timings (not network latency), five warm samples and two
EXPLAIN ANALYZE plans per endpoint. Never prints user identity or response text.
This is an offline admin diagnostic, not a public route or auth bypass.
"""
import json,time,statistics,hashlib
from django.db import connection,transaction
from django.db.models import Count,Q,OuterRef,Subquery
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIRequestFactory,force_authenticate
from drill.models import Question,QuestionAttempt
from drill.views import DrillQuestionDetailView,DrillQuestionListView,DrillHeatmapView

counts=QuestionAttempt.objects.values('user_id').annotate(n=Count('id')).order_by('-n').first()
user=get_user_model().objects.get(pk=counts['user_id'])
latest=QuestionAttempt.objects.filter(user=user,question_id=OuterRef('pk')).order_by('-created_at','-pk')
queries={}
for workspace in ['drill','ei']:
 q=Question.objects.filter(document__workspace=workspace,is_practiceable=True).annotate(n=Count('attempts')).order_by('-n','pk').first()
 if q:
  queries[workspace+'-detail']=(DrillQuestionDetailView,workspace,{}, {'question_uuid':q.uuid})
queries['drill-selected-detail']=(DrillQuestionDetailView,'drill',{'collection':'selected'},{'question_uuid':Question.objects.filter(document__workspace='drill',is_practiceable=True).filter(Q(answer_source='daguan_answer_guide_pdf')|Q(document__relation_type='selected_question_book')).order_by('pk').first().uuid})
queries['drill-list']=(DrillQuestionListView,'drill',{}, {})
queries['drill-search']=(DrillQuestionListView,'drill',{'q':'导数','search_version':'2'}, {})
queries['drill-selected-heatmap']=(DrillHeatmapView,'drill',{'scope':'all','mode':'questions','collection':'selected'}, {})
queries['ei-heatmap']=(DrillHeatmapView,'ei',{'scope':'all','mode':'questions'}, {})
result={}
with override_settings(ALLOWED_HOSTS=['drill.test','ei.test'],DRILL_HOSTS={'drill.test'},EI_HOSTS={'ei.test'}):
 with connection.cursor() as cursor:
  cursor.execute('SET default_transaction_read_only=on');cursor.execute("SET statement_timeout='6s'")
 for label,(View,workspace,params,kwargs) in queries.items():
  samples=[];sqlcounts=[];sqltimes=[];payloads=[];slow=[]
  for n in range(6):
   request=APIRequestFactory().get('/api/drill/',params,HTTP_HOST=workspace+'.test');force_authenticate(request,user)
   executed=[]
   def measure(execute,sql,params,many,context):
    start=time.perf_counter()
    try:return execute(sql,params,many,context)
    finally:executed.append(((time.perf_counter()-start)*1000,sql,params))
   start=time.perf_counter()
   with connection.execute_wrapper(measure):
    response=View.as_view()(request,**kwargs)
    if hasattr(response,'render'):response.render()
   elapsed=(time.perf_counter()-start)*1000
   assert response.status_code==200,(label,response.status_code)
   if n:
    samples.append(round(elapsed,3));sqlcounts.append(len(executed));sqltimes.append(round(sum(x[0] for x in executed),3));payloads.append(hashlib.sha256(response.content).hexdigest())
   if n==5:
    for ms,sql,params in sorted(executed,reverse=True,key=lambda x:x[0])[:2]:
     with connection.cursor() as cursor:
      cursor.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+sql,params);plan=cursor.fetchone()[0][0]
     nodes=[]
     def walk(node):
      nodes.append({k:node[k] for k in ['Node Type','Relation Name','Index Name','Actual Rows','Actual Loops','Rows Removed by Filter'] if k in node})
      for child in node.get('Plans',[]):walk(child)
     walk(plan['Plan']);slow.append({'sql_ms':round(ms,3),'plan_execution_ms':plan.get('Execution Time'),'planning_ms':plan.get('Planning Time'),'nodes':nodes})
  result[label]={'samples':len(samples),'p50_ms':round(statistics.median(samples),3),'p95_ms':sorted(samples)[-1],'sql_count':sqlcounts,'sql_total_ms':sqltimes,'payload_hashes':payloads,'slow_query_plans':slow,'response_bytes':len(response.content)}
 print(json.dumps(result))
