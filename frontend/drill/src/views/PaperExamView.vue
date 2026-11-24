<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { paperKeyboardMarks } from '../lib/paperKeyboardMarks'
import { installStudyShortcuts } from '../lib/studyShortcuts'
import { api, ApiError } from '../lib/api'
import { patchQuestionState } from '../lib/workspace'
import PaperQuestionContent from '../components/PaperQuestionContent.vue'
import FullscreenReader from '../components/FullscreenReader.vue'
import type { ExamPaper } from '../types'
import { createAndCopyShare } from '../lib/share'
import { withWorkspacePrefix } from '../lib/runtimePath'
import { buildListContext, previewLocation, previewQuestionLocation } from '../lib/listContext'

const props = defineProps<{ uuid: string }>()
const router = useRouter()
const route = useRoute()
const paper = ref<ExamPaper | null>(null)
const index = ref(0)
const error = ref('')
const now = ref(Date.now())
const answer = ref(false)
const sharing = ref(false)
const copied = ref(false)
const saving = ref(0)
const favoriteSaving = ref(false)
const replacing = ref(false)
const ending = ref(false)
const canRevealAnswers = computed(() => paper.value?.status === 'completed')
let removeShortcuts: (() => void) | undefined
const replaceError = ref('')
const replacementNotice = ref('')
const reader = ref<InstanceType<typeof FullscreenReader> | null>(null)
let timer = 0
let noteTimer = 0
let saveChain = Promise.resolve(true)
const item = computed(() => paper.value?.items[index.value] || null)
const marks=paperKeyboardMarks(()=>item.value,()=>paper.value,reason=>{error.value=(reason as Error).message})
const markSaving=marks.busy,markHistory=marks.history
const context = computed(() => buildListContext('paper', { paper: props.uuid }, `/papers/${props.uuid}?position=${index.value + 1}`))
const remaining = computed(() => {
  if (!paper.value?.started_at) return (paper.value?.duration_minutes || 0) * 60
  return Math.max(0, Math.ceil((new Date(paper.value.started_at).getTime() + paper.value.duration_minutes * 60000 - now.value) / 1000))
})
const clock = computed(() => `${Math.floor(remaining.value / 3600)}:${String(Math.floor(remaining.value / 60) % 60).padStart(2, '0')}:${String(remaining.value % 60).padStart(2, '0')}`)
const images = computed(() => (answer.value ? item.value?.question.answer_assets : item.value?.question.question_assets)?.map(asset => ({ src: withWorkspacePrefix(asset.url), width: asset.width, height: asset.height })) || [])
function practiceLocation() {
  return item.value ? previewQuestionLocation(context.value, { entry_id: `paper:${item.value.id}`, question_uuid: item.value.question.uuid, index: index.value }) : '/papers'
}
function save(entry = item.value, flush = false) {
  if (replacing.value && !flush) return saveChain
  window.clearTimeout(noteTimer)
  if (!entry) return saveChain
  const position = entry.position
  const user_answer = entry.user_answer
  saving.value++
  saveChain = saveChain.then(async () => {
    try {
      await api(`/api/drill/papers/${props.uuid}/items/${position}/`, { method: 'PATCH', body: JSON.stringify({ user_answer, expected_question_uuid: entry.question.uuid }) })
      error.value = ''
      return true
    } catch (reason) { error.value = `备注未保存，请重试：${(reason as Error).message}`; return false }
    finally { saving.value-- }
  })
  return saveChain
}
function scheduleSave() { if (replacing.value) return; window.clearTimeout(noteTimer); noteTimer = window.setTimeout(() => { void save() }, 500) }
async function move(next: number) {
  if (replacing.value || !paper.value || next < 0 || next >= paper.value.items.length || next === index.value) return
  void save()
  index.value = next
  answer.value = false
  replaceError.value = ''
  replacementNotice.value = ''
  await router.replace({ query: { ...route.query, position: String(next + 1) } })
}
function markExam(kind: 'review'|'mastered') { if (!replacing.value) return marks.mark(kind) }
function flag() { return markExam('review') }
const undoMark=marks.undo
async function showAnswer(fullscreen=false) {
  if (!canRevealAnswers.value) { error.value='考试未结束，暂不能查看答案。';return }
  answer.value=fullscreen ? true : !answer.value
  if (fullscreen) { await nextTick();await reader.value?.open() }
}
async function endExam() {
  if (!paper.value || ending.value || replacing.value || !window.confirm('结束本次考试并解锁答案？不会自动计算分数。')) return
  ending.value=true
  try {
    if (!await save()) return
    await api(`/api/drill/papers/${props.uuid}/`,{method:'PATCH',body:JSON.stringify({action:'complete'})})
    paper.value=await api<ExamPaper>(`/api/drill/papers/${props.uuid}/review/`)
  } catch(reason) {error.value=`结束或加载失败，请刷新核对：${(reason as Error).message}`}
  finally {ending.value=false}
}
async function toggleFavorite() {
  const question = item.value?.question
  if (!question || favoriteSaving.value || replacing.value) return
  favoriteSaving.value = true
  try {
    const state = await api<{ is_favorite: boolean; version: number }>(`/api/drill/questions/${question.uuid}/state/`, {
      method: 'POST', body: JSON.stringify({ is_favorite: !question.is_favorite, version: question.state_version || 1 }),
    })
    question.is_favorite = state.is_favorite
    question.state_version = state.version
    patchQuestionState(question.uuid, { is_favorite: state.is_favorite, state_version: state.version })
    error.value = ''
  } catch (reason) {
    if (reason instanceof ApiError && reason.status === 409) {
      question.is_favorite = !!reason.body.is_favorite
      question.state_version = Number(reason.body.version) || 1
    }
    error.value = (reason as Error).message
  } finally { favoriteSaving.value = false }
}
async function sharePaper() {
  if (sharing.value || replacing.value) return
  sharing.value = true
  try { await createAndCopyShare(`/api/drill/papers/${props.uuid}/share/`); copied.value = true }
  catch (reason) { error.value = (reason as Error).message }
  finally { sharing.value = false }
}
async function replaceQuestion() {
  const entry = item.value
  if (!entry || replacing.value || sharing.value || favoriteSaving.value) return
  if (!window.confirm('更换本题？该位置的备注和自评分会清空；原题的掌握状态、收藏和作答历史保持不变。')) return
  replacing.value = true
  replaceError.value = ''
  try {
    if (!await save(entry, true)) return
    const updated = await api<ExamPaper & { replacement?: { warning?: string } }>(`/api/drill/papers/${props.uuid}/items/${entry.position}/replace/`, {
      method: 'POST', body: JSON.stringify({ expected_question_uuid: entry.question.uuid }),
    })
    paper.value = updated
    replacementNotice.value = updated.replacement?.warning || '已更换本题，原题的学习记录保持不变。'
    answer.value = false
    copied.value = false
  } catch (reason) { replaceError.value = `更换失败：${(reason as Error).message}` }
  finally { replacing.value = false }
}
onMounted(async () => {
  removeShortcuts=installStudyShortcuts({
    previous:()=>move(index.value-1),next:()=>move(index.value+1),favorite:toggleFavorite,
    review:()=>markExam('review'),mastered:()=>markExam('mastered'),undo:undoMark,
    preview:()=>{reader.value?.close();void save();return router.push(previewLocation(context.value))},
    answer:()=>showAnswer(true),fullscreen:()=>reader.value?.open(),exit:()=>reader.value?.close(),
  },{blocked:()=>!paper.value || replacing.value || ending.value || markSaving.value,
     error:reason=>{error.value=(reason as Error).message}})

  try {
    paper.value = await api<ExamPaper>(`/api/drill/papers/${props.uuid}/review/`)
    index.value = Math.max(0, Math.min(paper.value.items.length - 1, (Number(route.query.position) || 1) - 1))
    if (!paper.value.started_at) {
      const started = await api<ExamPaper>(`/api/drill/papers/${props.uuid}/`, { method: 'PATCH', body: JSON.stringify({ action: 'start' }) })
      paper.value.started_at = started.started_at
    }
    timer = window.setInterval(() => { now.value = Date.now() }, 1000)
  } catch (reason) { error.value = (reason as Error).message }
})
onUnmounted(() => { removeShortcuts?.();window.clearInterval(timer); window.clearTimeout(noteTimer); if (item.value) void save(item.value) })
</script>

<template>
  <section class="page focus-training">
    <header class="training-header">
      <RouterLink to="/papers">← 专注训练</RouterLink>
      <strong>{{ paper?.title || '加载题单…' }}</strong>
      <span class="countdown" role="timer">{{ canRevealAnswers ? '考试已结束' : remaining ? clock : '计时结束，可继续训练' }}</span>
    </header>
    <nav v-if="paper" class="training-tools" aria-label="题单工具">
      <RouterLink :to="previewLocation(context)">整卷预览</RouterLink>
      <RouterLink v-if="canRevealAnswers" :to="`/papers/${uuid}/review?mode=self`">自评</RouterLink>
      <button v-else :disabled="ending || replacing" @click="endExam">{{ ending ? '正在结束…' : '结束考试并解锁答案' }}</button>
      <a :href="withWorkspacePrefix(`/api/drill/papers/${uuid}/pdf/questions/`)">试卷 PDF</a>
      <button :disabled="sharing || replacing" @click="sharePaper">{{ sharing ? '生成分享…' : copied ? '分享链接已复制' : '分享整卷' }}</button>
    </nav>
    <p v-if="error" class="error-state" role="alert">{{ error }} <button :disabled="replacing" @click="save()">重试保存</button></p>
    <p v-if="replaceError" class="error-state" role="alert">{{ replaceError }}</p>
    <p v-if="replacementNotice" role="status">{{ replacementNotice }}</p>
    <template v-if="paper && item">
      <div class="training-content">
        <header class="question-heading"><strong>第 {{ item.position }} / {{ paper.items.length }} 题</strong><span>{{ item.question.document }}</span></header>
        <div class="question-actions">
          <button :disabled="!canRevealAnswers" @click="showAnswer()">{{ answer ? '返回题目' : '查看答案' }}</button>
          <button @click="reader?.open()">全屏查看</button>
          <RouterLink v-if="canRevealAnswers" :to="practiceLocation()" :aria-disabled="replacing" :tabindex="replacing ? -1 : undefined" @click="replacing ? $event.preventDefault() : save()">标准练习 →</RouterLink>
          <button :aria-pressed="!!item.question.is_favorite" :disabled="favoriteSaving || replacing" @click="toggleFavorite">{{ item.question.is_favorite ? '已收藏' : '收藏' }}</button>
          <button :disabled="replacing || markSaving" @click="flag">待复习 (N)</button><button :disabled="replacing || markSaving" @click="markExam('mastered')">掌握 (M)</button><button :disabled="markSaving || !markHistory.length" @click="undoMark">撤销标记 (U)</button>
          <button :disabled="replacing || sharing || favoriteSaving" @click="replaceQuestion">{{ replacing ? '更换中…' : '更换本题' }}</button>
        </div>
        <PaperQuestionContent v-if="!answer" :question="item.question" />
        <div v-else class="training-answer">
          <img v-for="asset in item.question.answer_assets" :key="asset.id" :src="withWorkspacePrefix(asset.url)" :width="asset.width" :height="asset.height" loading="lazy" decoding="async" alt="原始答案贴图" />
          <p v-if="!item.question.answer_assets?.length">暂无答案贴图</p>
        </div>
        <label class="training-note">疑难原因 / 备注 <small>{{ saving ? '保存中…' : '自动保存' }}</small>
          <textarea v-model="item.user_answer" :disabled="replacing" rows="3" placeholder="记录不会做的原因或训练备注" @input="scheduleSave" @blur="save()" />
        </label>
      </div>
      <footer class="training-nav">
        <button :disabled="replacing || index === 0" @click="move(index - 1)">上一题</button>
        <div class="positions" aria-label="选择题号"><button v-for="(entry, n) in paper.items" :key="entry.position" :class="{ active: index === n, flagged: entry.question.mastery_state === 'review' || entry.user_answer.startsWith('不会做：') }" :aria-current="index === n ? 'step' : undefined" :disabled="replacing" @click="move(n)">{{ entry.position }}</button></div>
        <button :disabled="replacing || index === paper.items.length - 1" @click="move(index + 1)">下一题</button>
      </footer>
      <FullscreenReader ref="reader" hide-trigger :title="`第 ${item.position} 题 · ${answer ? '答案' : '题目'}`" :images="images" :content-key="`${item.question.uuid}-${answer}`">
        <template #actions><button :disabled="replacing || index === 0" @click="move(index - 1)">上一题</button><button :disabled="replacing || index === paper.items.length - 1" @click="move(index + 1)">下一题</button><button :aria-pressed="!!item.question.is_favorite" :disabled="favoriteSaving || replacing" @click="toggleFavorite">{{ item.question.is_favorite ? '已收藏' : '收藏' }}</button><button :disabled="replacing || sharing || favoriteSaving" @click="replaceQuestion">{{ replacing ? '更换中…' : '更换本题' }}</button></template>
        <template #recovery><p v-if="replaceError || error" class="replacement-feedback" role="alert">{{ replaceError || error }}</p></template>
      </FullscreenReader>
    </template>
  </section>
</template>

<style scoped>
.focus-training { min-width:0; }
.training-header { display:flex; align-items:center; gap:16px; flex-wrap:wrap; padding-bottom:12px; border-bottom:1px solid var(--border-subtle); }
.training-header strong { flex:1; font-size:18px; }
.training-header a,.training-tools a,.question-actions a { color:var(--text-secondary); text-decoration:none; }
.countdown { color:var(--text-secondary); font-variant-numeric:tabular-nums; }
.training-tools,.question-actions { display:flex; align-items:center; flex-wrap:wrap; gap:8px; }
.training-tools { margin:8px 0; }
.focus-training button,.training-tools a,.question-actions a { min-height:44px; display:inline-flex; align-items:center; padding:8px 12px; border:0; border-radius:var(--radius-control); background:transparent; color:var(--text-secondary); cursor:pointer; font:inherit; }
.focus-training button:hover,.training-tools a:hover,.question-actions a:hover { background:var(--surface-hover); }
.question-actions a[aria-disabled="true"] { opacity:.35; cursor:default; }
.replacement-feedback { margin:0; padding:8px 12px; color:var(--text-primary); background:var(--bg-surface); }
.focus-training button:disabled { opacity:.35; cursor:default; }
.training-content { max-width:1000px; margin:0 auto; }
.question-heading { display:flex; gap:12px; flex-wrap:wrap; padding:12px 0; }
.question-heading span { color:var(--text-tertiary); }
.training-answer { padding:24px 0; display:grid; gap:8px; }
.training-answer img { display:block; width:100%; height:auto; background:white; }
.training-note { display:grid; gap:8px; color:var(--text-secondary); }
.training-note small { font-size:12px; }
.training-note textarea { width:100%; font:inherit; padding:12px; border:1px solid var(--border-subtle); border-radius:var(--radius-control); background:var(--bg-surface); color:var(--text-primary); }
.training-nav { position:sticky; bottom:0; display:flex; align-items:center; gap:8px; padding:8px 0 max(8px,env(safe-area-inset-bottom)); background:var(--bg-surface); border-top:1px solid var(--border-subtle); }
.training-nav > button { flex-shrink:0; }
.positions { display:flex; flex:1; overflow-x:auto; gap:4px; }
.positions button { min-width:36px; justify-content:center; font-variant-numeric:tabular-nums; }
.positions .active { background:var(--surface-selected); color:var(--text-primary); font-weight:600; }
.positions .flagged { text-decoration:underline; text-underline-offset:4px; }
@media(max-width:600px) { .training-header { gap:8px; } .training-header strong { font-size:16px; } .training-header .countdown { margin-left:auto; } .training-tools { gap:0; } .training-tools a,.training-tools button { font-size:13px; padding:8px; } }
</style>
