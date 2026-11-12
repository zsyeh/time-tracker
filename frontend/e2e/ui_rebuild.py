"""Production-bundle visual audit against local synthetic APIs; never production writes."""
import argparse,asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
VIEWPORTS=[(375,812),(390,844),(430,932),(820,1180),(1180,820),(1440,1000)]
PAGES=['practice','progress','diagnostics','selected-heatmap','insight','settings']
async def run(args):
 out=Path(args.output);out.mkdir(parents=True,exist_ok=True);results=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path=args.chrome,headless=True,args=['--no-sandbox'])
  for scheme in ['light','dark']:
   for width,height in VIEWPORTS:
    ctx=await browser.new_context(viewport={'width':width,'height':height},is_mobile=width<768,has_touch=width<1200,color_scheme=scheme,device_scale_factor=1)
    await ctx.add_init_script("localStorage.setItem('learning.ui.visual.v1',JSON.stringify({version:1,appearance:'"+scheme+"',accent:'blue'}));localStorage.setItem('learning-os-ui-language','zh-CN')")
    page=await ctx.new_page()
    for route in PAGES:
     errors=[];handler=lambda error:errors.append(str(error));page.on('pageerror',handler)
     await page.goto(f'{args.base_url}/drill/{route}',wait_until='networkidle');await page.wait_for_timeout(300)
     metrics=await page.evaluate("""() => ({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,background:getComputedStyle(document.body).backgroundColor,scheme:document.documentElement.dataset.colorScheme,headings:[...document.querySelectorAll('h1')].map(x=>x.textContent),tiny:[...document.querySelectorAll('main button,main label,main small')].filter(x=>x.getBoundingClientRect().width&&parseFloat(getComputedStyle(x).fontSize)<12).map(x=>({text:x.textContent.slice(0,40),size:getComputedStyle(x).fontSize})),overflow:[...document.querySelectorAll('main *')].filter(x=>{let b=x.getBoundingClientRect();return b.width>0&&(b.right>innerWidth+1||b.left<-1)&&!x.closest('dialog:not([open])')}).slice(0,12).map(x=>({tag:x.tagName,cls:x.className,text:x.textContent.slice(0,40)}))})""")
     filename=f'{route}-{scheme}-{width}x{height}.png';await page.screenshot(path=str(out/filename),full_page=True)
     results.append({'page':route,'scheme':scheme,'viewport':[width,height],'metrics':metrics,'errors':errors,'screenshot':filename,'fixture':True,'browser':'Chromium; not real Safari'})
     page.remove_listener('pageerror',handler)
    await ctx.close()
  await browser.close()
 (out/'manifest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
 bad=[r for r in results if r['errors'] or r['metrics']['scrollWidth']>r['viewport'][0]+1]
 print(json.dumps({'screenshots':len(results),'layout_or_js_failures':len(bad),'failures':[{'page':r['page'],'scheme':r['scheme'],'viewport':r['viewport'],'errors':r['errors'],'overflow':r['metrics']['overflow']}for r in bad]},ensure_ascii=False))
 return 1 if bad else 0
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--base-url',default='http://127.0.0.1:8008');parser.add_argument('--output',required=True);parser.add_argument('--chrome',default='/usr/bin/google-chrome');args=parser.parse_args();raise SystemExit(asyncio.run(run(args)))
