<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { typeText } from '../lib/examTypes'
const props = withDefaults(defineProps<{ page: number; totalPages: number; count: number; loading?: boolean; position: 'top'|'bottom' }>(), { loading: false })
const emit = defineEmits<{ change: [page: number, position: 'top'|'bottom'] }>()
const draft = ref(String(props.page)), invalid = ref(false)
const unavailable = computed(() => props.loading || props.totalPages < 1)
watch(() => props.page, value => { draft.value = String(value); invalid.value = false })
function go(page: number) {
  if (unavailable.value || !Number.isSafeInteger(page) || page < 1 || page > props.totalPages) return
  invalid.value = false
  if (page === props.page) return
  emit('change', page, props.position)
}
function jump() {
  const value = Number(draft.value)
  if (!/^\d+$/.test(draft.value.trim()) || !Number.isSafeInteger(value) || value < 1 || value > props.totalPages) { invalid.value = true; return }
  go(value)
}
</script>
<template>
  <nav class="practice-pagination pager" :data-page-position="position" :aria-label="typeText(position === 'top' ? '题目列表顶部分页' : '题目列表底部分页', position === 'top' ? 'Question pagination, top' : 'Question pagination, bottom')" :aria-busy="loading">
    <button class="page-first" type="button" :aria-label="typeText('首页', 'First page')" :disabled="unavailable || page <= 1" @click="go(1)">{{ typeText('首页', 'First') }}</button>
    <button class="page-previous" type="button" :disabled="unavailable || page <= 1" @click="go(page - 1)">{{ typeText('上一页', 'Previous') }}</button>
    <span class="page-summary" :role="position === 'top' ? 'status' : undefined" :aria-live="position === 'top' ? 'polite' : 'off'">{{ typeText('第', 'Page') }} {{ totalPages ? page : 0 }} / {{ totalPages }} · {{ count }} {{ typeText('题', 'questions') }}</span>
    <button class="page-next" type="button" :disabled="unavailable || page >= totalPages" @click="go(page + 1)">{{ typeText('下一页', 'Next') }}</button>
    <button class="page-last" type="button" :aria-label="typeText('末页', 'Last page')" :disabled="unavailable || page >= totalPages" @click="go(totalPages)">{{ typeText('末页', 'Last') }}</button>
    <form class="page-jump" novalidate @submit.prevent="jump">
      <label>{{ typeText('跳至', 'Go to') }} <input v-model="draft" type="text" inputmode="numeric" pattern="[0-9]*" :disabled="unavailable" :aria-label="typeText('目标页码', 'Page number')" :aria-invalid="invalid" /></label>
      <button type="submit" :disabled="unavailable">{{ typeText('前往', 'Go') }}</button>
      <span v-if="invalid" class="page-error" role="alert">{{ typeText('请输入页码', 'Enter a page from') }} 1–{{ totalPages }}</span>
    </form>
  </nav>
</template>
<style scoped>
.practice-pagination { display:flex; flex-wrap:wrap; align-items:center; justify-content:flex-end; gap:8px 12px; margin:16px 0; border:0; padding:0; }
.practice-pagination button,.page-jump input { min-height:44px; }
.practice-pagination button { min-width:44px; padding:8px 12px; }
.page-summary { color:var(--text-secondary); font-size:13px; font-variant-numeric:tabular-nums; }
.page-jump { display:flex; align-items:center; flex-wrap:wrap; gap:8px; margin:0; }
.page-jump label { display:flex; align-items:center; gap:8px; color:var(--text-secondary); font-size:13px; }
.page-jump input { width:64px; min-width:0; padding:8px; font-variant-numeric:tabular-nums; }
.page-error { flex-basis:100%; color:var(--status-danger,var(--text-primary)); font-size:13px; }
@media(max-width:600px) {
  .practice-pagination { display:grid; grid-template-columns:44px 56px minmax(0,1fr) 56px 44px; gap:8px 4px; justify-content:stretch; }
  .practice-pagination > button { min-width:44px; padding:8px 2px; font-size:13px; }
  .page-summary { min-width:0; text-align:center; font-size:12px; line-height:1.4; }
  .page-jump { grid-column:1/-1; justify-content:center; }
}
</style>
