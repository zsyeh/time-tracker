"""Actual App/50 original PNGs, no Playwright.route: browser HTTP cache remains enabled."""
import asyncio,json,os
from urllib.parse import urlencode
from playwright.async_api import async_playwright
OUT=os.path.dirname(__file__)
async def main():
 credentials=json.load(open('/home/eh/learning-os-preview-private/fixture-sessions.json'))['50']
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
  page=await browser.new_page(viewport={'width':1024,'height':768});errors=[];headers=[];api_requests=[]
  await page.context.add_cookies([{'name':credentials['cookie_name'],'value':credentials['cookie_value'],'domain':'127.0.0.1','path':'/','httpOnly':True,'secure':False}])
  page.on('pageerror',lambda error:errors.append(error.stack or str(error)))
  async def response(reply):
   if '/collection-preview/' in reply.url:
    body=await reply.json();api_requests.append({'offset':body.get('offset'),'count':body.get('count'),'status':reply.status})
   if '/api/drill/assets/' in reply.url and len(headers)<3:headers.append({key:value for key,value in reply.headers.items() if key in ['cache-control','vary','content-type','etag','last-modified']})
  page.on('response',response)
  context={'version':1,'workspace':'drill','source':'favorite','query':{},'returnTo':'/favorites'}
  await page.goto('http://127.0.0.1:8035/drill/preview?'+urlencode({'list':json.dumps(context)}))
  await page.wait_for_selector('.preview-image-open');await page.wait_for_timeout(500)
  samples=[]
  for position in [50,1,50,1]:
   await page.locator('#preview-position').fill(str(position));await page.locator('button[type=submit]').click();await page.wait_for_timeout(700)
   samples.append(await page.evaluate('''position=>({position,ready:document.querySelectorAll('.preview-scroller img').length,mounted:document.querySelectorAll('.preview-row').length,cached:+document.querySelector('.collection-preview').dataset.cachedMetadata})''',position))
  resources=await page.evaluate("performance.getEntriesByType('resource').filter(x=>x.name.includes('/api/drill/assets/')).map(x=>({path:new URL(x.name).pathname,transferSize:x.transferSize,encodedBodySize:x.encodedBodySize,decodedBodySize:x.decodedBodySize,duration:x.duration}))")
  report={'kind':'isolated local actual production bundle, 50 original PNG collection; no network interception/cache bypass','http_cache_enabled':True,'metadata_requests':api_requests,'asset_headers':headers,'samples':samples,'resources':resources,'cache_hits':sum(x['transferSize']==0 and x['decodedBodySize']>0 for x in resources),'errors':errors}
  with open(os.path.join(OUT,'real-http-cache.json'),'w')as f:json.dump(report,f,ensure_ascii=False,indent=2)
  print(json.dumps({'cache_hits':report['cache_hits'],'requests':len(resources),'headers':headers,'samples':samples,'errors':errors},ensure_ascii=False,indent=2));await browser.close()
asyncio.run(main())
