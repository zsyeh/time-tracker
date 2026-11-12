import { expect, it } from 'vitest'
import { estimatePreviewHeight, previewRange, rememberBounded } from './layout'
it('reserves scan aspect ratio at rendered width, with bounded text estimates', () => {
 expect(estimatePreviewHeight([{width:1000,height:500}],1032)).toBe(612)
 expect(estimatePreviewHeight([{width:1000,height:500}],532)).toBe(362)
 expect(Number.isFinite(estimatePreviewHeight([{width:0,height:0}],0))).toBe(true)
})
it('keeps bidirectional overscan and a normal twenty-row target', () => {
 const range=previewRange(500,502,10000,800,()=>100)
 expect(range).toHaveLength(20);expect(range[0]).toBeLessThan(500);expect(range.at(-1)).toBeGreaterThan(502)
 expect(previewRange(0,1,3,800,()=>100)).toEqual([0,1,2])
})
it('never drops visible short rows and reports the exceptional window through its length',()=>{
 expect(previewRange(100,125,1000,800,()=>20)).toEqual(Array.from({length:26},(_,i)=>100+i))
 expect(previewRange(0,0,0,800,()=>100)).toEqual([])
})
it('bounds lightweight identity/height storage rather than retaining visited metadata',()=>{
 const map=new Map<number,string>();for(let i=0;i<10000;i++)rememberBounded(map,i,String(i))
 expect(map.size).toBe(500);expect(map.has(0)).toBe(false);expect(map.get(9999)).toBe('9999')
})
