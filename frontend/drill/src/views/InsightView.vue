<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../lib/api'
import type { InsightPayload } from '../types'
import LearningSharePanel from '../components/LearningSharePanel.vue'

const router = useRouter()
const route = useRoute()
const data = ref<InsightPayload | null>(null)
const loading = ref(true)
const pageLoading = ref(false)
const error = ref('')
const questionsPage = ref(Math.max(1, Number(route.query.questions_page) || 1))
const notesPage = ref(Math.max(1, Number(route.query.notes_page) || 1))
const expandedNotes = ref<Set<string>>(new Set())
const filterKeys = ['q', 'course', 'document', 'topic', 'state', 'error', 'start', 'end', 'has_note', 'sort'] as const
const filters = reactive(Object.fromEntries(filterKeys.map((key) => [
  key, String(route.query[key] || (key === 'sort' ? 'recent' : '')),
])) as Record<typeof filterKeys[number], string>)
const shareScope = computed(() => Object.fromEntries(
  (['q', 'course', 'document', 'topic', 'state', 'error', 'has_note', 'start', 'end'] as const)
    .filter((key) => filters[key]).map((key) => [key, filters[key]]),
))

function activeQuery() {
  return Object.fromEntries([
    ...filterKeys.map((key) => [key, filters[key]] as const),
    ['questions_page', questionsPage.value > 1 ? String(questionsPage.value) : ''],
    ['notes_page', notesPage.value > 1 ? String(notesPage.value) : ''],
  ].filter(([, value]) => value))
}

function openQuestion(uuid: string) {
  sessionStorage.setItem('drill.insight.scroll.v1', String(window.scrollY))
  const returnQuery = new URLSearchParams(activeQuery()).toString()
  void router.push({ path: `/practice/${uuid}`, query: { from: 'insight', insight_return: `/insight${returnQuery ? `?${returnQuery}` : ''}` } })
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

function toggleNote(uuid: string) {
  const next = new Set(expandedNotes.value)
  next.has(uuid) ? next.delete(uuid) : next.add(uuid)
  expandedNotes.value = next
}

async function load(initial = false) {
  if (initial) loading.value = true
  else pageLoading.value = true
  error.value = ''
  try {
    const query = new URLSearchParams(activeQuery()).toString()
    const payload = await api<InsightPayload>(`/api/drill/insight/${query ? `?${query}` : ''}`)
    data.value = payload
    questionsPage.value = payload.recent_questions.page
    notesPage.value = payload.recent_notes.page
    await router.replace({ query: activeQuery() })
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    loading.value = false
    pageLoading.value = false
  }
}

async function applyFilters() {
  questionsPage.value = 1
  notesPage.value = 1
  await load()
}

async function resetFilters() {
  filterKeys.forEach((key) => { filters[key] = '' })
  filters.sort = 'recent'
  await applyFilters()
}

async function changePage(kind: 'questions' | 'notes', page: number | null) {
  if (!page || loading.value || pageLoading.value) return
  if (kind === 'questions') questionsPage.value = page
  else notesPage.value = page
  await load()
}

onMounted(async () => {
  await load(true)
  const saved = Number(sessionStorage.getItem('drill.insight.scroll.v1'))
  if (Number.isFinite(saved)) {
    await nextTick()
    window.scrollTo({ top: saved })
    sessionStorage.removeItem('drill.insight.scroll.v1')
  }
})
</script>

<template>
  <section class="page insight-page">
    <header class="page-header"><div><span class="eyebrow">学习记录</span><h1>学习洞察</h1><p>按科目、诊断和笔记快速定位需要回看的题目。</p></div></header>
    <LearningSharePanel :current-scope="shareScope" />
    <form class="insight-filters" @submit.prevent="applyFilters">
      <label class="wide">关键词<input v-model="filters.q" type="search" placeholder="题号、章节或 Note 内容"></label>
      <label v-if="data?.options.courses.length">科目<select v-model="filters.course"><option value="">全部科目</option><option v-for="item in data.options.courses" :key="item.code" :value="item.code">{{ item.label }}</option></select></label>
      <label>书籍<select v-model="filters.document"><option value="">全部书籍</option><option v-for="item in data?.options.documents || []" :key="item.id" :value="item.id">{{ item.label }}</option></select></label>
      <label>章节<select v-model="filters.topic"><option value="">全部章节</option><option v-for="item in data?.options.topics || []" :key="item.id" :value="item.id">{{ item.label }}</option></select></label>
      <label>题目状态<select v-model="filters.state"><option value="">全部状态</option><option value="mastered">已掌握</option><option value="review">待复习</option></select></label>
      <label>诊断<select v-model="filters.error"><option value="">全部诊断</option><option v-for="item in data?.options.errors || []" :key="item.code" :value="item.code">{{ item.code }} · {{ item.label }}</option></select></label>
      <label>笔记<select v-model="filters.has_note"><option value="">不限</option><option value="1">有 Note</option><option value="0">无 Note</option></select></label>
      <label>开始日期<input v-model="filters.start" type="date"></label>
      <label>结束日期<input v-model="filters.end" type="date"></label>
      <label>排序<select v-model="filters.sort"><option value="recent">最近更新</option><option value="oldest">最早记录</option></select></label>
      <div class="filter-actions"><button type="submit">应用筛选</button><button type="button" @click="resetFilters">清空</button></div>
    </form>
    <p v-if="error" class="error-state">{{ error }}</p>
    <div v-else-if="loading" class="question-skeleton">正在加载学习记录…</div>
    <template v-else-if="data">
      <section class="marker-overview"><header><div><span class="eyebrow">学习标记</span><h2>标记概览</h2></div><small>仅统计当前用户的完整题目历史。</small></header><div><button v-for="marker in data.marker_stats" :key="marker.code" :disabled="!marker.count" @click="router.push({ path: '/practice', query: { marker: marker.code } })"><span>{{ marker.label }}</span><strong>{{ marker.count }}</strong><small>查看题目 →</small></button></div></section>
      <div class="insight-grid">
        <section :class="{ 'is-loading': pageLoading }"><header><span>近期作答</span><strong>{{ data.recent_questions.count }}</strong></header><div class="insight-list"><button v-for="item in data.recent_questions.results" :key="`${item.uuid}-${item.created_at}`" @click="openQuestion(item.uuid)"><span><strong>{{ item.label }}</strong><small>{{ item.document }} · {{ item.topic }}</small><small v-if="item.diagnoses.length">诊断 {{ item.diagnoses.join(' / ') }}</small></span><span><em :class="`text-${item.result === 'review' ? 'review' : 'mastered'}`">{{ item.result === 'review' ? '待复习' : '已掌握' }}</em><time>{{ formatTime(item.created_at) }}</time></span></button><p v-if="!data.recent_questions.results.length">当前筛选下没有作答记录。</p></div><footer class="insight-pagination"><button :disabled="!data.recent_questions.previous_page || pageLoading" @click="changePage('questions', data.recent_questions.previous_page)">上一页</button><span>{{ data.recent_questions.page }} / {{ data.recent_questions.total_pages }}</span><button :disabled="!data.recent_questions.next_page || pageLoading" @click="changePage('questions', data.recent_questions.next_page)">下一页</button></footer></section>
        <section :class="{ 'is-loading': pageLoading }"><header><span>题目笔记 Note</span><strong>{{ data.recent_notes.count }}</strong></header><div class="insight-list note-list"><article v-for="item in data.recent_notes.results" :key="item.uuid"><header><button type="button" @click="openQuestion(item.uuid)"><strong>{{ item.label }}</strong><small>{{ item.document }} · {{ item.topic }}</small></button><time>{{ formatTime(item.updated_at) }}</time></header><p :class="{ expanded: expandedNotes.has(item.uuid) }">{{ item.note }}</p><footer><span>{{ item.primary_error ? `诊断 ${item.primary_error}` : '无结构化诊断' }}</span><button v-if="item.note.length > 90" type="button" @click="toggleNote(item.uuid)">{{ expandedNotes.has(item.uuid) ? '收起' : '展开全文' }}</button><button type="button" @click="openQuestion(item.uuid)">进入原题 →</button></footer></article><p v-if="!data.recent_notes.results.length">当前筛选下没有题目笔记。</p></div><footer class="insight-pagination"><button :disabled="!data.recent_notes.previous_page || pageLoading" @click="changePage('notes', data.recent_notes.previous_page)">上一页</button><span>{{ data.recent_notes.page }} / {{ data.recent_notes.total_pages }}</span><button :disabled="!data.recent_notes.next_page || pageLoading" @click="changePage('notes', data.recent_notes.next_page)">下一页</button></footer></section>
      </div>
    </template>
  </section>
</template>
