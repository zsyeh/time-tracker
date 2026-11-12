<script setup lang="ts">
import { uiText } from '../lib/uiText'
import SelectedCollectionLayout from '../components/SelectedCollectionLayout.vue'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../lib/api'
import { signalFilters, signalPracticeQuery } from '../lib/signalSelected'
import ExamTypeControls from '../components/ExamTypeControls.vue'
import ExamTypeBadge from '../components/ExamTypeBadge.vue'
import { formatColours, type TypeStats } from '../lib/examTypes'
import HeatmapProgress from '../components/HeatmapProgress.vue'

type Progress = { total: number; attempted: number; mastered: number; unattempted: number }
type Item = { question_type?: string; type_group?: string; uuid: string; label: string; book: string; bucket: string; tier: string; kind: string; state: 'mastered' | 'review' | 'unattempted'; ready: boolean; combined: boolean; question_mode: string; answer_mode: string; scope_note: string; has_open_erratum: boolean; pdf_pages: { question: number; answer: number; paired: number } | null; tags: string[]; reason: string[] }
type Group = { key: string; title: string; rank: number; tier: string; focus: string; progress: Progress; questions: Item[] }
type Payload = { type_statistics?: TypeStats; title: string; basis: string; groups: Group[]; progress: Progress; ready_count: number; inventory_count: number; selected_count: number; review_count: number; excluded_count: number; review_items: { uuid: string; label: string; reason: string[] }[] }
const route = useRoute()
const router = useRouter()
const data = ref<Payload | null>(null)
const loading = ref(false)
const error = ref('')
const labels = { core: '核心必练', advanced: '进阶必过', foundation: '基础巩固', cross: '交叉选练' } as Record<string, string>
const showLabels = ref(true)
const filters = computed(() => signalFilters(route.query))
let sequence = 0
async function load() {
  const current = ++sequence
  loading.value = true; error.value = ''
  try {
    const payload = await api<Payload>('/api/drill/signal-selected/?' + new URLSearchParams(filters.value).toString())
    if (current !== sequence) return
    data.value = payload
    await nextTick()
    const uuid = String(route.query.question || '')
    if (uuid) document.querySelector(`[data-signal-question="${CSS.escape(uuid)}"]`)?.scrollIntoView({ block: 'center' })
  } catch (reason) { if (current === sequence) error.value = (reason as Error).message }
  finally { if (current === sequence) loading.value = false }
}
function change(key: string, value: string) {
  const query = { ...filters.value, [key]: value }
  if (!value) delete query[key]
  void router.replace({ path: '/signal-selected', query })
}
function open(question: Item) {
  void router.push({ path: `/practice/${question.uuid}`, query: signalPracticeQuery(filters.value) })
}
function start(group?: Group) {
  const pool = group ? group.questions : data.value?.groups.flatMap((g) => g.questions) || []
  const question = pool.find((q) => q.ready && q.state !== 'mastered') || pool.find((q) => q.state !== 'mastered') || pool[0]
  if (!question) return
  const query = signalPracticeQuery({ ...filters.value, ...(group ? { bucket: group.key } : {}) })
  void router.push({ path: `/practice/${question.uuid}`, query })
}
watch(() => route.fullPath, load)
onMounted(() => {
  if (!Object.keys(filters.value).length && !route.query.all) {
    void router.replace({ path: '/signal-selected', query: { tier: 'core' } })
  } else void load()
})
</script>

<template>
  <SelectedCollectionLayout :class="{ 'exam-type-colours': formatColours }" class="signal-selected-page">
    <header class="page-header"><div><h1>{{ uiText("信号严选") }}</h1><p>{{ uiText("先练 Z 变换、拉氏、傅里叶、卷积和系统函数；再补谱、抽样与基础小题。原题原记录，不重复建题。") }}</p></div><button class="primary-action" :disabled="!data?.progress.total || loading" @click="start()">{{ uiText("开始／继续刷题 →") }}</button></header>
    <details class="selected-notice"><summary>{{ uiText("题库说明") }}</summary><p>{{ uiText("排序采用你的备考优先级，不代表命题概率。傅里叶变换注意 2π 系数和频移符号；859 深度不等于 892 主攻深度。默认展示核心必练中的全部题目，不区分当前是否已有答案。") }}</p></details>
    <details class="selected-filter-disclosure"><summary>{{ uiText("筛选") }} · {{ Object.values(filters).filter(Boolean).length }}</summary>
    <section class="signal-filters selected-filters" :aria-label="uiText('信号严选筛选')">
      <label>{{ uiText("训练层级") }}<select :value="filters.tier || ''" @change="change('tier', ($event.target as HTMLSelectElement).value)"><option value="">{{ uiText("全部层级") }}</option><option v-for="(title, key) in labels" :key="key" :value="key">{{ uiText(title) }}</option></select></label>
      <label>{{ uiText("考点") }}<select :value="filters.bucket || ''" @change="change('bucket', ($event.target as HTMLSelectElement).value)"><option value="">{{ uiText("全部考点") }}</option><option v-for="group in data?.groups || []" :key="group.key" :value="group.key">{{ group.rank }} · {{ group.title }}</option></select></label>
      <label>{{ uiText("训练侧重") }}<select :value="filters.kind || ''" @change="change('kind', ($event.target as HTMLSelectElement).value)"><option value="">{{ uiText("计算＋概念") }}</option><option value="calculation">{{ uiText("计算／综合") }}</option><option value="concept">{{ uiText("概念／简答") }}</option></select></label>
      <label>{{ uiText("掌握") }}<select :value="filters.state || ''" @change="change('state', ($event.target as HTMLSelectElement).value)"><option value="">{{ uiText("全部状态") }}</option><option value="unattempted">{{ uiText("未做") }}</option><option value="review">{{ uiText("待复习") }}</option><option value="mastered">{{ uiText("已掌握") }}</option></select></label>
      <label>{{ uiText("组合训练") }}<select :value="filters.combined || ''" @change="change('combined', ($event.target as HTMLSelectElement).value)"><option value="">{{ uiText("全部") }}</option><option value="1">{{ uiText("Z 变换＋初始条件") }}</option></select></label>
      <button @click="router.replace({ path: '/signal-selected', query: { all: '1' } })">{{ uiText("查看全部匹配") }}</button>
    </section>
    <ExamTypeControls :model-value="filters.type_group || ''" :stats="data?.type_statistics" @update:model-value="change('type_group', $event)" @practice="router.push({ path: '/practice', query: { ...filters, collection: 'signal_selected', from: 'signal-selected', type_group: 'small' } })" />
    </details>
    <p v-if="error" role="alert" class="error">{{ uiText(error) }}</p>
    <p v-if="loading" role="status">{{ uiText("正在读取原题与掌握记录…") }}</p>
    <template v-if="data">
      <div class="signal-coverage selected-coverage">{{ uiText("盘点") }} {{ data.inventory_count }} {{ uiText("题 · 匹配") }} {{ data.selected_count }} {{ uiText("题 · 待复核") }} {{ data.review_count }} {{ uiText("· 不纳入") }} {{ data.excluded_count }}{{ uiText("。当前筛选") }} {{ data.progress.total }} {{ uiText("题，") }}{{ data.ready_count }} {{ uiText("题已具备题答。") }}</div>
      <HeatmapProgress :total="data.progress.total" :attempted="data.progress.attempted" :mastered="data.progress.mastered" />
      <div class="signal-legend selected-legend"><span class="unattempted">{{ uiText("未做") }}</span><span class="review">{{ uiText("待复习") }}</span><span class="mastered">{{ uiText("已掌握") }}</span><label><input v-model="showLabels" type="checkbox" />{{ uiText("显示原题标签") }}</label></div>
      <p v-if="!data.progress.total" class="empty-state">{{ uiText("当前筛选没有题目。可切换层级，或选择“查看全部匹配”；不会自动跳去其他学科。") }}</p>
      <article v-for="group in data.groups.filter((g) => g.questions.length)" :key="group.key" class="signal-group selected-group">
        <header><div><small>{{ group.rank }} · {{ uiText(labels[group.tier] || group.tier) }}</small><h2>{{ group.title }}</h2><p>{{ group.focus }}</p></div><button :disabled="loading" @click="start(group)">{{ uiText("刷这一组 →") }}</button></header>
        <HeatmapProgress :total="group.progress.total" :attempted="group.progress.attempted" :mastered="group.progress.mastered" />
        <div class="signal-question-grid selected-question-grid" :class="{ compact: !showLabels }">
          <button v-for="(question, index) in group.questions" :key="question.uuid" :data-type-group="question.type_group" :disabled="loading" :class="[question.state, { selected: route.query.question === question.uuid }]" :data-signal-question="question.uuid" :aria-label="`${question.label} · ${question.book} · ${question.state}`" :title="`${question.book}\n${question.label}\n${question.reason.join('；')}\n${question.question_mode} · ${question.answer_mode}`" @click="open(question)">
            <ExamTypeBadge :type="question.question_type" :group="question.type_group" /><strong>{{ showLabels ? question.label : index + 1 }}</strong><span class="selected-state">{{ question.state === 'mastered' ? uiText("已掌握") : question.state === 'review' ? uiText("待复习") : uiText("未做") }}</span>
            <template v-if="showLabels"><small>{{ question.book }}</small><small v-if="question.pdf_pages">{{ uiText("PDF 题") }} {{ question.pdf_pages.question }} {{ uiText("· 答") }} {{ question.pdf_pages.answer }} {{ uiText("· 对照") }} {{ question.pdf_pages.paired }} {{ uiText("页") }}</small><span>{{ question.question_mode }} · {{ question.answer_mode }}</span><em v-if="question.combined">{{ uiText("Z 变换＋初始条件") }}</em><em v-if="question.kind === 'concept'">{{ uiText("概念／简答") }}</em><em v-if="question.has_open_erratum">{{ uiText("有待处理勘误") }}</em><em v-if="question.scope_note">{{ uiText("原书部分超纲") }}</em></template>
          </button>
        </div>
      </article>
      <details class="signal-review selected-review"><summary>{{ uiText("待复核") }} {{ data.review_count }} {{ uiText("题：未混入严选刷题") }}</summary><p>{{ uiText("这些题已纳入盘点，但题意、深度、OCR 边界或考纲范围还不可靠，不凭章节号猜测。下面仅供查阅原题。") }}</p><ul><li v-for="item in data.review_items" :key="item.uuid"><RouterLink :to="`/practice/${item.uuid}`">{{ item.label }}</RouterLink> · {{ item.reason.join('；') }}</li></ul></details>
    </template>
  </SelectedCollectionLayout>
</template>
