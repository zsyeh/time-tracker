<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Back, CopyDocument, EditPen, Link, View } from '@element-plus/icons-vue'
import { api, patch, post, remove } from '../lib/api'
import type { ReviewTrend as ReviewTrendType, SessionShareStatus, StudySession } from '../types'
import MarkdownPreview from '../components/MarkdownPreview.vue'
import ReviewTrend from '../components/ReviewTrend.vue'

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
  <div class="view-stack session-article-view" v-loading="loading">
    <section v-if="notFound" class="panel resource-not-found">
      <span class="eyebrow">SESSION / NOT FOUND</span><h1>Session unavailable</h1><p>This resource does not exist or is not available to your account.</p><el-button type="primary" @click="router.push('/sessions')">Back to Sessions</el-button>
    </section>

    <template v-else-if="session">
      <section class="page-intro session-article-heading">
        <div><button type="button" class="article-back" @click="router.push('/sessions')"><el-icon><Back /></el-icon> SESSION HISTORY</button><span class="eyebrow">SESSION ARTICLE / {{ session.uuid }}</span><h1>{{ session.title || 'Untitled session' }}</h1><p>{{ session.subject_label }}<span v-if="session.task_path"> · {{ session.task_path }}</span> · permanent private resource</p></div>
        <el-button v-if="!editing" :icon="EditPen" @click="editing = true">Edit</el-button>
      </section>

      <section class="panel session-article-card session-detail-page">
        <dl><div><dt>SUBJECT</dt><dd>{{ session.subject_label }}</dd></div><div><dt>START</dt><dd>{{ localDate(session.start_time) }}</dd></div><div><dt>END</dt><dd>{{ localDate(session.end_time) }}</dd></div><div><dt>DURATION</dt><dd>{{ duration(session.duration_minutes) }}</dd></div></dl>
        <p class="session-disturbance-summary"><b>{{ session.disturbance_count }}</b> DISTURBANCE{{ session.disturbance_count === 1 ? '' : 'S' }}<span v-if="session.last_disturbance_at"> · LAST {{ localDate(session.last_disturbance_at) }}</span></p>
        <div v-if="session.tags.length" class="completion-tags"><span>TAGS</span><button v-for="tag in session.tags" :key="tag.id" type="button" class="selected">#{{ tag.name }}</button></div>
        <ReviewTrend v-if="session.status === 'completed'" :trend="reviewTrend" :loading="loading" />
        <el-form v-if="editing" label-position="top" class="simple-review review-editor">
          <el-form-item label="Title"><el-input v-model="edit.title" maxlength="500" show-word-limit /></el-form-item>
          <el-form-item label="Markdown source"><el-input v-model="edit.details" type="textarea" :rows="20" /></el-form-item>
          <MarkdownPreview :source="edit.details" />
          <div class="editor-actions"><el-button @click="editing = false">Cancel</el-button><el-button type="primary" @click="save">Save changes</el-button></div>
        </el-form>
        <MarkdownPreview v-else :key="session.uuid" :source="session.details" default-open allow-fullscreen empty-text="No details were recorded for this session." />
      </section>

      <section v-if="session.status === 'completed'" class="panel session-share-card">
        <div class="share-heading"><div><span class="eyebrow">PUBLIC SHARE</span><h2>Read-only article link</h2></div><span class="share-state" :class="`state-${share?.status || 'private'}`">{{ (share?.status || 'private').toUpperCase() }}</span></div>
        <p>Private by default. Public links expose only the article fields and can be revoked immediately.</p>
        <div v-if="!share?.is_active" class="share-create-row">
          <label><span>OPTIONAL EXPIRY</span><el-input v-model="expiry" type="datetime-local" /></label>
          <el-button type="primary" :icon="Link" :loading="sharing" @click="createShare">Create share link</el-button>
        </div>
        <div v-else class="share-active-row">
          <div><b>Link is active</b><small v-if="share.expires_at">Expires {{ localDate(share.expires_at) }}</small><small v-else>No expiry</small></div>
          <div class="share-actions"><el-button v-if="revealedShareUrl" :icon="CopyDocument" @click="copyShare">Copy link</el-button><el-button type="danger" plain @click="revokeShare">Revoke</el-button></div>
        </div>
        <div v-if="revealedShareUrl" class="share-reveal"><el-icon><View /></el-icon><a :href="revealedShareUrl" target="_blank" rel="noopener noreferrer nofollow">{{ revealedShareUrl }}</a></div>
        <p v-else-if="share?.is_active" class="share-once-note">For security, only the token hash is stored. Revoke and create a new link if the original URL was not saved.</p>
      </section>
    </template>
  </div>
</template>
