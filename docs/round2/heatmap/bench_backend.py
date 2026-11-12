import os,sys,time,json,statistics,hashlib
sys.path.insert(0,os.getcwd());os.environ.setdefault('DJANGO_SETTINGS_MODULE','time_server.settings')
import django;django.setup()
from django.db import connection
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory,force_authenticate
from drill.views import DrillHeatmapView
from drill.models import Question,QuestionAttempt

assert connection.settings_dict['NAME'] == 'precision_search_real', 'Run only against the isolated public-metadata fixture'
label=sys.argv[1];output=sys.argv[2]
user=get_user_model().objects.order_by('pk').first()
assert user is not None,'Fixture synthetic account required'
factory=APIRequestFactory();results=[]
# A read-only session forbids accidental model writes in a benchmark.
with connection.cursor() as c:c.execute('SET default_transaction_read_only=on')
for host,params in [('drill.test','scope=all&mode=questions'),('drill.test','scope=all&mode=questions&collection=selected'),('ei.test','scope=all&mode=questions'),('ei.test','scope=all&mode=questions&collection=core_selected&material=all'),('drill.test','scope=all&mode=topics')]:
 def run(capture=False):
  queries=[]
  def wrapper(execute,sql,params,many,context):
   start=time.perf_counter()
   try:return execute(sql,params,many,context)
   finally:
    queries.append({'ms':round((time.perf_counter()-start)*1000,4),'sql':sql,'params':params})
  req=factory.get('/api/drill/heatmap/?'+params,HTTP_HOST=host);force_authenticate(req,user=user)
  start=time.perf_counter()
  with connection.execute_wrapper(wrapper):
   response=DrillHeatmapView.as_view()(req);view_ms=(time.perf_counter()-start)*1000
   response.render();total_ms=(time.perf_counter()-start)*1000
  assert response.status_code==200,(response.status_code,str(response.data)[:100])
  payload=response.data
  return dict(view_ms=round(view_ms,3),rendered_ms=round(total_ms,3),sql_ms=round(sum(q['ms'] for q in queries),3),query_count=len(queries),payload_bytes=len(response.content),question_count=payload['question_count'],topic_count=payload['topic_count'],groups=len(payload['groups']),sha256=hashlib.sha256(response.content).hexdigest(),queries=queries if capture else None)
 run();run();samples=[run(capture=i==0) for i in range(10)]
 counts={x['query_count'] for x in samples};questions={x['question_count'] for x in samples}
 row=dict(label=label,host=host,params=params,samples=samples,medians={key:statistics.median(x[key] for x in samples) for key in ['view_ms','rendered_ms','sql_ms','query_count','payload_bytes','question_count','topic_count','groups']},p95_rendered_ms=sorted(x['rendered_ms'] for x in samples)[-1])
 results.append(row);print(json.dumps({key:value for key,value in row.items() if key!='samples'}),flush=True)
 # Actual prepared parameterized SELECT plans, not reconstructed SQL.
 plans=[]
 for query in sorted(samples[0]['queries'],key=lambda q:q['ms'],reverse=True)[:3]:
  if not query['sql'].lstrip().upper().startswith('SELECT'):continue
  with connection.cursor() as cursor:
   cursor.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+query['sql'],query['params']);plan=cursor.fetchone()[0]
  plans.append({'original_ms':query['ms'],'sql':query['sql'],'params':query['params'],'plan':plan})
 row['slow_query_plans']=plans
open(output,'w').write(json.dumps(results,ensure_ascii=False,indent=2,default=str)+'\n')
