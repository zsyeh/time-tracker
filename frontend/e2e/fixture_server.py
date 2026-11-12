"""Synthetic read-only API for checking the built Drill UI in a browser."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import json, mimetypes

import os
root=Path(os.environ.get('UI_REBUILD_FIXTURE_ROOT',Path(__file__).resolve().parents[2]))
dist=root/'frontend/drill-dist'
import fixture_data
legacy={'heatmap':fixture_data.heatmap,'diagnostics':fixture_data.diagnostics}
q=[]
for i in range(1,41):
 q.append({'uuid':f'11111111-1111-4111-8111-{i:012d}','question_order':i,'display_label':f'第 {i} 题 · 矩阵变换与特征值','document':'数学二严选题册','topic':'线性代数 / 矩阵','question_type':'choice' if i%2 else 'large','type_group':'small' if i%2 else 'large','source_category':'past_exam','source_category_label':'真题','state':'mastered' if i%3==0 else 'review' if i%4==0 else 'unattempted','review_overdue':False,'attempt_count':i%4,'record_kind':'single','pdf_pages':None})
coverage=lambda total,covered,mastered,review:{'total':total,'covered':covered,'mastered':mastered,'review':review,'remaining':total-covered,'required_daily':4}
points=[{'date':f'2026-11-{i:02d}','count':i%7+3,'submissions':i%7+4,'moving_average_7':5,'target':24,'is_today':i==12,'is_complete_day':i!=12} for i in range(1,13)]
scenario=lambda days:{'label':f'最近{days}日','average':5,'projected_added':45,'projected_total':73,'projected_toward_goal':73,'shortfall':7,'on_track':False,'window_days':days,'available_history_days':days,'history_sufficient':True,'status':'ready','estimated_completion_date':'2026-11-27'}

def response(path,query):
 extra=getattr(fixture_data,'response',lambda p,q:None)(path,query)
 if extra is not None:return extra
 if path.endswith('/api/auth/session/'):return {'user':{'username':'visual-audit','id':1}}
 if path.endswith('/api/learning/recovery/'):return {'version':0,'last_workspace':None,'locations':{}}
 if path.endswith('/api/drill/progress/'):return {'attempted_questions':28,'question_count':80,'total_attempts':42}
 if path.endswith('/api/drill/catalog/'):return {'summary':{'imported_count':80,'practiceable_count':80,'outline_count':0,'categories':[{'value':'past_exam','label':'真题','count':45},{'value':'workbook','label':'习题册','count':35}]},'coverage':{'available':[],'missing':[],'source_archive_checked':True},'documents':[{'id':1,'title':'数学二严选题册','question_count':80}],'topics':[{'id':1,'document_id':1,'path':'线性代数 / 矩阵','question_count':40}]}
 if path.endswith('/api/drill/questions/'):
  page=int(query.get('page',['1'])[0]);items=q[(page-1)*20:page*20]
  return {'count':40,'next':'next' if page==1 else None,'previous':'prev' if page>1 else None,'results':items,'type_statistics':{'small':{'total':20,'attempted':12,'mastered':7,'review':5},'large':{'total':20,'attempted':10,'mastered':4,'review':6},'short_answer':{'total':8,'attempted':4,'mastered':2,'review':2},'unknown':{'total':2,'attempted':0,'mastered':0,'review':0}}}
 if path.endswith('/api/drill/practice-trends/'):
  return {'workspace':'ei' if path.startswith('/ei/') else 'drill','project_label':'严选题','timezone':'Asia/Shanghai','today':'2026-11-12','range_days':30,'allowed_ranges':[7,14,30,50,90],'daily_target':24,'target_options':{'minimum':12,'standard':24,'sprint':36},'question_target':80,'available_questions':80,'points':points,'period':{'submissions':70,'different_questions':42,'daily_unique_total':60},'goal':{**coverage(80,28,16,12),'metric':'selected','status':'active','type_breakdown':{'small':coverage(40,16,10,6),'large':coverage(40,12,6,6),'unknown':coverage(0,0,0,0)}},'summary':{'today_net_coverage':3,'today_new_coverage':3,'today_removed_coverage':0,'today':8,'today_submissions':10,'last7':40,'average7':5.7,'last14':70,'average14':5,'previous7':30,'growth_percent':33,'last30':100,'streak':5,'target_days_last7':1,'completed_distinct':28,'remaining':52},'comparison_windows':{'last7':{'start':'2026-11-05','end':'2026-11-11'},'previous7':{'start':'2026-10-29','end':'2026-11-04'},'excludes_today':True},'prediction':{'deadline':'2026-11-21','days_remaining_including_today':10,'remaining_determinable':True,'remaining':52,'required_daily':6,'scenarios':[scenario(7),scenario(14)],'notice':'按现有速度估算，不构成完成承诺。'}}
 if path.endswith('/api/drill/search/suggestions/'):return {'query':query.get('q',[''])[0],'index_version':'fixture:1','results':[]}
 if path.endswith('/api/drill/heatmap/'):return legacy['heatmap']
 if path.endswith('/api/drill/diagnostics/'):return legacy['diagnostics']
 if path.endswith('/api/drill/insight/'):
  attempts=[{'attempt_id':i,'uuid':q[i]['uuid'],'label':q[i]['display_label'],'document':'数学二严选题册','topic':'线性代数 / 矩阵','result':'review' if i%2 else 'mastered','created_at':'2026-11-11T08:15:00Z','diagnoses':['K1'],'note':'检查矩阵的基底变换'} for i in range(10)]
  return {'marker_stats':[],'recent_questions':{'count':21,'page':1,'page_size':10,'total_pages':3,'previous_page':None,'next_page':2,'results':attempts},'recent_notes':{'count':8,'page':1,'page_size':10,'total_pages':1,'previous_page':None,'next_page':None,'results':[{'uuid':q[i]['uuid'],'label':q[i]['display_label'],'document':'数学二严选题册','topic':'线性代数','note':'检查基底变换。','updated_at':'2026-11-10T06:00:00Z','result':'review','primary_error':'K1'} for i in range(8)]},'options':{'errors':[],'courses':[],'documents':[],'topics':[]}}
 return None

class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  parsed=urlsplit(self.path);path=parsed.path
  data=response(path,parse_qs(parsed.query))
  if data is not None:
   body=json.dumps(data).encode();mime='application/json'
  else:
   if path.startswith('/static/drill/'):
    file=dist/path.removeprefix('/static/drill/')
   elif path.startswith('/static/app/'):
    file=root/'frontend/dist'/path.removeprefix('/static/app/')
   elif path=='/pwa/navigation.js':file=root/'deploy/pwa/navigation.js'
   elif path=='/manifest.webmanifest':file=root/'deploy/pwa/manifest.webmanifest'
   elif path.startswith('/pwa/'):file=root/'deploy/pwa'/path.removeprefix('/pwa/')
   elif path.startswith(('/drill/','/ei/')):file=dist/'index.html'
   elif path in ['/today','/trends','/sessions','/issues','/settings'] or path.startswith(('/sessions/','/share/')):file=root/'frontend/dist/index.html'
   else:file=None
   if not file or not file.is_file():self.send_error(404);return
   body=file.read_bytes();mime=mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
  self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def do_POST(self):
  # Only fixture responses; synthetic writes never reach any real API.
  parsed=urlsplit(self.path);data=response(parsed.path,parse_qs(parsed.query))
  if data is None:self.send_error(404);return
  body=json.dumps(data).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)
 def do_PUT(self):
  # Synthetic recovery acknowledgement only, never a production connection.
  length=int(self.headers.get('Content-Length','0'));payload=json.loads(self.rfile.read(length) or '{}')
  body=json.dumps({'version':payload.get('version',0)+1,'last_workspace':payload.get('workspace'),'locations':{}}).encode()
  self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass
if __name__ == '__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8008);args=parser.parse_args()
 ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
