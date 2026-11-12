"""Full built-app integration QA. Writes ONLY isolated synthetic users' settings/one answer."""
import asyncio,json,os,time,hashlib,traceback,argparse
from urllib.parse import urlencode,urlparse,parse_qs
from playwright.async_api import async_playwright
OUT=os.path.dirname(__file__);BASE='http://127.0.0.1:8035'
args=argparse.ArgumentParser();args.add_argument('--only',default='');options=args.parse_args();selected=set(options.only.split(','))if options.only else set()
SESSIONS=json.load(open('/home/eh/learning-os-preview-private/fixture-sessions.json'))
active_contexts=[]
report={'environment':'isolated localhost8035 production-prefix proxy/full production frontend/real PNGs; synthetic accounts only','cases':{},'errors':[],'writes':[],'network_failures':[]}
if selected and os.path.exists(os.path.join(OUT,'browser.json')):
 with open(os.path.join(OUT,'browser.json'))as previous:report=json.load(previous)
def context(source,workspace='drill',query=None,return_to=None):return {'version':1,'workspace':workspace,'source':source,'query':query or{},'returnTo':return_to or('/favorites'if source=='favorite'else'/practice')}
def preview(ctx,entry=None,question=None):return BASE+'/'+ctx['workspace']+'/preview?'+urlencode({'list':json.dumps(ctx,ensure_ascii=False),**({'entry':entry}if entry else{}),**({'question':question}if question else{})})
async def wait_url(page,part):
 for _ in range(150):
  if part in page.url:return
  await page.wait_for_timeout(100)
 raise AssertionError('URL did not reach '+part+' current '+page.url)
async def anchor(page):
 return await page.evaluate('''()=>{const s=document.querySelector('.preview-scroller'),b=s.getBoundingClientRect();const row=[...s.querySelectorAll('.preview-row')].find(x=>x.getBoundingClientRect().bottom>b.top+1);return{index:+row.dataset.index,entry:row.querySelector('[data-entry-id]')?.dataset.entryId,offset:row.getBoundingClientRect().top-b.top,scrollTop:s.scrollTop,cache:+document.querySelector('.collection-preview').dataset.cachedMetadata,mounted:s.querySelectorAll('.preview-row').length,overflow:document.body.scrollWidth>innerWidth}}''')
async def position(page,n):
 await page.locator('#preview-position').fill(str(n));await page.locator('button[type=submit]').click();await page.wait_for_timeout(600)
async def image_tap(page,index):
 await page.evaluate('''()=>{window.integrationGestureAnchor=null;document.addEventListener('click',event=>{if(!event.target.closest?.('.preview-image-open'))return;const s=document.querySelector('.preview-scroller'),b=s.getBoundingClientRect(),row=[...s.querySelectorAll('.preview-row')].find(x=>x.getBoundingClientRect().bottom>b.top+1);window.integrationGestureAnchor={index:+row.dataset.index,entry:row.querySelector('[data-entry-id]')?.dataset.entryId,offset:row.getBoundingClientRect().top-b.top}}, {capture:true,once:true})}''')
 bounds=await page.locator(f'.preview-row[data-index="{index}"] .preview-image-open').first.bounding_box();scroll=await page.locator('.preview-scroller').bounding_box();assert bounds and scroll
 top=max(bounds['y'],scroll['y']);bottom=min(bounds['y']+bounds['height'],scroll['y']+scroll['height']);assert bottom>top
 await page.mouse.click(bounds['x']+bounds['width']/2,(top+bottom)/2)
 return await page.evaluate('window.integrationGestureAnchor')
async def ready_preview(page):await page.wait_for_selector('.preview-question');await page.wait_for_timeout(450)
async def ready_question(page):
 await page.wait_for_selector('.question-timer',state='attached',timeout=20000);await page.wait_for_timeout(300)
 if await page.locator('.question-load-error').count():raise AssertionError(await page.locator('.question-load-error').inner_text())
async def api(page,path,method='GET',body=None):
 return await page.evaluate('''async({path,method,body})=>{const c=document.cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith('csrftoken='));const headers={Accept:'application/json'};if(c)headers['X-CSRFToken']=decodeURIComponent(c.slice(10));if(body)headers['Content-Type']='application/json';const response=await fetch(path,{method,credentials:'same-origin',headers,...(body?{body:JSON.stringify(body)}:{})});return{status:response.status,body:await response.json()}}''',{'path':path,'method':method,'body':body})
async def set_preferences(page,values,workspace='drill'):
 current=await api(page,f'/{workspace}/api/user-preferences/');assert current['status']==200,current
 snapshot=current['body'];payload={'schema_version':1,'changes':values,'base_revisions':{k:snapshot['field_revisions'].get(k,0)for k in values}}
 changed=await api(page,f'/{workspace}/api/user-preferences/','PATCH',payload);assert changed['status']==200,{'status':changed['status'],'body':changed['body']}
 return {k:snapshot['values'][k]for k in values}
async def page_for(browser,account):
 ctx=await browser.new_context(viewport={'width':1180,'height':820});active_contexts.append(ctx);s=SESSIONS[account]
 await ctx.add_cookies([{'name':s['cookie_name'],'value':s['cookie_value'],'domain':'127.0.0.1','path':'/','httpOnly':True,'secure':False}]);page=await ctx.new_page()
 page.on('pageerror',lambda error:report['errors'].append({'account':account,'stack':error.stack or str(error)}))
 page.on('requestfailed',lambda req:report['network_failures'].append({'account':account,'path':urlparse(req.url).path,'failure':req.failure}))
 page.on('response',lambda reply:report['network_failures'].append({'account':account,'path':urlparse(reply.url).path,'status':reply.status}) if reply.status>=400 else None)
 def request(req):
  if req.method not in ['GET','HEAD','OPTIONS']:
   try:data=req.post_data_json or{}
   except:data={}
   row={'account':account,'method':req.method,'path':urlparse(req.url).path}
   for key in ['action','result','protocol']: 
    if key in data:row[key]=data[key]
   if data.get('timing_key'):row['timing_digest']=hashlib.sha256(str(data['timing_key']).encode()).hexdigest()[:12]
   report['writes'].append(row)
 page.on('request',request);return ctx,page
async def run_case(name,fn):
 if selected and name not in selected:return
 try:report['cases'][name]={'passed':True,'result':await fn()};print('PASS',name,flush=True)
 except Exception as error:report['cases'][name]={'passed':False,'error':str(error),'trace':traceback.format_exc()};print('FAIL',name,str(error),flush=True)
 while active_contexts:
  active=active_contexts.pop()
  try:
   for page in active.pages:
    if await page.locator('.question-return').count():
     await page.locator('.question-return').click(timeout=2000);await page.wait_for_timeout(200)
   await active.close()
  except:pass
 with open(os.path.join(OUT,'browser.json'),'w')as f:json.dump(report,f,ensure_ascii=False,indent=2)
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
  async def favorite_roundtrip():
   ctx,page=await page_for(browser,'2000')
   await page.goto(BASE+'/drill/favorites');await page.locator('.preview-all').click();await ready_preview(page)
   first=await anchor(page);route_debug=await page.evaluate("()=>({actual:location.pathname+location.search,router:document.querySelector('#app').__vue_app__.config.globalProperties.$router.currentRoute.value.fullPath,indexScripts:[...document.scripts].map(x=>x.src).filter(x=>x.includes('/assets/index-'))})");assert route_debug['router'].startswith('/preview') and len(route_debug['indexScripts'])==1,route_debug;assert parse_qs(urlparse(page.url).query).get('entry')or parse_qs(urlparse(page.url).query).get('question'),'origin must locate first item'
   await position(page,238);await page.locator('.preview-scroller').evaluate('(s)=>s.scrollTop+=73');await page.wait_for_timeout(100);saved=await anchor(page)
   clicked=page.locator(f'.preview-row[data-index="{saved["index"]}"] .preview-image-open').first
   await clicked.wait_for();pre_tap=saved;saved=await image_tap(page,saved['index']);assert saved;await ready_question(page);question_url=page.url
   await page.go_back();await ready_preview(page);back=await anchor(page)
   assert back['entry']==saved['entry'] and abs(back['offset']-saved['offset'])<3,{'saved':saved,'back':back}
   saved=await image_tap(page,saved['index']);assert saved;await ready_question(page)
   await page.locator('.question-topbar .next').click();await page.wait_for_timeout(700);next_url=page.url
   assert next_url!=question_url,'next must change entry'
   await page.locator('.question-return').click();await ready_preview(page);returned=await anchor(page)
   assert returned['entry']==saved['entry'] and abs(returned['offset']-saved['offset'])<3,{'saved':saved,'returned':returned}
   await page.reload();await ready_preview(page);refreshed=await anchor(page)
   assert refreshed['entry']==saved['entry'] and abs(refreshed['offset']-saved['offset'])<3,{'saved':saved,'refreshed':refreshed}
   await page.screenshot(path=os.path.join(OUT,'favorite-return.png'));await ctx.close();return{'router_debug':route_debug,'first':first,'pre_tap':pre_tap,'saved':saved,'browser_back':back,'question_next_url':next_url,'question_return':returned,'refresh':refreshed}
  await run_case('favorite_origin_238_browser_back_next_and_refresh',favorite_roundtrip)
  async def history_cursor():
   ctx,page=await page_for(browser,'2000');collection=context('attempts',return_to='/insight')
   await page.goto(preview(collection,'attempt:100'));await ready_preview(page)
   loc=page.locator('.preview-question[data-entry-id="attempt:100"] .preview-open');await loc.click();await ready_question(page)
   await page.wait_for_timeout(6100)
   before_url=page.url;before=await page.locator('.question-timer strong').first.inner_text();start=len(report['writes'])
   await page.locator('.question-topbar .next').click();await page.wait_for_timeout(900)
   after_url=page.url;after=await page.locator('.question-timer strong').first.inner_text();writes=report['writes'][start:]
   a=urlparse(before_url);b=urlparse(after_url)
   assert parse_qs(b.query).get('entry')==['attempt:99'],after_url
   assert a.path==b.path,{'before':before_url,'after':after_url}
   claims=[x for x in writes if '/timing/'in x['path']and x.get('action')in ['claim','pause']]
   assert not claims,claims
   assert '秒后'not in after and 'seconds until'not in after,after
   await page.screenshot(path=os.path.join(OUT,'history-same-question.png'));await page.locator('.question-return').click();await ready_preview(page);await ctx.close()
   return{'before_url':before_url,'after_url':after_url,'timer_before':before,'timer_after':after,'timing_claim_or_pause_between':claims}
  await run_case('history_attempt100_to99_same_uuid_preserves_timer',history_cursor)
  async def ei_prefix():
   ctx,page=await page_for(browser,'2000');await page.goto(BASE+'/ei/practice?q=Fourier');await page.wait_for_selector('.preview-all');count=await page.locator('.question-row').count()
   if not count:
    await page.goto(BASE+'/ei/practice?q=变换');await page.wait_for_selector('.question-row');await page.wait_for_timeout(400)
   query_before=urlparse(page.url).query;await page.locator('.preview-all').click();await ready_preview(page)
   assert '/ei/preview' in page.url,page.url;qs=parse_qs(urlparse(page.url).query);collection=json.loads(qs['list'][0]);assert collection['workspace']=='ei'and collection['query'].get('q'),collection
   await page.locator('.preview-question .preview-open').first.click();await ready_question(page);assert '/ei/practice/'in page.url,page.url
   target=page.url;route_debug=await page.evaluate("()=>({actual:location.pathname+location.search,router:document.querySelector('#app').__vue_app__.config.globalProperties.$router.currentRoute.value.fullPath,indexScripts:[...document.scripts].map(x=>x.src).filter(x=>x.includes('/assets/index-'))})");assert route_debug['router'].startswith('/practice/') and len(route_debug['indexScripts'])==1,route_debug;await page.locator('.question-return').click();await ready_preview(page);assert'/ei/preview'in page.url
   await ctx.close();return{'router_debug':route_debug,'search_query':query_before,'context':collection,'question':target,'returned':page.url if not page.is_closed() else '/ei/preview'}
  await run_case('ei_search_preview_practice_prefix',ei_prefix)
  async def filtered_save():
   ctx,page=await page_for(browser,'50');collection=context('practice',query={'favorite':'1','status':'unattempted','sort':'source'})
   await page.goto(preview(collection));await ready_preview(page)
   original=await set_preferences(page,{'practice.mastered_auto_next':True,'practice.next_mode':'sequential','practice.drill.copy_mode':'off'})
   await page.reload();await ready_preview(page);saved=await anchor(page);count_before=int(await page.locator('#preview-position').get_attribute('max'))
   expected_page=await api(page,'/drill/api/drill/collection-preview/?source=practice&favorite=1&status=unattempted&sort=source&offset=0&limit=50');assert expected_page['status']==200;expected_next=expected_page['body']['results'][1]['question_uuid']
   entry=page.locator(f'.preview-row[data-index="{saved["index"]}"] .preview-open');await entry.click();await ready_question(page);before=page.url
   await page.wait_for_timeout(6000);await page.locator('button.correct.primary-action').click()
   await page.wait_for_timeout(1600);after=page.url
   assert before!=after,{'before':before,'after':after,'error':await page.locator('.error-state').all_text_contents()}
   assert '/drill/practice/'in after and urlparse(after).path.endswith('/'+expected_next),{'actual':after,'expected_next_uuid':expected_next}
   await page.locator('.question-return').click();await ready_preview(page);restored=await anchor(page);count_after=int(await page.locator('#preview-position').get_attribute('max'))
   assert count_after==count_before-1,{'before':count_before,'after':count_after}
   assert restored['index']==saved['index'],{'saved':saved,'restored':restored}
   assert restored['entry']!=saved['entry'],'removed question cannot remain in current unattempted collection'
   notices=await page.locator('.preview-notice').all_text_contents();await page.screenshot(path=os.path.join(OUT,'filtered-save-nearest.png'))
   await set_preferences(page,original);await ctx.close();return{'saved':saved,'restored':restored,'count_before':count_before,'count_after':count_after,'practice_before':before,'practice_after':after,'expected_next_uuid':expected_next,'notices':notices}
  await run_case('filtered_unattempted_save_and_removed_entry_nearest',filtered_save)
  async def themes_rotation_accounts():
   ctx,page=await page_for(browser,'50');await page.goto(preview(context('favorite')));await ready_preview(page)
   original=await set_preferences(page,{'appearance':'light','accent':'blue','font':'compact'})
   samples=[];zoom_smoke=None
   for appearance,accent,font in [('light','blue','compact'),('dark','purple','extra-large'),('system','monochrome','default')]:
    await page.emulate_media(color_scheme='dark'if appearance=='system'else'light')
    await set_preferences(page,{'appearance':appearance,'accent':accent,'font':font});await page.reload();await ready_preview(page);await position(page,12);saved=await anchor(page)
    if zoom_smoke is None:
     button=page.locator('.preview-row[data-index="11"] .preview-row-zoom');await button.click();await page.locator('dialog.fullscreen-reader[open]').wait_for();await page.wait_for_timeout(200);zoom_smoke={'dialog_open':True,'image_overlay_buttons':await page.locator('.preview-asset .preview-zoom').count(),'reader_practice_actions':await page.locator('dialog.fullscreen-reader .reader-practice-actions').count()};await page.locator('dialog.fullscreen-reader .reader-close').click();assert zoom_smoke['image_overlay_buttons']==0
    for width,height in [(390,844),(820,1180),(1180,820)]:
     await page.set_viewport_size({'width':width,'height':height});await page.wait_for_timeout(450);current=await anchor(page)
     visual=await page.evaluate('''()=>({theme:document.documentElement.dataset.theme,appearance:document.documentElement.dataset.appearance,accent:document.documentElement.dataset.accent,font:document.documentElement.dataset.fontSize,scale:getComputedStyle(document.documentElement).getPropertyValue('--ui-font-scale'),background:getComputedStyle(document.body).backgroundColor,htmlWidth:document.documentElement.scrollWidth,viewport:innerWidth})''')
     assert not current['overflow'],current
     assert current['entry']==saved['entry'],{'saved':saved,'current':current}
     samples.append({'requested':{'appearance':appearance,'accent':accent,'font':font},'width':width,'anchor':current,'visual':visual})
     await page.screenshot(path=os.path.join(OUT,f'{appearance}-{accent}-{font}-{width}.png'))
   await set_preferences(page,original)
   count50=int(await page.locator('#preview-position').get_attribute('max'))
   other=SESSIONS['2000'];await ctx.add_cookies([{'name':other['cookie_name'],'value':other['cookie_value'],'domain':'127.0.0.1','path':'/','httpOnly':True,'secure':False}]);await page.reload();await ready_preview(page)
   count2000=int(await page.locator('#preview-position').get_attribute('max'));assert count50==50 and count2000==2000,{'50':count50,'2000':count2000}
   await ctx.close();return{'screenshots':samples,'zoom_smoke':zoom_smoke,'account_count_50':count50,'account_count_2000':count2000}
  await run_case('appearance_font_accent_rotation_and_account_cache',themes_rotation_accounts)
  async def row_zoom():
   ctx,page=await page_for(browser,'50');await page.goto(preview(context('favorite')));await ready_preview(page)
   button=page.locator('.preview-row-zoom').first;await button.click();await page.locator('dialog.fullscreen-reader[open]').wait_for();await page.wait_for_timeout(250)
   result={'image_overlays':await page.locator('.preview-asset .preview-zoom').count(),'dialog_images':await page.locator('dialog.fullscreen-reader img').count(),'reader_practice_actions':await page.locator('dialog.fullscreen-reader .reader-practice-actions').count(),'zoom_triggers':await page.locator('.preview-row-zoom').count(),'question_rows':await page.locator('.preview-question').count()}
   assert result['image_overlays']==0 and result['dialog_images']>0 and result['reader_practice_actions']==0,result
   await page.locator('dialog.fullscreen-reader .reader-close').click();await page.set_viewport_size({'width':390,'height':844});await page.wait_for_timeout(400);await page.screenshot(path=os.path.join(OUT,'final-single-row-zoom-390.png'));await ctx.close();return result
  await run_case('row_zoom_does_not_cover_images',row_zoom)
  await browser.close()
asyncio.run(main())
