<script setup lang="ts">
import '../lib/examScores.css'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api } from '../lib/api'
import type { ExamPaper, ExamPaperItem } from '../types'
const props = defineProps<{ uuid: string }>()
const paper = ref<ExamPaper | null>(null)
const activePosition = ref(1)
const pending = ref(0)
const error = ref('')
const total = computed(() => paper.value?.items.reduce((sum, item) => sum + Number(item.self_score || 0), 0) || 0)
const maximum = computed(() => paper.value?.items.reduce((sum, item) => sum + item.score, 0) || 0)
const active = computed(() => paper.value?.items.find(item => item.position === activePosition.value))
const isSmall = (item: ExamPaperItem) => item.question.question_type !== 'solution'
type Update = { self_score?: number | null; self_note?: string }
const failed = new Map<number, Update>()
let chain = Promise.resolve()
let noteTimer = 0
let noteDraft: { item: ExamPaperItem; update: Update } | null = null
function persist(item: ExamPaperItem, update: Update) {
  const position = item.position
  pending.value++
  chain = chain.then(async () => {
    const patch = { ...failed.get(position), ...update }
    try {
      await api(`/api/drill/papers/${props.uuid}/items/${position}/`, { method: 'PATCH', body: JSON.stringify({ ...patch, expected_question_uuid: item.question.uuid }) })
      failed.delete(position)
      if (!failed.size) error.value = ''
    } catch (reason) {
      failed.set(position, patch)
      error.value = `第 ${position} 题保存失败：${(reason as Error).message}`
    } finally { pending.value-- }
  })
}
function flushNote() {
  window.clearTimeout(noteTimer)
  if (noteDraft) { persist(noteDraft.item, noteDraft.update); noteDraft = null }
}
function select(item: ExamPaperItem) { flushNote(); activePosition.value = item.position }
function toggle(item: ExamPaperItem) {
  select(item)
  item.self_score = item.self_score === item.score ? 0 : item.score
  persist(item, { self_score: item.self_score })
}
function updateScore(item: ExamPaperItem, value: string) {
  select(item)
  const score = Number(value)
  if (!Number.isFinite(score) || score < 0 || score > item.score) { error.value = `第 ${item.position} 题请输入 0～${item.score} 分`; return }
  item.self_score = Math.round(score * 100) / 100
  persist(item, { self_score: item.self_score })
}
function updateNote(value: string) {
  if (!active.value) return
  active.value.self_note = value
  window.clearTimeout(noteTimer)
  noteDraft = { item: active.value, update: { self_note: value } }
  noteTimer = window.setTimeout(flushNote, 500)
}
function retry() {
  for (const [position, update] of failed) {
    const item = paper.value?.items.find(item => item.position === position)
    if (item) persist(item, update)
  }
}
onMounted(async () => {
  try { paper.value = await api<ExamPaper>(`/api/drill/papers/${props.uuid}/review/`) }
  catch (reason) { error.value = (reason as Error).message }
})
onUnmounted(flushNote)
</script>

<template>
  <section class="page paper-self-evaluation">
    <header class="evaluation-header">
      <div><RouterLink to="/papers">← 我的套卷</RouterLink><h1>自评</h1><p>{{ paper?.title }}</p></div>
      <div class="evaluation-total" aria-live="polite"><strong>{{ Number(total.toFixed(2)) }}/{{ maximum }}</strong><span> 分</span></div>
    </header>
    <p class="evaluation-help">小题点选得满分，再点取消；未选为 0 分。大题填写得分，点击题框可记备注。</p>
    <p class="save-status" role="status">{{ pending ? '保存中…' : error ? '' : '自动保存到账号' }}</p>
    <p v-if="error" role="alert" class="error-state">{{ error }} <button @click="retry">重试保存</button></p>
    <div v-if="paper" class="score-grid" aria-label="试卷逐题自评">
      <template v-for="item in paper.items" :key="item.position">
        <button v-if="isSmall(item)" class="score-box small" :class="{ checked: item.self_score === item.score, selected: activePosition === item.position }" :aria-pressed="item.self_score === item.score" :aria-label="`第${item.position}题，${item.self_score || 0}/${item.score}分`" @click="toggle(item)"><span>{{ item.position }}</span><small class="score-value">{{ item.self_score ?? 0 }}/{{ item.score }}</small></button>
        <div v-else class="score-box large" :class="{ selected: activePosition === item.position }" @click="select(item)"><label :for="`self-score-${item.position}`">{{ item.position }}</label><input :id="`self-score-${item.position}`" :value="item.self_score ?? ''" type="number" inputmode="decimal" min="0" :max="item.score" step="0.5" placeholder="0" :aria-label="`第${item.position}题得分，满分${item.score}分`" @change="updateScore(item, ($event.target as HTMLInputElement).value)" @focus="select(item)" /><span class="score-value">/{{ item.score }}</span></div>
      </template>
    </div>
    <section v-if="active" class="evaluation-note">
      <header><label for="evaluation-note">第 {{ active.position }} 题备注</label><RouterLink :to="`/papers/${uuid}?position=${active.position}`">查看题目 / 答案 →</RouterLink></header>
      <textarea id="evaluation-note" :value="active.self_note || ''" rows="4" maxlength="10000" placeholder="记录扣分原因、疑问或复习提醒" @input="updateNote(($event.target as HTMLTextAreaElement).value)" @blur="flushNote" />
    </section>
    <p class="evaluation-help">自评分与备注仅自己可见，不改变掌握状态、收藏或原有作答记录。</p>
  </section>
</template>

<style scoped>
.paper-self-evaluation { max-width:1000px; }
.evaluation-header { display:flex; justify-content:space-between; align-items:center; gap:16px; }
.evaluation-header h1 { margin:12px 0 4px; }
.evaluation-header a,.evaluation-note a { color:var(--text-secondary); text-decoration:none; }
.evaluation-header p,.evaluation-help,.save-status { color:var(--text-secondary); font-size:13px; line-height:1.6; }
.evaluation-total { flex-shrink:0; font-variant-numeric:tabular-nums; }
.evaluation-total strong { font-size:36px; font-weight:600; }
.evaluation-total span { color:var(--text-secondary); }
.score-grid { display:grid; grid-template-columns:repeat(10,minmax(0,1fr)); gap:8px; margin:16px 0 24px; }
.score-box { min-width:0; min-height:72px; padding:8px; border:1px solid var(--border-subtle); border-radius:var(--radius-control); background:transparent; color:var(--text-primary); font:inherit; font-variant-numeric:tabular-nums; }
.score-box.small { display:flex; flex-direction:column; align-items:center; justify-content:center; gap:4px; cursor:pointer; }
.score-box small { color:var(--text-tertiary); font-size:12px; }
.score-box.checked { background:var(--surface-selected); font-weight:600; }
.score-box.selected { border-color:var(--border-default); }
.score-box.large { grid-column:span 2; display:flex; align-items:center; gap:8px; }
.score-box.large label { flex-shrink:0; }
.score-box.large label small { display:block; }
.score-box input { width:100%; min-width:0; min-height:44px; padding:4px; font:inherit; font-size:22px; text-align:center; border:0; border-radius:0; background:transparent; color:var(--text-primary); }
.score-box input:focus { outline-offset:0; }
.evaluation-note header { display:flex; justify-content:space-between; gap:12px; align-items:center; margin-bottom:8px; }
.evaluation-note textarea { box-sizing:border-box; width:100%; padding:12px; font:inherit; color:var(--text-primary); background:var(--surface-subtle); border:1px solid var(--border-subtle); border-radius:var(--radius-control); resize:vertical; }
@media(max-width:700px) { .score-grid { grid-template-columns:repeat(6,minmax(0,1fr)); } .evaluation-total strong { font-size:30px; } .evaluation-header { gap:8px; } .score-box { padding:4px; min-height:64px; } .score-box.large { gap:4px; } .evaluation-note header { font-size:13px; } }

.evaluation-total strong, .score-box input, .score-box .score-value { color:var(--score-ink); font-family:SimHei,"PingFang SC","Microsoft YaHei",sans-serif; font-weight:800; }
</style>
