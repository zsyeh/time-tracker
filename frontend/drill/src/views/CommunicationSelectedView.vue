<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../lib/api'
import { communicationFilters, communicationPracticeQuery } from '../lib/communicationSelected'
import HeatmapProgress from '../components/HeatmapProgress.vue'

type Progress = { total: number; attempted: number; mastered: number; unattempted: number }
type Item = { uuid: string; label: string; book: string; bucket: string; tier: string; kind: string; state: 'mastered' | 'review' | 'unattempted'; ready: boolean; combined: boolean; question_mode: string; answer_mode: string; scope_note: string; has_open_erratum: boolean; tags: string[]; reason: string[] }
type Group = { key: string; title: string; rank: number; tier: string; focus: string; progress: Progress; questions: Item[] }
type Payload = { coverage_notes?: string[]; title: string; basis: string; groups: Group[]; progress: Progress; ready_count: number; inventory_count: number; selected_count: number; review_count: number; excluded_count: number; review_items: { uuid: string; label: string; reason: string[] }[] }
const route = useRoute()
const router = useRouter()
const data = ref<Payload | null>(null)
const loading = ref(false)
const error = ref('')
const labels = { core: '核心必练', advanced: '进阶必过', foundation: '基础巩固', cross: '低优先级选练' } as Record<string, string>
const showLabels = ref(true)
const filters = computed(() => communicationFilters(route.query))
let sequence = 0
async function load() {
  const current = ++sequence
  loading.value = true; error.value = ''
  try {
    const payload = await api<Payload>('/api/drill/communication-selected/?' + new URLSearchParams(filters.value).toString())
    if (current !== sequence) return
    data.value = payload
    await nextTick()
    const uuid = String(route.query.question || '')
    if (uuid) document.querySelector(`[data-communication-question="${CSS.escape(uuid)}"]`)?.scrollIntoView({ block: 'center' })
  } catch (reason) { if (current === sequence) error.value = (reason as Error).message }
  finally { if (current === sequence) loading.value = false }
}
function change(key: string, value: string) {
  const query = { ...filters.value, [key]: value }
  if (!value) delete query[key]
  void router.replace({ path: '/communication-selected', query })
}
function open(question: Item) {
  void router.push({ path: `/practice/${question.uuid}`, query: communicationPracticeQuery(filters.value) })
}
function start(group?: Group) {
  const pool = group ? group.questions : data.value?.groups.flatMap((g) => g.questions) || []
  const question = pool.find((q) => q.ready && q.state !== 'mastered') || pool.find((q) => q.state !== 'mastered') || pool[0]
  if (!question) return
  const query = communicationPracticeQuery({ ...filters.value, ...(group ? { bucket: group.key } : {}) })
  void router.push({ path: `/practice/${question.uuid}`, query })
}
watch(() => route.fullPath, load)
onMounted(() => {
  if (!Object.keys(filters.value).length && !route.query.all) {
    void router.replace({ path: '/communication-selected', query: { tier: 'core' } })
  } else void load()
})
</script>

<template>
  <section class="page communication-selected-page">
    <header class="page-header"><div><span class="eyebrow">892 · COMMUNICATION SELECTED</span><h1>通信严选</h1><p>先练无码间串扰、匹配滤波和 PCM／香农容量，再补模拟与二进制调制。原题原记录，不重复建题。</p></div><button class="primary-action" :disabled="!data?.progress.total || loading" @click="start()">开始／继续刷题 →</button></header>
    <p class="communication-notice">排序采用你的备考优先级，不代表命题概率。接收误码率不等于匹配滤波大题；复杂均衡、抗噪推导不混入主攻。默认展示核心必练中的全部题目，不区分当前是否已有答案。</p>
    <section class="communication-filters" aria-label="通信严选筛选">
      <label>训练层级<select :value="filters.tier || ''" @change="change('tier', ($event.target as HTMLSelectElement).value)"><option value="">全部层级</option><option v-for="(title, key) in labels" :key="key" :value="key">{{ title }}</option></select></label>
      <label>考点<select :value="filters.bucket || ''" @change="change('bucket', ($event.target as HTMLSelectElement).value)"><option value="">全部考点</option><option v-for="group in data?.groups || []" :key="group.key" :value="group.key">{{ group.rank }} · {{ group.title }}</option></select></label>
      <label>题型<select :value="filters.kind || ''" @change="change('kind', ($event.target as HTMLSelectElement).value)"><option value="">全部题型</option><option value="calculation">计算／综合</option><option value="analysis">波形／框图分析</option><option value="concept">概念／简答</option></select></label>
      <label>掌握<select :value="filters.state || ''" @change="change('state', ($event.target as HTMLSelectElement).value)"><option value="">全部状态</option><option value="unattempted">未做</option><option value="review">待复习</option><option value="mastered">已掌握</option></select></label>
      <label>组合训练<select :value="filters.combined || ''" @change="change('combined', ($event.target as HTMLSelectElement).value)"><option value="">全部</option><option value="1">前三类重点攻坚</option></select></label>
      <button @click="router.replace({ path: '/communication-selected', query: { all: '1' } })">查看全部匹配</button>
    </section>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <p v-if="loading" role="status">正在读取原题与掌握记录…</p>
    <template v-if="data">
      <p v-for="note in data.coverage_notes || []" :key="note" class="communication-notice">{{ note }}</p>
      <div class="communication-coverage">盘点 {{ data.inventory_count }} 题 · 匹配 {{ data.selected_count }} 题 · 待复核 {{ data.review_count }} · 不纳入 {{ data.excluded_count }}。当前筛选 {{ data.progress.total }} 题，{{ data.ready_count }} 题已具备题答。</div>
      <HeatmapProgress :total="data.progress.total" :attempted="data.progress.attempted" :mastered="data.progress.mastered" />
      <div class="communication-legend"><span class="unattempted">未做</span><span class="review">待复习</span><span class="mastered">已掌握</span><label><input v-model="showLabels" type="checkbox" />显示原题标签</label></div>
      <p v-if="!data.progress.total" class="empty-state">当前筛选没有题目。可切换层级，或选择“查看全部匹配”；不会自动跳去其他学科。</p>
      <article v-for="group in data.groups.filter((g) => g.questions.length)" :key="group.key" class="communication-group">
        <header><div><small>{{ group.rank }} · {{ labels[group.tier] }}</small><h2>{{ group.title }}</h2><p>{{ group.focus }}</p></div><button @click="start(group)">刷这一组 →</button></header>
        <HeatmapProgress :total="group.progress.total" :attempted="group.progress.attempted" :mastered="group.progress.mastered" />
        <div class="communication-question-grid" :class="{ compact: !showLabels }">
          <button v-for="(question, index) in group.questions" :key="question.uuid" :class="[question.state, { selected: route.query.question === question.uuid }]" :data-communication-question="question.uuid" :aria-label="`${question.label} · ${question.book} · ${question.state}`" :title="`${question.book}\n${question.label}\n${question.reason.join('；')}\n${question.question_mode} · ${question.answer_mode}`" @click="open(question)">
            <strong>{{ showLabels ? question.label : index + 1 }}</strong>
            <template v-if="showLabels"><small>{{ question.book }}</small><span>{{ question.question_mode }} · {{ question.answer_mode }}</span><em v-if="question.combined">前三类重点攻坚</em><em v-if="question.kind === 'concept'">概念／简答</em><em v-if="question.has_open_erratum">有待处理勘误</em><em v-if="question.scope_note">原书部分超纲</em></template>
          </button>
        </div>
      </article>
      <details class="communication-review"><summary>待复核 {{ data.review_count }} 题：未混入严选刷题</summary><p>这些题已纳入盘点，但题意、资料完整性、推导深度或考纲范围还不可靠，不凭章节号猜测。下面仅供查阅原题。</p><ul><li v-for="item in data.review_items" :key="item.uuid"><RouterLink :to="`/practice/${item.uuid}`">{{ item.label }}</RouterLink> · {{ item.reason.join('；') }}</li></ul></details>
    </template>
  </section>
</template>

<style scoped>
.communication-notice, .communication-coverage { padding: 14px; margin: 14px 0; color: var(--text-secondary); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); line-height: 1.7; }
.communication-filters { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; margin-bottom: 18px; }
.communication-filters label { display: grid; gap: 6px; font-size: 12px; min-width: 145px; max-width: 100%; }
.communication-filters select { width: 100%; min-width: 0; max-width: 100%; padding: 9px; color: var(--text-primary); background: var(--bg-sidebar); border: 1px solid var(--border-default); border-radius: var(--radius-sm); }
.communication-filters button, .communication-group header button { min-height: 36px; padding: 8px 12px; color: var(--text-primary); background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: var(--radius-sm); cursor: pointer; }
.communication-group { border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 18px; margin: 22px 0; }
.communication-group header { display: flex; justify-content: space-between; align-items: start; gap: 12px; margin-bottom: 16px; }
.communication-group h2 { margin: 6px 0; font-size: 20px; }
.communication-group p { color: var(--text-secondary); line-height: 1.6; }
.communication-question-grid { display: grid; grid-template-columns: repeat(auto-fill,minmax(185px,1fr)); gap: 9px; }
.communication-question-grid button { min-width: 0; display: grid; gap: 6px; padding: 12px; text-align: left; overflow-wrap: anywhere; border: 1px solid var(--border-default); border-left-width: 4px; border-radius: var(--radius-sm); background: var(--bg-surface); color: var(--text-primary); cursor: pointer; }
.communication-question-grid button:hover { box-shadow: inset 0 0 0 1px var(--accent); }
.communication-question-grid small, .communication-question-grid span { font-size: 11px; color: var(--text-secondary); }
.communication-question-grid em { font-size: 11px; font-style: normal; }
.communication-question-grid .mastered { border-color: var(--success); background: color-mix(in srgb, var(--success) 12%, var(--bg-surface)); }
.communication-question-grid .review { border-color: var(--warning); background: color-mix(in srgb, var(--warning) 12%, var(--bg-surface)); }
.communication-question-grid .selected { outline: 2px solid var(--text-primary); outline-offset: 2px; }
.communication-question-grid.compact { grid-template-columns: repeat(auto-fill,minmax(40px,1fr)); }
.communication-question-grid.compact button { text-align: center; padding: 9px; }
.communication-legend { display: flex; gap: 18px; align-items: center; flex-wrap: wrap; margin: 18px 0; }
.communication-legend .mastered { color: var(--success); }.communication-legend .review { color: var(--warning); }
.communication-review { margin: 24px 0; line-height: 1.8; }.communication-review li { margin: 7px 0; }
@media (max-width:600px) { .communication-group { padding: 11px; }.communication-group header { flex-wrap: wrap; }.communication-question-grid { grid-template-columns: minmax(0,1fr); }.communication-filters label { min-width: 0; width: calc(50% - 6px); } }
</style>
