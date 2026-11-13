<script setup lang="ts">
import { computed } from 'vue'
import MarkdownAnswer from '../MarkdownAnswer.vue'
import PreviewAssetImage from './PreviewAssetImage.vue'
import type { PreviewItem } from '../../lib/listContext'
import type { PreviewImagePipeline } from '../../lib/preview/imagePipeline'
const props = defineProps<{ item: PreviewItem; pipeline: PreviewImagePipeline; scroller: HTMLElement | null; paperSnapshot?: boolean }>()
const emit = defineEmits<{ open: [item: PreviewItem]; zoom: [item: PreviewItem] }>()
const openLabel = computed(() => props.paperSnapshot ? '打开当前原题（独立练习）' : '进入做题')
const masteryState = computed(() => props.item.review_overdue || props.item.state === 'overdue' ? 'overdue' : ['mastered','done','correct'].includes(props.item.state) ? 'mastered' : ['review','review_later','wrong'].includes(props.item.state) ? 'review' : 'unattempted')
const stateLabel = computed(() => masteryState.value === 'overdue' ? '逾期复习' : ({ mastered: '已掌握', review: '待复习', review_later: '待复习', unattempted: '未做', unseen: '未做', new: '未做', wrong: '待复习' }[props.item.state] || props.item.state || '未做'))
const resultLabel = computed(() => ({done:'已做',correct:'已掌握',review:'待复习',reset:'重置'}[props.item.attempt?.result ?? ''] || props.item.attempt?.result || ''))
const attemptDate = computed(() => {
 if (!props.item.attempt) return ''
 const date = new Date(props.item.attempt.created_at)
 return Number.isNaN(date.getTime()) ? props.item.attempt.created_at : date.toLocaleString('zh-CN', { year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit' })
})
</script>
<template>
 <article class="preview-question" :data-entry-id="item.entry_id" :aria-label="`${item.index + 1}. ${item.label}`">
  <header class="preview-question-header" :class="{'paper-snapshot':paperSnapshot}">
   <div class="preview-question-title"><span class="preview-index">{{ item.index + 1 }}</span><h2>{{ item.label }}</h2></div>
   <button type="button" class="preview-open" @click="emit('open', item)">{{ openLabel }} <span aria-hidden="true">↗</span></button>
  </header>
  <div class="preview-question-meta"><span>{{ item.document }}</span><span v-if="item.topic">{{ item.topic }}</span><span class="preview-mastery-status" :data-status="masteryState"><i aria-hidden="true" />{{ stateLabel }}</span><span v-if="item.is_favorite">已收藏</span><span v-if="item.attempt">{{ attemptDate }} · {{ resultLabel }}</span><button v-if="item.preview.assets.length" type="button" class="preview-row-zoom" @click="emit('zoom', item)">放大题图</button></div>
  <p v-if="item.note_excerpt" class="preview-note">{{ item.note_excerpt }}</p>
  <div v-if="item.preview.question_markdown && !item.preview.assets.length" class="preview-markdown"><MarkdownAnswer :source="item.preview.question_markdown" /></div>
  <PreviewAssetImage v-for="(asset, index) in item.preview.assets" :key="asset.id" :asset="asset" :pipeline="pipeline" :scroller="scroller" :label="`${item.label} · 题图 ${index + 1}`" :open-label="openLabel" @open="emit('open', item)" />
  <p v-if="!item.preview.question_markdown && !item.preview.assets.length" class="preview-empty">暂无题干预览，可进入原题查看。</p>
  <p v-if="item.preview.source_page" class="preview-source">原页预览，可能包含同页其他题目。</p>
 </article>
</template>
<style scoped>
.preview-question{padding:16px;min-width:0;border-bottom:1px solid var(--border-subtle)}
.preview-question-header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.preview-question-header.paper-snapshot{flex-wrap:wrap}
.preview-question-title{display:flex;gap:12px;align-items:baseline;min-width:0}
h2{font-size:16px;line-height:1.5;font-weight:600;margin:0;overflow-wrap:anywhere}
.preview-index{font-size:13px;color:var(--text-muted,#888);font-variant-numeric:tabular-nums;flex-shrink:0}
.preview-open{flex-shrink:0;min-height:44px;padding:8px 12px;border:0;background:var(--surface-hover);color:var(--text-primary,inherit);border-radius:6px;font:inherit;font-size:14px;cursor:pointer}
.preview-open:focus-visible{outline:2px solid var(--accent,#6ba6ff);outline-offset:2px}
.preview-row-zoom{margin-left:auto;min-width:44px;min-height:44px;padding:8px;border:0;border-radius:6px;background:transparent;color:var(--text-secondary,#999);font:inherit;cursor:pointer}
.preview-row-zoom:hover{background:var(--surface-hover)}
.preview-row-zoom:focus-visible{outline:2px solid var(--accent,#6ba6ff);outline-offset:2px}
.preview-mastery-status{display:inline-flex;align-items:center;gap:6px;font-weight:600;color:var(--text-secondary)}
.preview-mastery-status i{width:7px;height:7px;border-radius:50%;background:currentColor;flex:none}
.preview-mastery-status[data-status="mastered"]{color:var(--success)}
.preview-mastery-status[data-status="review"]{color:var(--warning)}
.preview-mastery-status[data-status="overdue"]{color:var(--danger)}
.preview-question-meta{align-items:center;display:flex;flex-wrap:wrap;gap:4px 16px;color:var(--text-secondary,#999);font-size:12px;line-height:1.6;margin:4px 0 8px;overflow-wrap:anywhere}
.preview-note,.preview-source,.preview-empty{font-size:13px;line-height:1.6;color:var(--text-secondary,#999);margin:8px 0}
.preview-note{white-space:pre-wrap;overflow-wrap:anywhere}
.preview-markdown{margin-top:12px;min-width:0;overflow-x:auto;font-size:15px}
@media(max-width:480px){.preview-question{padding:12px}.preview-question-header{gap:8px}.preview-open{padding:8px}.preview-question-header.paper-snapshot{flex-wrap:wrap}
.preview-question-title{gap:8px}}
</style>
