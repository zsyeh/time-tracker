import { expect,it } from 'vitest'
import postcss from 'postcss'
import { fontScalePlugin } from './fontScalePlugin'
it('scales legacy typography while preserving hit targets, safe-area, images and Safari input floor',async()=>{
 const input='.a{font-size:14px;--font-size-body:14px;--el-font-size-base:14px;font:500 16px/24px sans-serif;min-height:44px;width:28px;padding-top:env(safe-area-inset-top);font-size:max(16px,calc(16px * var(--ui-font-scale,1)))}'
 const first=(await postcss([fontScalePlugin()]).process(input,{from:undefined})).css
 expect(first).toContain('font-size:calc(14px * var(--ui-font-scale, 1))');expect(first).toContain('font:500 calc(16px * var(--ui-font-scale, 1))/24px');expect(first).toContain('min-height:44px;width:28px');expect(first).toContain('max(16px,calc(16px * var(--ui-font-scale,1)))')
 expect((await postcss([fontScalePlugin()]).process(first,{from:undefined})).css).toBe(first)
})
