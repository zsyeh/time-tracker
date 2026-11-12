import argparse,asyncio,json,importlib.util,time,re,os
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from playwright.async_api import async_playwright
REPO=Path(os.environ.get('ROUND2_REPO',Path(__file__).resolve().parents[3]))
P=REPO/'docs/uiux-rebuild-implementation/review/browser_review.py'
spec=importlib.util.spec_from_file_location('review',P);review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)
QUESTION=review.QUESTION
UUIDS=[f'11111111-1111-4111-8111-{n:012d}' for n in range(1,9)]
async def run(args):
 report={'base':args.base,'engine':args.engine,'rotation_requested':args.rotate,'cases':[]}
 async with async_playwright() as p:
  browser=await p.webkit.launch(headless=True) if args.engine=='webkit' else await p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
  for workspace in (['drill'] if args.single else ['drill','ei']):
   for width,height in ([(820,1180)] if args.single else [(390,844),(820,1180),(1180,820),(1440,900)]):
    context=await browser.new_context(viewport={'width':width,'height':height},has_touch=True,color_scheme='light')
    await context.add_init_script("localStorage.setItem('learning-os-ui-language','zh-CN');window.longTasks=[];window.longTaskObserverSupported=typeof PerformanceObserver!=='undefined'&&PerformanceObserver.supportedEntryTypes?.includes('longtask');if(window.longTaskObserverSupported)new PerformanceObserver(l=>{for(const e of l.getEntries())window.longTasks.push(e.duration)}).observe({type:'longtask',buffered:true})")
    page=await context.new_page();errors=[];requests=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    async def intercept(route):
     url=route.request.url;path=urlsplit(url).path;query=parse_qs(urlsplit(url).query)
     if path.endswith('/api/drill/questions/'):
      await asyncio.sleep(.1)
      rows=[{**QUESTION,'uuid':uuid,'question_order':n,'display_label':f'题目{n} 偏导数'} for n,uuid in enumerate(UUIDS,1)]
      await route.fulfill(json={'count':8,'results':rows,'search':{'version':2,'index_version':'fixture:1'},'next':None,'previous':None})
     elif '/timing/' in path:
      await route.fulfill(json={**route.request.post_data_json,'finalized':False,'local_base_valid':True})
     elif re.search('/questions/[0-9a-f-]+/$',path):
      uuid=path.rstrip('/').split('/')[-1];n=UUIDS.index(uuid)
      requests.append({'uuid':uuid,'query':urlsplit(url).query,'start':time.perf_counter()})
      await asyncio.sleep(.16)
      await route.fulfill(json={**QUESTION,'uuid':uuid,'question_order':n+1,'display_label':f'题目{n+1} 偏导数','previous_question_uuid':UUIDS[n-1] if n else None,'next_question_uuid':UUIDS[(n+1)%8],'sequential_next_question_uuid':UUIDS[(n+1)%8]})
     else:await route.continue_()
    await page.route('**/api/drill/questions/**',intercept)
    first=UUIDS[0]
    start=time.perf_counter();await page.goto(args.base+'/'+workspace+'/practice/'+first,wait_until='domcontentloaded')
    await page.locator('h1').filter(has_text='题目1 偏导数').wait_for();direct_ms=(time.perf_counter()-start)*1000
    rotations=[]
    if args.rotate:
     for rotated in [{'width':height,'height':width},{'width':width,'height':height}]:
      await page.set_viewport_size(rotated);await page.wait_for_timeout(100)
      metrics=await page.evaluate('''() => {const a=document.querySelector('.question-navigation-toggle'),b=document.querySelector('.question-return');const x=a?.getBoundingClientRect(),y=b?.getBoundingClientRect();return {width:innerWidth,height:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth,navigationOverlap:!!x&&!!y&&Math.min(x.right,y.right)>Math.max(x.left,y.left)&&Math.min(x.bottom,y.bottom)>Math.max(x.top,y.top)}}''')
      rotations.append(metrics)
     assert all(not item['overflow'] and not item['navigationOverlap'] for item in rotations),rotations
    await page.goto(args.base+'/'+workspace+'/practice?q=偏导数&status=review',wait_until='domcontentloaded')
    await page.locator('.question-row').first.wait_for()
    # Trigger hover prefetch and click before its160ms request completes.
    before=len([r for r in requests if r['uuid']==first]);await page.locator('.question-row').first.hover();await page.wait_for_timeout(15)
    start=time.perf_counter();await page.locator('.question-row').first.click()
    await page.locator('h1').filter(has_text='题目1 偏导数').wait_for();click_ms=(time.perf_counter()-start)*1000
    await page.wait_for_timeout(220)
    primary_requests=len([r for r in requests if r['uuid']==first])-before
    start=time.perf_counter();await page.locator('.question-topbar .next').click()
    await page.locator('h1').filter(has_text='题目2 偏导数').wait_for();next_ms=(time.perf_counter()-start)*1000
    start=time.perf_counter();await page.locator('.question-page-turner button').first.click()
    await page.locator('h1').filter(has_text='题目1 偏导数').wait_for();previous_ms=(time.perf_counter()-start)*1000
    await page.locator('.question-return').click(timeout=4000);await page.locator('.question-row').first.wait_for()
    assert parse_qs(urlsplit(page.url).query).get('q')==['偏导数'],page.url
    assert parse_qs(urlsplit(page.url).query).get('status')==['review'],page.url
    input=page.locator('#practice-search');await input.fill('pending draft')
    await page.locator('.question-row').first.click();await page.wait_for_timeout(400)
    assert urlsplit(page.url).path.endswith('/practice/'+first),page.url
    assert parse_qs(urlsplit(page.url).query).get('q')==['偏导数'],page.url
    await page.locator('.question-return').click(timeout=4000);await page.locator('.question-row').first.wait_for()
    input=page.locator('#practice-search');await input.fill('隐函数');await input.press('Enter')
    await page.wait_for_url('**q=**');await page.wait_for_timeout(400)
    assert parse_qs(urlsplit(page.url).query).get('q')==['隐函数'],page.url
    overflow=await page.evaluate('document.documentElement.scrollWidth>innerWidth')
    longtasks=await page.evaluate('window.longTasks')
    case={'workspace':workspace,'width':width,'height':height,'first_open_ms':direct_ms,'search_click_to_ready_ms':click_ms,'next_ms':next_ms,'previous_ms':previous_ms,'primary_detail_requests':primary_requests,'long_tasks_ms':longtasks,'long_task_observer_supported':await page.evaluate('window.longTaskObserverSupported'),'rotations':rotations,'horizontal_overflow':overflow,'errors':errors,'pass':not errors and not overflow and primary_requests<=1}
    report['cases'].append(case);print(json.dumps(case,ensure_ascii=False),flush=True)
    if workspace=='drill' and width==1180:await page.screenshot(path=args.output+'/search-return-ipad.png',full_page=True)
    await context.close()
  await browser.close()
 report['pass']=all(c['pass'] for c in report['cases']);Path(args.output+'/browser-flow.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 if not report['pass']:raise SystemExit(1)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--engine',choices=['chromium','webkit'],default='chromium');parser.add_argument('--rotate',action='store_true');parser.add_argument('--single',action='store_true');parser.add_argument('--base',default='http://127.0.0.1:8016');parser.add_argument('--output',default='/home/eh/learning-os-round2-evidence/search-question');asyncio.run(run(parser.parse_args()))
