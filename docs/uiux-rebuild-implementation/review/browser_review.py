"""Independent read-only UI review; all state and API writes are synthetic.

Requires fixture_server.py listening on 127.0.0.1:8008 and current production builds.
The recovery test intercepts EVERY request on a simulated production origin and
fulfills only from local build files / synthetic fixture data. It never contacts
that origin. The archived copy belongs only to the independent review evidence.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from playwright.async_api import async_playwright

ROOT = Path('/home/eh/ui-rebuild-20261112')
UUID = '11111111-1111-4111-8111-000000000001'
QUESTION = dict(uuid=UUID, question_type='choice', type_group='small', document='数学二严选题册', question_order=1,
    source_label='第1题', display_label='第1题 · 求导与条件判断', topic='多元微分', is_past_exam=True,
    source_category='past_exam', source_category_label='真题', record_kind='question', exam_year=2025,
    exam_variant='', attempt_count=1, latest_result='review', state='review', can_undo=True,
    is_favorite=False, review_later=False, saved_note='', review_overdue=False, pdf_pages=None,
    prompt_text='已知可微函数 f(x,y)，求其偏导数，并验证隐函数适用的条件。', latex_text='', content_mode='text',
    formula_source='tex', document_author='', document_attribution='', previous_question_uuid=None,
    previous_overdue_review_uuid=None, previous_review_uuid=None, next_question_uuid=None,
    sequential_next_question_uuid=None, next_overdue_review_uuid=None, next_review_uuid=None,
    confidence=None, last_time_spent_seconds=None, last_timed_at=None, note='', state_version=1,
    markers=[], breadcrumbs=[], question_assets=[], answer_assets=[], has_answer=True,
    answer_markdown='首先写出隐函数成立的条件，然后求导。', answer_source='source', answer_confidence=None,
    answer_generated_at=None, latest_diagnosis=None, review_plan=None)
FOCUS = """() => {const e=document.activeElement;return {tag:e?.tagName,cls:e?.className,text:e?.textContent?.slice(0,60),inDrawer:!!e?.closest('dialog[open]'),connected:!!e?.isConnected}}"""

async def menus(browser):
    context = await browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    await context.add_init_script("localStorage.setItem('learning-os-ui-language','zh-CN')")
    page = await context.new_page()
    await page.goto('http://127.0.0.1:8008/drill/practice',wait_until='networkidle')
    await page.locator('.ui-app-header button').click()
    await page.locator('.more-tools-trigger').click()
    await page.keyboard.press('Escape')
    await page.wait_for_timeout(50)
    escape = {'drawer':await page.locator('dialog[open]').count(),'popup':await page.locator('[data-ui-popover]').count(),'focus':await page.evaluate(FOCUS)}
    if not escape['drawer']: await page.locator('.ui-app-header button').click()
    await page.locator('.workspace-account').click()
    await page.keyboard.press('Tab')
    await page.wait_for_timeout(50)
    tab = {'drawer':await page.locator('dialog[open]').count(),'popup':await page.locator('[data-ui-popover]').count(),'focus':await page.evaluate(FOCUS)}
    await page.locator('.workspace-account').click()
    await page.keyboard.press('ArrowDown')
    roving = {'focus':await page.evaluate(FOCUS),'zeroTabStops':await page.locator('[role=menu] button[tabindex="0"]').count()}
    await page.keyboard.press('Shift+Tab')
    await page.wait_for_timeout(50)
    shiftTab = {'drawer':await page.locator('dialog[open]').count(),'popup':await page.locator('[data-ui-popover]').count(),'focus':await page.evaluate(FOCUS)}
    await page.locator('.more-tools-trigger').click()
    await page.set_viewport_size({'width':1180,'height':820})
    await page.wait_for_timeout(100)
    rotation = {'drawer':await page.locator('dialog[open]').count(),'popup':await page.locator('[data-ui-popover]').count(),'bodyOverflow':await page.evaluate('document.body.style.overflow')}
    result = {'escape':escape,'tab':tab,'shiftTab':shiftTab,'roving':roving,'rotation':rotation}
    result['pass'] = escape['drawer']==1 and escape['popup']==0 and tab['drawer']==1 and tab['popup']==0 and tab['focus']['inDrawer'] and tab['focus']['tag']!='BODY' and shiftTab['focus']['inDrawer'] and shiftTab['popup']==0 and roving['zeroTabStops']==1 and rotation['drawer']==0 and rotation['popup']==0 and rotation['bodyOverflow']!='hidden'
    await context.close()
    return result

async def timer_menus(browser):
    context=await browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    page=await context.new_page();await page.goto('http://127.0.0.1:8008/settings',wait_until='networkidle')
    await page.locator('.timer-navigation-toggle').click()
    await page.locator('.timer-account').click();await page.keyboard.press('Escape');await page.wait_for_timeout(50)
    escape={'drawer':await page.locator('dialog[open]').count(),'popup':await page.locator('[data-ui-popover]').count(),'focus':await page.evaluate(FOCUS)}
    if not escape['drawer']:await page.locator('.timer-navigation-toggle').click()
    await page.locator('.timer-account').click();await page.keyboard.press('Tab');await page.wait_for_timeout(50)
    tab={'drawer':await page.locator('dialog[open]').count(),'popup':await page.locator('[data-ui-popover]').count(),'focus':await page.evaluate(FOCUS)}
    await context.close()
    return {'escape':escape,'tab':tab,'pass':escape['drawer']==1 and escape['popup']==0 and tab['focus']['inDrawer'] and tab['focus']['tag']!='BODY' and tab['popup']==0}

async def appearance(browser):
    context=await browser.new_context(viewport={'width':1440,'height':1000},color_scheme='light')
    await context.add_init_script("localStorage.setItem('learning-os-ui-language','zh-CN')")
    page=await context.new_page();await page.goto('http://127.0.0.1:8008/drill/settings',wait_until='networkidle')
    async def state(pg):return await pg.evaluate("()=>({appearance:document.documentElement.dataset.appearance,scheme:document.documentElement.dataset.colorScheme,accent:document.documentElement.dataset.accent,bg:getComputedStyle(document.body).backgroundColor})")
    result={'default':await state(page)}
    await page.emulate_media(color_scheme='dark');await page.wait_for_timeout(100);result['systemDark']=await state(page)
    await page.locator('.appearance-selector button').first.click();await page.locator('[data-ui-popover] label').nth(1).click()
    await page.emulate_media(color_scheme='light');await page.emulate_media(color_scheme='dark');result['manualLight']=await state(page)
    await page.get_by_role('button',name='Blue',exact=False).click();await page.locator('[data-ui-popover] label').filter(has_text='Yellow').click();result['yellow']=await state(page)
    await page.reload(wait_until='networkidle');result['reload']=await state(page)
    ei=await context.new_page();await ei.goto('http://127.0.0.1:8008/ei/settings',wait_until='networkidle');result['ei']=await state(ei)
    result['pass']=result['systemDark']['scheme']=='dark' and result['manualLight']['scheme']=='light' and all(result[k]['bg']=='rgb(255, 255, 255)' and result[k]['accent']=='yellow' for k in ['yellow','reload','ei'])
    await context.close();return result

async def question(browser,out):
    context = await browser.new_context(viewport={'width':1180,'height':820},has_touch=True,color_scheme='dark')
    await context.add_init_script("localStorage.setItem('learning-os-ui-language','zh-CN')")
    page = await context.new_page()
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    async def intercept(route):
        if '/timing/' in route.request.url:
            await route.fulfill(json={**route.request.post_data_json,'finalized':False,'local_base_valid':True})
        elif re.search('/questions/'+UUID+'/(?:\\?.*)?$',route.request.url):
            await route.fulfill(json=QUESTION)
        elif '/questions/'+UUID+'/' in route.request.url:
            await route.fulfill(json={'results':[]})
        else:
            await route.continue_()
    await page.route('**/api/drill/questions/**',intercept)
    await page.goto('http://127.0.0.1:8008/drill/practice/'+UUID,wait_until='networkidle')
    await page.get_by_role('button',name='填写诊断',exact=True).click()
    await page.wait_for_timeout(150)
    metrics=await page.evaluate("""() => {const rect=s=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();return {y:r.y,bottom:r.bottom,width:r.width,height:r.height,scrollHeight:e.scrollHeight,clientHeight:e.clientHeight}};return {pane:rect('.question-control-pane'),diagnosis:rect('.diagnosis-selector'),actions:rect('.practice-action-toolbar'),overflow:document.documentElement.scrollWidth>innerWidth,rows:[...document.querySelectorAll('.diagnosis-selection-row')].map(e=>({text:e.textContent,height:e.getBoundingClientRect().height,y:e.getBoundingClientRect().y}))}}""")
    await page.screenshot(path=str(out/'question-diagnosis-1180x820.png'),full_page=True)
    await page.locator('.diagnosis-selection-row').nth(0).click()
    await page.locator('.diagnosis-selection-row').nth(1).click()
    await page.wait_for_timeout(100)
    selected=await page.evaluate("""()=>{const p=document.querySelector('.question-control-pane').getBoundingClientRect(),a=document.querySelector('.practice-action-toolbar').getBoundingClientRect();return{checked:document.querySelectorAll('.diagnosis-selector input:checked').length,paneBottom:p.bottom,actionTop:a.top,actionBottom:a.bottom,fullyVisible:a.bottom<=p.bottom&&a.top>=p.top,primaryChoices:document.querySelector('.primary-help')?.textContent}}""")
    await page.screenshot(path=str(out/'question-diagnosis-selected-1180x820.png'),full_page=True)
    await page.locator('.note-field summary').click()
    await page.locator('.save-note').scroll_into_view_if_needed()
    await page.wait_for_timeout(100)
    note=await page.evaluate("""()=>{const p=document.querySelector('.question-control-pane').getBoundingClientRect(),e=document.querySelector('.save-note'),r=e.getBoundingClientRect(),a=document.querySelector('.practice-action-toolbar').getBoundingClientRect();return{open:document.querySelector('.note-field').open,save:{top:r.top,bottom:r.bottom,visible:r.top>=p.top&&r.bottom<=p.bottom,unobstructed:e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))},actions:{top:a.top,bottom:a.bottom,visible:a.top>=p.top&&a.bottom<=p.bottom}}}""")
    await page.locator('.practice-more summary').click()
    await page.wait_for_timeout(50)
    more=await page.evaluate("""()=>{const p=document.querySelector('.question-control-pane').getBoundingClientRect();return [...document.querySelectorAll('.practice-more-menu button')].map(e=>{const r=e.getBoundingClientRect();return{text:e.textContent,visible:r.top>=p.top&&r.bottom<=p.bottom,unobstructed:e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}})}""")
    await page.screenshot(path=str(out/'question-note-more-1180x820.png'),full_page=True)
    await page.keyboard.press('Escape')
    await page.locator('.inline-fullscreen-trigger').first.click()
    await page.wait_for_timeout(100)
    reader={'open':await page.locator('.fullscreen-reader[open]').count()}
    await page.set_viewport_size({'width':390,'height':844})
    await page.wait_for_timeout(100)
    reader['afterRotation']=await page.evaluate("""()=>({open:!!document.querySelector('.fullscreen-reader[open]'),overflow:document.documentElement.scrollWidth>innerWidth,buttons:[...document.querySelectorAll('.reader-toolbar button')].filter(e=>e.getBoundingClientRect().width).map(e=>{let r=e.getBoundingClientRect();return{label:e.getAttribute('aria-label')||e.textContent,width:r.width,height:r.height,right:r.right}})})""")
    await page.screenshot(path=str(out/'question-reader-390x844.png'),full_page=True)
    await page.keyboard.press('Escape')
    reader['closed']=await page.locator('.fullscreen-reader[open]').count()==0
    await context.close()
    passed = (not metrics['overflow'] and len(metrics['rows']) == 8
        and all(row['height'] >= 44 for row in metrics['rows'])
        and metrics['actions']['bottom'] <= metrics['pane']['bottom']
        and selected['checked'] == 2 and selected['fullyVisible']
        and note['open'] and note['save']['visible'] and note['save']['unobstructed']
        and note['save']['bottom'] - note['save']['top'] >= 44
        and note['actions']['visible'] and len(more) == 2
        and all(item['visible'] and item['unobstructed'] for item in more)
        and reader['open'] == 1 and reader['afterRotation']['open']
        and not reader['afterRotation']['overflow'] and reader['closed']
        and len(reader['afterRotation']['buttons']) == 7
        and all(item['height'] >= 44 and item['width'] >= 44 for item in reader['afterRotation']['buttons'])
        and not errors)
    return {'metrics':metrics,'twoSelected':selected,'noteEditor':note,'moreActions':more,'reader':reader,'errors':errors,'pass':passed,'note':'Synthetic complete QuestionView; no answer submitted.'}

async def deleted_paper(browser):
    spec=importlib.util.spec_from_file_location('review_fixture',ROOT/'frontend/e2e/fixture_data.py')
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    context=await browser.new_context(ignore_https_errors=True)
    state={'version':0,'dirty':True,'last_workspace':'ei','locations':{'ei':{'path':f'/ei/papers/{UUID}','scroll':{'window':0}}}}
    await context.add_init_script("Object.defineProperty(navigator,'standalone',{get:()=>true});localStorage.setItem('learning.locations.v2.1',"+json.dumps(json.dumps(state))+");")
    requests=[]
    async def fulfill_local(route):
        url=urlsplit(route.request.url);path=url.path;requests.append({'path':path,'method':route.request.method})
        if url.hostname!='47.95.10.128':
            await route.abort();return
        if path.endswith('/api/learning/recovery/'):
            await route.fulfill(json={'version':0,'last_workspace':None,'locations':{}});return
        if re.search(r'/api/drill/papers/[^/]+/',path):
            await route.fulfill(status=404,json={'detail':'Deleted synthetic paper'});return
        data=fixture.response(path,parse_qs(url.query))
        if data is not None:
            await route.fulfill(json=data);return
        file=None
        if path.startswith('/static/app/'):file=ROOT/'frontend/dist'/path.removeprefix('/static/app/')
        elif path.startswith('/static/drill/'):file=ROOT/'frontend/drill-dist'/path.removeprefix('/static/drill/')
        elif path=='/pwa/navigation.js':file=ROOT/'deploy/pwa/navigation.js'
        elif path in ['/','/today']:file=ROOT/'frontend/dist/index.html'
        elif path.startswith(('/drill/','/ei/')):file=ROOT/'frontend/drill-dist/index.html'
        if file and file.is_file():
            await route.fulfill(body=file.read_bytes(),content_type=mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
        else:await route.fulfill(status=404,body='Synthetic review: resource unavailable')
    await context.route('**/*',fulfill_local)
    page=await context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    await page.goto('https://47.95.10.128/?pwa_launch=1',wait_until='networkidle')
    await page.wait_for_timeout(350)
    result={'url':page.url,'paperRequests':[r for r in requests if '/papers/' in r['path']],'errors':errors,'pass':'/papers/' not in urlsplit(page.url).path,'network':'ALL intercepted; local static files + invented API only'}
    await context.close()
    return result

async def run(args):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    result={'fixture':True,'nativeSafari':False,'build':{name:hashlib.sha256((ROOT/f'frontend/{name}/index.html').read_bytes()).hexdigest() for name in ['dist','drill-dist']}}
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
        for key,fn in [('menus',lambda:menus(browser)),('timerMenus',lambda:timer_menus(browser)),('appearance',lambda:appearance(browser)),('question',lambda:question(browser,out)),('deletedPaper',lambda:deleted_paper(browser))]:
            try:result[key]=await fn()
            except Exception as error:result[key]={'error':str(error),'pass':False}
        await browser.close()
    result['pass'] = all(result[key].get('pass', False) for key in ['menus', 'timerMenus', 'appearance', 'question', 'deletedPaper'])
    (out/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result['pass']: raise SystemExit(1)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--repo',default=str(ROOT));args=parser.parse_args();ROOT=Path(args.repo).resolve();asyncio.run(run(args))
