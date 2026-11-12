"""Settings regression against local builds. Every API response is synthetic.

Start frontend/e2e/fixture_server.py with the chosen UI_REBUILD_FIXTURE_ROOT and
--port, then run this script. No request may reach a non-local host. URI strings
below deliberately use example.invalid and contain no real capability token.
"""
import argparse
import asyncio
import hashlib
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import async_playwright


TOKEN = dict(id=1, name='Synthetic capability for iPad study and interruption automation',
             subject='Mathematics', usage_count=14, max_uses=None,
             available_from='06:00:00', available_until='22:00:00',
             within_schedule=True, credential_valid=True, is_paused=False,
             usable=True, is_active=True, has_disturbance_uri=True,
             source_label='Synthetic fixture', notes='', expires_at=None)
URI = 'https://example.invalid/api/launch/SYNTHETIC-NOT-A-SECRET-' + 'long-test-text-' * 30 + '/start'
VALUES = dict(homepage_content='Synthetic editable draft', study_room_code='', tracking_start_date='2026-05-23',
              exam_date='2026-12-19', countdown_label='Study goal')
SIDEBAR_IDS = {
    'timer': ['today', 'trends', 'sessions', 'issues', 'subject-math', 'subject-english', 'subject-major', 'subject-training'],
    'drill': ['selected-heatmap', 'insight', 'progress', 'practice', 'diagnostics', 'activity', 'book-activity',
              'heatmap', 'papers', 'favorites', 'review-later', 'feel', 'errata'],
    'ei': ['core-heatmap', 'insight', 'progress', 'cockpit', 'practice', 'diagnostics', 'circuit-selected',
           'signal-selected', 'signal-formulas', 'analog-selected', 'digital-selected', 'communication-selected',
           'selected-pdf-pages', 'activity', 'book-activity', 'heatmap', 'papers', 'favorites', 'review-later', 'feel', 'errata'],
}


def preferences_fixture():
    values = {'appearance': 'system', 'accent': 'blue', 'font': 'small', 'language': 'en',
              'practice.next_mode': 'sequential', 'practice.review_auto_next': False,
              'practice.mastered_auto_next': True, 'practice.drill.copy_mode': 'off',
              'practice.ei.copy_mode': 'off', 'filters.drill': [], 'filters.ei': [], 'progress.drill': {'target': 24, 'deadline': '2026-11-21'}, 'progress.ei': {'target': 11, 'deadline': '2026-11-21'}}
    for workspace, ids in SIDEBAR_IDS.items():
        values['sidebar.' + workspace] = {'order': list(ids), 'hidden': ids[3 if workspace == 'drill' else 4:],
                                          'collapsed_groups': []}
    return {'schema_version': 1, 'revision': 0, 'values': values,
            'field_revisions': dict.fromkeys(values, 0)}


MEASURE = """() => {
 const rect = e => {if(!e)return null;let r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}};
 const visible = e => !!(e.offsetWidth||e.offsetHeight||e.getClientRects().length);
 return {scrollY,overflow:document.documentElement.scrollWidth>innerWidth,
  visiblePanels:[...document.querySelectorAll('.settings-content > section,.settings-content > article')].filter(visible).map(e=>e.id),
  content:rect(document.querySelector('.settings-content')), panel:rect(document.querySelector('#shortcuts')),
  title:rect(document.querySelector('.capability-row > div:first-child')),
  actions:[...document.querySelectorAll('.capability-actions button')].filter(visible).map(rect),
  accountVisible:visible(document.querySelector('.account-settings')),
  appearanceVisible:visible(document.querySelector('.appearance-settings')),
  uri:[...document.querySelectorAll('.reveal-url')].filter(visible).map(e=>({box:rect(e),overflow:e.scrollWidth>e.clientWidth}))};
}"""


async def run(args):
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    result = {'synthetic': True, 'build_sha256': hashlib.sha256(Path(args.build, 'index.html').read_bytes()).hexdigest(), 'cases': []}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox'])
        for scheme in ('light', 'dark'):
            for width, height in ((390, 844), (820, 1180), (1180, 820), (1440, 960)):
                context = await browser.new_context(viewport={'width': width, 'height': height}, color_scheme=scheme, has_touch=True)
                page = await context.new_page(); errors = []; writes = []
                preferences = preferences_fixture()
                page.on('pageerror', lambda error: errors.append(str(error)))

                async def route(request_route):
                    request = request_route.request
                    path = urlsplit(request.url).path
                    if urlsplit(request.url).hostname not in ('localhost', '127.0.0.1'):
                        await request_route.abort(); return
                    if path == '/settings' or path.startswith('/static/app/'):
                        file = Path(args.build, 'index.html' if path == '/settings' else path.removeprefix('/static/app/'))
                        if file.is_file():
                            await request_route.fulfill(body=file.read_bytes(), content_type=mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
                        else:
                            await request_route.abort()
                        return
                    data = None
                    if path == '/api/auth/session/':
                        data = {'authenticated': True, 'user': {'id': 1, 'username': 'synthetic-auditor', 'is_staff': True, 'is_superuser': True},
                                'preferences': preferences}
                    elif path == '/api/launch-tokens/': data = [TOKEN]
                    elif path == '/api/launch-tokens/1/regenerate/':
                        writes.append('synthetic-regenerate')
                        data = {**TOKEN, 'raw_token': 'SYNTHETIC', 'shortcut_start_url': URI,
                                'launch_url': URI, 'disturbance_url': URI, 'shortcuts_create_url': 'shortcuts://create-shortcut'}
                    elif path == '/api/settings/runtime/': data = {'values': VALUES, 'defaults': VALUES, 'local_env_exists': True}
                    elif path == '/api/settings/data-encryption/': data = {'enabled': False, 'algorithm': 'AES-256-GCM', 'available': True}
                    elif path in ('/api/task-presets/', '/api/study-tags/', '/api/invite-codes/'): data = []
                    elif path == '/api/user-preferences/':
                        if request.method != 'GET':
                            await request_route.abort(); return
                        data = preferences
                    if data is not None: await request_route.fulfill(json=data)
                    elif '/api/' in path and request.method not in ('GET', 'HEAD'):
                        # Only synthetic recovery acknowledgements are allowed.
                        if path.endswith('/learning/recovery/'):
                            await request_route.fulfill(json={'version': 1, 'last_workspace': 'timer', 'locations': {}})
                        else: await request_route.abort()
                    else: await request_route.continue_()

                await page.route('**/*', route)
                await page.goto(f'http://127.0.0.1:{args.port}/settings', wait_until='networkidle')
                await page.locator('.settings-content').wait_for()
                if width < 960:
                    await page.locator('.settings-mobile-section select').select_option('shortcuts')
                else:
                    await page.locator('.settings-index a[href="?section=shortcuts"]').click()
                await page.wait_for_timeout(100)
                navigation = await page.evaluate(MEASURE)
                # For the old scrolling page inspect the actual row as well as
                # the failed section-navigation position recorded above.
                await page.locator('.capability-row').scroll_into_view_if_needed()
                layout = await page.evaluate(MEASURE)
                await page.screenshot(path=str(out / f'shortcuts-{scheme}-{width}.png'), full_page=False)
                await page.get_by_role('button', name='New start URI', exact=True).click()
                await page.locator('.reveal-url').first.wait_for()
                # Element Plus mounts before its enter transition is painted.
                # A visible DOM box alone is insufficient screenshot evidence.
                await page.wait_for_timeout(400)
                dialog = await page.evaluate(MEASURE)
                await page.screenshot(path=str(out / f'synthetic-uri-{scheme}-{width}.png'), full_page=False)
                case = {'scheme': scheme, 'width': width, 'navigation': navigation, 'layout': layout,
                        'dialog': dialog, 'errors': errors, 'synthetic_writes': writes}
                if not args.baseline:
                    case['pass'] = (not errors and not layout['overflow'] and not dialog['overflow']
                        and navigation['visiblePanels'] == ['shortcuts']
                        and not navigation['accountVisible'] and not navigation['appearanceVisible']
                        and navigation['panel']['y'] < 300 and layout['title']['width'] >= 180
                        and len(dialog['uri']) == 3 and all(not item['overflow'] for item in dialog['uri'])
                        and all(item['right'] <= width + 1 for item in layout['actions']))
                result['cases'].append(case)
                await context.close()
        await browser.close()
    result['pass'] = None if args.baseline else all(case['pass'] for case in result['cases'])
    (out / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({'pass': result['pass'], 'cases': [{'scheme': case['scheme'], 'width': case['width'],
        'title_width': case['layout']['title']['width'], 'navigation_y': case['navigation']['panel']['y'],
        'overflow': case['layout']['overflow'], 'pass': case.get('pass'), 'errors': case['errors']} for case in result['cases']]}, indent=2))
    if result['pass'] is False: raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--build', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--baseline', action='store_true')
    asyncio.run(run(parser.parse_args()))
