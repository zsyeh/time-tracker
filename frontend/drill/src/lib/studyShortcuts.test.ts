// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { installStudyShortcuts } from './studyShortcuts'
let remove:(()=>void)|undefined
function key(value:string, target:HTMLElement=document.body,extra:KeyboardEventInit={}) { const e=new KeyboardEvent('keydown',{key:value,bubbles:true,cancelable:true,...extra});target.dispatchEvent(e);return e }
afterEach(()=>{remove?.();document.body.innerHTML=''})
it('maps the ten requested keyboard commands',()=>{
 const actions=Object.fromEntries(['previous','next','favorite','review','mastered','preview','undo','answer','fullscreen','exit'].map(k=>[k,vi.fn()]))
 remove=installStudyShortcuts(actions)
 for(const value of ['ArrowLeft','ArrowRight','f','n','m','q','u','a','p','x']) expect(key(value).defaultPrevented).toBe(true)
 for(const fn of Object.values(actions)) expect(fn).toHaveBeenCalledTimes(1)
})
it('does not hijack typing, IME or native browser shortcuts',()=>{
 const next=vi.fn();remove=installStudyShortcuts({next})
 for(const tag of ['textarea','input','select']) {const e=document.createElement(tag);document.body.append(e);key('ArrowRight',e)}
 const edit=document.createElement('div');edit.contentEditable='true';edit.setAttribute('contenteditable','true');document.body.append(edit);key('ArrowRight',edit)
 for(const extra of [{ctrlKey:true},{altKey:true},{metaKey:true},{isComposing:true},{repeat:true},{shiftKey:true}]) key('ArrowRight',document.body,extra)
 expect(next).not.toHaveBeenCalled()
})
it('blocks confirmation dialogs while keeping reader shortcuts active',()=>{
 const exit=vi.fn();remove=installStudyShortcuts({exit})
 const dialog=document.createElement('dialog');dialog.setAttribute('open','');document.body.append(dialog);key('x');expect(exit).not.toHaveBeenCalled()
 dialog.className='fullscreen-reader';key('x');expect(exit).toHaveBeenCalledTimes(1)
})
it('unregisters on leaving the page and ignores already handled events',()=>{
 const favorite=vi.fn();remove=installStudyShortcuts({favorite})
 const event=new KeyboardEvent('keydown',{key:'f',bubbles:true,cancelable:true});event.preventDefault();document.body.dispatchEvent(event)
 remove();key('f');expect(favorite).not.toHaveBeenCalled()
})

it('only flashes accepted commands and never lets feedback interrupt the action',()=>{
 const favorite=vi.fn(),feedback=vi.fn(()=>{throw new Error('animation unavailable')})
 remove=installStudyShortcuts({favorite},{feedback})
 const input=document.createElement('input');document.body.append(input);key('f',input)
 expect(feedback).not.toHaveBeenCalled()
 expect(()=>key('f')).not.toThrow()
 expect(favorite).toHaveBeenCalledOnce();expect(feedback).toHaveBeenCalledWith('favorite')
})
