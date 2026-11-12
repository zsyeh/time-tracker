<script setup lang="ts">
import { uiText } from '../lib/uiText'
import PdfPageStatusPanel from '../components/PdfPageStatusPanel.vue'
</script>

<template>
  <section class="page pdf-page-import-view">
    <header class="page-header">
      <div>

        <h1>{{ uiText("严选题 PDF 页码记录") }}</h1>
        <p>{{ uiText("仅适用于五科严选题。标准题库不参与匹配，也不能通过此入口批量记录。") }}</p>
      </div>
    </header>
    <aside class="selected-only-note">
      <strong>{{ uiText("严选题专用") }}</strong>
      <span>{{ uiText("请选择科目，并分别输入题目册与题答对照册的页码。系统将使用严选清单 UUID 和内容指纹双重核验。") }}</span>
    </aside>
    <PdfPageStatusPanel />
  </section>
</template>

<style scoped>
.selected-only-note { display: flex; gap:16px; align-items: center; margin: 0 0 18px; padding: 13px 16px; border:0; border-radius:8px; background:var(--surface-subtle); color:var(--text-secondary); font-size: 13px; line-height: 1.55; }
.selected-only-note strong { flex: none; color:var(--text-primary); }
@media (max-width: 600px) { .selected-only-note { display: block; } .selected-only-note strong { display: block; margin-bottom: 4px; } }
</style>
