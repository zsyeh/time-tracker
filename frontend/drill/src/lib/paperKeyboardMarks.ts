import { ref } from 'vue'
import { api } from './api'
import { patchQuestionState } from './workspace'
import type { ExamPaper, ExamPaperItem, QuestionDetail } from '../types'
type AttemptState = Partial<QuestionDetail> & { id: number }
/** Practice state actions; never alter paper scores, answers or exam duration. */
export function paperKeyboardMarks(current:()=>ExamPaperItem|null, paper:()=>ExamPaper|null, onError:(reason:unknown)=>void) {
  const busy=ref(false)
  const history=ref<Array<{uuid:string;attempt:number}>>([])
  let pending: { uuid:string;kind:string;body:Record<string,unknown> } | null=null
  function apply(uuid:string,state:Partial<QuestionDetail>) {
    const { id: _attemptId, ...patch } = state as AttemptState
    for (const entry of paper()?.items || []) if (entry.question.uuid===uuid) Object.assign(entry.question,patch,{mastery_state:patch.state})
    patchQuestionState(uuid,patch)
  }
  async function mark(kind:'review'|'mastered') {
    const entry=current();if (!entry || busy.value) return
    const uuid=entry.question.uuid
    if (pending && (pending.uuid!==uuid || pending.kind!==kind)) {onError(new Error('上次标记尚未确认，请回到原题按相同快捷键重试。'));return}
    pending ||= {uuid,kind,body:{result:kind==='mastered'?'correct':'review',timing_protocol:2,timing_omit:true,
      timing_key:crypto.randomUUID(),timing_owner:crypto.randomUUID(),submission_key:crypto.randomUUID(),judgement_source:'self'}}
    busy.value=true
    try {
      const state=await api<AttemptState>(`/api/drill/questions/${uuid}/attempts/`,{method:'POST',body:JSON.stringify(pending.body)})
      apply(uuid,state);history.value.push({uuid,attempt:state.id});pending=null
    } catch(reason){onError(reason)} finally {busy.value=false}
  }
  async function undo() {
    const last=history.value[history.value.length-1];if (!last || busy.value) return
    if (pending) {onError(new Error('请先重试确认上次标记，再撤销。'));return}
    busy.value=true
    try {
      const state=await api<AttemptState>(`/api/drill/questions/${last.uuid}/attempts/?expected_attempt_id=${last.attempt}`,{method:'DELETE'})
      apply(last.uuid,state);history.value.pop()
    } catch(reason){onError(reason)} finally {busy.value=false}
  }
  return {busy,history,mark,undo}
}
