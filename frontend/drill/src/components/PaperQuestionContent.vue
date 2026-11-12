<script setup lang="ts">
import type { ExamPaperQuestion } from '../types'
import { withWorkspacePrefix } from '../lib/runtimePath'

defineProps<{ question: ExamPaperQuestion }>()
</script>

<template>
  <div class="paper-question-content">
    <p v-if="!question.question_assets.length && question.prompt_text" class="paper-question-text">{{ question.prompt_text }}</p>
    <div v-if="question.question_assets.length" class="paper-question-assets">
      <img
        v-for="asset in question.question_assets"
        :key="asset.id"
        :src="withWorkspacePrefix(asset.url)"
        :width="asset.width"
        :height="asset.height"
        loading="lazy"
        decoding="async"
        :alt="question.display_label"
      />
    </div>
  </div>
</template>

<style scoped>
.paper-question-content { min-width:0; padding:24px 0; } .paper-question-text { font-size:16px; line-height:1.8; color:var(--text-primary); white-space:pre-wrap; } .paper-question-assets { display:grid; gap:8px; } .paper-question-assets img { display:block; width:100%; height:auto; background:#fff; border-radius:2px; }
</style>
