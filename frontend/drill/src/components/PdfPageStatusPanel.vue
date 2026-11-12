<script setup lang="ts">
import { uiText } from '../lib/uiText'
import DiagnosisSelector from './DiagnosisSelector.vue'
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
        <button class="direct-submit-button" :class="{ secondary: preview }" type="button" :disabled="loading || !course || (!questionPages.trim() && !pairedPages.trim())" @click="run('apply')">
{{ uiText("直接提交") }} </button>
      </div>
    </div>

    <details class="page-diagnosis">
      <summary><span>{{ uiText("本批次能力诊断") }}</span><small>{{ uiText("无需单独提交，将和掌握状态一起保存") }}</small></summary>
      <div class="independence-row"><label><input v-model="usedHint" type="checkbox" /> {{ uiText("使用过提示") }}</label><label><input v-model="viewedAnswer" type="checkbox" /> {{ uiText("查看过答案") }}</label><b>{{ usedHint || viewedAnswer ? uiText("非独立作答") : uiText("独立作答") }}</b></div>
      <DiagnosisSelector v-if="result === 'review'" :model-value="selectedErrors" :primary="primaryError" :options="errorOptions.map((item) => ({ ...item, group: item.code[0]! }))" :disabled="loading" @toggle="toggleError" />
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
.pdf-page-status { min-width:0; margin:16px 0 24px; padding:0; border:0; border-radius:0; background:transparent; box-shadow:none; color:var(--text-primary); }
.pdf-page-status header { display:flex; justify-content:space-between; align-items:start; gap:16px; margin-bottom:24px; }
.pdf-page-status h2 { margin:0 0 8px; font-size:17px; } .pdf-page-status header p { max-width:760px; margin:0; color:var(--text-secondary); font-size:13px; line-height:1.6; }
.safe-badge { flex:none; color:var(--text-secondary); font-size:12px; line-height:1.5; }
.page-status-form { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; align-items:end; } .page-status-form > label { display:grid; gap:8px; min-width:0; }
.page-status-form > label > span, fieldset legend { color:var(--text-secondary); font-size:13px; font-weight:500; }
.page-status-form select,.page-status-form > label input,.primary-error select,.page-levels select,.batch-note textarea { box-sizing:border-box; width:100%; min-width:0; min-height:44px; padding:8px 12px; border:1px solid var(--border-control); border-radius:6px; background:var(--surface-page); color:var(--text-primary); font:inherit; font-size:16px; }
.page-status-form small { color:var(--text-secondary); font-size:12px; } fieldset { display:flex; align-items:center; gap:16px; min-height:44px; min-width:0; margin:0; padding:0; border:0; } fieldset legend { margin-bottom:8px; padding:0; } fieldset label { display:flex; align-items:center; gap:8px; min-height:44px; color:var(--text-primary); font-size:14px; }
input[type=radio],input[type=checkbox] { width:18px; height:18px; accent-color:var(--accent-solid); }
.form-actions { grid-column:1/-1; display:flex; gap:8px; flex-wrap:wrap; }
.page-diagnosis { margin-top:24px; padding:16px 0; border:0; border-block:1px solid var(--border-subtle); border-radius:0; }
.page-diagnosis summary { display:flex; align-items:center; justify-content:space-between; gap:12px; min-height:44px; cursor:pointer; font-size:14px; font-weight:500; } .page-diagnosis summary small { color:var(--text-secondary); font-size:12px; font-weight:400; }
.independence-row { display:flex; align-items:center; flex-wrap:wrap; gap:16px; margin:12px 0; font-size:13px; } .independence-row label { display:flex; align-items:center; gap:8px; min-height:44px; } .independence-row b { color:var(--text-secondary); font-weight:500; }
.primary-error,.batch-note { display:grid; gap:8px; margin-top:16px; color:var(--text-secondary); font-size:13px; } .page-levels { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin-top:16px; } .page-levels label { display:grid; gap:8px; color:var(--text-secondary); font-size:13px; } .batch-note textarea { min-height:96px; resize:vertical; }
.preview-button,.direct-submit-button,.apply-button { min-height:44px; padding:8px 16px; border:0; border-radius:6px; color:var(--text-primary); background:var(--surface-subtle); font-size:14px; font-weight:500; cursor:pointer; }
.direct-submit-button,.apply-button { background:var(--accent-solid); color:var(--accent-on-solid); } .direct-submit-button.secondary { color:var(--text-primary); background:var(--surface-subtle); } .preview-button:disabled,.direct-submit-button:disabled,.apply-button:disabled { opacity:.5; cursor:default; }
.page-status-error,.page-status-success,.unmatched-warning { margin:16px 0 0; padding:12px 0; border:0; border-radius:0; font-size:13px; line-height:1.6; background:transparent; } .page-status-error { color:var(--status-danger); } .page-status-success { color:var(--status-success); } .unmatched-warning { color:var(--status-review); } .unmatched-warning span + span::before { content:' · '; }
.preview-result { margin-top:16px; padding-top:16px; border-top:1px solid var(--border-subtle); } .preview-summary { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; } .preview-summary > div { padding:12px 0; } .preview-summary small { display:block; margin-bottom:8px; color:var(--text-secondary); font-size:12px; } .preview-summary strong { font-size:24px; font-variant-numeric:tabular-nums; }
.match-list { max-height:320px; margin:16px 0; padding:0; overflow:auto; border:0; border-top:1px solid var(--border-subtle); border-radius:0; list-style:none; } .match-list li { display:flex; align-items:center; justify-content:space-between; gap:16px; padding:12px 0; border-bottom:1px solid var(--border-subtle); font-size:14px; } .match-list span { min-width:0; } .match-list strong,.match-list small { display:block; overflow-wrap:anywhere; } .match-list small { margin-top:4px; font-size:12px; color:var(--text-secondary); } .match-list b { flex:none; color:var(--text-secondary); font-size:12px; }
.match-actions { display:flex; flex:none; align-items:center; gap:12px; } .match-actions a { display:inline-flex; align-items:center; min-height:44px; padding:8px; border:0; color:var(--accent-ink); font-size:13px; text-decoration:none; }
@media(max-width:620px) { .pdf-page-status header { flex-direction:column; } .page-status-form,.page-levels { grid-template-columns:minmax(0,1fr); } .page-diagnosis summary { align-items:start; flex-direction:column; } .preview-summary { grid-template-columns:repeat(2,minmax(0,1fr)); } .match-list li { align-items:start; } .match-actions { align-items:end; flex-direction:column; } }
</style>
