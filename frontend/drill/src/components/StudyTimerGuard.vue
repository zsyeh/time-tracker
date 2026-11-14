<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { accountPreferences } from '../../../shared/preferences/store'
import type { StudyTimerMode } from '../../../shared/preferences/schema'
import { typeText } from '../lib/examTypes'
import { activeStudyTimer, startStudyTimer, studySubject, type StudyWorkspace } from '../lib/studyTimer'

const props = defineProps<{ workspace: StudyWorkspace; mode: StudyTimerMode; context: string }>()
const emit = defineEmits<{ 'update:mode': [mode: StudyTimerMode] }>()
const dialog = ref<HTMLDialogElement | null>(null), busy = ref(false), dontRemind = ref(false)
const message = ref(''), canStart = ref(false)
const subjectLabel = computed(() => props.workspace === 'drill' ? typeText('数学', 'Mathematics') : typeText('专业课', 'Major subject'))
let resolvePending: ((allowed: boolean) => void) | null = null, epoch = 0

function finish(allowed: boolean) {
  const resolve = resolvePending; resolvePending = null
  if (resolve) epoch++
  if (allowed && resolve && dontRemind.value) emit('update:mode', 'off')
  if (dialog.value?.open) dialog.value.close()
  resolve?.(allowed)
}
watch([() => props.context, () => accountPreferences.userId.value], () => { epoch++; finish(false) })
onBeforeUnmount(() => { epoch++; finish(false) })

async function start() {
  if (busy.value || !canStart.value) return
  const version = epoch
  busy.value = true
  try {
    await startStudyTimer(props.workspace)
    if (version === epoch) finish(true)
  } catch {
    if (version !== epoch) return
    message.value = typeText('未能开启计时，可能已在其他设备开启或网络暂不可用。不会自动停止其他计时；你仍可继续保存作答。', 'Could not start the timer. Another device may have started one, or the connection is unavailable. Other timers will not be stopped. You can still save your answer.')
    canStart.value = false
  } finally { busy.value = false }
}

async function ensure(): Promise<boolean> {
  if (resolvePending) finish(false)
  if (props.mode === 'off') return true
  const version = ++epoch
  dontRemind.value = false; canStart.value = false
  try {
    const active = await activeStudyTimer()
    if (version !== epoch) return false
    if (active?.subject === studySubject(props.workspace)) return true
    canStart.value = !active
    message.value = active
      ? typeText('其他科目的学习计时正在进行，不会自动结束或切换。可先到计时页处理，或继续保存本次作答。', 'A different subject is being timed. It will not be stopped or switched automatically. Manage it in Timer, or save this answer anyway.')
      : typeText(`尚未开启${subjectLabel.value}学习计时。现在开始只记录之后的学习时间，不补记之前的时间。`, `The ${subjectLabel.value} study timer is not running. Starting now records future time only.`)
    if (!active && props.mode === 'auto_start') {
      try { await startStudyTimer(props.workspace); return version === epoch }
      catch {
        if (version !== epoch) return false
        canStart.value = false
        message.value = typeText('自动开启计时失败，可能已在其他设备开启或网络暂不可用。你仍可继续保存作答。', 'The timer could not be started automatically. Another device may have started one, or the connection is unavailable. You can still save your answer.')
      }
    }
  } catch {
    if (version !== epoch) return false
    message.value = typeText('暂时无法检查学习计时。你可以继续保存作答，稍后再检查计时。', 'The study timer could not be checked. You can save your answer and check the timer later.')
  }
  return new Promise<boolean>(resolve => {
    resolvePending = resolve
    void nextTick(() => { if (resolvePending === resolve && version === epoch) dialog.value?.showModal() })
  })
}
defineExpose({ ensure })
</script>

<template>
  <Teleport to="body">
    <dialog ref="dialog" class="study-timer-dialog" aria-labelledby="study-timer-title" aria-describedby="study-timer-message" @cancel.prevent="finish(false)" @close="finish(false)" @keydown.esc.stop>
      <h2 id="study-timer-title">{{ typeText('学习计时提醒', 'Study timer reminder') }}</h2>
      <p id="study-timer-message" role="status">{{ message }}</p>
      <label class="study-timer-dismiss"><input v-model="dontRemind" type="checkbox" />{{ typeText('不再提醒（可在设置中重新开启）', 'Don’t remind me again (change this in Settings)') }}</label>
      <div class="study-timer-actions">
        <button type="button" class="ui-button ui-button--plain" :disabled="busy" @click="finish(false)">{{ typeText('取消本次提交', 'Cancel') }}</button>
        <button type="button" class="ui-button ui-button--secondary" :disabled="busy" @click="finish(true)">{{ typeText('继续保存', 'Save anyway') }}</button>
        <button v-if="canStart" type="button" class="ui-button ui-button--primary" :disabled="busy" @click="start">{{ busy ? typeText('正在开启…', 'Starting…') : typeText('开始计时并保存', 'Start timer & save') }}</button>
      </div>
      <a href="https://47.95.10.128/today" target="_blank" rel="noopener">{{ typeText('打开学习计时页', 'Open Timer') }} ↗</a>
    </dialog>
  </Teleport>
</template>

<style scoped>
.study-timer-dialog{width:min(460px,calc(100vw - 32px));box-sizing:border-box;max-height:calc(100dvh - 32px - env(safe-area-inset-top) - env(safe-area-inset-bottom));padding:24px;border:1px solid var(--border-subtle);border-radius:var(--radius-dialog);background:var(--surface-elevated);color:var(--text-primary);overflow:auto;overscroll-behavior:contain}
.study-timer-dialog::backdrop{background:var(--overlay-dim)}
.study-timer-dialog h2{margin:0 0 12px;font-size:18px;line-height:1.4}.study-timer-dialog p{margin:0 0 16px;line-height:1.6;color:var(--text-secondary)}
.study-timer-dismiss{display:flex;align-items:center;gap:8px;min-height:44px;font-size:13px}.study-timer-dismiss input{flex:none;accent-color:var(--accent-ink)}
.study-timer-actions{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:8px;margin:16px 0}.study-timer-actions button{min-height:44px}.study-timer-dialog>a{font-size:13px;color:var(--accent-ink)}
</style>
