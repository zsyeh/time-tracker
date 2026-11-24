<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { ExamPaper } from '../types'
import MarkdownSection from './MarkdownSection.vue'
import PaperQuestionContent from './PaperQuestionContent.vue'
import { withWorkspacePrefix } from '../lib/runtimePath'
const props = defineProps<{ paper: ExamPaper }>()
const route = useRoute(), router = useRouter()
const active = ref(1)
const grading = computed(() => props.paper.grading!)
const item = computed(() => props.paper.items.find(i => i.position === active.value))
const review = computed(() => grading.value.items.find(i => i.position === active.value))
const labels: Record<string,string> = { correct:'正确', incorrect:'错误', partial:'部分正确', incomplete:'未完成' }
watch(() => route.query.question, value => {
  const n = Number(value); active.value = props.paper.items.some(i => i.position === n) ? n : 1
}, { immediate:true })
function choose(n: number) {
  if (!props.paper.items.some(i => i.position === n)) return
  active.value = n
  void router.replace({ query:{ ...route.query, question:String(n) } })
}
const detail = computed(() => review.value ? `**用户作答**\n\n${review.value.user_answer}\n\n**核对参考**\n\n${review.value.reference}\n\n**逐题批阅 / 需要掌握**\n\n${review.value.note}\n\n**复习优先级**：${review.value.priority}\n\n**核实情况**：${review.value.verification}` : '')
</script>
<template>
  <section class="grading-report" aria-label="考试批阅记录">
    <RouterLink to="/papers">← 考试记录</RouterLink>
    <header><div><h1>{{ grading.title }}</h1><p>{{ grading.exam_date }} · AI 辅助批阅 · 非官方估分</p></div><div class="score"><strong>{{ grading.score }}</strong><span> / {{ grading.maximum }} 分</span></div></header>
    <div class="score-track" role="meter" aria-label="试卷估分" :aria-valuenow="grading.score" :aria-valuemax="grading.maximum" :aria-valuemin="0"><i :style="{ width:`${grading.score / grading.maximum * 100}%` }" /></div>
    <p>实际用时 {{ grading.actual_duration_seconds / 60 }} / {{ paper.duration_minutes }} 分钟 · 时间利用率 {{ (grading.actual_duration_seconds / (paper.duration_minutes * 60) * 100).toFixed(2) }}% · 未分配逐题用时</p>
    <section class="subjects" aria-label="分学科得分图表"><div v-for="s in grading.subjects" :key="s.subject" class="subject"><span>{{ s.subject }}</span><div class="score-track" role="meter" :aria-label="s.subject" :aria-valuenow="s.score" :aria-valuemax="s.maximum" :aria-valuemin="0"><i :style="{ width:`${s.score / s.maximum * 100}%` }" /></div><b>{{ s.score }} / {{ s.maximum }}</b></div></section>
    <MarkdownSection title="总体批阅与估分说明" :source="grading.summary" />
    <MarkdownSection v-if="grading.conflicts.length" title="核对差异与证据" :source="grading.conflicts.map(v => `- ${v}`).join('\n')" />
    <section class="question-review"><h2>逐题批阅</h2><nav class="question-grid" aria-label="选择批阅题目"><button v-for="g in grading.items" :key="g.position" type="button" :class="[g.status, { active:active === g.position }]" :aria-pressed="active === g.position" @click="choose(g.position)"><b>{{ g.position }}</b><span>{{ g.earned }}/{{ g.maximum }}</span><small>{{ labels[g.status] }}</small></button></nav>
      <div class="review-toolbar"><button type="button" :disabled="active === 1" @click="choose(active-1)">上一题</button><strong>第 {{ active }} / {{ paper.items.length }} 题 · {{ review ? labels[review.status] : '' }}</strong><button type="button" :disabled="active === paper.items.length" @click="choose(active+1)">下一题</button><RouterLink v-if="item" :to="`/practice/${item.question.uuid}?grading_return=${encodeURIComponent(route.fullPath)}`">标准 Practice ↗</RouterLink></div>
      <MarkdownSection title="本题批阅记录" :source="detail" />
      <details v-if="item"><summary>查看本题原始题图</summary><PaperQuestionContent :question="item.question" /></details>
      <details v-if="item"><summary>查看原答案贴图</summary><div class="answer-images"><img v-for="asset in item.question.answer_assets" :key="asset.id" :src="withWorkspacePrefix(asset.url)" :width="asset.width" :height="asset.height" loading="lazy" decoding="async" alt="原始答案" /></div></details>
    </section>
    <section><h2>五科学习薄弱点</h2><MarkdownSection v-for="(text, subject) in grading.weaknesses" :key="subject" :title="String(subject)" :source="text" :open="false" /></section>
    <MarkdownSection title="26 天复习安排与下一次考试用时" :source="grading.strategy" :open="false" />
  </section>
</template>
<style scoped>
.grading-report { min-width:0; } header { display:flex; gap:16px; align-items:center; justify-content:space-between; flex-wrap:wrap; } h1 { font-size:24px; } h2 { font-size:18px; margin:24px 0 12px; } p { color:var(--text-secondary); font-size:14px; line-height:1.7; } .score strong { font-size:36px; font-variant-numeric:tabular-nums; } .score span { color:var(--text-secondary); } .score-track { height:8px; background:var(--surface-subtle); border-radius:4px; overflow:hidden; } .score-track i { display:block; height:100%; background:var(--accent); background:var(--color-accent, var(--accent)); min-width:0; } .subjects { display:grid; gap:16px; margin:24px 0; } .subject { display:grid; grid-template-columns:120px minmax(0,1fr) 90px; gap:16px; align-items:center; font-size:14px; } .subject b { text-align:right; font-variant-numeric:tabular-nums; } .question-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(72px,1fr)); gap:8px; } .question-grid button { display:grid; gap:4px; padding:8px; background:var(--surface-subtle); border:0; border-radius:4px; min-height:72px; cursor:pointer; color:var(--text-primary); } .question-grid button.active { outline:2px solid var(--accent); outline-offset:1px; } .question-grid small { font-size:12px; } .question-grid .correct small { color:var(--status-success, #55b88a); } .question-grid .incorrect small { color:var(--status-danger, #db7777); } .question-grid .partial small { color:var(--status-warning, #c69b46); } .review-toolbar { display:flex; align-items:center; flex-wrap:wrap; gap:12px; margin:24px 0 8px; } .review-toolbar button, .review-toolbar a { min-height:44px; padding:8px; border:0; background:var(--surface-subtle); color:var(--text-primary); border-radius:4px; font-size:14px; text-decoration:none; } .review-toolbar button:disabled { opacity:.4; } details > summary { min-height:44px; cursor:pointer; padding:12px 0; } .answer-images img { max-width:100%; height:auto; background:#fff; } .answer-images { display:grid; gap:8px; } @media(max-width:600px) { .subject { grid-template-columns:100px minmax(0,1fr) 72px; gap:8px; font-size:13px; } }
</style>
