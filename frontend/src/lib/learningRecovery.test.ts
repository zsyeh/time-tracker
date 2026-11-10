// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'
let stop: (()=>void) | undefined
let replace: ReturnType<typeof vi.fn>
let state: { version: number; last_workspace: string | null; locations: Record<string,{path:string;scroll:Record<string,number>}> }
let puts: unknown[]
function request<T>(_url:string,opts?:RequestInit):Promise<T> {
  if (opts?.method==='PUT') {
    const body=JSON.parse(String(opts.body));puts.push(body)
    state={version:state.version+1,last_workspace:body.workspace,locations:{...state.locations,[body.workspace]:body.location}}
  }
  return Promise.resolve(structuredClone(state) as T)
}
async function setup(marker=false, standalone=true) {
  replace=vi.fn()
  vi.stubGlobal('location',{href:`https://47.95.10.128/${marker?'?pwa_launch=1':''}`,pathname:'/',origin:'https://47.95.10.128',hostname:'47.95.10.128',replace})
  vi.stubGlobal('matchMedia',vi.fn(()=>({matches:standalone})))
  vi.stubGlobal('ResizeObserver',class {observe(){} disconnect(){}})
  vi.stubGlobal('scrollTo',vi.fn())
  vi.spyOn(document,'visibilityState','get').mockReturnValue('visible')
  const module=await import('../../shared/learningRecovery')
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',name:'home',component:{template:'<p>home</p>'}},{path:'/today',component:{template:'<p>today</p>'}}]})
  await router.push(marker?'/?pwa_launch=1':'/')
  return {module,router}
}
beforeEach(()=>{vi.resetModules();localStorage.clear();sessionStorage.clear();puts=[];state={version:0,last_workspace:'ei',locations:{ei:{path:'/ei/practice',scroll:{right:123}}}};document.body.innerHTML='<div id="app"></div>'})
afterEach(()=>{stop?.();stop=undefined;vi.restoreAllMocks();vi.unstubAllGlobals()})
it('restores only a marked standalone cold launch',async()=>{
  const {module,router}=await setup(true)
  stop=await module.startLearningRecovery(1,'timer',router,request)
  expect(replace).toHaveBeenCalledWith('/ei/practice')
  expect(router.currentRoute.value.fullPath).toBe('/')
})
it('Home and ordinary refresh do not redirect to another workspace',async()=>{
  const {module,router}=await setup(false)
  stop=await module.startLearningRecovery(1,'timer',router,request)
  expect(replace).not.toHaveBeenCalled()
  await router.push('/today');await router.push('/')
  expect(replace).not.toHaveBeenCalled()
})
it('normal Safari does not auto-restore even if it opens the launch marker',async()=>{
  const {module,router}=await setup(true,false)
  stop=await module.startLearningRecovery(1,'timer',router,request)
  expect(replace).not.toHaveBeenCalled()
})
it('does not revive deleted questions or loop through authentication URLs',async()=>{
  const {module,router}=await setup(true)
  state.locations.ei!.path='/ei/practice/123e4567-e89b-12d3-a456-426614174000'
  vi.stubGlobal('fetch',vi.fn(async()=>({ok:false,status:404})))
  stop=await module.startLearningRecovery(1,'timer',router,request)
  expect(replace).not.toHaveBeenCalled()
  expect(module.safeResumePath('/accounts/login/')).toBe(false)
  expect(module.safeResumePath('//evil.test')).toBe(false)
  expect(module.safeResumePath('/?token=private')).toBe(false)
})
it('a different account does not read the previous account local position',async()=>{
  const {module,router}=await setup(true)
  localStorage.setItem('learning.locations.v2.1',JSON.stringify({...state,dirty:true}))
  state={version:0,last_workspace:null,locations:{}}
  stop=await module.startLearningRecovery(2,'timer',router,request)
  expect(replace).not.toHaveBeenCalled()
})

it('marks a quickly revisited workspace without overwriting its pending scroll restore',async()=>{
  const {module,router}=await setup(false)
  vi.spyOn(document,'hasFocus').mockReturnValue(true)
  router.addRoute({path:'/practice',component:{template:'<p>practice</p>'}})
  await router.push('/practice')
  state={version:2,last_workspace:'timer',locations:{drill:{path:'/drill/practice',scroll:{right:123}},timer:{path:'/',scroll:{}}}}
  stop=await module.startLearningRecovery(1,'drill',router,request)
  for(let i=0;i<5;i++)await Promise.resolve()
  expect(puts).toContainEqual(expect.objectContaining({workspace:'drill',location:expect.objectContaining({path:'/drill/practice',scroll:{right:123}})}))
})
