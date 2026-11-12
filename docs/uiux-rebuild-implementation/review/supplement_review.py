"""Supplemental read-only browser review. All API content is synthetic."""
import argparse, asyncio, hashlib, json, re
from pathlib import Path
from urllib.parse import urlsplit
from playwright.async_api import async_playwright
ROOT=Path('/home/eh/ui-rebuild-20261112')
ACCENTS=['blue','cyan','green','lime','yellow','orange','pink','magenta','purple','monochrome']
STATE="""()=>{const r=document.documentElement,c=getComputedStyle(r),style=e=>{const v=getComputedStyle(e);return{background:v.backgroundColor,color:v.color}};return{appearance:r.dataset.appearance,scheme:r.dataset.colorScheme,accent:r.dataset.accent,body:style(document.body),surface:c.getPropertyValue('--surface-page').trim(),subtle:c.getPropertyValue('--surface-subtle').trim(),elevated:c.getPropertyValue('--surface-elevated').trim(),canvas:c.getPropertyValue('--surface-sidebar').trim(),accentSolid:c.getPropertyValue('--accent-solid').trim(),stored:JSON.parse(localStorage.getItem('learning.ui.visual.v1')||'null'),cookie:document.cookie.includes('learning_ui_visual_v1='),overflow:r.scrollWidth>innerWidth}}"""
async def trends(browser,out):
    result=[]
    for scheme in ['light','dark']:
      for width,height in [(390,844),(1180,820)]:
        context=await browser.new_context(viewport={'width':width,'height':height},has_touch=True,color_scheme=scheme)
        await context.add_init_script("localStorage.setItem('learning-os-ui-language','zh-CN')")
        page=await context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto('http://127.0.0.1:8008/trends',wait_until='networkidle');await page.locator('.trend-chart canvas').wait_for();await page.wait_for_timeout(250)
        metrics=await page.evaluate("""()=>{const rect=e=>{const r=e.getBoundingClientRect();return{x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height}},pair=(e,a,b)=>{let x=e.querySelector(a),y=e.querySelector(b);if(!x||!y)return null;let p=rect(x),q=rect(y);return{label:x.textContent,value:y.textContent,labelBox:p,valueBox:q,overlap:p.x<q.right&&q.x<p.right&&p.y<q.bottom&&q.y<p.bottom}};return{overflow:document.documentElement.scrollWidth>innerWidth,summary:[...document.querySelectorAll('.insight')].map(e=>pair(e,'span','strong')),rows:[...document.querySelectorAll('.trend-data-row')].map(e=>pair(e,':scope > span',':scope > b')),subjects:[...document.querySelectorAll('.subject-time-card')].map(e=>({label:e.querySelector('header').textContent,value:e.querySelector('strong').textContent,card:rect(e),valueBox:rect(e.querySelector('strong')),footer:rect(e.querySelector('footer'))})),canvas:[...document.querySelectorAll('.trend-chart canvas')].map(rect),headers:[...document.querySelectorAll('.trend-data-group > header')].map(e=>pair(e,'h2','span'))}}""")
        await page.screenshot(path=str(out/f'trends-{scheme}-{width}.png'),full_page=True)
        metrics['summarySeparated']=all(p['valueBox']['y']>=p['labelBox']['bottom']+4 or p['valueBox']['x']>=p['labelBox']['right']+8 for p in metrics['summary'])
        metrics['pass']=metrics['summarySeparated'] and not metrics['overflow'] and not errors and all(not p['overlap'] for name in ['summary','rows','headers'] for p in metrics[name]) and all(x['valueBox']['right']<=x['card']['right']+1 for x in metrics['subjects'])
        result.append({'scheme':scheme,'width':width,'metrics':metrics,'errors':errors})
        await context.close()
    return {'cases':result,'pass':all(x['metrics']['pass'] for x in result)}

async def search(browser,out):
    context=await browser.new_context(viewport={'width':1180,'height':820},color_scheme='light')
    await context.add_init_script("localStorage.setItem('learning-os-ui-language','zh-CN')")
    page=await context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    excerpt='🧪 Fourier 傅里叶变换 <img src=x onerror="window.__reviewInjected=1"> 与 LaTeX \\frac{a}{b} 的公开题干'
    start=excerpt.index('Fourier')
    item={'uuid':'11111111-1111-4111-8111-000000000001','question_order':1,'display_label':'第 1 题 · 傅里叶变换与频移','document':'信号与系统公开题册','topic':'傅里叶变换','question_type':'large','type_group':'large','source_category':'workbook','source_category_label':'练习册','state':'unattempted','review_overdue':False,'attempt_count':0,'record_kind':'single','pdf_pages':None,'search_match':{'fields':['prompt'],'kind':'spelling','excerpt':excerpt,'highlights':[[start,start+len('Fourier')]],'coverage':'text'}}
    payload={'count':1,'next':None,'previous':None,'results':[item],'search':{'version':2,'index_version':'synthetic:1','corrected_terms':['fourier'],'coverage':{'metadata_only_count':0},'suggestions':[]}}
    async def intercept(route):
      if urlsplit(route.request.url).path.endswith('/api/drill/questions/'):await route.fulfill(json=payload)
      else:await route.continue_()
    await page.route('**/api/drill/questions/**',intercept)
    await page.goto('http://127.0.0.1:8008/ei/practice?q=fourire',wait_until='networkidle')
    await page.locator('.practice-search-excerpt').wait_for()
    metrics=await page.evaluate("""()=>({query:document.querySelector('#practice-search').value,excerpt:document.querySelector('.practice-search-excerpt').textContent,marks:[...document.querySelectorAll('.practice-search-excerpt mark')].map(e=>e.textContent),injectedImages:document.querySelectorAll('.practice-search-excerpt img').length,injectedScripts:document.querySelectorAll('.practice-search-excerpt script').length,executed:window.__reviewInjected||false,correction:document.querySelector('.search-expansion')?.textContent,overflow:document.documentElement.scrollWidth>innerWidth})""")
    await page.screenshot(path=str(out/'practice-safe-search-light-1180.png'),full_page=True)
    metrics['pass']=metrics['query']=='fourire' and metrics['marks']==['Fourier'] and metrics['excerpt']==excerpt and metrics['injectedImages']==0 and metrics['injectedScripts']==0 and not metrics['executed'] and 'fourier' in metrics['correction'] and not metrics['overflow'] and not errors
    await context.close();return {'metrics':metrics,'errors':errors,'syntheticPublicFieldsOnly':True,'pass':metrics['pass']}

async def palettes(browser,out):
    context=await browser.new_context(viewport={'width':1180,'height':820},color_scheme='light')
    await context.add_init_script("localStorage.setItem('learning-os-ui-language','zh-CN')")
    page=await context.new_page();await page.goto('http://127.0.0.1:8008/drill/settings',wait_until='networkidle')
    rows=[]
    for scheme in ['light','dark']:
      await page.locator('.appearance-selector > button').click();await page.locator('[data-ui-popover] label').nth(1 if scheme=='light' else 2).click()
      baseline=None
      for index,accent in enumerate(ACCENTS):
        await page.locator('button').filter(has=page.locator('.accent-swatch')).click()
        await page.locator('[data-ui-popover] label').nth(index).click()
        before=await page.evaluate(STATE)
        if baseline is None:baseline={k:before[k] for k in ['body','surface','subtle','elevated','canvas']}
        await page.reload(wait_until='networkidle');after=await page.evaluate(STATE)
        if accent in ['yellow','monochrome']:await page.screenshot(path=str(out/f'appearance-{scheme}-{accent}-1180.png'),full_page=True)
        expected='rgb(255, 255, 255)' if scheme=='light' else 'rgb(20, 20, 20)'
        passed=before['scheme']==scheme and before['accent']==accent and after['scheme']==scheme and after['accent']==accent and after['stored']=={'version':1,'appearance':scheme,'accent':accent} and after['cookie'] and after['body']['background']==expected and all(before[k]==baseline[k] and after[k]==baseline[k] for k in baseline) and not after['overflow']
        rows.append({'scheme':scheme,'accent':accent,'before':before,'after':after,'pass':passed})
    await context.close();return{'combinations':rows,'pass':len(rows)==20 and all(x['pass'] for x in rows)}

async def run(args):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    result={'fixture':True,'nativeSafari':False,'build':{name:hashlib.sha256((ROOT/f'frontend/{name}/index.html').read_bytes()).hexdigest() for name in ['dist','drill-dist']}}
    async with async_playwright() as p:
      browser=await p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
      for key,fn in [('trends',trends),('search',search),('palettes',palettes)]:
        if key not in args.cases.split(','): continue
        try:result[key]=await fn(browser,out)
        except Exception as e:result[key]={'error':str(e),'pass':False}
      await browser.close()
    result['pass']=all(result[k].get('pass',False) for k in args.cases.split(','))
    (out/'supplement.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:{'pass':v.get('pass'),'error':v.get('error')} if isinstance(v,dict) and k != 'build' else v for k,v in result.items()},ensure_ascii=False,indent=2))
    if not result['pass']:raise SystemExit(1)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--cases',default='trends,search,palettes');parser.add_argument('--repo',default=str(ROOT));args=parser.parse_args();ROOT=Path(args.repo).resolve();asyncio.run(run(args))
