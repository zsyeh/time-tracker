<script setup lang="ts">
import type { ExamPaperQuestion } from '../types'

defineProps<{ question: ExamPaperQuestion }>()
</script>

<template>
  <div class="paper-question-content">
    <p v-if="!question.question_assets.length && question.prompt_text" class="paper-question-text">{{ question.prompt_text }}</p>
    <div v-if="question.question_assets.length" class="paper-question-assets">
      <img
        v-for="asset in question.question_assets"
        :key="asset.id"
        :src="asset.url"
        :width="asset.width"
        :height="asset.height"
        loading="lazy"
        decoding="async"
        :alt="question.display_label"
      />
    </div>
  </div>
</template>
