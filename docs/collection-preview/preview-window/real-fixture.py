"""Read-only localhost8033 fixture QA. Never stores session cookies or private fixture data."""
import asyncio,json,os,time,argparse
from playwright.async_api import async_playwright
OUT=os.path.dirname(__file__)
args=argparse.ArgumentParser();args.add_argument('--source',default='favorite');args.add_argument('--account',default='2000');args.add_argument('--continuous-steps',type=int,default=0);args.add_argument('--base',default='http://127.0.0.1:8035/drill');options=args.parse_args();BASE=options.base;NAME='real-'+options.source+'-'+options.account
async def main():
 private=json.load(open('/home/eh/learning-os-preview-private/fixture-sessions.json'))
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
  page=await browser.new_page(viewport={'width':1024,'height':768});errors=[];api=[];writes=[];fail_page=False
  await page.add_init_script("window.previewLongTasks=[];window.previewFirstImageReady=null;document.addEventListener('load',e=>{if(window.previewFirstImageReady===null&&e.target instanceof HTMLImageElement&&e.target.closest('.preview-scroller')&&e.target.naturalWidth>0)window.previewFirstImageReady=performance.now()},true);try{new PerformanceObserver(list=>{for(const e of list.getEntries())if(window.previewLongTasks.length<500)window.previewLongTasks.push({start:e.startTime,duration:e.duration})}).observe({type:'longtask',buffered:true})}catch{}")
  await page.context.add_cookies([{'name':private[options.account]['cookie_name'],'value':private[options.account]['cookie_value'],'domain':'127.0.0.1','path':'/','httpOnly':True,'secure':False}])
  page.on('pageerror',lambda e:errors.append(e.stack or str(e)))
  page.on('request',lambda r:writes.append({'method':r.method,'path':r.url.split('8033')[-1].split('?')[0]}) if r.method not in ['GET','HEAD','OPTIONS'] else None)
  async def intercept(r):
   nonlocal fail_page
   if fail_page and 'offset=600' in r.request.url:
    fail_page=False;await r.abort('failed');return
   await r.continue_()
  await page.route('**/api/drill/collection-preview/**',intercept)
  async def response(r):
   if '/collection-preview/' in r.url:
    try:
     body=await r.json();api.append({'offset':body.get('offset'),'count':body.get('count'),'status':r.status,'results':len(body.get('results',[]))})
    except:pass
  page.on('response',response)
  context={'version':1,'workspace':'drill','source':options.source,'query':{},'returnTo':'/practice'}
  from urllib.parse import urlencode
  started=time.perf_counter()
  document_response=await page.goto(BASE+'/preview?'+urlencode({'list':json.dumps(context)}));
  try:await page.wait_for_selector('.preview-question',timeout=10000)
  except Exception:
   print(json.dumps({'errors':errors,'body_heading':(await page.locator('body').inner_text())[:400],'api':api},ensure_ascii=False));await browser.close();return
  try:
   await page.wait_for_function('window.previewFirstImageReady !== null',timeout=5000);first_decode_ms=await page.evaluate('window.previewFirstImageReady')
  except:first_decode_ms=None
  await page.wait_for_timeout(200)
  async def snapshot(label):
   return await page.evaluate('''label=>{const root=document.querySelector('.preview-scroller'),b=root.getBoundingClientRect();const rows=[...root.querySelectorAll('.preview-row')].map(x=>({index:+x.dataset.index,id:x.querySelector('[data-entry-id]')?.dataset.entryId,top:x.getBoundingClientRect().top-b.top,height:x.offsetHeight}));return{label,mounted:rows.length,firstVisible:rows.find(x=>x.top+x.height>1),rows,cached:document.querySelector('.collection-preview')?.dataset.cachedMetadata??null,hasVue:!!root.__vueParentComponent,overflow:document.body.scrollWidth>innerWidth,scrollTop:root.scrollTop,height:root.clientHeight,images:root.querySelectorAll('img').length,dom:document.querySelectorAll('*').length,jsHeap:performance.memory?.usedJSHeapSize??null,decodedPixels:[...root.querySelectorAll('img')].reduce((sum,img)=>sum+img.naturalWidth*img.naturalHeight,0),error:document.querySelector('[role=alert]')?.textContent??''}}''',label)
  samples=[await snapshot('initial')]
  # Input is absolute ordinal, independent of backend 50-item page boundaries.
  for n in ([1,10,25,50,1] if options.account=='50' else list(range(51,1001,50))+[51,750,1250,2000,1]):
   if n==601:fail_page=True
   await page.locator('#preview-position').fill(str(n));await page.locator('button[type=submit]').click();await page.wait_for_timeout(180)
   if await page.locator('p[role=alert]').count():
    await page.locator('p[role=alert]').get_by_role('button',name='重试').click();await page.wait_for_timeout(300)
   samples.append(await snapshot(str(n)))
  if options.continuous_steps:
   for step in range(options.continuous_steps):
    await page.locator('.preview-scroller').evaluate('(r)=>{r.scrollTop+=r.clientHeight*.85}')
    await page.wait_for_timeout(40)
    if step%25==0:
     state=await snapshot('continuous-'+str(step));samples.append(state)
     if state['firstVisible'] and state['firstVisible']['index']>=1000:break
   for step in range(min(150,options.continuous_steps)):
    await page.locator('.preview-scroller').evaluate('(r)=>{r.scrollTop-=r.clientHeight*.85}')
    await page.wait_for_timeout(40)
    if step%25==0:samples.append(await snapshot('reverse-'+str(step)))
  await page.set_viewport_size({'width':390,'height':844});await page.wait_for_timeout(350);samples.append(await snapshot('390portrait'))
  await page.screenshot(path=os.path.join(OUT,NAME+'-mobile.png'))
  await page.set_viewport_size({'width':1366,'height':1024});await page.wait_for_timeout(350);samples.append(await snapshot('1366landscape'))
  await page.screenshot(path=os.path.join(OUT,NAME+'-landscape.png'))
  resources=await page.evaluate("performance.getEntriesByType('resource').filter(x=>x.name.includes('/assets/')).map(x=>({transferSize:x.transferSize,encodedBodySize:x.encodedBodySize,decodedBodySize:x.decodedBodySize,duration:x.duration}))")
  longtasks=await page.evaluate('window.previewLongTasks')
  report={'document_csp':document_response.headers.get('content-security-policy'),'first_rendered_image_ms':first_decode_ms,'asset_resources':resources,'longtasks':longtasks,'kind':'isolated local fixture actual app/public metadata; source='+options.source+' account-size='+options.account+'; final isolated fixture has2326 SHA-verified original PNGs for the2000 favorites/anchors; other collections may remain metadata-only','api':api,'samples':samples,'max_mounted':max(x['mounted']for x in samples),'errors':errors,'writes':writes,'network_abort_injected_consumed':not fail_page}
  with open(os.path.join(OUT,NAME+'.json'),'w')as f:json.dump(report,f,ensure_ascii=False,indent=2)
  print(json.dumps({k:v for k,v in report.items()if k!='samples'},ensure_ascii=False,indent=2));await browser.close()
asyncio.run(main())
