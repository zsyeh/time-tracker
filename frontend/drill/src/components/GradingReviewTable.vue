<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ExamGrading } from '../types'
import { api } from '../lib/api'
import MarkdownAnswer from './MarkdownAnswer.vue'
type Review = ExamGrading['items'][number]
type Field = 'user_answer' | 'reference' | 'note' | 'priority' | 'verification'
const props = defineProps<{ paperUuid: string; review: Review }>()
const emit = defineEmits<{ saved: [review: Review]; dirty: [value: boolean]; busy: [value: boolean] }>()
const fields: Array<{ key: Field; label: string }> = [
  { key:'user_answer',label:'我的作答' }, { key:'reference',label:'参考核对' },
  { key:'note',label:'批阅与需要掌握' }, { key:'priority',label:'复习优先级' }, { key:'verification',label:'核实情况' },
]
const draft = ref({} as Record<Field,string>)
const original = ref({} as Record<Field,string>)
const editing = ref(false), saving = ref(false), error = ref(''), saved = ref(false)
function reset() {
  const values = Object.fromEntries(fields.map(f => [f.key,String(props.review[f.key] || '')])) as Record<Field,string>
  draft.value = { ...values }; original.value = values
  editing.value = false; error.value = '';emit('dirty',false)
}
watch(() => props.review, reset, { immediate:true })
const dirty = computed(() => fields.some(f => draft.value[f.key] !== original.value[f.key]))
watch(dirty, value => { emit('dirty',value);if (value) saved.value=false })
async function save() {
  if (saving.value || !dirty.value) return
  const keys = fields.filter(f => draft.value[f.key] !== original.value[f.key]).map(f => f.key)
  saving.value=true;emit('busy',true);error.value=''
  try {
    const response = await api<{ item: Review }>(`/api/drill/papers/${props.paperUuid}/items/${props.review.position}/grading/`, {
      method:'PATCH',body:JSON.stringify({ expected_question_uuid:props.review.question_uuid,
        changes:Object.fromEntries(keys.map(k => [k,draft.value[k]])),
        expected:Object.fromEntries(keys.map(k => [k,original.value[k]])),
      }),
    })
    emit('saved',response.item)
    original.value={...draft.value};editing.value=false;saved.value=true;emit('dirty',false)
  } catch (reason) { error.value=(reason as Error).message }
  finally { saving.value=false;emit('busy',false) }
}
</script>
<template>
  <section class="review-table-section" aria-label="本题批阅记录">
    <header><h3>本题批阅记录</h3><div><template v-if="editing"><button type="button" :disabled="saving || !dirty" @click="save">{{ saving ? '保存中…' : '保存修改' }}</button><button type="button" :disabled="saving" @click="reset">取消</button></template><button v-else type="button" @click="editing=true;saved=false">编辑批阅</button></div></header>
    <p v-if="error" class="error-state" role="alert">{{ error }}</p><p v-if="saved" class="save-state" role="status">已保存</p>
    <table class="review-table"><colgroup><col class="label-column"><col></colgroup><tbody><tr v-for="field in fields" :key="field.key"><th scope="row"><label v-if="editing" :for="`review-${review.position}-${field.key}`">{{ field.label }}</label><template v-else>{{ field.label }}</template></th><td>
      <textarea v-if="editing" :id="`review-${review.position}-${field.key}`" v-model="draft[field.key]" :disabled="saving" :rows="field.key === 'priority' ? 2 : 4" :maxlength="field.key === 'priority' ? 64 : 10000" />
      <MarkdownAnswer v-else :source="String(review[field.key] || '—')" />
    </td></tr></tbody></table>
    <p class="question-score">本题得分 <strong>{{ review.earned }}/{{ review.maximum }}</strong></p>
  </section>
</template>
<style scoped>
.question-score { display:flex; align-items:center; gap:12px; font-size:14px; } .question-score strong { font-family:SimHei,"PingFang SC","Microsoft YaHei",sans-serif; font-weight:800; color:var(--score-ink, #c62828); font-size:24px; font-variant-numeric:tabular-nums; } .review-table-section { min-width:0; margin:24px 0; } header { display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; } h3 { font-size:16px; margin:0; } header > div { display:flex; gap:8px; } button { min-height:44px; border:0; border-radius:4px; padding:8px 12px; background:var(--surface-subtle); color:var(--text-primary); cursor:pointer; font:inherit; } button:disabled { opacity:.5; cursor:default; } .review-table { width:100%; table-layout:fixed; border-collapse:collapse; margin-top:12px; font-size:14px; } .label-column { width:128px; } th,td { padding:16px 12px; border-bottom:1px solid var(--border-subtle); vertical-align:top; overflow-wrap:anywhere; } th { text-align:left; font-weight:500; color:var(--text-secondary); background:var(--surface-subtle); } textarea { display:block; box-sizing:border-box; width:100%; min-width:0; min-height:64px; resize:vertical; padding:8px; border:1px solid var(--border-default); border-radius:4px; color:var(--text-primary); background:var(--bg-surface); font-family:inherit; font-size:16px; line-height:1.6; } .save-state { font-size:13px; color:var(--text-secondary); } :deep(.markdown-body) { font-size:14px; overflow-wrap:anywhere; } :deep(.markdown-body > :first-child) { margin-top:0; } :deep(.markdown-body > :last-child) { margin-bottom:0; } @media(max-width:600px) { .label-column { width:88px; } th,td { padding:12px 8px; } }
</style>
