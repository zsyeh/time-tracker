<script setup lang="ts">
import { useAccountPreferences } from '../../shared/preferences/store'
import PreferenceSyncStatus from '../../shared/ui/PreferenceSyncStatus.vue'
import type { SprintProgress } from '../types'
const props=defineProps<{progress:SprintProgress|null|undefined;today:string}>()
const emit=defineEmits<{changed:[]}>()
const preferences=useAccountPreferences()
const minutes=(value:number)=>{const n=Math.max(0,Math.floor(value));return `${Math.floor(n/60)}小时${n%60}分`}
const fill=(value:number)=>`${Math.max(0,Math.min(100,value))}%`
async function change(mode:'standard'|'sprint20',start=preferences.values['timer.goal_plan'].start_date){
 preferences.set('timer.goal_plan',{mode,start_date:start||props.today})
 await preferences.flush();emit('changed')
}
function selectMode(event:Event){const mode=(event.target as HTMLSelectElement).value as 'standard'|'sprint20';void change(mode,mode==='sprint20'&&preferences.values['timer.goal_plan'].mode!=='sprint20'?props.today:undefined)}
</script>
<template>
<section class="sprint-section" aria-label="每日学习目标配置">
 <header class="sprint-header"><h2>{{ progress?.name || '每日学习目标' }}</h2><div class="plan-controls"><label>目标模式<select :value="preferences.values['timer.goal_plan'].mode" @change="selectMode"><option value="standard">原有目标</option><option value="sprint20">考研最后20天冲刺</option></select></label><label v-if="preferences.values['timer.goal_plan'].mode==='sprint20'">起始日期<input type="date" :value="preferences.values['timer.goal_plan'].start_date" @change="change('sprint20',($event.target as HTMLInputElement).value)" /></label></div></header>
 <PreferenceSyncStatus />
 <template v-if="progress">
  <div class="sprint-summary"><div><span>今日目标进度</span><strong>{{ minutes(progress.today.credited_minutes) }} <small>/ 11小时21分</small></strong></div><b>{{ progress.today.completion_percent }}%</b><span>还差 {{ minutes(progress.today.remaining_minutes) }}</span></div>
  <div class="goal-track" role="progressbar" aria-label="当天总目标完成进度" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="Math.min(100,progress.today.completion_percent)"><i :style="{width:fill(progress.today.completion_percent)}" /></div>
  <p class="goal-note">今日实际净学习 {{ minutes(progress.today.actual_minutes) }} · 其中额外任务 {{ minutes(progress.today.extra_minutes) }}。各科超额独立保留，不抵扣其他科目。</p>
  <div class="sprint-subjects">
   <article v-for="row in progress.today.subjects" :key="row.subject" :data-subject="row.subject">
    <header><h3>{{ row.label }}</h3><b>{{ row.completion_percent }}%</b></header>
    <dl><div><dt>目标</dt><dd>{{ minutes(row.target_minutes) }}</dd></div><div><dt>实际净学习</dt><dd>{{ minutes(row.actual_minutes) }}</dd></div><div><dt>剩余基础目标</dt><dd>{{ minutes(row.remaining_minutes) }}</dd></div></dl>
    <div class="goal-track" role="progressbar" :aria-label="`${row.label}目标进度`" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="Math.min(100,row.completion_percent)"><i :style="{width:fill(row.completion_percent)}" /></div>
    <p class="goal-note">{{ row.task }}</p><p v-if="row.extra_minutes>0" class="goal-note">基础 {{ minutes(row.base_minutes) }} · 额外 {{ minutes(row.extra_minutes) }}（不计基础目标）</p>
   </article>
  </div>
  <div class="sprint-cumulative"><header><h3>20天累计学习进度</h3><span>第 {{ progress.day_index }} / 20 天 · {{ progress.start_date }} — {{ progress.end_date }}</span></header><div class="sprint-summary"><strong>{{ minutes(progress.cumulative.credited_minutes) }} <small>/ 227小时</small></strong><b>{{ progress.cumulative.completion_percent }}%</b></div><div class="goal-track" role="progressbar" aria-label="20天累计学习进度" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="Math.min(100,progress.cumulative.completion_percent)"><i :style="{width:fill(progress.cumulative.completion_percent)}" /></div><p class="goal-note">实际净学习 {{ minutes(progress.cumulative.actual_minutes) }} · 额外 {{ minutes(progress.cumulative.extra_minutes) }} · 完整达标 {{ progress.cumulative.completed_days }} 天。逐日、逐科核算，不用某一天的超额补其他天。</p></div>
  <p class="goal-note">英语作文及各科错题订正为额外任务：使用对应任务预设或“冲刺额外任务”标签，计入实际总时长。暂停与休息不计时，运行中进度每30秒刷新。</p>
 </template>
</section>
</template>
<style scoped>
.sprint-section{padding:20px 2px;border-bottom:1px solid var(--border-subtle);min-width:0}.sprint-header,.sprint-subjects header,.sprint-cumulative header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}h2{font-size:18px;margin:0}h3{font-size:15px;margin:0}.plan-controls{display:flex;gap:12px;flex-wrap:wrap}.plan-controls label{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--text-secondary)}select,input{min-height:36px;max-width:100%;font:inherit;color:var(--text-primary);background:var(--bg-surface);border:1px solid var(--border-subtle);border-radius:6px;padding:4px 8px}.sprint-summary{display:flex;align-items:baseline;gap:12px;justify-content:space-between;flex-wrap:wrap;margin:16px 0 8px}.sprint-summary>div{display:grid;gap:4px}.sprint-summary strong{font-size:24px;font-variant-numeric:tabular-nums}.sprint-summary small{font-size:14px;font-weight:400;color:var(--text-secondary)}.goal-track{height:6px;overflow:hidden;background:var(--surface-hover,var(--bg-sidebar));border-radius:4px}.goal-track i{display:block;height:100%;background:var(--accent-ink,var(--accent));transition:width .2s ease}.goal-note{font-size:12px;color:var(--text-secondary);line-height:1.6;margin:8px 0}.sprint-subjects{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px;margin:24px 0}.sprint-subjects article{min-width:0}.sprint-subjects dl{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:12px 0}.sprint-subjects dt{font-size:12px;color:var(--text-secondary)}.sprint-subjects dd{margin:4px 0;font-size:14px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}.sprint-cumulative{padding-top:16px;border-top:1px solid var(--border-subtle)}.sprint-cumulative header span{font-size:12px;color:var(--text-secondary)}@media(max-width:640px){.sprint-subjects{grid-template-columns:minmax(0,1fr);gap:20px}.sprint-summary strong{font-size:21px}.sprint-header{align-items:flex-start;flex-direction:column}.plan-controls{width:100%;gap:8px}.plan-controls label{flex-wrap:wrap}}@media(prefers-reduced-motion:reduce){.goal-track i{transition:none}}
</style>
