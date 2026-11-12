#!/usr/bin/env python3
"""Read-only real HTTP benchmark. Session cookie never appears in output/argv.

Cookie file (0600): a single Cookie header value, obtained from an authorized
staging fixture login. API authentication/middleware/serialization are included.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import statistics
import time
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-url',required=True)
    parser.add_argument('--queries',required=True)
    parser.add_argument('--endpoint',default='/api/drill/questions/')
    parser.add_argument('--query-param',default='q',choices=('q','search'))
    parser.add_argument('--cookie-file',required=True)
    parser.add_argument('--repeats',type=int,default=30)
    parser.add_argument('--concurrency',type=int,default=5)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    path=Path(args.cookie_file)
    if path.stat().st_mode & 0o077:
        parser.error('Cookie file must be private (chmod 600).')
    cookie=path.read_text().strip()
    queries=[json.loads(line) for line in Path(args.queries).read_text().splitlines() if line.strip()]
    def sample(query):
        url=args.base_url.rstrip('/')+args.endpoint+'?'+urlencode({args.query_param:query['q'],'search_version':'2',**query.get('params',{})})
        request=Request(url,headers={'Cookie':cookie,'Accept':'application/json'})
        started=time.perf_counter()
        try:
            with urlopen(request,timeout=10) as response:
                data=json.load(response)
                return {'ms':(time.perf_counter()-started)*1000,'status':response.status,'count':data.get('count',len(data.get('results',[]))),
                    'top20':[row.get('uuid',row.get('session_uuid',row.get('record_id'))) for row in data.get('results',[])[:20]],'index_version':data.get('search',{}).get('index_version')}
        except HTTPError as exc:
            return {'ms':(time.perf_counter()-started)*1000,'status':exc.code,'count':None,'top20':[]}
        except Exception as exc:
            return {'ms':(time.perf_counter()-started)*1000,'status':0,'count':None,'top20':[],'error':type(exc).__name__}
    rows=[]
    for query in queries:
        for _ in range(5):sample(query)
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            samples=list(pool.map(lambda _:sample(query),range(args.repeats)))
        values=sorted(row['ms'] for row in samples)
        rows.append({'id':query['id'],'median_ms':statistics.median(values),
            'p95_ms':values[math.ceil(.95*len(values))-1],'p99_ms':values[math.ceil(.99*len(values))-1],
            'max_ms':values[-1],
            'count':samples[-1]['count'],'top20':samples[-1]['top20'],'statuses':[s['status'] for s in samples],
            'samples_ms':[s['ms'] for s in samples],
            'index_versions':sorted({s['index_version'] for s in samples if s.get('index_version')}),
            'counts':sorted({s['count'] for s in samples if s.get('count') is not None})})
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as file:
        json.dump({'kind':'http','endpoint':args.endpoint,'warmups':5,'repeats':args.repeats,'concurrency':args.concurrency,'rows':rows},file,ensure_ascii=False,indent=2)
    print(f'HTTP benchmark saved; queries={len(rows)}; non-200={sum(s!=200 for r in rows for s in r["statuses"])}')

if __name__=='__main__':main()
