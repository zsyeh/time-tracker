<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../lib/api'

type Grade = 'A'|'B'|'C'|'D'
interface Topic { id:number; chapter:string; title:string; requirement:string; grade:Grade; attempts:number; accuracy:number|null; average_time_seconds:number|null; last_reviewed_at:string|null; next_review_at:string|null; due:boolean; correct_streak:number; retention_score:number; representative_question_uuid:string|null }
interface Course { code:string; label:string; coverage_percent:number; counts:Record<Grade,number>; topics:Topic[] }
interface Recommendation extends Topic { course:string; reason:string; priority:number }
interface Payload { coverage_percent:number; counts:Record<Grade,number>; due_count:number; courses:Course[]; recommendations:Recommendation[]; type_stats:Array<{type:string;count:number;accuracy:number|null;average_time_seconds:number|null}>; diagnosis:{largest_gap:string;allocation:string;next_focus:string}; requirement_notice:string }
const data=ref<Payload|null>(null), loading=ref(true), error=ref(''), saving=ref<number|null>(null)
const openCourses=ref(new Set<string>(['circuit']))
function toggleCourse(code:string){ const next=new Set(openCourses.value); next.has(code)?next.delete(code):next.add(code); openCourses.value=next }
function duration(seconds:number|null){ if(seconds===null)return '—'; return seconds>=60?`${Math.floor(seconds/60)}m ${seconds%60}s`:`${seconds}s` }
function requirement(value:string){ return ({master:'掌握',understand:'理解',know:'了解',unspecified:'未核定'} as Record<string,string>)[value]||value }
async function load(silent=false){
  if(!silent) loading.value=true
  error.value=''
  try{ data.value=await api<Payload>('/api/drill/cockpit/') }
  catch(reason){ error.value=(reason as Error).message }
  finally{ if(!silent) loading.value=false }
}
async function setGrade(topic:Topic,grade:Grade){
  if(topic.grade===grade || saving.value===topic.id) return
  const previous=topic.grade
  topic.grade=grade
  saving.value=topic.id
  try{
    const result=await api<{grade:Grade;next_review_at:string|null;retention_score:number;correct_streak:number}>(`/api/drill/cockpit/topics/${topic.id}/`,{method:'PATCH',body:JSON.stringify({grade,reviewed:true})})
    topic.grade=result.grade
    topic.next_review_at=result.next_review_at
    topic.retention_score=result.retention_score
    topic.correct_streak=result.correct_streak
    void load(true)
  }catch(reason){
    topic.grade=previous
    error.value=(reason as Error).message
  }finally{ saving.value=null }
}
onMounted(()=>void load())
</script>
<template><section class="page cockpit-page"><header class="page-header"><div><span class="eyebrow">892 PREPARATION</span><h1>892 备考驾驶舱</h1><p>Coverage, mastery, retention and exam readiness from real records.</p></div><RouterLink class="header-action" to="/practice">Practice →</RouterLink></header><p v-if="error" class="error-state">{{ error }}</p><div v-if="loading" class="question-skeleton">BUILDING 892 COCKPIT…</div><template v-else-if="data"><section class="cockpit-diagnosis"><div><span>最大漏洞</span><strong>{{ data.diagnosis.largest_gap }}</strong></div><div><span>投入分布</span><strong>{{ data.diagnosis.allocation }}</strong></div><div><span>下一步重点</span><strong>{{ data.diagnosis.next_focus }}</strong></div></section><section class="cockpit-overview"><div class="cockpit-total"><span>SYLLABUS COVERAGE</span><strong>{{ data.coverage_percent }}%</strong><small>{{ data.due_count }} reviews due</small></div><div v-for="course in data.courses" :key="course.code"><span>{{ course.label }}</span><strong>{{ course.coverage_percent }}%</strong><small>A {{ course.counts.A }} · B {{ course.counts.B }} · C {{ course.counts.C }} · D {{ course.counts.D }}</small><i><b :style="{width:`${course.coverage_percent}%`}" /></i></div></section><p class="cockpit-notice">{{ data.requirement_notice }}</p><section class="cockpit-grid"><div class="cockpit-primary"><header class="section-heading"><div><span class="eyebrow">MASTERY MAP</span><h2>考纲掌握地图</h2></div><small>Quick-rate A/B/C/D. Requirement and personal state are independent.</small></header><article v-for="course in data.courses" :key="course.code" class="cockpit-course"><button class="course-toggle" @click="toggleCourse(course.code)"><span>{{ course.label }}</span><small>{{ course.topics.length }} points · {{ course.coverage_percent }}%</small><b>{{ openCourses.has(course.code)?'−':'+' }}</b></button><div v-if="openCourses.has(course.code)" class="topic-table"><div class="topic-row topic-head"><span>Knowledge point</span><span>Requirement</span><span>Evidence</span><span>Personal mastery</span><span>Action</span></div><div v-for="topic in course.topics" :key="topic.id" class="topic-row" :class="{due:topic.due}"><div><small>{{ topic.chapter }}</small><strong>{{ topic.title }}</strong></div><span class="requirement">{{ requirement(topic.requirement) }}</span><span class="evidence">{{ topic.attempts }} attempts<small>{{ topic.accuracy===null?'No score':`${topic.accuracy}% correct` }}</small></span><div class="grade-switch"><button v-for="grade in (['A','B','C','D'] as Grade[])" :key="grade" :class="[`grade-${grade.toLowerCase()}`,{active:topic.grade===grade}]" :disabled="saving===topic.id" @click="setGrade(topic,grade)">{{ grade }}</button></div><RouterLink v-if="topic.representative_question_uuid" :to="`/practice/${topic.representative_question_uuid}?from=cockpit`">Practice →</RouterLink><span v-else>—</span></div></div></article></div><aside><section class="cockpit-recommend"><header><span class="eyebrow">TODAY</span><h2>今日学习建议</h2></header><article v-for="item in data.recommendations" :key="item.id"><div><span>{{ item.course }}</span><b :class="`grade-${item.grade.toLowerCase()}`">{{ item.grade }}</b></div><strong>{{ item.title }}</strong><p>{{ item.reason }}</p><RouterLink v-if="item.representative_question_uuid" :to="`/practice/${item.representative_question_uuid}?from=cockpit`">Start representative question →</RouterLink></article><p v-if="!data.recommendations.length" class="empty-state">No evidence-backed task yet.</p></section><section class="cockpit-types"><header><span class="eyebrow">EXAM ABILITY</span><h2>题型能力</h2></header><div v-for="item in data.type_stats" :key="item.type"><strong>{{ item.type.replaceAll('_',' ') }}</strong><span>{{ item.count }} attempts</span><span>{{ item.accuracy===null?'—':`${item.accuracy}%` }}</span><span>{{ duration(item.average_time_seconds) }}</span></div><p v-if="!data.type_stats.length">Complete questions to build evidence.</p></section></aside></section></template></section></template>
