<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Back, CopyDocument, EditPen, Link, View } from '@element-plus/icons-vue'
import { api, patch, post, remove } from '../lib/api'
import type { ReviewTrend as ReviewTrendType, SessionShareStatus, StudySession } from '../types'
import MarkdownPreview from '../components/MarkdownPreview.vue'
import ReviewTrend from '../components/ReviewTrend.vue'
import PageHeader from '../components/layout/PageHeader.vue'

const props = defineProps<{ uuid: string }>()
const router = useRouter()
const session = ref<StudySession | null>(null)
const reviewTrend = ref<ReviewTrendType | null>(null)
const share = ref<SessionShareStatus | null>(null)
const revealedShareUrl = ref('')
const expiry = ref('')
const loading = ref(true)
const sharing = ref(false)
const editing = ref(false)
const notFound = ref(false)
const edit = reactive({ title: '', details: '' })

function duration(minutes: number) {
  return minutes >= 60 ? `${Math.floor(minutes / 60)}h ${minutes % 60}m` : `${minutes}m`
}

function localDate(value: string | null) {
  return value ? new Date(value).toLocaleString('en-GB') : '—'
}

async function load() {
  loading.value = true
  notFound.value = false
  try {
    const value = await api<StudySession>(`/api/sessions/${props.uuid}/`)
    session.value = value
    Object.assign(edit, { title: value.title || '', details: value.details })
    const requests: Array<Promise<unknown>> = [
      api<SessionShareStatus>(`/api/sessions/${props.uuid}/share/`).then((state) => { share.value = state }),
    ]
    if (value.status === 'completed') {
      requests.push(post<ReviewTrendType>(`/api/sessions/${props.uuid}/reviews/`).then((trend) => {
        reviewTrend.value = trend
        value.review_count = trend.total
        value.last_reviewed_at = trend.last_reviewed_at
      }))
    }
    await Promise.all(requests)
  } catch (error) {
    notFound.value = (error as Error & { status?: number }).status === 404
    if (!notFound.value) ElMessage.error((error as Error).message)
  } finally { loading.value = false }
}

async function save() {
  if (!session.value) return
  try {
    session.value = await patch<StudySession>(`/api/sessions/${props.uuid}/`, edit)
    editing.value = false
    ElMessage.success('Session updated')
  } catch (error) { ElMessage.error((error as Error).message) }
}

async function createShare() {
  sharing.value = true
  try {
    const payload = expiry.value ? { expires_at: new Date(expiry.value).toISOString() } : { expires_at: null }
    share.value = await post<SessionShareStatus>(`/api/sessions/${props.uuid}/share/`, payload)
    revealedShareUrl.value = share.value.share_url || ''
    ElMessage.success('Share link created')
  } catch (error) { ElMessage.error((error as Error).message) }
  finally { sharing.value = false }
}

async function copyShare() {
  if (!revealedShareUrl.value) return
  await navigator.clipboard.writeText(revealedShareUrl.value)
  ElMessage.success('Share link copied')
}

async function revokeShare() {
  try {
    await ElMessageBox.confirm('The current public URL will stop working immediately.', 'Revoke share?', {
      type: 'warning', confirmButtonText: 'Revoke', cancelButtonText: 'Cancel',
    })
    share.value = await remove<SessionShareStatus>(`/api/sessions/${props.uuid}/share/`)
    revealedShareUrl.value = ''
    ElMessage.success('Share revoked')
  } catch (error) { if (error !== 'cancel') ElMessage.error((error as Error).message) }
}

watch(() => props.uuid, load)
onMounted(load)
</script>

<template>
  <div class="workspace-view session-article-view" v-loading="loading">
    <section v-if="notFound" class="resource-not-found">
      <PageHeader title="Session unavailable" metadata="This resource is missing or private"><template #actions><button type="button" class="header-action" @click="router.push('/sessions')"><el-icon><Back /></el-icon> Sessions</button></template></PageHeader>
      <div class="empty-workspace"><span>404</span><h2>Session unavailable</h2><p>This resource does not exist or is not available to your account.</p></div>
    </section>

    <template v-else-if="session">
      <PageHeader context="Sessions" :title="session.title || 'Untitled session'" :metadata="`${session.subject_label}${session.task_path ? ` · ${session.task_path}` : ''}`"><template #actions><button type="button" class="header-action" @click="router.push('/sessions')"><el-icon><Back /></el-icon> Sessions</button><el-button v-if="!editing" :icon="EditPen" @click="editing = true">Edit</el-button></template></PageHeader>
      <div class="session-detail-workspace">
        <main class="session-document">
          <div class="document-identity"><span>Session article</span><small>{{ session.uuid }}</small></div>
          <el-form v-if="editing" label-position="top" class="simple-review review-editor">
            <el-form-item label="Title"><el-input v-model="edit.title" maxlength="500" show-word-limit /></el-form-item>
            <el-form-item label="Markdown source"><el-input v-model="edit.details" type="textarea" :rows="20" /></el-form-item>
            <MarkdownPreview :source="edit.details" />
            <div class="editor-actions"><el-button @click="editing = false">Cancel</el-button><el-button type="primary" @click="save">Save changes</el-button></div>
          </el-form>
          <MarkdownPreview v-else :key="session.uuid" :source="session.details" default-open allow-fullscreen empty-text="No details were recorded for this session." />
        </main>
        <aside class="session-context-rail" aria-label="Session context">
          <section class="context-section"><header><span>Properties</span><b :class="`state-${session.status}`">{{ session.status }}</b></header><dl class="context-properties"><div><dt>Subject</dt><dd>{{ session.subject_label }}</dd></div><div><dt>Started</dt><dd>{{ localDate(session.start_time) }}</dd></div><div><dt>Ended</dt><dd>{{ localDate(session.end_time) }}</dd></div><div><dt>Credited</dt><dd>{{ duration(session.credited_duration_minutes) }}</dd></div><div><dt>Actual</dt><dd>{{ duration(session.duration_minutes) }}</dd></div><div><dt>Efficiency</dt><dd>{{ session.efficiency_grade }} · ×{{ session.efficiency_coefficient.toFixed(2) }}</dd></div><div><dt>Disturbances</dt><dd>{{ session.disturbance_count }}</dd></div></dl></section>
          <section v-if="session.tags.length" class="context-section"><header><span>Tags</span></header><div class="context-tags"><span v-for="tag in session.tags" :key="tag.id">#{{ tag.name }}</span></div></section>
          <section v-if="session.status === 'completed'" class="context-section"><header><span>Review activity</span><b>{{ reviewTrend?.total || 0 }}</b></header><ReviewTrend :trend="reviewTrend" :loading="loading" /></section>
          <section v-if="session.status === 'completed'" class="context-section share-context"><header><span>Public share</span><b class="share-state" :class="`state-${share?.status || 'private'}`">{{ share?.status || 'private' }}</b></header><p>Read-only and revocable. Private metadata is never included.</p><template v-if="!share?.is_active"><el-input v-model="expiry" type="datetime-local" aria-label="Optional share expiry" /><el-button type="primary" :icon="Link" :loading="sharing" @click="createShare">Create link</el-button></template><template v-else><small v-if="share.expires_at">Expires {{ localDate(share.expires_at) }}</small><small v-else>No expiry</small><div class="share-actions"><el-button v-if="revealedShareUrl" :icon="CopyDocument" @click="copyShare">Copy</el-button><el-button type="danger" plain @click="revokeShare">Revoke</el-button></div></template><div v-if="revealedShareUrl" class="share-reveal"><el-icon><View /></el-icon><a :href="revealedShareUrl" target="_blank" rel="noopener noreferrer nofollow">Open shared article</a></div><p v-else-if="share?.is_active" class="share-once-note">Only the token hash remains. Create a new link if the original was not saved.</p></section>
        </aside>
      </div>
    </template>
  </div>
</template>
