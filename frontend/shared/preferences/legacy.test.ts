// @vitest-environment jsdom
import { beforeEach, expect, it } from 'vitest'
import { readLegacyPreferences, clearLegacyPreferences } from './legacy'
beforeEach(()=>localStorage.clear())
it('offers valid unowned goals only for explicit import and preserves v2 dates',()=>{
 localStorage.setItem('practice.trend.settings.v2.drill',JSON.stringify({target:36,deadline:'2026-11-22'}))
 localStorage.setItem('practice.trend.settings.v1.ei',JSON.stringify({target:15,deadline:'2026-11-22'}))
 expect(readLegacyPreferences()).toEqual({'progress.drill':{target:36,deadline:'2026-11-22'},'progress.ei':{target:15,deadline:'2026-11-21'}})
 expect(localStorage.length).toBe(2)
 clearLegacyPreferences();expect(localStorage.length).toBe(0)
})
it('rejects invalid local goals and does not fall back behind a present v2 record',()=>{
 localStorage.setItem('practice.trend.settings.v2.drill',JSON.stringify({target:0,deadline:'2026-11-21'}))
 localStorage.setItem('practice.trend.settings.v1.drill',JSON.stringify({target:25,deadline:'2026-11-21'}))
 localStorage.setItem('practice.trend.settings.v1.ei',JSON.stringify({target:12,deadline:'2026-02-30'}))
 expect(readLegacyPreferences()).toEqual({})
})
