// @vitest-environment jsdom
import {beforeEach,expect,it,vi} from 'vitest'
import {accents,accentIds,colorVariables} from './palette'
import {applyVisualPreferences,parseVisual,readVisualPreferences,resolveScheme,VISUAL_COOKIE,VISUAL_KEY} from './resolve'
beforeEach(()=>{localStorage.clear();document.cookie.split(';').forEach(item=>document.cookie=`${item.split('=')[0].trim()}=; Max-Age=0; Path=/`);document.documentElement.removeAttribute('style');vi.stubGlobal('matchMedia',()=>({matches:true}))})
it('follows System only when no explicit legacy or versioned choice exists',()=>{
 expect(readVisualPreferences()).toEqual({version:1,appearance:'system',accent:'blue'})
 localStorage.setItem('learning-os-color-scheme','light');localStorage.setItem('learning-os-theme','meituan')
 expect(readVisualPreferences()).toEqual({version:1,appearance:'light',accent:'yellow'})
 localStorage.setItem(VISUAL_KEY,JSON.stringify({version:1,appearance:'system',accent:'monochrome'}))
 expect(readVisualPreferences().accent).toBe('monochrome')
 document.cookie=`${VISUAL_COOKIE}=${encodeURIComponent(JSON.stringify({version:1,appearance:'dark',accent:'cyan'}))}; Path=/`
 expect(readVisualPreferences().accent).toBe('cyan')
 expect(resolveScheme('system',true)).toBe('dark');expect(resolveScheme('light',true)).toBe('light')
})
it('rejects corrupt or unknown settings and safely handles unavailable storage',()=>{
 expect(parseVisual('{bad')).toBeNull();expect(parseVisual('{"version":1,"appearance":"dark","accent":"red"}')).toBeNull()
 vi.spyOn(Storage.prototype,'getItem').mockImplementation(()=>{throw new Error('blocked')})
 expect(readVisualPreferences()).toEqual({version:1,appearance:'system',accent:'blue'});vi.restoreAllMocks()
})
it('separates resolved appearance, accent and neutral browser theme',()=>{
 applyVisualPreferences({version:1,appearance:'system',accent:'purple'})
 expect(document.documentElement.dataset.colorScheme).toBe('dark');expect(document.documentElement.style.getPropertyValue('--accent-solid')).toBe(accents.purple.dark.solid)
 applyVisualPreferences({version:1,appearance:'light',accent:'yellow'})
 expect(document.documentElement.dataset.colorScheme).toBe('light');expect(document.documentElement.style.getPropertyValue('--surface-page')).toBe('')
})
function luminance(hex:string){const c=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return c[0]*.2126+c[1]*.7152+c[2]*.0722}
function contrast(a:string,b:string){const x=luminance(a),y=luminance(b);return(Math.max(x,y)+.05)/(Math.min(x,y)+.05)}
for(const id of accentIds)for(const scheme of ['light','dark']as const)it(`${id}/${scheme} maintains readable button, link and selected text`,()=>{
 const c=accents[id][scheme],bg=scheme==='light'?'#ffffff':'#141414',selected=scheme==='light'?'#e5e5e5':'#333333'
 expect(contrast(c.solid,c.onSolid)).toBeGreaterThanOrEqual(4.5);expect(contrast(colorVariables(id,scheme)['--accent-solid-hover'],c.onSolid)).toBeGreaterThanOrEqual(4.5);expect(contrast(colorVariables(id,scheme)['--accent-solid-pressed'],c.onSolid)).toBeGreaterThanOrEqual(4.5);expect(contrast(c.ink,bg)).toBeGreaterThanOrEqual(4.5);expect(contrast(c.ink,selected)).toBeGreaterThanOrEqual(4.5)
 expect(Object.keys(colorVariables(id,scheme)).some(k=>k.startsWith('--surface'))).toBe(false)
})
