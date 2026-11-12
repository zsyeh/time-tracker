import argparse,asyncio,json,time
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from playwright.async_api import async_playwright
async def run(a):
 output=Path(a.output);output.mkdir(parents=True,exist_ok=True);results=[]
 async with async_playwright()as p:
  browser=await p.webkit.launch(headless=True)if a.engine=='webkit'else await p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
  for workspace in ('drill','ei'):
   for width,height in ([(375,812),(390,844),(430,932)] if a.phone_only else [(390,844),(820,1180),(1180,820),(1440,900)]):
    context=await browser.new_context(viewport={'width':width,'height':height},has_touch=True,color_scheme='light');page=await context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    search='偏导数'if workspace=='drill'else'Fourier';collection='selected'if workspace=='drill'else'core_selected'
    await page.goto('http://127.0.0.1:8062/'+workspace+'/practice?q='+search+'&collection='+collection+'&status=review&sort=source',wait_until='domcontentloaded')
    async def wait_page(n):
     await page.wait_for_function("n=>{const p=document.querySelector('[data-page-position=bottom]');return Number(new URL(location.href).searchParams.get('page')||1)===n&&!!p&&p.getAttribute('aria-busy')==='false'&&p.querySelector('.page-jump input').value===String(n)}",arg=n)
     await page.wait_for_timeout(80)
    await wait_page(1)
    control_rows=[]
    if width<600:
     for cls in ['page-first','page-previous','page-next','page-last']:
      control_rows.append((await page.locator('[data-page-position=top] .'+cls).bounding_box())['y'])
     assert max(control_rows)-min(control_rows)<2,control_rows
    bottom=page.locator('[data-page-position=bottom]');await bottom.scroll_into_view_if_needed()
    before=(await bottom.bounding_box())['y'];await page.evaluate('window.__pagerY=[scrollY];window.__pagerListener=()=>window.__pagerY.push(scrollY);window.addEventListener("scroll",window.__pagerListener)');await bottom.locator('.page-next').click();await wait_page(2)
    after=(await bottom.bounding_box())['y'];trace=await page.evaluate('window.removeEventListener("scroll",window.__pagerListener);window.__pagerY');assert abs(after-before)<3,(before,after)
    if trace[0]>0:assert min(trace)>0,trace
    # Enter jumps to any page; typed search draft must not fire its old debounce.
    await page.locator('#practice-search').fill('unsubmitted draft')
    await bottom.locator('input').fill('4');await bottom.scroll_into_view_if_needed();anchor=(await bottom.bounding_box())['y'];await bottom.locator('input').press('Enter');await wait_page(4)
    await page.wait_for_timeout(300);assert parse_qs(urlsplit(page.url).query)['q']==[search];assert parse_qs(urlsplit(page.url).query)['page']==['4']
    assert abs((await bottom.bounding_box())['y']-anchor)<3
    # Native Enter and Space activate explicit first and last controls.
    top=page.locator('[data-page-position=top]');await top.locator('.page-first').focus();await page.keyboard.press('Enter');await wait_page(1)
    assert await top.locator('.page-first').is_disabled()
    await bottom.scroll_into_view_if_needed();await bottom.locator('.page-last').focus();await page.keyboard.press('Space');await wait_page(5)
    assert await bottom.locator('.page-last').is_disabled();assert await page.locator('.question-row').count()==1
    position=await page.evaluate('({y:scrollY,max:Math.max(0,document.documentElement.scrollHeight-innerHeight)})');assert 0<=position['y']<=position['max']+1
    newbox=box={'y':0}
    if not a.pager_only:
     # Return from a real QuestionView restores the clicked row and applied URL.
     await top.locator('input').fill('2');await top.locator('input').press('Enter');await wait_page(2)
     row=page.locator('.question-row').nth(12);await row.scroll_into_view_if_needed();box=await row.bounding_box();uuid=await row.get_attribute('data-question-uuid');original=page.url
     await row.click();await page.locator('.question-header h1').wait_for();await page.locator('.question-return').click();await wait_page(2)
     restored=page.locator('[data-question-uuid="'+uuid+'"]');newbox=await restored.bounding_box();assert abs(newbox['y']-box['y'])<4,(box,newbox);assert page.url==original,(page.url,original)
     # Preview keeps the complete source context and returns to that exact page/anchor.
     await restored.scroll_into_view_if_needed();await page.locator('.preview-all').focus();await page.keyboard.press('Enter')
     await page.wait_for_url('**/preview?**');q=parse_qs(urlsplit(page.url).query);ctx=json.loads(q['list'][0]);assert ctx['source']=='practice'and ctx['query']['q']==search and 'page'not in ctx['query'];assert'page=2'in ctx['returnTo']
     await page.get_by_role('button',name='返回题单',exact=True).click();await wait_page(2)
     assert page.url==original
    assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth')
    case={'engine':a.engine,'workspace':workspace,'width':width,'height':height,'bottom_anchor_before':before,'bottom_anchor_after':after,'full_page_scroll_trace':trace,'short_last_page_scroll':position,'question_return_offset_delta':None if a.pager_only else newbox['y']-box['y'],'first_enter_last_space':True,'mobile_button_row_offsets':control_rows,'full_preview_context':not a.pager_only,'errors':errors,'pass':not errors}
    results.append(case);print(json.dumps(case),flush=True)
    if workspace=='drill':await page.screenshot(path=str(output/f'practice-{width}.png'),full_page=False)
    await context.close()
  await browser.close()
 (output/'browser.json').write_text(json.dumps({'cases':results,'pass':all(r['pass']for r in results)},indent=2))
 if not all(r['pass']for r in results):raise SystemExit(1)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--engine',choices=['chromium','webkit'],default='chromium');ap.add_argument('--output',required=True);ap.add_argument('--pager-only',action='store_true');ap.add_argument('--phone-only',action='store_true');asyncio.run(run(ap.parse_args()))
