<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Catalog } from '../types'
import { clearPracticeFilters, type PracticeQuery } from '../../../shared/search/queryState'
import { uiText } from '../lib/uiText'
import { runtimeWorkspace } from '../lib/runtimePath'
const props = defineProps<{ modelValue: PracticeQuery; catalog: Catalog; open: boolean; anchor?: HTMLElement | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: PracticeQuery]; 'update:open': [value: boolean] }>()
const dialog = ref<HTMLDialogElement | null>(null)
const includeStructureAvailable = ref(Boolean(props.modelValue.include_structure))
watch(() => props.modelValue.include_structure, (value) => { if (value) includeStructureAvailable.value = true })
const topics = computed(() => props.catalog.topics.filter((topic) => !props.modelValue.document || String(topic.document_id) === props.modelValue.document))
function change(key: string, value: string) {
  const next = { ...props.modelValue, [key]: value }
  if (key === 'document' && !props.catalog.topics.some((topic) => String(topic.id) === next.topic && (!value || String(topic.document_id) === value))) next.topic = ''
  if (key === 'type_group') next.exam_type = ''
  emit('update:modelValue', next)
}
function value(event: Event) { return (event.target as HTMLSelectElement).value }
function close() { emit('update:open', false) }
function position() {
  if (!dialog.value) return
  const viewport = window.visualViewport
  const visibleHeight = viewport?.height || window.innerHeight
  const offsetTop = viewport?.offsetTop || 0
  const keyboardBottom = Math.max(0, window.innerHeight - visibleHeight - offsetTop)
  if (window.innerWidth < 768) {
    dialog.value.style.bottom = `${keyboardBottom}px`
    dialog.value.style.maxHeight = `${visibleHeight - 24}px`
    return
  }
  const rect = props.anchor?.getBoundingClientRect()
  const top = Math.min((rect?.bottom || 64) + 8, Math.max(offsetTop + 12, offsetTop + visibleHeight - 200))
  dialog.value.style.left = `${Math.max(12, Math.min((rect?.right || window.innerWidth - 16) - 360, window.innerWidth - 372))}px`
  dialog.value.style.top = `${top}px`
  dialog.value.style.maxHeight = `${Math.min(640, offsetTop + visibleHeight - top - 12)}px`
}
onMounted(() => { window.addEventListener('resize', position); window.visualViewport?.addEventListener('resize', position); window.visualViewport?.addEventListener('scroll', position) })
onUnmounted(() => { window.removeEventListener('resize', position); window.visualViewport?.removeEventListener('resize', position); window.visualViewport?.removeEventListener('scroll', position) })
watch(() => props.open, async (open) => {
  await nextTick()
  if (open && !dialog.value?.open) { dialog.value?.showModal(); position() }
  else if (!open && dialog.value?.open) { dialog.value.close(); props.anchor?.focus() }
}, { immediate: true })
</script>
<template>
  <dialog ref="dialog" class="practice-filters" aria-labelledby="practice-filter-title" @cancel.prevent="close" @click="($event.target === dialog) && close()" @close="close">
    <div class="filter-sheet">
      <header><h2 id="practice-filter-title">{{ uiText('筛选') }}</h2><button type="button" class="plain-action" @click="close">{{ uiText('完成') }}</button></header>
      <div class="filter-fields">
        <p v-if="modelValue.collection" class="filter-scope">{{ uiText('当前范围') }}：{{ modelValue.collection }} <RouterLink to="/practice" @click="close">{{ uiText('离开此范围') }}</RouterLink></p>
        <label><span>{{ uiText('题目来源') }}</span><select :value="modelValue.source_category || ''" @change="change('source_category', value($event))"><option value="">{{ uiText('全部来源') }}</option><option v-for="category in catalog.summary.categories" :key="category.value" :value="category.value">{{ uiText(category.label) }} · {{ category.count }}</option></select></label>
        <label><span>{{ uiText('题册') }}</span><select :value="modelValue.document || ''" @change="change('document', value($event))"><option value="">{{ uiText('全部题册') }}</option><option v-for="book in catalog.documents" :key="book.id" :value="book.id">{{ book.title }} · {{ book.question_count }}</option></select></label>
        <label><span>{{ uiText('知识点') }}</span><select :value="modelValue.topic || ''" @change="change('topic', value($event))"><option value="">{{ uiText('全部知识点') }}</option><option v-for="topic in topics" :key="topic.id" :value="topic.id">{{ topic.path }} · {{ topic.question_count }}</option></select></label>
        <label><span>{{ uiText('题型') }}</span><select :value="modelValue.type_group || ''" @change="change('type_group', value($event))"><option value="">{{ uiText('全部题型') }}</option><option value="small">{{ uiText('小题') }}</option><option value="large">{{ uiText('大题') }}</option><option v-if="runtimeWorkspace === 'ei'" value="short_answer">{{ uiText('简答题') }}</option><option value="unknown">{{ uiText('未分类') }}</option></select></label>
        <label><span>{{ uiText('具体题型') }}</span><select :value="modelValue.exam_type || ''" @change="change('exam_type', value($event))"><option value="">{{ uiText('全部具体题型') }}</option><option value="choice">{{ uiText('选择题') }}</option><option value="fill">{{ uiText('填空题') }}</option><option v-if="runtimeWorkspace === 'ei'" value="judgment">{{ uiText('判断题') }}</option><option v-if="runtimeWorkspace === 'ei'" value="short_answer">{{ uiText('简答题') }}</option><option value="large">{{ uiText('大题') }}</option><option value="unknown">{{ uiText('未分类') }}</option></select></label>
        <label><span>{{ uiText('学习状态') }}</span><select :value="modelValue.status || ''" @change="change('status', value($event))"><option value="">{{ uiText('全部状态') }}</option><option value="unattempted">{{ uiText('未作答') }}</option><option value="mastered">{{ uiText('已掌握') }}</option><option value="review">{{ uiText('待复习') }}</option><option value="overdue">{{ uiText('已到期') }}</option></select></label>
        <label><span>{{ uiText('学习标记') }}</span><select :value="modelValue.marker || ''" @change="change('marker', value($event))"><option value="">{{ uiText('全部标记') }}</option><option value="overconfident">{{ uiText('过度自信') }}</option><option value="concept_gap">{{ uiText('概念缺口') }}</option><option value="rusty">{{ uiText('生疏') }}</option><option value="forgotten">{{ uiText('遗忘') }}</option></select></label>
        <label class="check-row"><span>{{ uiText('仅收藏') }}</span><input type="checkbox" :checked="modelValue.favorite === '1'" @change="change('favorite', ($event.target as HTMLInputElement).checked ? '1' : '')" /></label>
        <label class="check-row"><span>{{ uiText('加入下次复习') }}</span><input type="checkbox" :checked="modelValue.review_later === '1'" @change="change('review_later', ($event.target as HTMLInputElement).checked ? '1' : '')" /></label>
        <label v-if="includeStructureAvailable" class="check-row"><span>{{ uiText('包含资料目录') }}</span><input type="checkbox" :checked="modelValue.include_structure === '1'" @change="change('include_structure', ($event.target as HTMLInputElement).checked ? '1' : '')" /></label>
      </div>
      <footer><button class="plain-action" type="button" @click="emit('update:modelValue', clearPracticeFilters(modelValue))">{{ uiText('清除筛选') }}</button><small>{{ uiText('更改即时生效') }}</small></footer>
    </div>
  </dialog>
</template>
<style scoped>
.practice-filters { padding:0; border:1px solid var(--border-subtle); border-radius:12px; background:var(--surface-elevated); color:var(--text-primary); width:min(360px, calc(100vw - 24px)); max-width:none; margin:0; position:fixed; max-height:calc(100dvh - 24px); }
.practice-filters::backdrop { background:rgb(0 0 0 / .2); }
.filter-sheet { display:flex; flex-direction:column; max-height:inherit; }
header, footer { display:flex; align-items:center; justify-content:space-between; padding:12px 16px; flex:none; }
header { border-bottom:1px solid var(--border-subtle); } header h2 { margin:0; font-size:16px; } footer { border-top:1px solid var(--border-subtle); }
.filter-fields { overflow:auto; overscroll-behavior:contain; padding:4px 16px; }
.filter-fields > label { display:flex; flex-direction:column; gap:8px; padding:12px 0; font-size:13px; } select { width:100%; min-height:40px; background:var(--surface-subtle); border:1px solid var(--border-control); border-radius:6px; padding:8px; color:var(--text-primary); font:inherit; }
.filter-fields > .check-row { flex-direction:row; align-items:center; justify-content:space-between; min-height:44px; } input[type=checkbox] { width:18px; height:18px; accent-color:var(--accent-solid); }
.plain-action { border:0; background:transparent; color:var(--accent-ink); min-height:44px; padding:8px; font:inherit; cursor:pointer; } .filter-scope, footer small { font-size:12px; color:var(--text-secondary); }
@media (max-width:767px) { .practice-filters { top:auto !important; left:0 !important; bottom:0; width:100%; max-height:calc(100dvh - env(safe-area-inset-top) - 16px); border-radius:12px 12px 0 0; border-bottom:0; } footer { padding-bottom:max(12px, env(safe-area-inset-bottom)); } }
@media(pointer:coarse) { select { font-size:16px; } }
</style>
