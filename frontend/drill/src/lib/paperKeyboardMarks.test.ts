// @vitest-environment jsdom
import { beforeEach, expect, it, vi } from 'vitest'
import { paperKeyboardMarks } from './paperKeyboardMarks'
import { api } from './api'
import type { ExamPaper } from '../types'
vi.mock('./api',()=>({api:vi.fn()}))
vi.mock('./workspace',()=>({patchQuestionState:vi.fn()}))
beforeEach(()=>vi.clearAllMocks())
it('updates Practice status, preserves paper score and notes, and undoes only its own attempt',async()=>{
 const paper={items:[{position:1,self_score:3,self_note:'批阅',user_answer:'C',question:{uuid:'q1'}}]} as unknown as ExamPaper
 const marks=paperKeyboardMarks(()=>paper.items[0]!,()=>paper,vi.fn())
 vi.mocked(api).mockResolvedValueOnce({id:42,state:'review'}).mockResolvedValueOnce({state:'unattempted'})
 await marks.mark('review')
 expect(paper.items[0]!.question.mastery_state).toBe('review')
 const [url,options]=vi.mocked(api).mock.calls[0]!
 expect(url).toBe('/api/drill/questions/q1/attempts/')
 expect(JSON.parse(options!.body as string)).toMatchObject({result:'review',timing_omit:true,timing_protocol:2})
 expect(JSON.parse(options!.body as string)).not.toHaveProperty('time_spent_seconds')
 await marks.undo()
 expect(vi.mocked(api).mock.calls[1]![0]).toBe('/api/drill/questions/q1/attempts/?expected_attempt_id=42')
 expect(paper.items[0]).toMatchObject({self_score:3,self_note:'批阅',user_answer:'C'})
 expect(paper.items[0]!.question.mastery_state).toBe('unattempted')
})
it('retries lost responses with the same submission key and never treats a failed save as undoable',async()=>{
 const paper={items:[{question:{uuid:'q1'}}]} as unknown as ExamPaper
 const error=vi.fn(),marks=paperKeyboardMarks(()=>paper.items[0]!,()=>paper,error)
 vi.mocked(api).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({id:7,state:'mastered'})
 await marks.mark('mastered');expect(marks.history.value).toHaveLength(0)
 await marks.mark('mastered')
 expect(vi.mocked(api).mock.calls[0]![1]!.body).toBe(vi.mocked(api).mock.calls[1]![1]!.body)
 expect(marks.history.value).toHaveLength(1)
})
