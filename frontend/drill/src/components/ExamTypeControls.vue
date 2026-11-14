<script setup lang="ts">
import { watch } from 'vue'
import { runtimeWorkspace } from '../lib/runtimePath'
import { useBrowsePreferences } from '../lib/browsePreferences'
const isEi = runtimeWorkspace === 'ei'
import { formatColours, typeGroups, typeLabel, typeText, type TypeStats } from '../lib/examTypes'
const visibleGroups = typeGroups.filter((key) => isEi || key === 'small' || key === 'large')
const props = defineProps<{ modelValue: string; stats?: TypeStats }>()
const emit = defineEmits<{ 'update:modelValue': [value: string]; practice: [] }>()
const { remember, filters } = useBrowsePreferences()
function select(value: string) {
  remember({ type_group: value, exam_type: '' })
  emit('update:modelValue', value)
}
function practice() {
  remember({ type_group: 'small', exam_type: '' })
  emit('practice')
}
watch(() => props.modelValue, (value) => {
  if (value && !visibleGroups.some((key) => key === value)) emit('update:modelValue', '')
  // Adopt a previously selected URL/local value once on upgrade. A later deep
  // link must not silently overwrite an established account default.
  else if (value && filters.value.type_group === undefined) remember({ type_group: value })
}, { immediate: true })
</script>
<template>
  <section class="exam-type-controls" :aria-label="typeText('题型筛选与分析', 'Format filters and analysis')">
    <div class="exam-type-toolbar">
      <label>{{ typeText('题型', 'Format') }}<select :value="modelValue" @change="select(($event.target as HTMLSelectElement).value)"><option value="">{{ typeLabel('all') }}</option><option v-for="key in visibleGroups" :key="key" :value="key">{{ typeLabel(key) }}</option></select></label>
      <button type="button" class="exam-small-entry" @click="practice">{{ typeText('小题专练 →', 'Short questions →') }}</button>
      <label><input v-model="formatColours" type="checkbox" />{{ typeText('题型分色预览', 'Highlight formats') }}</label>
      <small>{{ isEi ? typeText('小题含选择、填空、判断；简答单列。色点表示题型，原掌握颜色保留。', 'Short questions: choice, fill in and true / false. Short answers are separate. Dots show format; existing colours show mastery.') : typeText('小题含选择、填空；大题单列。色点表示题型，原掌握颜色保留。', 'Short questions: choice and fill in. Worked solutions are separate. Dots show format; existing colours show mastery.') }}</small>
    </div>
    <div v-if="stats" class="exam-type-stats">
      <button v-for="key in visibleGroups" :key="key" type="button" :class="[`exam-${key}`, { active: modelValue === key }]" :aria-pressed="modelValue === key" @click="select(modelValue === key ? '' : key)">
        <strong>{{ typeLabel(key) }} · {{ stats[key]?.total || 0 }} <span v-if="modelValue === key" aria-hidden="true">✓</span></strong>
        <span>{{ typeText('已做', 'Attempted') }} {{ stats[key]?.attempted || 0 }} · {{ typeText('掌握', 'Mastered') }} {{ stats[key]?.mastered || 0 }} · {{ typeText('待复习', 'Review') }} {{ stats[key]?.review || 0 }}</span>
        <span>{{ typeText('覆盖率', 'Coverage') }} {{ stats[key]?.total ? Math.round((stats[key]?.attempted || 0) * 100 / stats[key]!.total) : 0 }}% · {{ typeText('已做掌握率', 'Mastery of attempted') }} {{ stats[key]?.attempted ? Math.round((stats[key]?.mastered || 0) * 100 / stats[key]!.attempted) + '%' : '—' }}</span>
      </button>
    </div>
  </section>
</template>
<style scoped>
.exam-type-controls { margin:16px 0; }
.exam-type-toolbar { display:flex; align-items:center; flex-wrap:wrap; gap:8px 16px; }
.exam-type-toolbar label { display:flex; align-items:center; gap:8px; font-size:13px; }
.exam-type-toolbar select,.exam-small-entry { min-height:40px; padding:8px 12px; color:var(--text-primary); background:var(--bg-surface); border:1px solid var(--border-default); border-radius:var(--radius-sm); }
.exam-small-entry { cursor:pointer; color:var(--accent); }.exam-type-toolbar small { font-size:12px; color:var(--text-secondary); }
.exam-type-stats { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:0 12px; margin-top:12px; border-top:1px solid var(--border-subtle); }
.exam-type-stats button { min-width:0; min-height:76px; display:grid; align-content:center; gap:3px; padding:10px 12px; color:var(--text-primary); background:transparent; border:0; border-bottom:1px solid var(--border-subtle); border-radius:0; text-align:left; cursor:pointer; }
.exam-type-stats button:hover { background:var(--bg-surface-hover); }
.exam-type-stats button.active { background:var(--surface-selected); }
.exam-type-stats strong { font-size:14px; font-weight:650; }
.exam-type-stats strong span { color:var(--accent); }
.exam-type-stats button>span { color:var(--text-secondary); font-size:12px; line-height:1.35; }
@media(max-width:700px) { .exam-type-toolbar select,.exam-small-entry { min-height:44px; font-size:16px; } .exam-type-toolbar label { min-height:44px; } .exam-type-toolbar small { flex-basis:100%; } .exam-type-stats { gap:0 8px; } .exam-type-stats button { padding:10px 8px; } }
</style>
<style>
.exam-type-colours [data-type-group="small"] { box-shadow:inset 0 -3px 0 var(--format-small); }
.exam-type-colours [data-type-group="large"] { box-shadow:inset 0 -3px 0 var(--format-large); }
.exam-type-colours [data-type-group="short_answer"] { box-shadow:inset 0 -3px 0 var(--format-short-answer); }
.exam-type-colours [data-type-group="unknown"] { box-shadow:inset 0 -3px 0 var(--text-secondary); }
</style>
