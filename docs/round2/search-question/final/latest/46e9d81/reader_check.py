import argparse,asyncio,json,inspect,importlib.util
from pathlib import Path
from playwright.async_api import async_playwright
repo=Path('/home/eh/learning-os-round2')
spec=importlib.util.spec_from_file_location('review',repo/'docs/uiux-rebuild-implementation/review/browser_review.py');review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)
# Reuse every original interaction and assertion; configure only its fixture URL.
source=inspect.getsource(review.question).replace('http://127.0.0.1:8008/','http://127.0.0.1:8023/')
exec(compile(source,str(repo/'docs/uiux-rebuild-implementation/review/browser_review.py'),'exec'),review.__dict__)
async def run(args):
 out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
 async with async_playwright() as p:
  browser=await p.webkit.launch(headless=True) if args.engine=='webkit' else await p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
  result=await review.question(browser,out);result.update(engine=args.engine,browser_version=browser.version,fixture='http://127.0.0.1:8023',reuse='Original review.question interactions and pass conditions; only fixture URL configured')
  await browser.close()
 (out/'reader-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
 if not result['pass']:raise SystemExit(1)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--engine',choices=['chromium','webkit'],required=True);ap.add_argument('--output',required=True);asyncio.run(run(ap.parse_args()))
