"""Only localhost synthetic pagination/context data; no production connections."""
import ast,copy,importlib.util,json,re,sys,time
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
ROOT=Path('/home/eh/learning-os-preview');sys.path.insert(0,str(ROOT/'frontend/e2e'));import fixture_server
fixture_server.root=ROOT;fixture_server.dist=ROOT/'frontend/drill-dist'
tree=ast.parse((ROOT/'tracker/user_preferences.py').read_text());nodes=[node for node in tree.body if isinstance(node,ast.FunctionDef)and node.name=='preference_defaults'or isinstance(node,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='SIDEBAR_IDS'for t in node.targets)];ns={};exec(compile(ast.Module(body=nodes,type_ignores=[]),'actual-defaults','exec'),ns)
values=ns['preference_defaults']();values['language']='zh-CN';snapshot={'schema_version':1,'revision':0,'values':values,'field_revisions':{key:0 for key in values}}
spec=importlib.util.spec_from_file_location('review',ROOT/'docs/uiux-rebuild-implementation/review/browser_review.py');review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)
UUIDS=[f'11111111-1111-4111-8111-{i:012d}'for i in range(1,98)]
def question(i):return{**review.QUESTION,'uuid':UUIDS[i],'question_order':i+1,'display_label':f'分页测试 · 第{i+1}题','previous_question_uuid':UUIDS[i-1]if i else None,'next_question_uuid':UUIDS[i+1]if i+1<len(UUIDS)else None,'sequential_next_question_uuid':UUIDS[i+1]if i+1<len(UUIDS)else None}
def entry(i):return{'entry_id':'question:'+UUIDS[i],'question_uuid':UUIDS[i],'index':i,'label':f'分页测试 · 第{i+1}题','document':'合成题册','topic':'偏导数','state':'review','preview':{'question_markdown':'仅本地合成预览，不是生产题目。','assets':[]}}
base=fixture_server.response
def response(path,q):
 if path.endswith('/api/auth/session/'):return{'authenticated':True,'user':{'id':1,'username':'pagination-qa'},'preferences':copy.deepcopy(snapshot)}
 if path.endswith('/api/user-preferences/'):return copy.deepcopy(snapshot)
 if path.endswith('/api/drill/questions/'):
  time.sleep(.12);page=int(q.get('page',['1'])[0]);start=(page-1)*24
  return{'count':97,'page':page,'page_size':24,'total_pages':5,'next':'next'if page<5 else None,'previous':'previous'if page>1 else None,'results':[question(i)for i in range(start,min(start+24,97))],'search':{'version':2,'index_version':'pagination:1'}}
 if path.endswith('/api/drill/collection-preview/'):
  offset=int(q.get('offset',['0'])[0]);target=None
  uuid=q.get('locate_uuid',[''])[0];name=q.get('locate_entry',[''])[0]
  if uuid in UUIDS:target=UUIDS.index(uuid)
  elif name.startswith('question:')and name[9:]in UUIDS:target=UUIDS.index(name[9:])
  if target is not None:offset=target//50*50
  return{'count':97,'offset':offset,'limit':50,'has_more':offset+50<97,'collection_version':'pagination:1','located':entry(target)if target is not None else None,'results':[entry(i)for i in range(offset,min(offset+50,97))],'previous_entry':entry(target-1)if target is not None and target>0 else None,'next_entry':entry(target+1)if target is not None and target+1<97 else None}
 if re.search(r'/api/drill/questions/[^/]+/$',path):
  uuid=path.rstrip('/').split('/')[-1]
  if uuid in UUIDS:return question(UUIDS.index(uuid))
 return base(path,q)
fixture_server.response=response
class Handler(fixture_server.Handler):
 def do_GET(self):
  path=urlsplit(self.path).path
  if path.startswith(('/drill/','/ei/'))and'/api/'not in path:
   html=(fixture_server.dist/'index.html').read_text().replace('<head>','<head><script id="learning-user-preferences" type="application/json">'+json.dumps({'user_id':'1','snapshot':snapshot})+'</script>',1).encode();self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(html)));self.end_headers();self.wfile.write(html);return
  super().do_GET()
 def do_POST(self):
  if '/timing/'in urlsplit(self.path).path:
   payload=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0')))or'{}');body=json.dumps({**payload,'finalized':False,'local_base_valid':True}).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body);return
  super().do_POST()
 def do_PATCH(self):
  body=json.dumps(snapshot).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)
fixture_server.ThreadingHTTPServer(('127.0.0.1',8062),Handler).serve_forever()
