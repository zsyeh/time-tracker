<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { QuestionDetail } from '../types'

const props = defineProps<{ question: QuestionDetail }>()
const emit = defineEmits<{ select: [uuid: string] }>()
const root = ref<HTMLElement | null>(null)
const assets = computed(() => props.question.question_assets || props.question.assets || [])
const anchors = computed(() => props.question.source_context?.anchors || [])
let sequence = 0

async function scrollToCurrent() {
  const token = ++sequence
  await nextTick()
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
  if (token !== sequence) return
  root.value?.querySelector<HTMLElement>('[data-current-source-question="true"]')
    ?.scrollIntoView({ block: 'center', behavior: 'auto' })
}

watch(() => [props.question.uuid, props.question.source_context?.anchor?.asset_id, props.question.source_context?.anchor?.y],
  () => void scrollToCurrent(), { immediate: true, flush: 'post' })
defineExpose({ scrollToCurrent })
</script>

<template>
  <div ref="root" class="source-paper-viewer">
    <p class="source-paper-help">原图完整显示 · 点击左侧题号切换当前小题，掌握情况逐题保存。</p>
    <p v-if="question.source_context?.anchor" class="source-paper-help">本题切分边界尚待核对，暂保留完整原卷，避免遗漏题图。</p>
    <p v-if="question.source_context?.index_complete === false" class="source-paper-help">本卷部分扫描题号尚待补全，原卷所有页面仍完整保留。</p>
    <figure v-for="asset in assets" :key="asset.id" class="source-paper-page" :style="{ aspectRatio: `${asset.width} / ${asset.height}` }" :data-source-asset="asset.id">
      <img :src="asset.url" :width="asset.width" :height="asset.height" alt="完整原卷页面" loading="eager" decoding="async" />
      <button v-for="anchor in anchors.filter((item) => item.asset_id === asset.id)" :key="anchor.uuid"
        type="button" class="source-question-pin" :class="[`source-state-${anchor.state}`, { current: anchor.uuid === question.uuid }]"
        :style="{ top: `${anchor.y * 100}%` }" :data-source-question="anchor.uuid"
        :data-current-source-question="anchor.uuid === question.uuid ? 'true' : undefined"
        :aria-current="anchor.uuid === question.uuid ? 'true' : undefined" :aria-label="`定位到${anchor.label}`" :title="anchor.label"
        @click="emit('select', anchor.uuid)">{{ anchor.label }}</button>
    </figure>
  </div>
</template>

<style scoped>
.source-paper-help { margin: 0 0 12px; color: #505763; font-size: 12px; }
.source-paper-viewer { box-sizing: border-box; min-width: 0; padding-left: 76px; }
.source-paper-page { position: relative; width: 100%; margin: 0 auto 12px; background: white; }
.source-paper-page img { display: block; width: 100%; max-width: 100%; height: auto; margin: 0; }
.source-question-pin { position: absolute; left: -72px; z-index: 1; box-sizing: border-box; width: 64px; padding: 3px 5px; overflow-wrap: anywhere; border: 1px solid #87919f; border-radius: 5px; background: #f5f6f8f0; color: #343b45; font-size: 10px; line-height: 1.35; cursor: pointer; transform: translateY(-90%); scroll-margin: 100px; text-align: left; }
.source-question-pin.current { border: 2px solid #2169da; color: #1252af; background: #edf4ff; box-shadow: 0 0 0 3px #2169da33; }
.source-state-mastered { border-color: #2c854e; background: #edf9f1f0; }
.source-state-review { border-color: #bd8b18; background: #fff7dff0; }
@media (max-width: 600px) {
  .source-paper-viewer { padding-left: 50px; }
  .source-question-pin { left: -46px; width: 40px; padding: 3px; }
}
</style>
