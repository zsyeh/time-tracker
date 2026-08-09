<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { post } from '../lib/api'
import type { StudySession, Subject } from '../types'

const props = defineProps<{ session: StudySession | null }>()
const emit = defineEmits<{ changed: [] }>()
const finishOpen = ref(false)
const saving = ref(false)
const form = reactive({
  chapter: '', topic: '', learning_mode: 'theory', difficulty: 3, energy_level: 'medium',
  focus_level: 3, confidence_after: 3, note: '', breakthrough: '', problems: '', next_action: '',
})
const subjects: Array<{ id: Subject; label: string; shortcut: string }> = [
  { id: 'math', label: 'Mathematics', shortcut: 'M' }, { id: 'english', label: 'English', shortcut: 'E' },
  { id: 'major', label: 'Major', shortcut: 'P' }, { id: 'training', label: 'Training', shortcut: 'T' },
]
async function start(subject: Subject) {
  try {
    await post('/api/sessions/', { subject })
    ElMessage.success('Session started')
    emit('changed')
  } catch (error) { ElMessage.error((error as Error).message) }
}

function prepareFinish() {
  if (!props.session) return
  form.chapter = props.session.chapter
  form.topic = props.session.topic
  form.learning_mode = props.session.learning_mode || 'theory'
  finishOpen.value = true
}

async function finish() {
  if (!props.session) return
  if (!(form.chapter.trim() || form.topic.trim()) || !form.note.trim() || !form.breakthrough.trim() || !form.problems.trim() || !form.next_action.trim()) {
    ElMessage.warning('Complete the topic, summary, breakthrough, problems, and next action')
    return
  }
  saving.value = true
  try {
    const result = await post<{ discarded: boolean }>(`/api/sessions/${props.session.id}/finish/`, form)
    finishOpen.value = false
    if (result.discarded) ElMessage.info('Session discarded: duration was under 25 minutes')
    else ElMessage.success('Session completed')
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
      <div><span class="pulse-dot" /><span class="eyebrow">SESSION IN PROGRESS</span><h2>{{ session.subject_label }}</h2><p>{{ session.topic || session.chapter || 'Start time recorded.' }}</p></div>
      <div class="hidden-timer" aria-label="Active duration hidden"><span>TIMER HIDDEN</span><small>Visible after completion</small></div>
      <div class="active-actions"><el-button plain @click="abandon">Discard</el-button><el-button type="primary" @click="prepareFinish">Finish & review</el-button></div>
    </template>
    <template v-else>
      <div><span class="eyebrow">START SESSION</span><h2>Select a subject.</h2><p>Start time is recorded automatically. Duplicate starts are ignored.</p></div>
      <div class="subject-actions">
        <button v-for="item in subjects" :key="item.id" :class="`subject-button subject-${item.id}`" @click="start(item.id)"><b>{{ item.shortcut }}</b><span>{{ item.label }}</span></button>
      </div>
    </template>
  </section>

  <el-dialog v-model="finishOpen" title="Finish session · Structured review" width="min(720px, 94vw)" destroy-on-close>
    <el-form label-position="top" class="review-form">
      <div class="form-pair"><el-form-item label="Chapter"><el-input v-model="form.chapter" placeholder="Example: Chapter 3" /></el-form-item><el-form-item label="Topic"><el-input v-model="form.topic" placeholder="What was studied" /></el-form-item></div>
      <div class="form-pair"><el-form-item label="Mode"><el-select v-model="form.learning_mode"><el-option v-for="item in [['theory','Theory'],['exercise','Exercise'],['review','Review'],['memorization','Memorization'],['project','Project'],['exam_simulation','Exam simulation']]" :key="item[0]" :label="item[1]" :value="item[0]" /></el-select></el-form-item><el-form-item label="Focus"><el-rate v-model="form.focus_level" /></el-form-item></div>
      <el-form-item label="Summary · Required"><el-input v-model="form.note" type="textarea" :rows="3" placeholder="Record facts, methods, and outcomes" /></el-form-item>
      <el-form-item label="Breakthrough · Required"><el-input v-model="form.breakthrough" type="textarea" :rows="2" /></el-form-item>
      <el-form-item label="Open problems · Required"><el-input v-model="form.problems" type="textarea" :rows="2" /></el-form-item>
      <el-form-item label="Next action · Required"><el-input v-model="form.next_action" type="textarea" :rows="2" /></el-form-item>
      <p class="minimum-note">Sessions shorter than 25 minutes are discarded automatically.</p>
    </el-form>
    <template #footer><el-button @click="finishOpen = false">Continue session</el-button><el-button type="primary" :loading="saving" @click="finish">Save & finish</el-button></template>
  </el-dialog>
</template>
