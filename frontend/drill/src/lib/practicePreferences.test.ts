// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import type { PreferenceSnapshot } from '../../../shared/preferences/schema'
let cleanup:(()=>void)|undefined
async function setup(){const {accountPreferences:store}=await import('../../../shared/preferences/store');const {preferenceDefaults}=await import('../../../shared/preferences/schema');const snapshot:PreferenceSnapshot={schema_version:1,revision:0,values:preferenceDefaults(),field_revisions:{}};await store.bind('test-account',snapshot);cleanup=()=>{store.reset(true);store.dispose()};return store}
afterEach(()=>{cleanup?.();localStorage.clear();vi.restoreAllMocks();vi.resetModules()})
it('shares server-backed live preferences between Settings and Question routes',async()=>{
 const store=await setup();const {usePracticePreferences}=await import('./practicePreferences');const question=usePracticePreferences('drill'),settings=usePracticePreferences('drill');expect(settings).toBe(question)
 expect(question.nextMode.value).toBe('sequential');expect(question.masteredAutoNext.value).toBe(true);expect(question.reviewAutoNext.value).toBe(false)
 settings.reviewAutoNext.value=true;settings.nextMode.value='unattempted';expect(question.reviewAutoNext.value).toBe(true);expect(store.values['practice.next_mode']).toBe('unattempted');expect(store.pendingCount.value).toBe(2)
})
it('isolates workspace copying and requires explicit import of unowned legacy preferences',async()=>{
 localStorage.setItem('drill.next-mode.v1','review');localStorage.setItem('ei.page-turn-copy.v1','image');const store=await setup();const {usePracticePreferences}=await import('./practicePreferences');const {readLegacyPreferences}=await import('../../../shared/preferences/legacy');const drill=usePracticePreferences('drill'),ei=usePracticePreferences('ei');expect(ei.nextMode.value).toBe('sequential');expect(ei.pageTurnCopyMode.value).toBe('off');expect(readLegacyPreferences()).toMatchObject({'practice.next_mode':'review','practice.ei.copy_mode':'image'})
 drill.pageTurnCopyMode.value='link';ei.pageTurnCopyMode.value='image';ei.reviewAutoNext.value=true;expect(store.values['practice.drill.copy_mode']).toBe('link');expect(store.values['practice.ei.copy_mode']).toBe('image');expect(drill.reviewAutoNext.value).toBe(true)
})
it('keeps core preferences usable when browser storage is denied',async()=>{
 vi.spyOn(Storage.prototype,'getItem').mockImplementation(()=>{throw Error('denied')});vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw Error('denied')});await setup();const {usePracticePreferences}=await import('./practicePreferences');const prefs=usePracticePreferences('ei');expect(()=>{prefs.pageTurnCopyMode.value='image';prefs.masteredAutoNext.value=false}).not.toThrow();expect(prefs.pageTurnCopyMode.value).toBe('image')
})
it('shares the account saved copy scale across Drill and EI',async()=>{
 const store=await setup();const {usePracticePreferences}=await import('./practicePreferences');const drill=usePracticePreferences('drill'),ei=usePracticePreferences('ei')
 expect(drill.imageCopyScale.value).toBe(1);drill.imageCopyScale.value=3.5
 expect(ei.imageCopyScale.value).toBe(3.5);expect(store.values['practice.image_copy_scale']).toBe(3.5)
})
