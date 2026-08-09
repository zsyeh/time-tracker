<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { post } from '../lib/api'
import type { StudySession, Subject } from '../types'
import MarkdownPreview from './MarkdownPreview.vue'

const props = defineProps<{ session: StudySession | null }>()
const emit = defineEmits<{ changed: [] }>()
const finishOpen = ref(false)
const saving = ref(false)
const form = reactive({ title: '', details: '' })
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
  finishOpen.value = true
}

async function finish() {
  if (!props.session) return
  if (!form.title.trim() || !form.details.trim()) {
    ElMessage.warning('Add a title and details before finishing')
    return
  }
  saving.value = true
  try {
    const result = await post<{ discarded: boolean; discard_reason: string | null }>(`/api/sessions/${props.session.id}/finish/`, form)
    finishOpen.value = false
    if (result.discarded) {
      ElMessage.info(result.discard_reason === 'longer_than_maximum'
        ? 'Session deleted: duration exceeded 12 hours'
        : 'Session deleted: duration was under 25 minutes')
    } else {
      ElMessage.success('Session completed')
      form.title = ''
      form.details = ''
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

  <el-dialog v-model="finishOpen" title="Complete session" width="min(760px, 94vw)" destroy-on-close>
    <el-form label-position="top" class="review-form simple-review">
      <el-form-item label="Title · Required"><el-input v-model="form.title" maxlength="500" show-word-limit placeholder="A concise heading for this session" /></el-form-item>
      <el-form-item label="Details · Required"><el-input v-model="form.details" type="textarea" :rows="14" placeholder="Paste Markdown from ChatGPT. TeX formulas support $...$, $$...$$, \(...\), and \[...\]." /></el-form-item>
      <MarkdownPreview :source="form.details" />
      <p class="minimum-note">Sessions under 25 minutes or over 12 hours are deleted automatically.</p>
    </el-form>
    <template #footer><el-button @click="finishOpen = false">Continue session</el-button><el-button type="primary" :loading="saving" @click="finish">Save & finish</el-button></template>
  </el-dialog>
</template>
