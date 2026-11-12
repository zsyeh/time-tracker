// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { buildClipboardPng, copyImagesToClipboard, fittedCanvasSize } from './imageClipboard'

describe('question image clipboard layout', () => {
  afterEach(()=>{vi.restoreAllMocks();vi.unstubAllGlobals()})
  it('stacks multiple images vertically at a shared width', () => {
    expect(fittedCanvasSize([
      { width: 1000, height: 500 },
      { width: 500, height: 500 },
    ])).toEqual({ width: 1000, height: 1500, scale: 1 })
  })

  it('scales oversized composites without cropping', () => {
    const result = fittedCanvasSize([
      { width: 10000, height: 10000 },
      { width: 10000, height: 10000 },
    ])
    expect(result.width).toBe(8192)
    expect(result.height).toBe(16384)
    expect(result.scale).toBeCloseTo(0.8192)
  })

  it('starts copying before a later question image URL is available', async () => {
    let resolveUrls!: (urls: string[]) => void
    const urls = new Promise<string[]>((resolve) => { resolveUrls = resolve })
    const copied: Array<Record<string, Promise<Blob>>> = []
    class TestClipboardItem {
      constructor(public data: Record<string, Promise<Blob>>) { copied.push(data) }
    }
    Object.defineProperty(window, 'ClipboardItem', { configurable: true, value: TestClipboardItem })
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { write: vi.fn().mockResolvedValue(undefined) },
    })
    const blob = new Blob(['png'], { type: 'image/png' })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, blob: () => Promise.resolve(blob) }))

    const result = copyImagesToClipboard(urls)
    expect(navigator.clipboard.write).toHaveBeenCalledTimes(1)
    resolveUrls(['/api/drill/assets/example/'])
    expect(await copied[0]['image/png']).toBe(blob)
    expect((await result).combined).toBe(false)
    vi.unstubAllGlobals()
  })
})


describe('resampled clipboard PNG',()=>{
 afterEach(()=>{vi.restoreAllMocks();vi.unstubAllGlobals()})
 function media(width=1000,height=600){
  const source=new Blob(['source'],{type:'image/png'}),output=new Blob(['scaled'],{type:'image/png'}),draw=vi.fn(),close=vi.fn()
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,blob:async()=>source}))
  vi.stubGlobal('createImageBitmap',vi.fn().mockResolvedValue({width,height,close}))
  vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue({fillRect:vi.fn(),drawImage:draw} as never)
  const canvases:HTMLCanvasElement[]=[]
  vi.spyOn(HTMLCanvasElement.prototype,'toBlob').mockImplementation(function(this:HTMLCanvasElement,callback:BlobCallback){canvases.push(this);callback(output)})
  return {source,output,draw,close,canvases}
 }
 it.each([2,3,4,1.5])('exports actual %s× pixel dimensions even for a single PNG',async scale=>{
  const m=media();const result=await buildClipboardPng(['/question.png'],scale)
  expect(m.canvases[0]!.width).toBe(1000*scale);expect(m.canvases[0]!.height).toBe(600*scale)
  expect(result.blob).toBe(m.output);expect(result.limited).toBe(false);expect(m.draw).toHaveBeenCalledWith(expect.anything(),0,0,1000*scale,600*scale);expect(m.close).toHaveBeenCalledOnce()
 })
 it('keeps the original single PNG bytes at 1× without decoding or allocating a canvas',async()=>{
  const m=media();const result=await buildClipboardPng(['/question.png'])
  expect(result.blob).toBe(m.source);expect(m.canvases).toHaveLength(0);expect(createImageBitmap).not.toHaveBeenCalled()
 })
 it('stacks scaled pages without cropping and reports the memory budget limit',async()=>{
  const m=media(5000,4000);const result=await buildClipboardPng(['/one','/two'],4)
  const canvas=m.canvases[0]!;expect(canvas.width*canvas.height).toBeLessThanOrEqual(16*1024*1024)
  expect(result.combined).toBe(true);expect(result.limited).toBe(true)
  const first=m.draw.mock.calls[0]!,last=m.draw.mock.calls[1]!
  expect(first[2]).toBe(0);expect(last[2]).toBe(first[4]);expect(last[2]+last[4]).toBe(canvas.height)
 })
 it('starts a scaled clipboard write synchronously before its URLs finish loading',async()=>{
  media();let resolve!:(urls:string[])=>void;const urls=new Promise<string[]>(r=>{resolve=r})
  const write=vi.fn(async(items:Array<{data:Record<string,Promise<Blob>>}>)=>{await items[0]!.data['image/png']})
  Object.defineProperty(window,'ClipboardItem',{configurable:true,value:class{constructor(public data:Record<string,Promise<Blob>>){}}})
  Object.defineProperty(navigator,'clipboard',{configurable:true,value:{write}})
  const copying=copyImagesToClipboard(urls,3);expect(write).toHaveBeenCalledOnce();resolve(['/q'])
  await copying
 })
})
