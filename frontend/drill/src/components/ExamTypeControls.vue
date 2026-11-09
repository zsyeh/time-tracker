<script setup lang="ts">
import { formatColours, typeGroups, typeLabel, typeText, type TypeStats } from '../lib/examTypes'
defineProps<{ modelValue: string; stats?: TypeStats }>()
const emit = defineEmits<{ 'update:modelValue': [value: string]; practice: [] }>()
</script>
<template>
  <section class="exam-type-controls" :aria-label="typeText('题型筛选与分析', 'Format filters and analysis')">
    <div class="exam-type-toolbar">
      <label>{{ typeText('题型', 'Format') }}<select :value="modelValue" @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)"><option value="">{{ typeLabel('all') }}</option><option v-for="key in typeGroups" :key="key" :value="key">{{ typeLabel(key) }}</option></select></label>
      <button type="button" class="exam-small-entry" @click="emit('practice')">{{ typeText('小题专练 →', 'Practise short questions →') }}</button>
      <label><input v-model="formatColours" type="checkbox" />{{ typeText('题型分色预览', 'Highlight formats') }}</label>
      <small>{{ typeText('小题含选择、填空、判断；简答单列。色点表示题型，原掌握颜色保留。', 'Short questions: choice, fill in and true / false. Short answers are separate. Dots show format; existing colours show mastery.') }}</small>
    </div>
    <div v-if="stats" class="exam-type-stats">
      <button v-for="key in typeGroups" :key="key" type="button" :class="[`exam-${key}`, { active: modelValue === key }]" @click="emit('update:modelValue', modelValue === key ? '' : key)">
        <strong>{{ typeLabel(key) }} · {{ stats[key]?.total || 0 }}</strong>
        <span>{{ typeText('已做', 'Attempted') }} {{ stats[key]?.attempted || 0 }} · {{ typeText('掌握', 'Mastered') }} {{ stats[key]?.mastered || 0 }} · {{ typeText('待复习', 'Review') }} {{ stats[key]?.review || 0 }}</span>
        <span>{{ typeText('覆盖率', 'Coverage') }} {{ stats[key]?.total ? Math.round((stats[key]?.attempted || 0) * 100 / stats[key]!.total) : 0 }}% · {{ typeText('已做掌握率', 'Mastery of attempted') }} {{ stats[key]?.attempted ? Math.round((stats[key]?.mastered || 0) * 100 / stats[key]!.attempted) + '%' : '—' }}</span>
      </button>
    </div>
  </section>
</template>
<style scoped>
.exam-type-controls { margin:14px 0; }
.exam-type-toolbar { display:flex; align-items:center; flex-wrap:wrap; gap:12px; }
.exam-type-toolbar label { display:flex; align-items:center; gap:8px; font-size:12px; }
.exam-type-toolbar select,.exam-small-entry { min-height:36px; padding:7px 10px; color:var(--text-primary); background:var(--bg-surface); border:1px solid var(--border-default); border-radius:var(--radius-sm); }
.exam-small-entry { cursor:pointer; color:var(--accent); }.exam-type-toolbar small { font-size:11px; color:var(--text-secondary); }
.exam-type-stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:8px; margin-top:10px; }
.exam-type-stats button { display:grid; gap:5px; padding:10px; color:var(--text-primary); background:var(--bg-surface); border:1px solid var(--border-default); border-top:3px solid var(--text-secondary); border-radius:var(--radius-sm); text-align:left; cursor:pointer; }
.exam-type-stats .exam-small { border-top-color:var(--accent); }.exam-type-stats .exam-large { border-top-color:var(--warning); }.exam-type-stats .exam-short_answer { border-top-color:#a895da; }
.exam-type-stats button.active { outline:1px solid var(--accent); }.exam-type-stats span { font-size:11px; color:var(--text-secondary); }
</style>
<style>
.exam-type-colours [data-type-group="small"] { box-shadow:inset 0 -3px 0 var(--accent); }
.exam-type-colours [data-type-group="large"] { box-shadow:inset 0 -3px 0 var(--warning); }
.exam-type-colours [data-type-group="short_answer"] { box-shadow:inset 0 -3px 0 #a895da; }
.exam-type-colours [data-type-group="unknown"] { box-shadow:inset 0 -3px 0 var(--text-secondary); }
</style>
