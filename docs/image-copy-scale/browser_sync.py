import asyncio,json,time,os
from pathlib import Path
from playwright.async_api import async_playwright
BASE='http://127.0.0.1:8027'
OUT=Path('/home/eh/learning-os-round2-evidence/sync-browser-'+os.environ.get('ROUND2_ENGINE','chromium'));OUT.mkdir(exist_ok=True)
users=json.loads(Path('/home/eh/learning-os-round2-private/sync-users.json').read_text())
async def main():
 async with async_playwright() as p:
  browser=await p.webkit.launch(headless=True) if os.environ.get('ROUND2_ENGINE')=='webkit' else await p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
  contexts=[];report={'real_postgres_http':True,'cases':[]}
  for user,size in [(users[0],(820,1180)),(users[0],(1180,820)),(users[1],(390,844))]:
   c=await browser.new_context(viewport={'width':size[0],'height':size[1]},has_touch=True,color_scheme='light');contexts.append(c)
   await c.add_cookies([{'name':user['cookie'],'value':user['session'],'url':BASE}])
  async def prefix(route):
   response=await route.fetch(url=route.request.url.replace('/drill/api/','/api/').replace('/ei/api/','/api/'));await route.fulfill(response=response)
  for c in contexts:
   await c.route('**/drill/api/**',prefix)
   await c.route('**/ei/api/**',prefix)
  pages=[await c.new_page() for c in contexts];errors=[]
  for page in pages:page.on('pageerror',lambda e:errors.append(str(e)))
  a,b,other=pages
  for page in pages:
   print('open',flush=True)
   await page.goto(BASE+'/drill/settings',wait_until='networkidle');await page.locator('.font-size-setting').wait_for()
  await a.locator('.appearance-selector button').click();await a.get_by_text('深色 · Dark',exact=True).click();await a.wait_for_timeout(900)
  assert (await (await a.request.get(BASE+'/api/user-preferences/')).json())['values']['appearance']=='dark'
  await b.evaluate("window.dispatchEvent(new Event('focus'))");await b.wait_for_timeout(400)
  assert await b.evaluate('document.documentElement.dataset.colorScheme')=='dark'
  assert await other.evaluate('document.documentElement.dataset.colorScheme')=='light'
  await b.get_by_label('全局字体大小',exact=True).select_option('compact');await b.wait_for_timeout(900)
  await a.evaluate("window.dispatchEvent(new Event('focus'))");await a.wait_for_timeout(300)
  assert await a.evaluate('document.documentElement.dataset.fontSize')=='compact'
  # Newly opened/restarted context renders server state before app modules.
  fresh=await browser.new_context(viewport={'width':430,'height':932},color_scheme='light');contexts.append(fresh)
  await fresh.add_cookies([{'name':users[0]['cookie'],'value':users[0]['session'],'url':BASE}]);first=await fresh.new_page()
  await first.route('**/static/drill/assets/index-*.js',lambda route:route.abort())
  await first.goto(BASE+'/drill/settings',wait_until='networkidle')
  assert await first.evaluate('document.documentElement.dataset.colorScheme')=='dark'
  assert await first.evaluate('document.documentElement.dataset.fontSize')=='compact'
  report['cases'].append({'case':'account-isolation-cross-device-and-first-paint','pass':True})
  # Workspace preset including collection scope survives real server storage.
  await a.goto(BASE+'/drill/practice?q=导数&status=review',wait_until='networkidle');await a.get_by_role('button',name='筛选预设',exact=False).click()
  await a.get_by_label('筛选预设名称').fill('Synthetic derivative review');await a.get_by_role('button',name='保存当前筛选',exact=True).click();await a.wait_for_timeout(900)
  saved=(await (await a.request.get(BASE+'/api/user-preferences/')).json())['values']['filters.drill'];assert saved[0]['query']=={'q':'导数','status':'review'},saved
  await b.goto(BASE+'/drill/practice',wait_until='networkidle');await b.get_by_role('button',name='筛选预设',exact=False).click();await b.get_by_role('button',name='Synthetic derivative review',exact=True).click();await b.wait_for_timeout(350);assert 'status=review' in b.url and 'q=' in b.url
  report['cases'].append({'case':'saved-filter-real-server-roundtrip','pass':True})
  await a.goto(BASE+'/drill/settings',wait_until='networkidle')
  # Show and move Practice into pinned navigation through touch-sized buttons.
  item=a.locator('.sidebar-customization li').filter(has_text='Practice 题库')
  if not await item.count():item=a.locator('.sidebar-customization li').filter(has_text='Question bank')
  await item.locator('input[type=checkbox]').check();await item.get_by_role('button',name='上移',exact=False).click();await a.wait_for_timeout(900)
  await b.goto(BASE+'/drill/settings',wait_until='networkidle');check=b.locator('.sidebar-customization li').filter(has_text='Question bank')
  assert await check.locator('input[type=checkbox]').is_checked()
  value=(await (await a.request.get(BASE+'/api/user-preferences/')).json())['values']['sidebar.drill'];assert value['order'][2]=='practice' and 'practice' not in value['hidden'],value
  report['cases'].append({'case':'sidebar-pin-and-order-cross-device','pass':True})
  # Daily workload target and deadline are account preferences, not device state.
  await a.goto(BASE+'/drill/progress',wait_until='networkidle')
  await a.locator('.trend-controls input[type=number]').fill('37')
  await a.locator('.trend-controls input[type=number]').press('Tab')
  await a.locator('.deadline-control input').fill('2026-12-05')
  await a.locator('.deadline-control input').press('Tab')
  await a.wait_for_timeout(1200)
  assert (await (await a.request.get(BASE+'/api/user-preferences/')).json())['values']['progress.drill']=={'target':37,'deadline':'2026-12-05'}
  await b.goto(BASE+'/drill/progress',wait_until='networkidle')
  assert await b.locator('.trend-controls input[type=number]').input_value()=='37'
  assert await b.locator('.deadline-control input').input_value()=='2026-12-05'
  assert (await (await other.request.get(BASE+'/api/user-preferences/')).json())['values']['progress.drill']=={'target':24,'deadline':'2026-11-21'}
  await a.screenshot(path=str(OUT/'progress-account-goal.png'),full_page=False)
  report['cases'].append({'case':'daily-goal-and-deadline-real-server-two-device-roundtrip','pass':True})
  await a.goto(BASE+'/drill/settings',wait_until='networkidle')
  # Copy multiplier is account-owned and shared by both learning workspaces.
  await a.get_by_label('Image copy scale',exact=True).select_option('custom')
  await a.get_by_label('Custom image copy scale',exact=True).fill('3.5')
  await a.get_by_role('button',name='Save scale',exact=True).click();await a.wait_for_timeout(900)
  assert (await (await a.request.get(BASE+'/api/user-preferences/')).json())['values']['practice.image_copy_scale']==3.5
  await b.goto(BASE+'/ei/settings',wait_until='networkidle')
  assert await b.get_by_label('Custom image copy scale',exact=True).input_value()=='3.5'
  assert (await (await other.request.get(BASE+'/api/user-preferences/')).json())['values']['practice.image_copy_scale']==1
  for width in [375,820,1180]:
   await a.set_viewport_size({'width':width,'height':844})
   await a.get_by_label('Custom image copy scale',exact=True).scroll_into_view_if_needed()
   assert not await a.evaluate('document.documentElement.scrollWidth>innerWidth')
   await a.screenshot(path=str(OUT/f'copy-scale-{width}.png'))
  report['cases'].append({'case':'copy-custom-scale-drill-ei-cross-device-account-isolation','pass':True})
  # Offline optimistic edit, restart/cache survives, online retries.
  await contexts[0].set_offline(True);await a.get_by_label('全局字体大小',exact=True).select_option('large');await a.wait_for_timeout(1000)
  assert await a.evaluate('document.documentElement.dataset.fontSize')=='large'
  assert await a.locator('.preference-sync-status').inner_text()
  await contexts[0].set_offline(False);await a.evaluate("window.dispatchEvent(new Event('online'))");await a.wait_for_timeout(1000)
  assert (await (await a.request.get(BASE+'/api/user-preferences/')).json())['values']['font']=='large'
  report['cases'].append({'case':'offline-edit-online-resume','pass':True})
  # All font choices, mobile width changes: no document overflow, inputs>=16px.
  for width,height in [(375,812),(390,844),(430,932),(820,1180),(1180,820),(1440,960),(820,1180)]:
   await a.set_viewport_size({'width':width,'height':height})
   for font in ['compact','small','default','large','extra-large']:
    await a.get_by_label('全局字体大小',exact=True).select_option(font);await a.wait_for_timeout(50)
    assert not await a.evaluate('document.documentElement.scrollWidth>innerWidth'),(width,font)
    assert float(await a.locator('.font-size-setting select').evaluate('(e)=>parseFloat(getComputedStyle(e).fontSize)'))>=16,(width,font,'Safari input floor')
   await a.screenshot(path=str(OUT/f'settings-{width}.png'),full_page=False)
  report['cases'].append({'case':'seven-viewports-rotation-five-fonts','pass':True})
  assert not errors,errors
  report['errors']=errors;report['pass']=True;(OUT/'results.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
  for c in contexts:await c.close()
  await browser.close()
asyncio.run(main())
