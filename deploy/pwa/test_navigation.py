import asyncio,json,re,os,shutil,tempfile
from pathlib import Path
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlparse
from playwright.async_api import async_playwright
REPO=Path(__file__).resolve().parents[2];OUT=Path(os.environ.get('PWA_TEST_OUTPUT') or tempfile.mkdtemp(prefix='pwa-test-'));OUT.mkdir(parents=True,exist_ok=True);PORT=int(os.environ.get('PWA_TEST_PORT','18776'))
class Handler(SimpleHTTPRequestHandler):
 def do_GET(self):
  path=urlparse(self.path).path
  if path=='/manifest.webmanifest':f=REPO/'deploy/pwa/manifest.webmanifest';kind='application/manifest+json'
  elif path.startswith('/pwa/'):f=REPO/'deploy/pwa'/path.removeprefix('/pwa/');kind='application/javascript' if path.endswith('.js') else 'image/png'
  elif path.startswith('/static/app/') or path.startswith('/static/drill/'):
   drill=path.startswith('/static/drill/');f=REPO/'frontend'/('drill-dist' if drill else 'dist')/path.split('/',3)[3];kind='text/css' if path.endswith('.css') else 'application/javascript'
  else:
   f=REPO/'frontend'/('drill-dist' if path.startswith(('/drill/','/ei/')) else 'dist')/'index.html'
   html=f.read_text();head=html.split('</head>')[0]+'</head>'
   head=re.sub(r'<script type="module"[^>]*></script>','',head)
   body=head+'<body><main style="height:2400px"><h1>'+path+'</h1><p>PWA navigation fixture</p></main></body></html>'
   self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(body.encode());return
  if not f.is_file():self.send_error(404);return
  self.send_response(200);self.send_header('Content-Type',kind);self.end_headers();self.wfile.write(f.read_bytes())
 def log_message(self,*args):pass
async def run():
 server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler);Thread(target=server.serve_forever,daemon=True).start();results=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--no-sandbox'])
  for kind in ['browser','standalone','ios-standalone']:
   context=await browser.new_context(viewport={'width':1024,'height':768})
   async def map_ip(r):
    import urllib.request
    def fetch():
     with urllib.request.urlopen(f'http://127.0.0.1:{PORT}'+urlparse(r.request.url).path,timeout=10) as res:return res.read(),res.headers.get('Content-Type')
    content,mime=await asyncio.to_thread(fetch)
    await r.fulfill(body=content,content_type=mime)
   await context.route('https://47.95.10.128/**',map_ip)
   page=await context.new_page()
   page.on('pageerror',lambda e:print('PAGE ERROR',e,flush=True))
   if kind=='standalone':
    await page.add_init_script("const originalMatchMedia=window.matchMedia.bind(window);window.matchMedia=q=>{const m=originalMatchMedia(q);if(q==='(display-mode: standalone)')Object.defineProperty(m,'matches',{value:true});return m}")
   elif kind=='ios-standalone':await page.add_init_script("Object.defineProperty(navigator,'standalone',{value:true})")
   await page.goto(f'http://127.0.0.1:{PORT}/')
   await page.wait_for_load_state('networkidle')
   print(kind,await page.evaluate("({standalone:matchMedia('(display-mode: standalone)').matches,ios:navigator.standalone,nav:!!document.querySelector('eh-pwa-navigation')})"),flush=True)
   assert await page.locator('link[rel=manifest]').get_attribute('href')=='/manifest.webmanifest'
   assert await page.locator('meta[name=apple-mobile-web-app-capable]').get_attribute('content')=='yes'
   assert 'width=device-width' in (await page.locator('meta[name=viewport]').get_attribute('content') or '')
   assert await page.evaluate('navigator.serviceWorker.getRegistrations().then(r=>r.length)')==0
   nav=page.locator('eh-pwa-navigation')
   if kind=='browser':
    assert await nav.count()==0
    results.append({'mode':kind,'menu_absent':True});await context.close();continue
   await nav.wait_for()
   await nav.locator('summary').click()
   links=await nav.locator('a').evaluate_all('(ls)=>ls.map(l=>({href:l.href,target:l.target}))')
   assert len(links)==4 and all(l['href'].startswith('https://47.95.10.128/') and not l['target'] for l in links)
   for service,path in [('Drill','/drill/practice'),('EI','/ei/practice')]:
    await nav.get_by_role('link',name=service,exact=True).click()
    await page.wait_for_url('https://47.95.10.128'+path)
    await page.wait_for_load_state('networkidle')
    # Each workspace supplies its own drawer, including on deep links.
    assert await page.locator('eh-pwa-navigation').count()==0
    await page.goto('https://47.95.10.128/')
    await page.wait_for_load_state('networkidle')
    nav=page.locator('eh-pwa-navigation');await nav.wait_for()
    await nav.locator('summary').click()
   await nav.get_by_role('link',name='Home',exact=True).click()
   await page.wait_for_url('https://47.95.10.128/')
   for path in ['/drill/progress','/ei/diagnostics','/drill/practice/example']:
    await page.goto('https://47.95.10.128'+path)
    await page.wait_for_load_state('networkidle')
    assert await page.locator('eh-pwa-navigation').count()==0
   await page.goto('https://47.95.10.128/')
   await page.wait_for_load_state('networkidle');nav=page.locator('eh-pwa-navigation');await nav.locator('summary').click()
   await page.evaluate("document.documentElement.lang='zh-CN'")
   await nav.get_by_role('button',name='刷新',exact=True).wait_for()
   await nav.get_by_role('button',name='刷新',exact=True).click()
   await page.wait_for_load_state('networkidle');nav=page.locator('eh-pwa-navigation');await nav.wait_for()
   assert await page.evaluate('window.scrollY')==0
   await page.evaluate('window.scrollTo(0,500)');assert await page.evaluate('window.scrollY')>0
   await page.set_viewport_size({'width':390,'height':844});await nav.locator('summary').click()
   bounds=await nav.locator('nav').bounding_box();assert bounds['x']>=0 and bounds['x']+bounds['width']<=390
   await page.screenshot(path=str(OUT/(kind+'.png')))
   results.append({'mode':kind,'services_same_origin':True,'workspace_menu_absent':True,'refresh':True,'scroll':True,'mobile_menu_fits':True})
   await context.close()
  await browser.close()
 server.shutdown();(OUT/'browser-results.json').write_text(json.dumps(results,indent=2));print('Browser, standalone and navigator.standalone navigation checks passed')
asyncio.run(run())
