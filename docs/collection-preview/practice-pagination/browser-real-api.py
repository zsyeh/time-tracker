"""Local isolated PG metadata only. No Question route, submissions or Notes."""
import argparse,asyncio,json,re
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from playwright.async_api import async_playwright
async def run(args):
 identities=json.loads(Path(args.identity).read_text());identity=identities['2000'];out=Path(args.output);out.mkdir(parents=True,exist_ok=True);cases=[]
 async with async_playwright()as p:
  browser=await p.webkit.launch(headless=True)if args.engine=='webkit'else await p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
  for width,height in ((390,844),(820,1180)):
   context=await browser.new_context(viewport={'width':width,'height':height},has_touch=True,color_scheme='light');await context.add_cookies([{'name':identity['cookie_name'],'value':identity['cookie_value'],'url':'http://127.0.0.1:8033','httpOnly':True}])
   session=await context.request.get('http://127.0.0.1:8033/api/auth/session/');data=await session.json();assert str(data['user']['id'])==str(identity['user_id'])
   page=await context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(re.sub(r'[0-9a-f]{8}-[0-9a-f-]{27,}','[question]',str(e))))
   await page.goto('http://127.0.0.1:8033/practice?favorite=1&sort=source',wait_until='domcontentloaded')
   async def wait_page(n):
    await page.wait_for_function("n=>{const e=document.querySelector('[data-page-position=bottom]');return Number(new URL(location.href).searchParams.get('page')||1)===n&&!!e&&e.getAttribute('aria-busy')==='false'&&e.querySelector('input').value===String(n)}",arg=n);await page.wait_for_timeout(100)
   await wait_page(1)
   summary=await page.locator('.page-summary').first.inner_text();numbers=[int(n)for n in re.findall(r'\d+',summary)];total=numbers[1];count=numbers[2];assert count>=1000 and total>2,(total,count)
   bottom=page.locator('[data-page-position=bottom]');await bottom.scroll_into_view_if_needed();before=(await bottom.bounding_box())['y'];await bottom.locator('.page-next').click();await wait_page(2);after=(await bottom.bounding_box())['y'];assert abs(after-before)<3,(before,after)
   assert parse_qs(urlsplit(page.url).query)['favorite']==['1']
   await bottom.locator('input').fill(str(total));await bottom.locator('input').press('Enter');await wait_page(total)
   last_rows=await page.locator('.question-row').count();assert last_rows==count-(total-1)*24,(last_rows,count,total)
   assert await bottom.locator('.page-last').is_disabled()
   last_scroll=await page.evaluate('({y:scrollY,max:Math.max(0,document.documentElement.scrollHeight-innerHeight)})');assert 0<=last_scroll['y']<=last_scroll['max']+1
   top=page.locator('[data-page-position=top]');await top.locator('.page-first').focus();await page.keyboard.press('Enter');await wait_page(1)
   await bottom.scroll_into_view_if_needed();await bottom.locator('.page-last').focus();await page.keyboard.press('Space');await wait_page(total)
   assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth')
   result={'engine':args.engine,'width':width,'height':height,'fixture_scope':'isolated 2000 synthetic account, favorites','count':count,'total_pages':total,'last_page_rows':last_rows,'bottom_before':before,'bottom_after':after,'anchor_delta':after-before,'last_scroll':last_scroll,'first_enter_last_space':True,'errors':errors,'pass':not errors};cases.append(result);print(json.dumps(result),flush=True)
   await page.screenshot(path=str(out/f'last-page-{width}.png'),full_page=False);await context.close()
  await browser.close()
 (out/'browser.json').write_text(json.dumps({'cases':cases,'pass':all(c['pass']for c in cases)},indent=2))
 if not all(c['pass']for c in cases):raise SystemExit(1)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--identity',default='/home/eh/learning-os-preview-private/fixture-sessions.json');parser.add_argument('--engine',choices=['chromium','webkit'],default='chromium');parser.add_argument('--output',required=True);asyncio.run(run(parser.parse_args()))
