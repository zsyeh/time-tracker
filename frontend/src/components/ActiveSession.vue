<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, post } from '../lib/api'
import type { CompletionOptions, EfficiencyGrade, StudySession, Subject, TaskPreset, TaskShortcut } from '../types'
import MarkdownPreview from './MarkdownPreview.vue'
import { useUiPreferences } from '../lib/uiPreferences'

const props = defineProps<{ session: StudySession | null; shortcuts?: TaskShortcut[] }>()
const { t } = useUiPreferences()
const emit = defineEmits<{ changed: [] }>()
const finishOpen = ref(false)
const saving = ref(false)
const form = reactive({
  title: '',
  details: '',
  tag_ids: [] as number[],
  efficiency_grade: 'A' as EfficiencyGrade,
})
const efficiencyGrades: Array<{ grade: EfficiencyGrade; coefficient: string }> = [
  { grade: 'A', coefficient: '1.00' },
  { grade: 'B', coefficient: '0.95' },
  { grade: 'C', coefficient: '0.90' },
  { grade: 'D', coefficient: '0.85' },
  { grade: 'E', coefficient: '0.80' },
  { grade: 'F', coefficient: '0.75' },
]
const completionOptions = ref<CompletionOptions>({ presets: [], tags: [], recent_titles: [] })
const optionsLoaded = ref(false)
const taskBrowserOpen = ref(false)
const taskSelection = ref<Array<string | number>>([])
const cascaderProps = { checkStrictly: true, expandTrigger: 'hover' as const }
const subjects = computed<Array<{ id: Subject; label: string; shortcut: string }>>(() => [
  { id: 'math', label: t('mathematics'), shortcut: 'M' }, { id: 'english', label: t('english'), shortcut: 'E' },
  { id: 'major', label: t('major'), shortcut: 'P' }, { id: 'training', label: t('training'), shortcut: 'T' },
])
async function start(subject: Subject) {
  try {
    await post('/api/sessions/', { subject })
    ElMessage.success('Session started')
    emit('changed')
  } catch (error) { ElMessage.error((error as Error).message) }
}

type StartablePreset = TaskShortcut | TaskPreset
async function startPreset(preset: StartablePreset) {
  try {
    await post('/api/sessions/', { task_preset: preset.id })
    const label = 'label' in preset ? preset.label : preset.shortcut_label
    ElMessage.success(`${label} started`)
    emit('changed')
  } catch (error) { ElMessage.error((error as Error).message) }
}

async function loadCompletionOptions() {
  if (optionsLoaded.value) return
  try {
    completionOptions.value = await api<CompletionOptions>('/api/completion-options/')
    optionsLoaded.value = true
  } catch (error) { ElMessage.error((error as Error).message) }
}

type TaskMenuNode = { value: string | number; label: string; children?: TaskMenuNode[] }
const presetMenuOptions = computed<TaskMenuNode[]>(() => {
  const active = completionOptions.value.presets.filter((preset) => preset.is_active)
  const nodes = new Map<number, TaskMenuNode>()
  active.forEach((preset) => nodes.set(preset.id, { value: preset.id, label: preset.name, children: [] }))
  const roots = new Map<Subject, TaskMenuNode[]>(subjects.value.map((subject) => [subject.id, []]))
  active.forEach((preset) => {
    const node = nodes.get(preset.id)!
    const parent = preset.parent ? nodes.get(preset.parent) : null
    if (parent) parent.children!.push(node)
    else roots.get(preset.subject)?.push(node)
  })
  const trimAndSort = (items: TaskMenuNode[]) => {
    items.sort((a, b) => a.label.localeCompare(b.label))
    items.forEach((item) => {
      if (item.children?.length) trimAndSort(item.children)
      else delete item.children
    })
  }
  return subjects.value.flatMap((subject) => {
    const children = roots.get(subject.id) || []
    trimAndSort(children)
    return children.length ? [{ value: `subject:${subject.id}`, label: subject.label, children }] : []
  })
})
const selectedPreset = computed(() => {
  const selectedId = [...taskSelection.value].reverse().find((value) => typeof value === 'number')
  return completionOptions.value.presets.find((preset) => preset.id === selectedId) || null
})

async function openTaskBrowser() {
  await loadCompletionOptions()
  if (!completionOptions.value.presets.some((preset) => preset.is_active)) {
    ElMessage.info('Create a task preset in Settings first')
    return
  }
  taskSelection.value = []
  taskBrowserOpen.value = true
}

async function startSelectedPreset() {
  if (!selectedPreset.value) return
  await startPreset(selectedPreset.value)
  taskBrowserOpen.value = false
}

function toggleTag(tagId: number) {
  const index = form.tag_ids.indexOf(tagId)
  if (index >= 0) form.tag_ids.splice(index, 1)
  else form.tag_ids.push(tagId)
}

async function prepareFinish() {
  if (!props.session) return
  const elapsed = Date.now() - new Date(props.session.start_time).getTime()
  if (elapsed < 25 * 60 * 1000 || elapsed > 12 * 60 * 60 * 1000) {
    saving.value = true
    try {
      const result = await post<{ discarded: boolean; discard_reason: string | null }>(`/api/sessions/${props.session.id}/finish/`, {})
      if (result.discarded) {
        const message = result.discard_reason === 'longer_than_maximum'
          ? 'Session deleted: duration exceeded 12 hours'
          : 'Session deleted: duration was under 25 minutes'
        ElMessage.info(message)
        emit('changed')
        return
      }
    } catch {
      // If the browser clock differs from the server, use the normal form and
      // let the server make the authoritative duration decision on submit.
    } finally { saving.value = false }
  }
  form.tag_ids = props.session.tags.map((tag) => tag.id)
  form.efficiency_grade = 'A'
  finishOpen.value = true
  void loadCompletionOptions()
}

async function finish() {
  if (!props.session) return
  saving.value = true
  try {
    const result = await post<{ discarded: boolean; discard_reason: string | null; github_note?: { status: string } }>(`/api/sessions/${props.session.id}/finish/`, form)
    finishOpen.value = false
    if (result.discarded) {
      ElMessage.info(result.discard_reason === 'longer_than_maximum'
        ? 'Session deleted: duration exceeded 12 hours'
        : 'Session deleted: duration was under 25 minutes')
    } else {
      ElMessage.success(result.github_note?.status === 'queued' ? 'Session completed · GitHub sync queued' : 'Session completed')
      form.title = ''
      form.details = ''
      form.tag_ids = []
      form.efficiency_grade = 'A'
    }
    emit('changed')
  } catch (error) { ElMessage.error((error as Error).message) } finally { saving.value = false }
}

async function abandon() {
  if (!props.session) return
  try {
    await ElMessageBox.confirm('This session will be deleted permanently.', 'Discard session?', { type: 'warning', confirmButtonText: 'Discard', cancelButtonText: 'Keep session' })
    await post(`/api/sessions/${props.session.id}/abandon/`)
    ElMessage.info('Session deleted')
    emit('changed')
  } catch (error) { if (error !== 'cancel') ElMessage.error((error as Error).message) }
}
</script>

<template>
  <section class="focus-panel" :class="{ active: session }">
    <template v-if="session">
      <div><span class="pulse-dot" /><span class="eyebrow">{{ t('sessionInProgress') }}</span><h2>{{ session.task_path || session.subject_label }}</h2><p>{{ session.task_path ? session.subject_label : session.topic || session.chapter || t('startRecorded') }}<span v-if="session.disturbance_count" class="active-disturbance-count"> · {{ session.disturbance_count }} {{ t('disturbances').toLocaleLowerCase() }}</span></p></div>
      <div class="hidden-timer" aria-label="Active duration hidden"><span>{{ t('timerHidden') }}</span><small>{{ t('visibleAfter') }}</small></div>
      <div class="active-actions"><el-button plain @click="abandon">{{ t('discard') }}</el-button><el-button type="primary" @click="prepareFinish">{{ t('finishReview') }}</el-button></div>
    </template>
    <template v-else>
      <div><span class="eyebrow">{{ t('startSession') }}</span><h2>{{ t('selectTask') }}</h2><p>{{ t('automaticStart') }}</p></div>
      <div class="start-action-stack">
        <div v-if="shortcuts?.length" class="preset-shortcuts">
          <button v-for="preset in shortcuts" :key="preset.id" type="button" @click="startPreset(preset)"><span>{{ preset.subject_label }}</span><b>{{ preset.path }}</b><small v-if="preset.tags.length">{{ preset.tags.map((tag) => `#${tag.name}`).join(' ') }}</small></button>
        </div>
        <div class="subject-actions">
          <button v-for="item in subjects" :key="item.id" :class="`subject-button subject-${item.id}`" @click="start(item.id)"><b>{{ item.shortcut }}</b><span>{{ item.label }}</span></button>
        </div>
        <button type="button" class="browse-task-button" @click="openTaskBrowser">{{ t('browseTasks') }}</button>
      </div>
    </template>
  </section>

  <el-dialog v-model="taskBrowserOpen" :title="t('choosePreset')" width="min(680px, 94vw)">
    <p class="task-browser-note">Browse by subject and up to four task levels. Any level can start a Session.</p>
    <el-cascader v-model="taskSelection" :options="presetMenuOptions" :props="cascaderProps" filterable clearable placeholder="Subject → task → subtask" class="task-browser-cascader" />
    <div v-if="selectedPreset" class="task-browser-selection"><span>{{ selectedPreset.subject_label }}</span><strong>{{ selectedPreset.path }}</strong><small v-if="selectedPreset.tags.length">{{ selectedPreset.tags.map((tag) => `#${tag.name}`).join(' ') }}</small></div>
    <template #footer><el-button @click="taskBrowserOpen = false">{{ t('cancel') }}</el-button><el-button type="primary" :disabled="!selectedPreset" @click="startSelectedPreset">{{ t('startSelected') }}</el-button></template>
  </el-dialog>

  <el-dialog v-model="finishOpen" :title="t('completeSession')" width="min(760px, 94vw)" destroy-on-close>
    <el-form label-position="top" class="review-form simple-review">
      <div class="efficiency-assessment">
        <div><span>{{ t('efficiencyAssessment') }}</span><small>{{ t('creditedFormula') }}</small></div>
        <div class="efficiency-options" role="radiogroup" aria-label="Efficiency grade">
          <button
            v-for="item in efficiencyGrades"
            :key="item.grade"
            type="button"
            role="radio"
            :aria-checked="form.efficiency_grade === item.grade"
            :class="{ selected: form.efficiency_grade === item.grade }"
            @click="form.efficiency_grade = item.grade"
          ><b>{{ item.grade }}</b><span>×{{ item.coefficient }}</span></button>
        </div>
      </div>
      <el-form-item :label="t('titleOptional')"><el-input v-model="form.title" maxlength="500" show-word-limit :placeholder="session?.task_path ? `Defaults to ${session.task_path.split(' › ').at(-1)}` : 'Leave empty to finish without notes'" /></el-form-item>
      <div v-if="completionOptions.recent_titles.length" class="completion-suggestions"><span>{{ t('recentNotes') }}</span><button v-for="title in completionOptions.recent_titles" :key="title" type="button" @click="form.title = title">{{ title }}</button></div>
      <el-form-item :label="t('markdownOptional')"><el-input v-model="form.details" type="textarea" :rows="14" placeholder="Optional Markdown. TeX formulas support $...$, $$...$$, \(...\), and \[...\]." /></el-form-item>
      <MarkdownPreview :source="form.details" />
      <div v-if="completionOptions.tags.length" class="completion-tags"><span>TAGS</span><button v-for="tag in completionOptions.tags" :key="tag.id" type="button" :class="{ selected: form.tag_ids.includes(tag.id) }" @click="toggleTag(tag.id)">#{{ tag.name }}</button></div>
      <p class="minimum-note">{{ t('emptyAllowed') }}</p>
    </el-form>
    <template #footer><el-button @click="finishOpen = false">{{ t('continueSession') }}</el-button><el-button type="primary" :loading="saving" @click="finish">{{ t('saveFinish') }}</el-button></template>
  </el-dialog>
</template>
