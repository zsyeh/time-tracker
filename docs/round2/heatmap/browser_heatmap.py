"""Synthetic browser-only heatmap benchmark. Never contacts production or writes learning data."""
import argparse,json,time,statistics
from pathlib import Path
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser();parser.add_argument('--url',required=True);parser.add_argument('--label',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
def payload(n):
 qs=[dict(uuid=f'11111111-1111-4111-8111-{i:012d}',order=i,label=f'第 {i} 题',topic='线性代数',year=2024,variant='',attempt_count=i%4,latest_result='review' if i%4==0 else None,review_overdue=i%19==0,state='mastered' if i%3==0 else 'review' if i%4==0 else 'unattempted',source_indexed=False,type_group='small' if i%2 else 'large') for i in range(1,n+1)]
 stat=dict(attempted_question_count=n//2,mastered_question_count=n//3,review_question_count=n//4,coverage_percent=50)
 return dict(question_count=n,topic_count=0,statistics=stat,groups=[dict(document_id=1,document='热力图性能测试册 · 合成资料',questions=qs,topics=[],statistics=stat)])
results=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
 for count in [963,9281]:
  for coarse,width,height in [(True,1180,820),(True,390,844),(False,1440,900)]:
   samples=[]
   for repeat in range(5):
    ctx=browser.new_context(viewport=dict(width=width,height=height),has_touch=coarse,is_mobile=coarse,device_scale_factor=1)
    page=ctx.new_page();errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
    page.add_init_script("localStorage.setItem('learning-os-ui-language','zh-CN'); localStorage.setItem('learning-os-color-scheme','light'); localStorage.setItem('learning.ui.visual.v1',JSON.stringify({version:1,appearance:'light',accent:'blue'})); window.__long=[]; new PerformanceObserver(l=>window.__long.push(...l.getEntries().map(e=>e.duration))).observe({entryTypes:['longtask']});")
    body=json.dumps(payload(count),ensure_ascii=False)
    page.route('**/api/drill/heatmap/**',lambda r:r.fulfill(status=200,content_type='application/json',body=body))
    start=time.monotonic();page.goto(args.url+'/drill/selected-heatmap',wait_until='domcontentloaded')
    page.wait_for_function('(n)=>document.querySelectorAll("[data-question-uuid]").length===n',arg=count)
    page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    load_ms=round((time.monotonic()-start)*1000,2)
    dom=page.locator('.question-heatmap *').count()
    rect=page.locator('[data-question-uuid]').first.bounding_box()
    t=page.evaluate('()=>performance.now()');page.locator('[data-question-uuid]').first.click();page.wait_for_selector('.question-preview-card')
    page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    select_ms=round(page.evaluate('()=>performance.now()')-t,2)
    t=page.evaluate('()=>performance.now()');page.locator('.heatmap-state-filters button').nth(1).click()
    page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    filter_ms=round(page.evaluate('()=>performance.now()')-t,2)
    scroll=page.evaluate('''async()=>{let last=performance.now(), gaps=[];for(let i=0;i<45;i++){await new Promise(r=>requestAnimationFrame(r));let now=performance.now();gaps.push(now-last);last=now;window.scrollBy(0,100)}return {p95:gaps.sort((a,b)=>a-b)[Math.floor(gaps.length*.95)],max:Math.max(...gaps)}}''')
    item=dict(load_ms=load_ms,select_ms=select_ms,filter_ms=filter_ms,dom_nodes=dom,cell_px=rect['width'],scroll_frame_ms=scroll,long_tasks=page.evaluate('window.__long'),errors=errs)
    samples.append(item)
    if repeat==0:
     page.evaluate('()=>window.scrollTo(0,0)');page.screenshot(path=str(out/f'{args.label}-{count}-{width}.png'),full_page=False)
    ctx.close()
   row=dict(label=args.label,questions=count,width=width,coarse=coarse,payload_bytes=len(body.encode()),samples=samples,medians={k:statistics.median(s[k] for s in samples) for k in ['load_ms','select_ms','filter_ms','dom_nodes','cell_px']})
   results.append(row);print(json.dumps({k:v for k,v in row.items() if k!='samples'}),flush=True)
 browser.close()
(out/(args.label+'.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
