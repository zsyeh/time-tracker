<script setup lang="ts">
import { uiText } from '../lib/uiText'
import { computed, onMounted, ref, watch } from 'vue'
import { api, post } from '../lib/api'
import { notifyPracticeTrendChanged } from '../lib/practiceTrend'
import type { ErrorCode } from '../types'

type Course = {
  code: string
  label: string
  question_max_page: number
  paired_max_page: number
}
type Match = {
  uuid: string
  label: string
  book: string
  matched_by: { book: 'question' | 'paired'; page: number }[]
  route: string
}
type Preview = {
  action: 'preview' | 'apply'
  course_label: string
  result: 'correct' | 'review'
  matched_count: number
  created_count: number
  unmatched_question_pages: number[]
  unmatched_paired_pages: number[]
  stale_mapping_count: number
  questions: Match[]
}

const emit = defineEmits<{ applied: [] }>()
const courses = ref<Course[]>([])
const course = ref('')
const questionPages = ref('')
const pairedPages = ref('')
const result = ref<'correct' | 'review'>('correct')
const preview = ref<Preview | null>(null)
const loading = ref(false)
const error = ref('')
const message = ref('')
const errorOptions: Array<{ code: ErrorCode; label: string }> = [
  { code: 'A', label: '知识断层' }, { code: 'B1', label: '想不起来' },
  { code: 'B2', label: '不会启动' }, { code: 'B3', label: '不会组合' },
  { code: 'C1', label: '计算错误' }, { code: 'C2', label: '符号/方向/单位' },
  { code: 'C3', label: '边界/条件错误' }, { code: 'D', label: '看解析仍不懂' },
]
const selectedErrors = ref<ErrorCode[]>([])
const primaryError = ref<ErrorCode | null>(null)
const knowledgeLevel = ref<'K0' | 'K1' | 'K2' | null>(null)
const methodLevel = ref<'M0' | 'M1' | 'M2' | null>(null)
const executionLevel = ref<'E0' | 'E1' | 'E2' | null>(null)
const usedHint = ref(false)
const viewedAnswer = ref(false)
const note = ref('')

const selectedCourse = computed(() => courses.value.find((item) => item.code === course.value))
const payload = (action: 'preview' | 'apply') => ({
  action,
  course: course.value,
  question_pages: questionPages.value,
  paired_pages: pairedPages.value,
  result: result.value,
  error_codes: result.value === 'review' ? selectedErrors.value : [],
  primary_error: result.value === 'review' ? primaryError.value : null,
  knowledge_level: knowledgeLevel.value,
  method_level: methodLevel.value,
  execution_level: executionLevel.value,
  used_hint: usedHint.value,
  viewed_answer: viewedAnswer.value,
  is_independent: !usedHint.value && !viewedAnswer.value,
  note: note.value,
})

watch([course, questionPages, pairedPages, result, selectedErrors, primaryError, knowledgeLevel, methodLevel, executionLevel, usedHint, viewedAnswer, note], () => {
  preview.value = null
  error.value = ''
  message.value = ''
})

watch(result, (value) => {
  if (value === 'correct') {
    selectedErrors.value = []
    primaryError.value = null
  }
})

function toggleError(code: ErrorCode) {
  if (selectedErrors.value.includes(code)) {
    selectedErrors.value = selectedErrors.value.filter((item) => item !== code)
    if (primaryError.value === code) primaryError.value = selectedErrors.value[0] || null
  } else {
    selectedErrors.value = [...selectedErrors.value, code]
    primaryError.value ||= code
  }
}

async function loadConfig() {
  try {
    const data = await api<{ courses: Course[] }>('/api/drill/pdf-page-status/')
    courses.value = data.courses
    course.value ||= data.courses[0]?.code || ''
  } catch (reason) {
    error.value = (reason as Error).message
  }
}

async function run(action: 'preview' | 'apply') {
  loading.value = true
  error.value = ''
  message.value = ''
  try {
    const data = await post<Preview>('/api/drill/pdf-page-status/', payload(action))
    preview.value = data
    if (action === 'apply') {
      message.value = data.created_count
        ? `已保存 ${data.created_count} 道题的状态与诊断记录。`
        : '没有可写入的匹配题目。'
      notifyPracticeTrendChanged()
      emit('applied')
    }
  } catch (reason) {
    error.value = (reason as Error).message
  } finally {
    loading.value = false
  }
}

function matchLabel(item: Match) {
  return item.matched_by.map((match) => `${match.book === 'question' ? '题目册' : '对照册'} P${match.page}`).join(' · ')
}

onMounted(loadConfig)
</script>

<template>
  <section class="pdf-page-status" aria-labelledby="pdf-page-status-title">
    <header>
      <div>
        <span class="kicker">PDF PAGE STATUS</span>
        <h2 id="pdf-page-status-title">{{ uiText("按 PDF 页码批量记录") }}</h2>
        <p>{{ uiText("题目册与题答对照册页码分别输入。先预览匹配，再追加 Mastered / Need to review；不会覆盖历史记录。") }}</p>
      </div>
      <span class="safe-badge">{{ uiText("先预览 · 后写入") }}</span>
    </header>

    <div class="page-status-form">
      <label>
        <span>{{ uiText("科目") }}</span>
        <select v-model="course" :disabled="loading">
          <option v-for="item in courses" :key="item.code" :value="item.code">{{ item.label }}</option>
        </select>
      </label>
      <label>
        <span>{{ uiText("题目册页码") }}</span>
        <input v-model="questionPages" :disabled="loading" inputmode="numeric" :placeholder="uiText('例如 12, 15-18')" />
        <small v-if="selectedCourse">已映射页码至 P{{ selectedCourse.question_max_page }}</small>
      </label>
      <label>
        <span>{{ uiText("题答对照册页码") }}</span>
        <input v-model="pairedPages" :disabled="loading" inputmode="numeric" :placeholder="uiText('例如 20, 23-26')" />
        <small v-if="selectedCourse">已映射页码至 P{{ selectedCourse.paired_max_page }}</small>
      </label>
      <fieldset>
        <legend>{{ uiText("记录为") }}</legend>
        <label><input v-model="result" type="radio" value="correct" :disabled="loading" /> {{ uiText("Mastered") }}</label>
        <label><input v-model="result" type="radio" value="review" :disabled="loading" /> Need to review</label>
      </fieldset>
      <div class="form-actions">
        <button class="preview-button" type="button" :disabled="loading || !course" @click="run('preview')">
          {{ loading ? '处理中…' : uiText("预览匹配") }}
        </button>
        <button class="direct-submit-button" type="button" :disabled="loading || !course || (!questionPages.trim() && !pairedPages.trim())" @click="run('apply')">
{{ uiText("直接提交") }} </button>
      </div>
    </div>

    <details class="page-diagnosis">
      <summary><span>{{ uiText("本批次能力诊断") }}</span><small>{{ uiText("无需单独提交，将和掌握状态一起保存") }}</small></summary>
      <div class="independence-row"><label><input v-model="usedHint" type="checkbox" /> {{ uiText("使用过提示") }}</label><label><input v-model="viewedAnswer" type="checkbox" /> {{ uiText("查看过答案") }}</label><b>{{ usedHint || viewedAnswer ? uiText("非独立作答") : uiText("独立作答") }}</b></div>
      <div v-if="result === 'review'" class="page-error-picker"><button v-for="item in errorOptions" :key="item.code" type="button" :class="{ active: selectedErrors.includes(item.code) }" @click="toggleError(item.code)"><b>{{ item.code }}</b>{{ uiText(item.label) }}</button></div>
      <label v-if="result === 'review' && selectedErrors.length" class="primary-error">{{ uiText("主要原因") }}<select v-model="primaryError"><option v-for="code in selectedErrors" :key="code" :value="code">{{ code }} · {{ errorOptions.find((item) => item.code === code)?.label }}</option></select></label>
      <div class="page-levels"><label>{{ uiText("知识提取") }}<select v-model="knowledgeLevel"><option :value="null">{{ uiText("未知") }}</option><option value="K0">{{ uiText("K0 不知道") }}</option><option value="K1">{{ uiText("K1 回忆不完整") }}</option><option value="K2">{{ uiText("K2 准确提取") }}</option></select></label><label>{{ uiText("方法启动") }}<select v-model="methodLevel"><option :value="null">{{ uiText("未知") }}</option><option value="M0">{{ uiText("M0 无法开始") }}</option><option value="M1">{{ uiText("M1 需要提示") }}</option><option value="M2">{{ uiText("M2 自主确定路径") }}</option></select></label><label>{{ uiText("执行验证") }}<select v-model="executionLevel"><option :value="null">{{ uiText("未知") }}</option><option value="E0">{{ uiText("E0 无法完成") }}</option><option value="E1">{{ uiText("E1 完成但有误") }}</option><option value="E2">{{ uiText("E2 正确并验证") }}</option></select></label></div>
      <label class="batch-note">{{ uiText("题目笔记 Note") }}<textarea v-model="note" maxlength="20000" :placeholder="uiText('可选：本批次匹配到的每道题都会追加这段 Note；不会覆盖已有笔记。')" /></label>
    </details>

    <p v-if="error" class="page-status-error" role="alert">{{ uiText(error) }}</p>
    <p v-if="message" class="page-status-success" role="status">{{ message }}</p>

    <div v-if="preview" class="preview-result">
      <div class="preview-summary">
        <div><small>{{ uiText("匹配题目") }}</small><strong>{{ preview.matched_count }}</strong></div>
        <div><small>{{ uiText("将记录为") }}</small><strong>{{ preview.result === 'correct' ? uiText("Mastered") : 'Need to review' }}</strong></div>
        <div><small>{{ uiText("未匹配页") }}</small><strong>{{ preview.unmatched_question_pages.length + preview.unmatched_paired_pages.length }}</strong></div>
      </div>
      <p v-if="preview.unmatched_question_pages.length || preview.unmatched_paired_pages.length" class="unmatched-warning">
{{ uiText("未匹配，不会写入：") }} <span v-if="preview.unmatched_question_pages.length">{{ uiText("题目册 P") }}{{ preview.unmatched_question_pages.join(', ') }}</span>
        <span v-if="preview.unmatched_paired_pages.length">{{ uiText("题答对照册 P") }}{{ preview.unmatched_paired_pages.join(', ') }}</span>
      </p>
      <p v-if="preview.stale_mapping_count" class="unmatched-warning">{{ uiText("另有") }} {{ preview.stale_mapping_count }} {{ uiText("道题因题库指纹变化被安全跳过。") }}</p>
      <ol v-if="preview.questions.length" class="match-list">
        <li v-for="item in preview.questions" :key="item.uuid">
          <span><strong>{{ item.label }}</strong><small>{{ item.book }}</small></span>
          <span class="match-actions"><b>{{ matchLabel(item) }}</b><RouterLink :to="item.route">{{ uiText("进入题目 →") }}</RouterLink></span>
        </li>
      </ol>
      <button v-if="preview.action === 'preview' && preview.matched_count" class="apply-button" type="button" :disabled="loading" @click="run('apply')">
{{ uiText("确认追加") }} {{ preview.matched_count }} {{ uiText("道记录") }} </button>
    </div>
  </section>
</template>

<style scoped>
.pdf-page-status { margin: 18px 0 22px; padding: 22px; border: 1px solid #d9dee5; border-radius: 16px; background: #fff; box-shadow: 0 10px 30px #1d2b3a0a; color: #1f2933; }
.pdf-page-status header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 18px; }
.pdf-page-status h2 { margin: 3px 0 5px; font-size: 20px; }
.pdf-page-status header p { max-width: 760px; margin: 0; color: #66717d; font-size: 13px; line-height: 1.6; }
.kicker { color: #19746e; font-size: 10px; font-weight: 800; letter-spacing: .14em; }
.safe-badge { flex: none; padding: 7px 10px; border-radius: 999px; background: #eaf7f3; color: #176b5f; font-size: 11px; font-weight: 700; }
.page-status-form { display: grid; grid-template-columns: minmax(130px, .7fr) repeat(2, minmax(190px, 1fr)) minmax(190px, 1fr) auto; align-items: end; gap: 12px; }
.page-status-form > label { display: grid; gap: 6px; min-width: 0; }
.page-status-form > label > span, fieldset legend { color: #5d6875; font-size: 11px; font-weight: 800; letter-spacing: .05em; }
.page-status-form select, .page-status-form > label input { box-sizing: border-box; width: 100%; height: 42px; padding: 0 11px; border: 1px solid #c9d0d9; border-radius: 9px; background: #fff; color: inherit; font: inherit; }
.page-status-form small { color: #88919b; font-size: 10px; }
fieldset { display: flex; align-items: center; gap: 10px; min-height: 42px; margin: 0; padding: 4px 10px; border: 1px solid #c9d0d9; border-radius: 9px; }
fieldset legend { padding: 0 4px; }
fieldset label { display: flex; align-items: center; gap: 4px; color: #34404c; font-size: 12px; white-space: nowrap; }
.form-actions { display: flex; gap: 8px; }
.page-diagnosis { margin-top: 12px; padding: 10px 12px; border: 1px solid #d9dee5; border-radius: 10px; }
.page-diagnosis summary { display: flex; align-items: center; justify-content: space-between; gap: 10px; cursor: pointer; font-size: 12px; font-weight: 750; }
.page-diagnosis summary small { color: #71808d; font-size: 10px; font-weight: 500; }
.independence-row { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin-top: 12px; font-size: 11px; }
.independence-row label { display: flex; align-items: center; gap: 5px; }
.independence-row b { color: #19746e; }
.page-error-picker { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; margin-top: 10px; }
.page-error-picker button { min-height: 38px; border: 1px solid #c9d0d9; border-radius: 7px; background: #fff; color: #34404c; cursor: pointer; font-size: 11px; }
.page-error-picker button b { margin-right: 5px; }
.page-error-picker button.active { border-color: #b27a12; background: #fff7e5; }
.primary-error { display: grid; gap: 5px; margin-top: 10px; color: #5d6875; font-size: 11px; }
.primary-error select, .page-levels select { padding: 8px; border: 1px solid #c9d0d9; border-radius: 7px; background: #fff; color: #34404c; }
.page-levels { display: grid; grid-template-columns: repeat(3, 1fr); gap: 7px; margin-top: 10px; }
.page-levels label { display: grid; gap: 5px; color: #5d6875; font-size: 11px; }
.batch-note { margin-top: 10px; display: grid; gap: 5px; color: #5d6875; font-size: 11px; }
.batch-note textarea { min-height: 76px; padding: 9px; resize: vertical; border: 1px solid #c9d0d9; border-radius: 7px; background: #fff; color: #34404c; font: inherit; }
.preview-button, .direct-submit-button, .apply-button { min-height: 42px; padding: 0 16px; border: 0; border-radius: 9px; background: #24384c; color: #fff; font-weight: 750; cursor: pointer; white-space: nowrap; }
.direct-submit-button, .apply-button { background: #16725b; }
.preview-button:disabled, .direct-submit-button:disabled, .apply-button:disabled { cursor: wait; opacity: .55; }
.page-status-error, .page-status-success, .unmatched-warning { margin: 14px 0 0; padding: 10px 12px; border-radius: 8px; font-size: 12px; }
.page-status-error, .unmatched-warning { background: #fff3e7; color: #8a4a13; }
.page-status-success { background: #eaf7f0; color: #176b43; }
.unmatched-warning span + span::before { content: ' · '; }
.preview-result { margin-top: 16px; padding-top: 16px; border-top: 1px solid #e1e5ea; }
.preview-summary { display: grid; grid-template-columns: repeat(3, minmax(100px, 1fr)); gap: 10px; }
.preview-summary > div { padding: 11px 13px; border-radius: 10px; background: #f4f6f8; }
.preview-summary small { display: block; margin-bottom: 5px; color: #727d88; }
.preview-summary strong { font-size: 17px; }
.match-list { max-height: 260px; margin: 13px 0; padding: 0; overflow: auto; border: 1px solid #e0e4e9; border-radius: 10px; list-style: none; }
.match-list li { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 9px 11px; border-bottom: 1px solid #edf0f3; font-size: 12px; }
.match-list li:last-child { border-bottom: 0; }
.match-list span { min-width: 0; }
.match-list strong, .match-list small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.match-list small { margin-top: 2px; color: #7c8792; }
.match-list b { flex: none; color: #19746e; }
.match-actions { display: flex; flex: none; align-items: center; gap: 12px; }
.match-actions a { padding: 5px 8px; border: 1px solid #9dc9c0; border-radius: 7px; color: #12695e; font-size: 11px; font-weight: 750; text-decoration: none; white-space: nowrap; }
@media (max-width: 1050px) { .page-status-form { grid-template-columns: repeat(2, minmax(0, 1fr)); } .preview-button { width: 100%; } }
@media (max-width: 620px) {
  .pdf-page-status { padding: 16px; border-radius: 12px; }
  .pdf-page-status header { display: block; }
  .safe-badge { display: inline-block; margin-top: 10px; }
  .page-status-form { grid-template-columns: 1fr; }
  .preview-summary { grid-template-columns: 1fr; }
  .match-list li { align-items: flex-start; }
  .form-actions { display: grid; grid-template-columns: 1fr 1fr; }
  .match-actions { align-items: flex-end; flex-direction: column; gap: 5px; }
  .page-error-picker { grid-template-columns: repeat(2, 1fr); }
  .page-levels { grid-template-columns: 1fr; }
}
</style>
