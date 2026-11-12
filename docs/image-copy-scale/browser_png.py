import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
async def main():
 report={'engines':[],'real_png_decode':True,'clipboard_os_tested':False}
 async with async_playwright() as p:
  for name in ['chromium','webkit']:
   browser=await p.webkit.launch(headless=True) if name=='webkit' else await p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
   page=await browser.new_page();await page.goto('http://127.0.0.1:8031/static/app/@vite/client')
   result=await page.evaluate('''async()=>{
    const {buildClipboardPng,copyImagesToClipboard}=await import('/static/app/drill/src/lib/imageClipboard.ts')
    const c=document.createElement('canvas');c.width=320;c.height=180
    const ctx=c.getContext('2d');ctx.fillStyle='white';ctx.fillRect(0,0,320,180);ctx.fillStyle='black';ctx.font='24px sans-serif';ctx.fillText('Copy scale test',12,80)
    const source=await new Promise(r=>c.toBlob(r,'image/png')),url=URL.createObjectURL(source),rows=[]
    async function dimensions(blob){const u=URL.createObjectURL(blob);try{const img=new Image();img.src=u;await img.decode();return[img.naturalWidth,img.naturalHeight]}finally{URL.revokeObjectURL(u)}}
    for(const scale of [1,2,3,4,1.5]){const out=await buildClipboardPng([url],scale),size=await dimensions(out.blob);if(size[0]!==320*scale||size[1]!==180*scale)throw Error(JSON.stringify(size));rows.push({scale,width:size[0],height:size[1],limited:out.limited})}
    const stacked=await buildClipboardPng([url,url],3);const size=await dimensions(stacked.blob);if(size[0]!==960||size[1]!==1080)throw Error('Stack dimensions wrong')
    URL.revokeObjectURL(url);return{rows,stacked:size}
   }''')
   report['engines'].append({'engine':name,'pass':True,**result});await browser.close()
 Path('/home/eh/learning-os-round2-evidence/image-scale-browser-png.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
asyncio.run(main())
