<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import FullscreenReader from '../components/FullscreenReader.vue'
import VirtualPreviewList from '../components/preview/VirtualPreviewList.vue'
import { getPreviewAnchor, getPreviewSession, savePreviewAnchor, type PreviewSession } from '../lib/collectionPreview'
import { parseListContext, previewQuestionLocation, type ListContext, type PreviewAnchor, type PreviewItem } from '../lib/listContext'
import { createPreviewImagePipeline } from '../lib/preview/imagePipeline'
import { createPreviewRangeLoader } from '../lib/preview/rangeLoader'
import { withWorkspacePrefix } from '../lib/runtimePath'
import { accountPreferences } from '../../../shared/preferences/store'
const route = useRoute(), router = useRouter()
const context = computed(() => parseListContext(route.query.list))
const list = ref<InstanceType<typeof VirtualPreviewList> | null>(null), reader = ref<InstanceType<typeof FullscreenReader> | null>(null)
const session = shallowRef<PreviewSession | null>(null), revision = ref(0), count = ref(0), version = ref('')
const loading = ref(true), error = ref(''), notice = ref(''), current = ref(0), jump = ref('1')
const zoomItem = shallowRef<PreviewItem | null>(null)
const pipeline = createPreviewImagePipeline({ userId:accountPreferences.userId.value || undefined })
const noticeMessages: Record<string,string> = { PAPER_REVISION_PREVIEW_CANONICAL_PRACTICE_IS_SEPARATE:'此处预览试卷快照。打开当前原题会进入独立练习，不会修改这份试卷的题目或作答。', ENTRY_REMOVED_USING_NEAREST:'原题目已不在当前题单中，已定位到附近题目。' }
const noticeText = computed(() => noticeMessages[notice.value] ?? (/^[A-Z][A-Z0-9_]+$/.test(notice.value) ? '题单已更新，已恢复到附近题目。' : notice.value))
const images = computed(() => zoomItem.value?.preview.assets.map(asset => ({ src:withWorkspacePrefix(asset.url), width:asset.width, height:asset.height })) ?? [])
let generation = 0, positionSerial = 0, destroyed = false, lastAnchor: PreviewAnchor | null = null, activeContext: ListContext | null = null
const initialOwner = accountPreferences.userId.value
let rangeLoader = createRangeLoader()
function createRangeLoader() {
 return createPreviewRangeLoader({
  cached: offset => !!session.value?.get(offset),
  load: async (offset, signal) => {
   const active = session.value, token = generation
   if (!active || loading.value) return
   try {
    const page = await active.load({offset, signal})
    if (token !== generation || destroyed || signal.aborted) return
    update(); if (page.notice) { notice.value = page.notice; const anchor = lastAnchor; if (anchor) await list.value?.restoreAnchor({...anchor,index:page.located?.index ?? anchor.index}) }
   } catch (reason) { if (token === generation && !signal.aborted && !(reason instanceof DOMException && reason.name === 'AbortError')) error.value = reason instanceof Error ? reason.message : '部分题目加载失败' }
  },
 })
}
function item(index: number) { void revision.value; return session.value?.get(index) }
function remember(anchor: PreviewAnchor) {
 lastAnchor = anchor; current.value = anchor.index + 1; if (document.activeElement?.id !== 'preview-position') jump.value = String(current.value)
 if (activeContext) savePreviewAnchor(activeContext, anchor)
}
function save() { const anchor = list.value?.captureAnchor() ?? lastAnchor; if (anchor && activeContext) { lastAnchor = anchor; savePreviewAnchor(activeContext, anchor) } }
function update() { if (!session.value) return; count.value = session.value.count; version.value = session.value.version; revision.value++ }
async function start(fresh = false) {
 const token = ++generation; positionSerial++; loading.value = true; error.value = ''; rangeLoader.dispose(); rangeLoader = createRangeLoader()
 const ctx = context.value
 if (!ctx) { session.value?.abort(); session.value = null; activeContext = null; count.value = 0; version.value = ''; loading.value = false; error.value = '题单上下文无效，请返回列表重新打开预览。'; return }
 try {
  activeContext = ctx; session.value = getPreviewSession(ctx)
  const saved = lastAnchor ?? getPreviewAnchor(ctx)
  const entry = typeof route.query.entry === 'string' ? route.query.entry : undefined
  const uuid = typeof route.query.question === 'string' ? route.query.question : undefined
  const page = await session.value.load({ locate_entry: entry || saved?.entry_id, locate_uuid: uuid || saved?.question_uuid, fallback_index:saved?.index, fresh })
  if (token !== generation || destroyed) return
  update(); notice.value = page.notice || ''; loading.value = false
  await nextTick()
  const target = page.located ?? (saved ? session.value.get(Math.min(saved.index, Math.max(0,page.count-1))) : page.results[0])
  if (target) {
   // URL entry wins when opening a new origin; saved offset is used only for the same entry.
   const anchor: PreviewAnchor = { ...target, offset:saved?.entry_id === target.entry_id ? saved.offset : 0, collection_version:page.collection_version }
   await list.value?.restoreAnchor(anchor); if(token === generation && !destroyed) remember(list.value?.captureAnchor() ?? anchor)
  }
 } catch (reason) {
  if (token !== generation || destroyed || (reason instanceof DOMException && reason.name === 'AbortError')) return
  error.value = reason instanceof Error ? reason.message : '题单加载失败，请重试。'; loading.value = false
 }
}
function loadRange(first: number, last: number, visible = first) {
 if (!session.value || loading.value) return
 rangeLoader.schedule(first, last, visible)
}
async function go() {
 const n = Number(jump.value)
 if (!Number.isSafeInteger(n) || n < 1 || n > count.value) { jump.value = String(current.value || 1); return }
 const active = session.value; if (!active) return
 const token = generation, position = ++positionSerial
 try { const page = await active.load({offset:n-1}); if (token !== generation || position !== positionSerial || destroyed) return; update(); notice.value = page.notice || ''; await nextTick(); list.value?.scrollToIndex(n-1) }
 catch(reason) { if(token === generation && position === positionSerial && !destroyed) error.value = reason instanceof Error ? reason.message : '定位失败' }
}
async function openQuestion(value: PreviewItem) {
 const ctx = context.value; if (!ctx) return
 save(); const token = generation
 if (route.query.entry || route.query.question) {
  // A deep-link entry is a one-time positioning request. Consume it before
  // leaving so browser Back restores the most recent saved browsing anchor.
  // Preserve the exact list string to avoid starting a new-context reload.
  await router.replace({ path:route.path, query:{list:route.query.list}, hash:route.hash })
  if (token !== generation || destroyed) return
 }
 await router.push(previewQuestionLocation(ctx,value))
}
async function zoom(value: PreviewItem) { zoomItem.value = value; await nextTick(); await reader.value?.open() }
function changed() { save(); void start(true) }
function returnToList() { save(); void router.push(context.value?.returnTo ?? '/practice') }
onBeforeRouteLeave(save)
watch(() => route.query.list, () => { save(); lastAnchor = null; session.value?.abort(); void start() })
watch(accountPreferences.userId, owner => { if (owner === initialOwner) return; generation++; rangeLoader.dispose(); session.value?.abort(); session.value = null; pipeline.dispose(); count.value = 0; loading.value = false; error.value = '账号已变化，请返回题单重新打开预览。' })
onMounted(() => { void start(true); window.addEventListener('drill:question-state-changed', changed) })
onBeforeUnmount(() => { save(); destroyed = true; generation++; rangeLoader.dispose(); session.value?.abort(); pipeline.dispose(); window.removeEventListener('drill:question-state-changed', changed) })
</script>
<template>
 <section class="collection-preview" :data-cached-metadata="session?.cachedCount ?? 0">
  <header class="collection-preview-toolbar">
   <div class="collection-preview-heading"><button type="button" @click="returnToList">{{ context?.source === 'navigation' ? '返回做题' : '返回题单' }}</button><h1>题单预览</h1></div>
   <form v-if="count" class="preview-position" @submit.prevent="go"><label for="preview-position">第</label><input id="preview-position" v-model="jump" type="number" inputmode="numeric" min="1" :max="count" aria-label="定位到题单中的第几题" /><span>/ {{ count }}</span><button type="submit">定位</button></form>
  </header>
  <p v-if="notice" class="preview-notice" role="status">{{ noticeText }}</p>
  <div v-if="loading" class="preview-message" role="status">正在加载题单…</div>
  <div v-else-if="error && !count" class="preview-message" role="alert">{{ error }} <button type="button" @click="start(true)">重试</button></div>
  <template v-else>
   <p v-if="error" class="preview-notice" role="alert">{{ error }} <button type="button" @click="start(true)">重试</button></p>
   <VirtualPreviewList v-if="count" ref="list" :count="count" :version="version" :revision="revision" :get-item="item" :pipeline="pipeline" :paper-snapshot="context?.source === 'paper'" @range="loadRange" @anchor="remember" @open="openQuestion" @zoom="zoom" />
   <div v-else class="preview-message">当前筛选下没有题目。<button type="button" @click="returnToList">调整筛选</button></div>
  </template>
  <FullscreenReader ref="reader" hide-trigger :title="zoomItem?.label ?? '题目预览'" :content-key="zoomItem?.entry_id" :images="images" :markdown="images.length ? undefined : zoomItem?.preview.question_markdown" />
 </section>
</template>
<style scoped>
.collection-preview{width:min(1040px,calc(100% - 32px));margin:0 auto;padding:12px 0 0;min-width:0}
.collection-preview-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:8px}
.collection-preview-heading,.preview-position{display:flex;align-items:center;gap:8px;min-width:0}
h1{font-size:20px;line-height:1.4;margin:0;font-weight:600}
button{min-height:44px;border:0;background:var(--surface-hover);color:var(--text-primary,inherit);font:inherit;font-size:14px;border-radius:6px;padding:8px 12px;cursor:pointer}
button:focus-visible,input:focus-visible{outline:2px solid var(--accent,#6ba6ff);outline-offset:2px}
.preview-position{font-size:13px;font-variant-numeric:tabular-nums;margin:0}
.preview-position input{width:76px;min-height:44px;box-sizing:border-box;background:var(--bg-surface);color:var(--text-primary,inherit);font:inherit;border:1px solid var(--border-default);border-radius:6px;padding:8px}
.preview-message{padding:32px 8px;line-height:1.8;font-size:15px}
.preview-notice{margin:0 0 8px;font-size:13px;line-height:1.6;color:var(--text-secondary,#999);overflow-wrap:anywhere}
@media(max-width:480px){.collection-preview{width:calc(100% - 16px);padding-top:8px}.collection-preview-toolbar{gap:8px}h1{font-size:18px}.preview-position input{width:60px}}
</style>
