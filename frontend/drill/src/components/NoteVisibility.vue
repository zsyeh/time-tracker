<script setup lang="ts">
import { ref, watch } from 'vue'
import { runtimeWorkspace } from '../lib/runtimePath'
import { typeText } from '../lib/examTypes'

const props = defineProps<{ note: string; questionKey: string }>()
const storageKey = `${runtimeWorkspace}.hide-notes.v1`
function readPreference() {
  try { return localStorage.getItem(storageKey) === 'true' } catch { return false }
}
const hideNotes = ref(readPreference())
const revealed = ref(false)
watch(hideNotes, (value) => {
  revealed.value = false
  try { localStorage.setItem(storageKey, String(value)) } catch { /* Display still works without storage. */ }
})
watch(() => props.questionKey, () => { revealed.value = false }, { flush: 'sync' })
</script>

<template>
  <section class="note-visibility">
    <label class="note-privacy-toggle"><input v-model="hideNotes" type="checkbox" />{{ typeText('隐藏笔记', 'Hide notes') }}</label>
    <button v-if="hideNotes && note.trim() && !revealed" type="button" class="note-hidden" @click="revealed = true">{{ typeText('笔记已隐藏 · 点击显示', 'Note hidden · click to show') }}</button>
    <div v-else @focusin="revealed = true"><slot /></div>
  </section>
</template>

<style scoped>
.note-visibility { margin-top: 6px; }
.note-privacy-toggle { display: flex; align-items: center; justify-content: flex-end; gap: 4px; color: var(--text-secondary); font-size: 10px; cursor: pointer; }
.note-privacy-toggle input { width: 13px; height: 13px; margin: 0; accent-color: var(--accent); }
.note-hidden { display: block; width: 100%; margin-top: 6px; padding: 9px 10px; border: 1px solid var(--border-default); border-radius: var(--radius-sm); background: var(--bg-sidebar); color: var(--text-secondary); text-align: left; font-size: 11px; cursor: pointer; }
.note-hidden:hover, .note-hidden:focus-visible { color: var(--accent); border-color: var(--accent); }
</style>
