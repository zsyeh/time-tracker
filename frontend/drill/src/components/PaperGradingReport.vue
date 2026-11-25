<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { installStudyShortcuts } from '../lib/studyShortcuts'
import { paperKeyboardMarks } from '../lib/paperKeyboardMarks'
import { api } from '../lib/api'
import { patchQuestionState } from '../lib/workspace'
import { buildListContext, previewLocation } from '../lib/listContext'
import FullscreenReader from './FullscreenReader.vue'
import type { ExamPaper } from '../types'
import MarkdownSection from './MarkdownSection.vue'
import PaperQuestionContent from './PaperQuestionContent.vue'
import GradingReviewTable from './GradingReviewTable.vue'
import { withWorkspacePrefix } from '../lib/runtimePath'
const props = defineProps<{ paper: ExamPaper }>()
const route = useRoute(), router = useRouter()
const active = ref(1)
const dirtyReview = ref(false), savingReview = ref(false)
function allowNavigation() {
  return !savingReview.value && (!dirtyReview.value || window.confirm('本题批阅修改尚未保存，放弃修改并离开？'))
}
onBeforeRouteLeave(allowNavigation)
onBeforeRouteUpdate((to, from) => to.fullPath === from.fullPath || allowNavigation())
const detailElement = ref<HTMLElement | null>(null)
let renderedOverview = 0
function overviewRendered() {
  renderedOverview++
  if (route.query.question) void revealReview()
}
async function revealReview() {
  // Above-the-anchor Markdown must finish layout before restoring a question.
  if (renderedOverview < (grading.value.conflicts.length ? 2 : 1)) return
  await nextTick()
  detailElement.value?.scrollIntoView({ block: 'start', behavior: 'auto' })
}
const grading = computed(() => props.paper.grading!)
const item = computed(() => props.paper.items.find(i => i.position === active.value))
const review = computed(() => grading.value.items.find(i => i.position === active.value))
const shortcutError=ref(''),favoriteSaving=ref(false)
const reader=ref<InstanceType<typeof FullscreenReader>|null>(null),readerAnswer=ref(false)
const marks=paperKeyboardMarks(()=>item.value||null,()=>props.paper,reason=>{shortcutError.value=(reason as Error).message})
const readerImages=computed(()=>(readerAnswer.value?item.value?.question.answer_assets:item.value?.question.question_assets)?.map(a=>({src:withWorkspacePrefix(a.url),width:a.width,height:a.height}))||[])
function toggleKeyboardFullscreen() {
  if (reader.value?.isOpen) reader.value.close()
  else return fullscreen(readerAnswer.value)
}
async function fullscreen(answer=false) {
  if (answer && props.paper.status!=='completed') {shortcutError.value='考试未结束，暂不能查看答案。';return}
  readerAnswer.value=answer;await nextTick();await reader.value?.open()
}
async function favorite() {
  const q=item.value?.question;if(!q||favoriteSaving.value)return
  favoriteSaving.value=true
  try {const state=await api<{is_favorite:boolean;version:number}>(`/api/drill/questions/${q.uuid}/state/`,{method:'POST',body:JSON.stringify({is_favorite:!q.is_favorite,version:q.state_version||1})});q.is_favorite=state.is_favorite;q.state_version=state.version;patchQuestionState(q.uuid,{is_favorite:state.is_favorite,state_version:state.version});shortcutError.value='';reader.value?.showFeedback(state.is_favorite?'已收藏':'已取消收藏')}
  catch(reason){shortcutError.value=(reason as Error).message}finally{favoriteSaving.value=false}
}
let removeShortcuts:(()=>void)|undefined
onMounted(()=>{removeShortcuts=installStudyShortcuts({
 previous:()=>choose(active.value-1),next:()=>choose(active.value+1),favorite,
 review:()=>marks.mark('review'),mastered:()=>marks.mark('mastered'),undo:marks.undo,
 fullscreen:toggleKeyboardFullscreen,answer:()=>fullscreen(!readerAnswer.value),exit:toggleKeyboardFullscreen,
 preview:()=>{reader.value?.close();return router.push(previewLocation(buildListContext('paper',{paper:props.paper.uuid},route.fullPath)))},
},{blocked:()=>editingReviewBlocked(),feedback:action=>reader.value?.flashShortcut(action),error:reason=>{shortcutError.value=(reason as Error).message}})})
function editingReviewBlocked(){return dirtyReview.value||savingReview.value||marks.busy.value||favoriteSaving.value}
onUnmounted(()=>removeShortcuts?.())
const labels: Record<string,string> = { correct:'正确', incorrect:'错误', partial:'部分正确', incomplete:'未完成' }
watch(() => route.query.question, value => {
  const n = Number(value); active.value = props.paper.items.some(i => i.position === n) ? n : 1
  if (value) void revealReview()
}, { immediate:true })
function choose(n: number) {
  if (savingReview.value || !props.paper.items.some(i => i.position === n)) return
  if (dirtyReview.value && !window.confirm('本题批阅修改尚未保存，放弃修改并切换题目？')) return
  dirtyReview.value = false
  active.value = n
  if (Number(route.query.question) === n) void revealReview()
  void router.replace({ query:{ ...route.query, question:String(n) } })
}

</script>
<template>
  <section class="grading-report" aria-label="考试批阅记录">
    <nav class="report-links"><RouterLink to="/papers">← 考试记录</RouterLink><RouterLink :to="`/papers/${paper.uuid}/review?mode=all`">整卷回顾</RouterLink></nav>
    <header><div><h1>{{ grading.title }}</h1><p>{{ grading.exam_date }} · AI 辅助批阅 · 非官方估分</p></div><div class="score"><strong>{{ grading.score }}/{{ grading.maximum }}</strong><span> 分</span></div></header>
    <div class="score-track" role="meter" aria-label="试卷估分" :aria-valuenow="grading.score" :aria-valuemax="grading.maximum" :aria-valuemin="0"><i :style="{ width:`${grading.score / grading.maximum * 100}%` }" /></div>
    <p>实际用时 {{ grading.actual_duration_seconds / 60 }} / {{ paper.duration_minutes }} 分钟 · 时间利用率 {{ (grading.actual_duration_seconds / (paper.duration_minutes * 60) * 100).toFixed(2) }}% · 未分配逐题用时</p>
    <section class="subjects" aria-label="分学科得分图表"><div v-for="s in grading.subjects" :key="s.subject" class="subject"><span>{{ s.subject }}</span><div class="score-track" role="meter" :aria-label="s.subject" :aria-valuenow="s.score" :aria-valuemax="s.maximum" :aria-valuemin="0"><i :style="{ width:`${s.score / s.maximum * 100}%` }" /></div><b>{{ s.score }} / {{ s.maximum }}</b></div></section>
    <MarkdownSection title="总体批阅与估分说明" :source="grading.summary" @rendered="overviewRendered" />
    <MarkdownSection v-if="grading.conflicts.length" title="核对差异与证据" @rendered="overviewRendered" :source="grading.conflicts.map(v => `- ${v}`).join('\n')" />
    <p v-if="shortcutError" role="status">{{ shortcutError }}</p>
    <section class="question-review"><h2>逐题批阅</h2><nav class="question-grid" aria-label="选择批阅题目"><button v-for="g in grading.items" :key="g.position" type="button" :class="[g.status, { active:active === g.position }]" :aria-pressed="active === g.position" @click="choose(g.position)"><b>{{ g.position }}</b><span class="score-fraction">{{ g.earned }}/{{ g.maximum }}</span><small>{{ labels[g.status] }}</small></button></nav>
      <div id="paper-review-detail" ref="detailElement" class="review-toolbar"><button type="button" :disabled="active === 1" @click="choose(active-1)">上一题</button><button v-if="item" type="button" data-action="favorite" :aria-pressed="!!item.question.is_favorite" :disabled="favoriteSaving || marks.busy.value" title="收藏 / 取消收藏 (F)" @click="favorite">{{ favoriteSaving ? '保存中…' : item.question.is_favorite ? '已收藏 (F)' : '收藏 (F)' }}</button><strong>第 {{ active }} / {{ paper.items.length }} 题 · {{ review ? labels[review.status] : '' }}</strong><b v-if="review" class="score-fraction">{{ review.earned }}/{{ review.maximum }}</b><button type="button" :disabled="active === paper.items.length" @click="choose(active+1)">下一题</button><RouterLink v-if="item" :to="`/practice/${item.question.uuid}?grading_return=${encodeURIComponent(route.fullPath)}`">标准 Practice ↗</RouterLink></div>
      <details v-if="item" :key="`question-${active}`" class="review-original-question" open><summary>原题图</summary><PaperQuestionContent :question="item.question" /></details>
      <details v-if="item" :key="`answer-${active}`" class="review-original-answer" open><summary>答案贴图</summary><div class="answer-images"><img v-for="asset in item.question.answer_assets" :key="asset.id" :src="withWorkspacePrefix(asset.url)" :width="asset.width" :height="asset.height" loading="lazy" decoding="async" alt="原始答案" /></div></details>
      <GradingReviewTable v-if="review" :key="active" :paper-uuid="paper.uuid" :review="review" @saved="Object.assign(review, $event)" @dirty="dirtyReview=$event" @busy="savingReview=$event" />
    </section>
    <FullscreenReader ref="reader" hide-trigger :title="`第 ${active} 题 · ${readerAnswer ? '答案' : '题目'}`" :images="readerImages" :content-key="`${active}-${readerAnswer}`"><template #actions><button v-if="item" type="button" data-action="favorite" :aria-pressed="!!item.question.is_favorite" :disabled="favoriteSaving" @click="favorite">{{ favoriteSaving ? '保存中…' : item.question.is_favorite ? '已收藏 (F)' : '收藏 (F)' }}</button></template><template #recovery><p v-if="shortcutError" role="status">{{ shortcutError }}</p></template></FullscreenReader>
    <section><h2>五科学习薄弱点</h2><MarkdownSection v-for="(text, subject) in grading.weaknesses" :key="subject" :title="String(subject)" :source="text" :open="false" /></section>
    <MarkdownSection title="26 天复习安排与下一次考试用时" :source="grading.strategy" :open="false" />
  </section>
</template>
<style scoped>
.score strong, .subject b, .score-fraction { color:var(--score-ink, #c62828); font-family:SimHei,"PingFang SC","Microsoft YaHei",sans-serif; font-weight:800; font-variant-numeric:tabular-nums; } .report-links { display:flex; flex-wrap:wrap; gap:16px; align-items:center; } .report-links a { min-height:44px; display:inline-flex; align-items:center; } .grading-report { min-width:0; } header { display:flex; gap:16px; align-items:center; justify-content:space-between; flex-wrap:wrap; } h1 { font-size:24px; } h2 { font-size:18px; margin:24px 0 12px; } p { color:var(--text-secondary); font-size:14px; line-height:1.7; } .score strong { font-size:36px; font-variant-numeric:tabular-nums; } .score span { color:var(--text-secondary); } .score-track { height:8px; background:var(--surface-subtle); border-radius:4px; overflow:hidden; } .score-track i { display:block; height:100%; background:var(--accent); background:var(--color-accent, var(--accent)); min-width:0; } .subjects { display:grid; gap:16px; margin:24px 0; } .subject { display:grid; grid-template-columns:120px minmax(0,1fr) 90px; gap:16px; align-items:center; font-size:14px; } .subject b { text-align:right; font-variant-numeric:tabular-nums; } .question-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(72px,1fr)); gap:8px; } .question-grid button { display:grid; gap:4px; padding:8px; background:var(--surface-subtle); border:0; border-radius:4px; min-height:72px; cursor:pointer; color:var(--text-primary); } .question-grid button.active { outline:2px solid var(--accent); outline-offset:1px; } .question-grid small { font-size:12px; } .question-grid .correct small { color:var(--status-success, #55b88a); } .question-grid .incorrect small { color:var(--status-danger, #db7777); } .question-grid .partial small { color:var(--status-warning, #c69b46); } .review-toolbar { scroll-margin-top:64px; display:flex; align-items:center; flex-wrap:wrap; gap:12px; margin:24px 0 8px; } .review-toolbar button, .review-toolbar a { min-height:44px; padding:8px; border:0; background:var(--surface-subtle); color:var(--text-primary); border-radius:4px; font-size:14px; text-decoration:none; } .review-toolbar button:disabled { opacity:.4; } details > summary { min-height:44px; cursor:pointer; padding:12px 0; } .answer-images img { max-width:100%; height:auto; background:#fff; } .answer-images { display:grid; gap:8px; } @media(max-width:600px) { .subject { grid-template-columns:100px minmax(0,1fr) 72px; gap:8px; font-size:13px; } }
</style>
