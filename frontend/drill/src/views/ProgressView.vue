<script setup lang="ts">
import PracticeTrendPanel from '../components/PracticeTrendPanel.vue'
import { typeText } from '../lib/examTypes'
import { runtimeWorkspace } from '../lib/runtimePath'

const isEi = runtimeWorkspace === 'ei'
</script>

<template>
  <section class="page progress-page">
    <header class="page-header progress-page-header">
      <div>
        <h1>{{ typeText('学习进度', 'Learning progress') }}</h1>
        <p>{{ isEi ? typeText('892 专业课的目标、工作量与趋势', 'EI goals, workload and trends') : typeText('数学二严选题的目标、工作量与趋势', 'Math II selected questions: goals, workload and trends') }}</p>
      </div>
      <RouterLink class="progress-diagnostics-link" to="/diagnostics">{{ typeText('查看解题能力', 'View solving ability') }} <span aria-hidden="true">→</span></RouterLink>
    </header>
    <PracticeTrendPanel />
  </section>
</template>

<style scoped>
.progress-page-header { align-items:center; margin-bottom:16px; }
.progress-page-header h1 { margin:0 0 4px; font-size:26px; }
.progress-page-header p { color:var(--text-secondary); font-size:14px; line-height:1.5; }
.progress-diagnostics-link { display:inline-flex; align-items:center; gap:8px; min-height:40px; padding:0 12px; flex:none; border:1px solid var(--border-default); border-radius:var(--radius-sm); color:var(--text-secondary); font-size:14px; text-decoration:none; }
.progress-diagnostics-link:hover { color:var(--text-primary); background:var(--bg-surface-hover); }
.progress-diagnostics-link:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
@media(max-width:620px) { .progress-page-header { align-items:start; flex-direction:column; gap:12px; } }
</style>
