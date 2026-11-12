// @vitest-environment jsdom
import { expect, it, vi } from 'vitest'
import { createApp } from 'vue'
import PreviewQuestionRow from './PreviewQuestionRow.vue'
import type { PreviewItem } from '../../lib/listContext'
import type { PreviewImagePipeline } from '../../lib/preview/imagePipeline'
vi.mock('./PreviewAssetImage.vue',()=>({default:{template:'<div class="asset-stub" />'}}))
it('offers one question-level zoom action outside all original scans, including multi-page questions',()=>{
 const item:PreviewItem={entry_id:'attempt:9',question_uuid:'uuid',index:0,label:'题目',document:'题册',topic:'',state:'review',preview:{question_markdown:'',assets:[{id:1,url:'/asset/1',width:1000,height:200},{id:2,url:'/asset/2',width:1000,height:500}]}}
 const host=document.createElement('div'),zoom=vi.fn(),open=vi.fn();document.body.append(host)
 const app=createApp(PreviewQuestionRow,{item,pipeline:{} as PreviewImagePipeline,scroller:null,onZoom:zoom,onOpen:open});app.mount(host)
 expect(host.querySelectorAll('.asset-stub')).toHaveLength(2);expect(host.querySelectorAll('.preview-row-zoom')).toHaveLength(1)
 host.querySelector<HTMLButtonElement>('.preview-row-zoom')!.click();expect(zoom).toHaveBeenCalledWith(item);expect(open).not.toHaveBeenCalled()
 host.querySelector<HTMLButtonElement>('.preview-open')!.click();expect(open).toHaveBeenCalledWith(item)
 app.unmount();host.remove()
})
