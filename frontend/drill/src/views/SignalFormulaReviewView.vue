<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, post } from '../lib/api'
import MarkdownAnswer from '../components/MarkdownAnswer.vue'

type Grade = 'A' | 'B' | 'C'
type Mastery = { grade: Grade; last_reviewed_on: string; next_review_on: string | null; due_dates: string[]; review_count: number }
type Formula = {
  key: string
  section: string
  title: string
  formulas: string[]
  condition: string
  principle: string
  pitfall: string
  tags: string[]
  mastery: Mastery | null
}
type Application = { kind: string; uuid: string; label: string; book: string; bucket: string; tier: string; state: string; reason: string[]; route: string }
type Payload = {
  track: 'signal' | 'four'
  track_title: string
  date: string
  day_number: number
  cycle_day: number
  title: string
  topic: string
  subject: string
  return_route: string
  duration_minutes: number
  recall: Formula[]
  core: Formula[]
  applications: Application[]
  mistakes: string[]
  weak_review: Formula[]
  due_keys: string[]
  has_history: boolean
  formula_count: number
  formula_counts?: Record<string, number>
  answer_policy: string
}

const data = ref<Payload | null>(null)
const route = useRoute()
const router = useRouter()
const track = ref<'signal' | 'four'>(route.query.track === 'four' ? 'four' : 'signal')
const loading = ref(true)
const error = ref('')
const recallIndex = ref(0)
const revealed = ref<Record<string, boolean>>({})
const drafts = ref<Record<string, string>>({})
const saving = ref('')
const current = computed(() => data.value?.recall[recallIndex.value] || null)
const completedCount = computed(() => data.value?.recall.filter((item) => Boolean(item.mastery?.last_reviewed_on === data.value?.date)).length || 0)

function formulaMarkdown(item: Formula) {
  return item.formulas.map((formula) => `$$\n${formula}\n$$`).join('\n\n')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api<Payload>(`/api/drill/signal-formulas/?track=${track.value}`)
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    loading.value = false
  }
}

async function switchTrack(value: 'signal' | 'four') {
  if (track.value === value) return
  track.value = value
  recallIndex.value = 0
  revealed.value = {}
  drafts.value = {}
  await router.replace({ query: { ...route.query, track: value } })
  await load()
}

async function grade(item: Formula, value: Grade) {
  if (!data.value) return
  saving.value = item.key
  error.value = ''
  try {
    const updated = await post<Formula>('/api/drill/signal-formulas/', {
      formula_key: item.key,
      grade: value,
      date: data.value.date,
    })
    const replace = (items: Formula[]) => items.map((entry) => entry.key === updated.key ? updated : entry)
    data.value.recall = replace(data.value.recall)
    data.value.core = replace(data.value.core)
    data.value.weak_review = replace(data.value.weak_review)
    if (recallIndex.value < data.value.recall.length - 1) recallIndex.value += 1
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    saving.value = ''
  }
}

function reveal(item: Formula) {
  revealed.value[item.key] = true
}

onMounted(load)
</script>

<template>
  <section class="page formula-review-page">
    <header class="page-header">
      <div>
        <span class="eyebrow">892 · DAILY FORMULA LOOP · {{ data?.track_title || uiText("公式复习") }}</span>
        <h1>{{ data?.title || uiText("892 信号与系统｜每日公式复习") }}</h1>
        <p v-if="data">{{ uiText("四天循环第") }} {{ data.cycle_day }} {{ uiText("天 · 约") }} {{ data.duration_minutes }} {{ uiText("分钟 · 固定公式库") }} {{ data.formula_count }} {{ data.track === 'four' ? uiText("条") : uiText("组") }}</p>
      </div>
      <RouterLink class="selected-link" :to="data?.return_route || '/signal-selected'">{{ uiText("回到") }}{{ data?.topic || uiText("信号") }}{{ uiText("严选 →") }}</RouterLink>
    </header>

    <nav class="track-switch" :aria-label="uiText('公式复习循环')">
      <button :class="{ active: track === 'signal' }" @click="switchTrack('signal')"><strong>{{ uiText("信号与系统") }}</strong><small>{{ uiText("独立四日循环") }}</small></button>
      <button :class="{ active: track === 'four' }" @click="switchTrack('four')"><strong>{{ uiText("其他四科") }}</strong><small>{{ uiText("电路 · 模电 · 数电 · 通信") }}</small></button>
    </nav>

    <p v-if="error" role="alert" class="error">{{ uiText(error) }}</p>
    <p v-if="loading" role="status">{{ uiText("正在生成今日训练…") }}</p>

    <template v-if="data">
      <section class="today-overview">
        <div><small>{{ uiText("今日专题") }}</small><strong>{{ data.topic }}</strong></div>
        <div><small>闭卷进度</small><strong>{{ completedCount }} / 5</strong></div>
        <div><small>{{ uiText("应用题") }}</small><strong>{{ data.applications.length }} {{ uiText("道") }}{{ data.topic }}严选原题</strong></div>
        <div v-if="data.formula_counts" class="formula-counts"><small>{{ uiText("完整四科底稿") }}</small><strong>{{ uiText("电路") }} {{ data.formula_counts.circuit }} {{ uiText("· 模电") }} {{ data.formula_counts.analog }} {{ uiText("· 数电") }} {{ data.formula_counts.digital }} {{ uiText("· 通信") }} {{ data.formula_counts.communication }}</strong></div>
        <p>{{ data.answer_policy }}</p>
      </section>

      <section class="review-block recall-block">
        <header>
          <div><span>{{ uiText("01 · 5 分钟") }}</span><h2>{{ uiText("闭卷默写") }}</h2><p>{{ uiText("一次只做一道。先写答案，再揭示公式并自评。") }}</p></div>
          <strong>{{ recallIndex + 1 }} / {{ data.recall.length }}</strong>
        </header>
        <nav class="recall-tabs" :aria-label="uiText('闭卷默写题目')">
          <button v-for="(item, index) in data.recall" :key="item.key" :class="{ active: index === recallIndex, graded: item.mastery?.last_reviewed_on === data.date }" @click="recallIndex = index">{{ index + 1 }}</button>
        </nav>
        <article v-if="current" class="recall-card">
          <small>{{ current.section }} · {{ current.tags.includes('fourier') ? uiText("傅里叶必查") : uiText("今日专题") }}</small>
          <h3>{{ current.title }}</h3>
          <p>{{ uiText("请默写完整公式，并在脑中说明适用条件。") }}</p>
          <textarea v-model="drafts[current.key]" rows="5" :aria-label="`${current.title} 默写答案`" :placeholder="uiText('在这里默写；也可以在纸上完成后直接揭示答案。')" />
          <button v-if="!revealed[current.key]" class="reveal-button" @click="reveal(current)">{{ uiText("揭示答案") }}</button>
          <div v-else class="revealed-answer">
            <MarkdownAnswer :source="formulaMarkdown(current)" />
            <dl><div><dt>{{ uiText("适用条件") }}</dt><dd>{{ current.condition }}</dd></div><div><dt>{{ uiText("易错点") }}</dt><dd>{{ current.pitfall }}</dd></div></dl>
            <div class="grade-actions">
              <span>{{ uiText("本次掌握：") }}</span>
              <button :disabled="saving === current.key" @click="grade(current, 'A')"><b>A</b> {{ uiText("熟练") }}</button>
              <button :disabled="saving === current.key" @click="grade(current, 'B')"><b>B</b> {{ uiText("基本会") }}</button>
              <button :disabled="saving === current.key" @click="grade(current, 'C')"><b>C</b> {{ uiText("答错／遗忘") }}</button>
            </div>
          </div>
        </article>
      </section>

      <section class="review-block">
        <header><div><span>{{ uiText("02 · 5 分钟") }}</span><h2>{{ uiText("核心公式复习") }}</h2><p>{{ uiText("完整公式、条件、原理和典型误判点。") }}</p></div></header>
        <div class="core-grid">
          <details v-for="(item, index) in data.core" :key="item.key" :open="index === 0">
            <summary><span>{{ String(index + 1).padStart(2, '0') }}</span><strong>{{ item.title }}</strong><em v-if="item.mastery">{{ item.mastery.grade }}</em></summary>
            <MarkdownAnswer :source="formulaMarkdown(item)" />
            <dl>
              <div><dt>{{ uiText("适用条件") }}</dt><dd>{{ item.condition }}</dd></div>
              <div><dt>{{ uiText("原理") }}</dt><dd>{{ item.principle }}</dd></div>
              <div><dt>{{ uiText("误判点") }}</dt><dd>{{ item.pitfall }}</dd></div>
            </dl>
          </details>
        </div>
      </section>

      <section class="review-block">
        <header><div><span>{{ uiText("03 · 8–10 分钟") }}</span><h2>{{ uiText("892 应用计算") }}</h2><p>{{ uiText("直接复用今日科目严选中的原题、答案和你的历史记录，不重复建题。") }}</p></div></header>
        <div class="application-grid">
          <RouterLink v-for="item in data.applications" :key="item.uuid" :to="item.route" class="application-card">
            <div><span>{{ item.kind }}</span><em :class="item.state">{{ item.state === 'mastered' ? uiText("已掌握") : item.state === 'review' ? uiText("待复习") : uiText("未做") }}</em></div>
            <h3>{{ item.label }}</h3>
            <p>{{ item.book }}</p>
            <small>{{ item.reason.join('；') }}</small>
            <b>{{ uiText("进入原题作答 →") }}</b>
          </RouterLink>
        </div>
      </section>

      <section class="review-block error-review">
        <header><div><span>{{ uiText("04 · 2 分钟") }}</span><h2>{{ uiText("错误复习") }}</h2><p v-if="!data.has_history">{{ uiText("目前没有公式历史数据，按规则使用默认薄弱项，不虚构掌握状态。") }}</p><p v-else>{{ uiText("优先安排到期的 B/C 类公式。") }}</p></div></header>
        <div class="mistake-grid">
          <article><h3>{{ uiText("今日 3 个易错点") }}</h3><ol><li v-for="item in data.mistakes" :key="item">{{ item }}</li></ol></article>
          <article><h3>{{ uiText("针对性公式") }}</h3><ul><li v-for="item in data.weak_review" :key="item.key"><strong>{{ item.title }}</strong><span v-if="item.mastery">{{ item.mastery.grade }} {{ uiText("· 下次") }} {{ item.mastery.next_review_on || uiText("待安排") }}</span><span v-else>{{ uiText("默认检查项 · 尚无历史评级") }}</span></li></ul></article>
        </div>
      </section>
    </template>
  </section>
</template>

<style scoped>
.formula-review-page { max-width: 1120px; }
.selected-link { min-height: 38px; padding: 0 14px; border: 1px solid var(--border-default); border-radius: var(--radius-sm); color: var(--text-primary); text-decoration: none; display: inline-flex; align-items: center; }
.track-switch { margin: 18px 0; display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 10px; }.track-switch button { padding: 13px 15px; border: 1px solid var(--border-default); border-radius: var(--radius-sm); color: var(--text-primary); background: var(--bg-surface); cursor: pointer; display: grid; gap: 4px; text-align: left; }.track-switch button.active { border-color: var(--accent); background: color-mix(in srgb,var(--accent) 10%,var(--bg-surface)); }.track-switch small { color: var(--text-tertiary); }
.today-overview { margin: 18px 0 28px; padding: 16px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: var(--bg-surface); display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 12px; }
.today-overview div { padding: 12px; border-left: 2px solid var(--accent); display: grid; gap: 6px; }.today-overview small { color: var(--text-tertiary); }.today-overview strong { font-size: 16px; }.today-overview p { grid-column: 1/-1; margin: 0; color: var(--text-secondary); }
.today-overview .formula-counts { grid-column: 1/-1; }
.review-block { margin: 24px 0; padding: 20px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: var(--bg-surface); }
.review-block > header { display: flex; justify-content: space-between; gap: 16px; align-items: start; }.review-block > header span { color: var(--accent); font: 600 11px ui-monospace,monospace; }.review-block h2 { margin: 5px 0; font-size: 22px; }.review-block header p { color: var(--text-secondary); }
.recall-tabs { margin: 18px 0 12px; display: flex; gap: 8px; }.recall-tabs button { width: 34px; height: 34px; border: 1px solid var(--border-default); border-radius: 50%; color: var(--text-secondary); background: var(--bg-sidebar); cursor: pointer; }.recall-tabs button.active { border-color: var(--accent); color: var(--text-primary); }.recall-tabs button.graded { background: color-mix(in srgb,var(--success) 18%,var(--bg-sidebar)); }
.recall-card { padding: 18px; border: 1px solid var(--border-default); border-radius: var(--radius-sm); }.recall-card h3 { margin: 8px 0; font-size: 20px; }.recall-card > small { color: var(--accent); }.recall-card textarea { width: 100%; margin: 12px 0; padding: 12px; resize: vertical; border: 1px solid var(--border-default); border-radius: var(--radius-sm); color: var(--text-primary); background: var(--bg-sidebar); font-family: ui-monospace,monospace; }
.reveal-button,.grade-actions button { min-height: 36px; padding: 8px 12px; border: 1px solid var(--border-default); border-radius: var(--radius-sm); color: var(--text-primary); background: var(--bg-sidebar); cursor: pointer; }.reveal-button:disabled { opacity: .45; cursor: not-allowed; }
.revealed-answer { margin-top: 12px; padding-top: 14px; border-top: 1px solid var(--border-subtle); }.revealed-answer dl,.core-grid dl { display: grid; gap: 8px; }.revealed-answer dl div,.core-grid dl div { display: grid; grid-template-columns: 76px 1fr; gap: 10px; }.revealed-answer dt,.core-grid dt { color: var(--text-tertiary); }.revealed-answer dd,.core-grid dd { margin: 0; line-height: 1.65; }
.grade-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 14px; }.grade-actions button b { margin-right: 4px; color: var(--accent); }
.core-grid { margin-top: 16px; display: grid; gap: 9px; }.core-grid details { border: 1px solid var(--border-default); border-radius: var(--radius-sm); padding: 12px; }.core-grid summary { cursor: pointer; display: flex; gap: 10px; align-items: center; }.core-grid summary span { color: var(--accent); }.core-grid summary em { margin-left: auto; font-style: normal; color: var(--warning); }
.application-grid { margin-top: 16px; display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px; }.application-card { padding: 16px; border: 1px solid var(--border-default); border-radius: var(--radius-sm); color: var(--text-primary); text-decoration: none; display: grid; gap: 9px; }.application-card:hover { border-color: var(--accent); }.application-card > div { display: flex; justify-content: space-between; }.application-card span { color: var(--accent); }.application-card em { font-style: normal; color: var(--text-tertiary); }.application-card em.review { color: var(--warning); }.application-card em.mastered { color: var(--success); }.application-card h3,.application-card p { margin: 0; }.application-card p,.application-card small { color: var(--text-secondary); }.application-card b { margin-top: 6px; }
.mistake-grid { margin-top: 14px; display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px; }.mistake-grid article { padding: 14px; border: 1px solid var(--border-default); border-radius: var(--radius-sm); }.mistake-grid li { margin: 10px 0; line-height: 1.6; }.mistake-grid ul { list-style: none; padding: 0; }.mistake-grid ul li { display: grid; gap: 4px; }.mistake-grid ul span { color: var(--text-tertiary); font-size: 12px; }
@media (max-width: 720px) { .track-switch,.today-overview,.application-grid,.mistake-grid { grid-template-columns: 1fr; }.today-overview p,.today-overview .formula-counts { grid-column: auto; }.review-block { padding: 13px; }.page-header { gap: 12px; }.revealed-answer dl div,.core-grid dl div { grid-template-columns: 1fr; gap: 3px; } }
</style>
