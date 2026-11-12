import asyncio,json,zlib,struct,os
from playwright.async_api import async_playwright
html='''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{margin:0;font-family:system-ui;color:#ddd;background:#181818}#app{max-width:1000px;margin:auto}</style></head><body><div id="app"></div><script type="module">
import{createApp,ref,h}from'/static/drill/@fs/work/frontend/node_modules/.vite/deps/vue.js';
import List from'/static/drill/src/components/preview/VirtualPreviewList.vue';
import{createPreviewImagePipeline}from'/static/drill/src/lib/preview/imagePipeline.ts';
const pipeline=createPreviewImagePipeline();window.pipeline=pipeline;
const app=createApp({components:{List},setup(){const list=ref(null);window.list=()=>list.value;window.anchors=[];return{list,pipeline,item:i=>({entry_id:'question:'+i,question_uuid:'uuid-'+i,index:i,label:'测试题 '+i,document:'试题集',topic:'微积分',state:i%2?'mastered':'unattempted',preview:{question_markdown:'',assets:[{id:i,url:'/asset/'+i,width:1000,height:200+(i%7)*150}]}}),anchor:a=>window.anchors.push(a)}},render(){return h(List,{ref:'list',count:10000,version:'v1',revision:0,getItem:this.item,pipeline:this.pipeline,onAnchor:this.anchor})}});app.mount('#app');window.ready=true;
</script></body></html>'''
def png(width,height):
 def chunk(typ,data):return struct.pack('!I',len(data))+typ+data+struct.pack('!I',zlib.crc32(typ+data)&0xffffffff)
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\xf8'*width*3)*height))+chunk(b'IEND',b'')
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
  page=await browser.new_page(viewport={'width':1024,'height':768});errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('console',lambda e: print('CONSOLE',e.type,e.text) if e.type=='error' else None)
  await page.route('**/preview-harness',lambda r:r.fulfill(content_type='text/html',body=html))
  async def image(r):
   n=int(r.request.url.rsplit('/',1)[1]);await r.fulfill(content_type='image/png',body=png(1000,200+(n%7)*150))
  await page.route('**/asset/*',image)
  await page.goto('http://127.0.0.1:5187/static/drill/preview-harness');await page.wait_for_function('window.ready===true');await page.wait_for_timeout(1200)
  results=[]
  for index in [0,100,5000,9999,7000,50,1]:
   await page.evaluate('(n)=>window.list().scrollToIndex(n)',index);await page.wait_for_timeout(500)
   data=await page.evaluate('''()=>({anchor:window.list().captureAnchor(),mounted:document.querySelectorAll('.preview-row').length,scroll:document.querySelector('.preview-scroller').scrollTop,stats:window.pipeline.stats(),overflow:document.body.scrollWidth>innerWidth})''');results.append(data)
  anchor=await page.evaluate('window.list().captureAnchor()')
  await page.evaluate('window.list().scrollToIndex(7000)');await page.wait_for_timeout(300)
  await page.evaluate('(a)=>window.list().restoreAnchor(a)',anchor);await page.wait_for_timeout(300)
  restored=await page.evaluate('window.list().captureAnchor()')
  await page.set_viewport_size({'width':390,'height':844});await page.wait_for_timeout(600)
  portrait=await page.evaluate('({anchor:window.list().captureAnchor(),mounted:document.querySelectorAll(".preview-row").length,width:document.body.scrollWidth,viewport:innerWidth,stats:window.pipeline.stats()})')
  await page.screenshot(path=os.path.join(os.path.dirname(__file__),'synthetic-mobile.png'))
  report={'kind':'synthetic 10000 dynamic PNGs / isolated virtual list, NOT actual corpus performance','samples':results,'saved':anchor,'restored':restored,'portrait':portrait,'errors':errors}
  with open(os.path.join(os.path.dirname(__file__),'synthetic-window.json'),'w')as f:json.dump(report,f,ensure_ascii=False,indent=2)
  print(json.dumps(report,ensure_ascii=False,indent=2))
  await browser.close()
asyncio.run(main())
