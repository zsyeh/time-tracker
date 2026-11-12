"""Read-only service benchmark, deliberately separate from HTTP timing."""
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand,CommandError
from django.db import close_old_connections, connection
from django.test import override_settings
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory
from drill.models import QuestionSearchDocument
from drill.search.service import question_list_response


def percentile(values,p):
    ordered=sorted(values)
    return ordered[max(0,math.ceil(p*len(ordered))-1)] if ordered else None


def relevance(rows,qrels):
    """Only explicitly judged queries contribute; unjudged is not invented ground truth."""
    output=[]
    for row in rows:
        judgments=qrels.get(row['id'])
        if not judgments:
            continue
        ranking=row['top20'];gains=[judgments.get(uuid,0) for uuid in ranking]
        ideal=sorted(judgments.values(),reverse=True)
        dcg=lambda scores:sum((2**score-1)/math.log2(i+2) for i,score in enumerate(scores[:10]))
        positives={uuid for uuid,score in judgments.items() if score>=2}
        output.append({'id':row['id'],'ndcg_at_10':dcg(gains)/dcg(ideal) if dcg(ideal) else 0,
            'pooled_recall_at_20':len(set(ranking[:20])&positives)/len(positives) if positives else None,
            'precision_at_10':sum(score>=2 for score in gains[:10])/min(10,len(gains)) if gains else 0,
            'mrr_at_10':next((1/(i+1) for i,score in enumerate(gains[:10]) if score>=2),0)})
    return output


class Command(BaseCommand):
    help='Measure scoped search service only. Use tests/search/benchmark_http.py for complete HTTP latency.'
    def add_arguments(self,parser):
        parser.add_argument('--backend',choices=('legacy','hybrid_v1'),required=True)
        parser.add_argument('--user-id',type=int,required=True)
        parser.add_argument('--queries',required=True)
        parser.add_argument('--qrels')
        parser.add_argument('--repeats',type=int,default=30)
        parser.add_argument('--concurrency',type=int,default=1)
        parser.add_argument('--output',required=True)
    def handle(self,*args,**opts):
        if not 1<=opts['repeats']<=1000 or not 1<=opts['concurrency']<=16:
            raise CommandError('Invalid benchmark budget')
        queries=[json.loads(line) for line in Path(opts['queries']).read_text().splitlines() if line.strip()]
        qrels={}
        if opts['qrels']:
            for line in Path(opts['qrels']).read_text().splitlines():
                row=json.loads(line);qrels[row['id']]=row['judgments']
        user=get_user_model().objects.get(pk=opts['user_id'])
        rows=[]
        def sample(query):
            close_old_connections()
            host='ei.search.test' if query.get('workspace')=='ei' else 'drill.search.test'
            request=Request(APIRequestFactory().get('/api/drill/questions/',{'q':query['q'],'search_version':'2',**query.get('params',{})},HTTP_HOST=host))
            request._user=user
            timings=[]
            def wrapper(execute,sql,params,many,context):
                started=time.perf_counter()
                try:return execute(sql,params,many,context)
                finally:timings.append((time.perf_counter()-started)*1000)
            started=time.perf_counter()
            try:
                with connection.execute_wrapper(wrapper):
                    response=question_list_response(request)
                return {'ms':(time.perf_counter()-started)*1000,'db_ms':sum(timings),'queries':len(timings),
                    'count':response.data['count'],'top20':[r['uuid'] for r in response.data['results'][:20]],'error':None}
            except Exception as exc:
                return {'ms':(time.perf_counter()-started)*1000,'db_ms':sum(timings),'queries':len(timings),
                    'count':None,'top20':[],'error':type(exc).__name__}
            finally:
                close_old_connections()
        with override_settings(DRILL_SEARCH_BACKEND=opts['backend'],DRILL_HOSTS={'drill.search.test'},EI_HOSTS={'ei.search.test'},ALLOWED_HOSTS=['drill.search.test','ei.search.test']):
            for query in queries:
                for _ in range(5):sample(query)
                with ThreadPoolExecutor(max_workers=opts['concurrency']) as pool:
                    samples=list(pool.map(lambda _:sample(query),range(opts['repeats'])))
                times=[s['ms'] for s in samples]
                rows.append({'id':query['id'],'count':samples[-1]['count'],'top20':samples[-1]['top20'],
                    'median_ms':statistics.median(times),'p95_ms':percentile(times,.95),'p99_ms':percentile(times,.99),
                    'db_median_ms':statistics.median(s['db_ms'] for s in samples),
                    'query_count':samples[-1]['queries'],'errors':[s['error'] for s in samples if s['error']]})
        try:sha=os.environ.get('SEARCH_BENCHMARK_GIT_SHA') or subprocess.check_output(['git','rev-parse','HEAD'],text=True,stderr=subprocess.DEVNULL).strip()
        except (OSError,subprocess.SubprocessError):sha='unavailable'
        digest=hashlib.sha256()
        for pk,source_hash in QuestionSearchDocument.objects.order_by('pk').values_list('pk','source_hash').iterator():
            digest.update(f'{pk}:{source_hash}\n'.encode())
        payload={'kind':'service-not-http','git_sha':sha,'backend':opts['backend'],'db_vendor':connection.vendor,
            'db_version':getattr(connection,'pg_version',None) if connection.vendor=='postgresql' else None,
            'platform':platform.platform(),'cpu_count':os.cpu_count(),'dataset_hash':digest.hexdigest(),
            'repeats':opts['repeats'],'warmups':5,'concurrency':opts['concurrency'],'rows':rows,
            'relevance':relevance(rows,qrels),'qrels_provided':bool(qrels)}
        path=Path(opts['output']);path.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(path,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w') as file:json.dump(payload,file,ensure_ascii=False,indent=2)
        self.stdout.write(f'Service benchmark saved: {path}; queries={len(rows)}; errors={sum(len(r["errors"]) for r in rows)}')
