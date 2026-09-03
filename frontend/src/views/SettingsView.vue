<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, patch, post, put, remove } from '../lib/api'
import type { DataEncryptionStatus, InviteCode, LaunchToken, RuntimeSettingsResponse, RuntimeSettingsValues, StudyTag, Subject, TaskPreset } from '../types'

const emit = defineEmits<{ changed: [] }>()

const tokens = ref<LaunchToken[]>([])
const open = ref(false)
const revealed = ref<LaunchToken | null>(null)
const tokenConfigureOpen = ref(false)
const editingToken = ref<LaunchToken | null>(null)
const theme = ref(localStorage.getItem('learning-os-theme') || 'violet')
const runtimeLoading = ref(true)
const runtimeSaving = ref(false)
const runtimeMeta = ref<RuntimeSettingsResponse | null>(null)
const dataEncryption = ref<DataEncryptionStatus | null>(null)
const encryptionLoading = ref(true)
const encryptionSaving = ref(false)
const isAdmin = ref(false)
const isSuperuser = ref(false)
const invites = ref<InviteCode[]>([])
const inviteOpen = ref(false)
const revealedInvite = ref<InviteCode | null>(null)
const runtimeForm = reactive<RuntimeSettingsValues>({
  homepage_content: '', study_room_code: '', tracking_start_date: '2026-05-23',
  exam_date: '2026-12-26', countdown_label: '2026 Postgraduate Exam',
})
const form = reactive({ name: 'Study shortcut', subject: 'math', source_label: 'iPhone Shortcuts', max_uses: null as number | null, expires_at: null as string | null, notes: '', available_from: '06:00', available_until: '22:00' })
const tokenConfigureForm = reactive({ name: '', source_label: '', max_uses: null as number | null, expires_at: null as string | null, notes: '', available_from: '06:00', available_until: '22:00' })
const inviteForm = reactive({ name: 'New member', max_uses: 1, expires_at: '' })
const presets = ref<TaskPreset[]>([])
const studyTags = ref<StudyTag[]>([])
const presetOpen = ref(false)
const editingPreset = ref<TaskPreset | null>(null)
const tagName = ref('')
const tagColor = ref('green')
const presetForm = reactive({
  name: '', subject: 'math' as Subject, parent: null as number | null,
  tag_ids: [] as number[], is_home_shortcut: false, is_active: true, sort_order: 0,
})
const subjects = { math: 'Mathematics', english: 'English', major: 'Major', training: 'Training' }
const themes = [
  { id: 'violet', label: 'Linear Violet', color: '#8b7cf6' },
  { id: 'coolapk', label: 'Coolapk Green', color: '#10c469' },
  { id: 'youtube', label: 'YouTube Red', color: '#ff0033' },
  { id: 'bilibili', label: 'Bilibili Pink', color: '#fb7299' },
  { id: 'meituan', label: 'Meituan Yellow', color: '#ffd100' },
  { id: 'apple', label: 'Apple White', color: '#f5f5f7' },
]

const shanghaiDate = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
})
const dailyInviteAvailable = computed(() => {
  if (isAdmin.value) return true
  const today = shanghaiDate.format(new Date())
  return !invites.value.some((invite) => invite.is_self_service && invite.issued_local_date === today)
})
type PresetTreeNode = TaskPreset & { children: PresetTreeNode[] }
const presetTree = computed<PresetTreeNode[]>(() => {
  const nodes = new Map<number, PresetTreeNode>()
  presets.value.forEach((preset) => nodes.set(preset.id, { ...preset, children: [] }))
  const roots: PresetTreeNode[] = []
  nodes.forEach((node) => {
    const parent = node.parent ? nodes.get(node.parent) : null
    if (parent) parent.children.push(node)
    else roots.push(node)
  })
  const sortNodes = (items: PresetTreeNode[]) => {
    items.sort((a, b) => a.subject.localeCompare(b.subject) || a.sort_order - b.sort_order || a.name.localeCompare(b.name))
    items.forEach((item) => sortNodes(item.children))
  }
  sortNodes(roots)
  return roots
})
const parentOptions = computed(() => presets.value.filter((preset) => (
  preset.is_active
  && preset.subject === presetForm.subject
  && preset.depth < 4
  && preset.id !== editingPreset.value?.id
)))

function setTheme(value: string) {
  theme.value = value
  document.documentElement.dataset.theme = value
  localStorage.setItem('learning-os-theme', value)
}
function tagLabels(tags: StudyTag[]) { return tags.map((tag) => `#${tag.name}`).join(' ') }

async function load() {
  try { tokens.value = await api<LaunchToken[]>('/api/launch-tokens/') }
  catch (error) { ElMessage.error((error as Error).message) }
}
function applyRuntime(values: RuntimeSettingsValues) {
  Object.assign(runtimeForm, values)
}
async function loadRuntime() {
  runtimeLoading.value = true
  try {
    runtimeMeta.value = await api<RuntimeSettingsResponse>('/api/settings/runtime/')
    applyRuntime(runtimeMeta.value.values)
  } catch (error) { ElMessage.error((error as Error).message) }
  finally { runtimeLoading.value = false }
}
async function loadInvites() {
  try { invites.value = await api<InviteCode[]>('/api/invite-codes/') }
  catch (error) { ElMessage.error((error as Error).message) }
}
async function loadEncryption() {
  encryptionLoading.value = true
  try { dataEncryption.value = await api<DataEncryptionStatus>('/api/settings/data-encryption/') }
  catch (error) { ElMessage.error((error as Error).message) }
  finally { encryptionLoading.value = false }
}
async function loadOrganization() {
  try {
    const [presetValues, tagValues] = await Promise.all([
      api<TaskPreset[]>('/api/task-presets/'),
      api<StudyTag[]>('/api/study-tags/'),
    ])
    presets.value = presetValues
    studyTags.value = tagValues
  } catch (error) { ElMessage.error((error as Error).message) }
}
function openPresetEditor(preset?: TaskPreset, parent?: TaskPreset) {
  editingPreset.value = preset || null
  Object.assign(presetForm, preset ? {
    name: preset.name,
    subject: preset.subject,
    parent: preset.parent,
    tag_ids: preset.tags.map((tag) => tag.id),
    is_home_shortcut: preset.is_home_shortcut,
    is_active: preset.is_active,
    sort_order: preset.sort_order,
  } : {
    name: '',
    subject: parent?.subject || 'math',
    parent: parent?.id || null,
    tag_ids: parent?.tags.map((tag) => tag.id) || [],
    is_home_shortcut: false,
    is_active: true,
    sort_order: 0,
  })
  presetOpen.value = true
}
async function savePreset() {
  try {
    if (editingPreset.value) await patch(`/api/task-presets/${editingPreset.value.id}/`, presetForm)
    else await post('/api/task-presets/', presetForm)
    presetOpen.value = false
    editingPreset.value = null
    await loadOrganization()
    emit('changed')
    ElMessage.success('Task preset saved')
  } catch (error) { ElMessage.error((error as Error).message) }
}
async function deletePreset(preset: TaskPreset) {
  try {
    await ElMessageBox.confirm(
      preset.is_active ? 'Used tasks are archived so historical Sessions keep their classification.' : 'Remove this unused task?',
      'Remove task preset?',
      { type: 'warning', confirmButtonText: 'Remove', cancelButtonText: 'Cancel' },
    )
    await remove(`/api/task-presets/${preset.id}/`)
    await loadOrganization()
    emit('changed')
  } catch (error) { if (error !== 'cancel') ElMessage.error((error as Error).message) }
}
async function createStudyTag() {
  if (!tagName.value.trim()) return
  try {
    await post('/api/study-tags/', { name: tagName.value, color: tagColor.value })
    tagName.value = ''
    await loadOrganization()
  } catch (error) { ElMessage.error((error as Error).message) }
}
async function deleteStudyTag(tag: StudyTag) {
  try {
    await remove(`/api/study-tags/${tag.id}/`)
    await loadOrganization()
  } catch (error) { ElMessage.error((error as Error).message) }
}
async function changeEncryption(value: string | number | boolean) {
  const enabled = Boolean(value)
  const action = enabled ? 'enable' : 'disable'
  try {
    await ElMessageBox.confirm(
      enabled
        ? 'Existing private study content will be rewritten as ciphertext. Public share links and server features will continue to return readable content.'
        : 'Existing private study content will be rewritten to plaintext database fields.',
      `${enabled ? 'Enable' : 'Disable'} at-rest encryption?`,
      { type: enabled ? 'warning' : 'info', confirmButtonText: enabled ? 'Enable encryption' : 'Store as plaintext', cancelButtonText: 'Cancel' },
    )
    encryptionSaving.value = true
    dataEncryption.value = await put<DataEncryptionStatus>('/api/settings/data-encryption/', { enabled })
    ElMessage.success(`At-rest encryption ${action}d${dataEncryption.value.migrated_records ? ` for ${dataEncryption.value.migrated_records} records` : ''}`)
  } catch (error) {
    if (error !== 'cancel') ElMessage.error((error as Error).message)
  } finally { encryptionSaving.value = false }
}
async function loadAccess() {
  try {
    const auth = await api<{ user: { username: string; is_staff: boolean; is_superuser: boolean } }>('/api/auth/session/')
    isAdmin.value = auth.user.is_staff || auth.user.is_superuser
    isSuperuser.value = auth.user.is_superuser
    await loadInvites()
  } catch (error) { ElMessage.error((error as Error).message) }
}
async function createInvite() {
  try {
    const payload: Record<string, unknown> = {
      name: inviteForm.name,
    }
    if (isAdmin.value) {
      payload.max_uses = inviteForm.max_uses
      payload.expires_at = inviteForm.expires_at || null
    }
    revealedInvite.value = await post<InviteCode>('/api/invite-codes/', payload)
    inviteOpen.value = false
    await loadInvites()
  } catch (error) { ElMessage.error((error as Error).message) }
}
async function revokeInvite(invite: InviteCode) {
  try {
    await ElMessageBox.confirm('This invite will stop accepting new registrations.', 'Revoke invite?', { type: 'warning', confirmButtonText: 'Revoke', cancelButtonText: 'Cancel' })
    await post(`/api/invite-codes/${invite.id}/revoke/`)
    await loadInvites()
  } catch (error) { if (error !== 'cancel') ElMessage.error((error as Error).message) }
}
async function copyInvite() {
  if (!revealedInvite.value?.raw_code) return
  await navigator.clipboard.writeText(revealedInvite.value.raw_code)
  ElMessage.success('Invite code copied')
}
async function saveRuntime() {
  runtimeSaving.value = true
  try {
    runtimeMeta.value = await put<RuntimeSettingsResponse>('/api/settings/runtime/', runtimeForm)
    applyRuntime(runtimeMeta.value.values)
    ElMessage.success('Local settings saved')
    emit('changed')
  } catch (error) { ElMessage.error((error as Error).message) }
  finally { runtimeSaving.value = false }
}
function loadDefaults() {
  if (!runtimeMeta.value) return
  applyRuntime(runtimeMeta.value.defaults)
  ElMessage.info('Defaults loaded. Save to apply them.')
}
async function create() {
  try { revealed.value = await post<LaunchToken>('/api/launch-tokens/', form); open.value = false; await load() }
  catch (error) { ElMessage.error((error as Error).message) }
}
function configure(token: LaunchToken) {
  editingToken.value = token
  Object.assign(tokenConfigureForm, {
    name: token.name,
    source_label: token.source_label || '',
    max_uses: token.max_uses,
    expires_at: token.expires_at ? token.expires_at.slice(0, 16) : null,
    notes: token.notes || '',
    available_from: token.available_from.slice(0, 5),
    available_until: token.available_until.slice(0, 5),
  })
  tokenConfigureOpen.value = true
}
async function saveTokenConfiguration() {
  if (!editingToken.value) return
  try {
    await put(`/api/launch-tokens/${editingToken.value.id}/configure/`, tokenConfigureForm)
    tokenConfigureOpen.value = false
    editingToken.value = null
    await load()
    ElMessage.success('Capability settings saved')
  } catch (error) { ElMessage.error((error as Error).message) }
}
async function action(token: LaunchToken, name: string) {
  try {
    if (name === 'delete') await ElMessageBox.confirm('This launch URL will stop working immediately.', 'Delete launch token?', { type: 'warning', confirmButtonText: 'Delete', cancelButtonText: 'Cancel' })
    const value = await post<LaunchToken | undefined>(`/api/launch-tokens/${token.id}/${name}/`)
    if (value?.raw_token || value?.raw_disturbance_token) revealed.value = value
    await load()
  } catch (error) { if (error !== 'cancel') ElMessage.error((error as Error).message) }
}
async function copyCapability(url: string | undefined, label: string) {
  if (!url) return
  await navigator.clipboard.writeText(url)
  ElMessage.success(`${label} copied`)
}
async function copyAndOpenShortcuts(url: string | undefined, label: string) {
  if (!url) return
  await navigator.clipboard.writeText(url)
  ElMessage.success(`${label} copied. Paste it into Get Contents of URL.`)
  window.location.href = revealed.value?.shortcuts_create_url || 'shortcuts://create-shortcut'
}
onMounted(() => { load(); loadRuntime(); loadAccess(); loadEncryption(); loadOrganization() })
</script>

<template>
  <div class="view-stack">
    <section class="page-intro"><span class="eyebrow">SYSTEM / ACCESS</span><h1>Settings</h1><p>Authentication, portable data, and scoped launch capabilities.</p></section>
    <div class="settings-layout">
      <nav class="settings-index" aria-label="Settings sections">
        <a href="#appearance">Appearance</a>
        <a href="#privacy">Privacy</a>
        <a href="#access">Access</a>
        <a href="#organization">Organization</a>
        <a href="#invitations">Invitations</a>
        <a href="#shortcuts">Shortcuts</a>
      </nav>
      <div class="settings-content">
    <section class="settings-grid">
      <article v-if="isSuperuser" id="instance" class="panel settings-card instance-settings" v-loading="runtimeLoading">
        <div class="card-title"><div><span class="eyebrow">LOCAL INSTANCE</span><h2>Homepage and schedule</h2></div><span class="env-badge">.ENV ↔ WEB</span></div>
        <p>These display values are read from the local environment file. Saving updates only the fields shown here and applies them immediately.</p>
        <el-form label-position="top" class="runtime-settings-form" @submit.prevent="saveRuntime">
          <el-form-item label="Homepage content">
            <el-input v-model="runtimeForm.homepage_content" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="Optional text shown below today's date" />
          </el-form-item>
          <div class="form-pair">
            <el-form-item label="Study room code"><el-input v-model="runtimeForm.study_room_code" maxlength="120" placeholder="Hidden when empty" /></el-form-item>
            <el-form-item label="Countdown label"><el-input v-model="runtimeForm.countdown_label" maxlength="80" /></el-form-item>
          </div>
          <div class="form-pair">
            <el-form-item label="Tracking start date"><el-input v-model="runtimeForm.tracking_start_date" type="date" /></el-form-item>
            <el-form-item label="Exam date"><el-input v-model="runtimeForm.exam_date" type="date" /></el-form-item>
          </div>
          <div class="runtime-settings-footer">
            <small>{{ runtimeMeta?.local_env_exists ? 'LOCAL FILE CONNECTED' : 'LOCAL FILE WILL BE CREATED ON SAVE' }}</small>
            <div><el-button @click="loadDefaults">Load defaults</el-button><el-button type="primary" :loading="runtimeSaving" @click="saveRuntime">Save settings</el-button></div>
          </div>
        </el-form>
      </article>
      <article id="appearance" class="panel settings-card theme-card">
        <div class="card-title"><div><span class="eyebrow">APPEARANCE</span><h2>Theme color</h2></div></div>
        <p>Choose one accent. Activity heatmap colors stay consistent for comparison.</p>
        <div class="theme-options">
          <button v-for="item in themes" :key="item.id" type="button" :class="{ active: theme === item.id }" @click="setTheme(item.id)"><i :style="{ background: item.color }" /><span>{{ item.label }}</span><b>{{ theme === item.id ? 'SELECTED' : '' }}</b></button>
        </div>
      </article>
      <article id="privacy" class="panel settings-card encryption-card" v-loading="encryptionLoading">
        <div class="card-title">
          <div><span class="eyebrow">STORAGE PRIVACY</span><h2>Private content at rest</h2></div>
          <span class="secure-badge">{{ dataEncryption?.algorithm || 'AES-256-GCM' }}</span>
        </div>
        <div class="encryption-toggle-row">
          <div><strong>Encrypt my private study content</strong><small>{{ dataEncryption?.enabled ? 'DATABASE STORAGE IS ENCRYPTED' : 'DATABASE STORAGE IS PLAINTEXT' }}</small></div>
          <el-switch :model-value="dataEncryption?.enabled || false" :loading="encryptionSaving" :disabled="encryptionLoading || encryptionSaving" aria-label="Encrypt my private study content" @change="changeEncryption" />
        </div>
        <p class="encryption-disclosure"><b>This is not end-to-end encryption.</b> When enabled, study titles, Markdown, reflection fields, personal ratings, and Issue text are stored as ciphertext and cannot be read directly from database rows or database-only backups. Operational metadata remains available for fast timelines and statistics.</p>
        <p class="encryption-disclosure">No additional password is required. To preserve performance and convenience, the encryption key remains on the server. A person with sufficient server access may still obtain the key and decrypt the data; this protection increases the effort required but does not make access impossible.</p>
        <p class="encryption-disclosure">If you require privacy from the server operator, use a self-hosted deployment. The server administrator will apply reasonable safeguards to prevent database disclosure, but no hosted service can guarantee absolute confidentiality. Public share links and GitHub Markdown archives remain readable at their destinations.</p>
      </article>
      <article id="access" class="panel settings-card">
        <div class="card-title"><div><span class="eyebrow">PASSKEY</span><h2>Secure access</h2></div><span class="secure-badge">WebAuthn</span></div>
        <p>Passkey and password are alternative sign-in methods. Either one completes login; no second factor is required. Passwords are optional, and Passkey-only accounts are supported.</p>
        <div class="settings-actions"><a class="el-button el-button--primary" href="/accounts/2fa/webauthn/add/">Add Passkey</a><a class="text-link" href="/accounts/2fa/">Manage</a></div>
      </article>
      <article class="panel settings-card">
        <div class="card-title"><div><span class="eyebrow">PORTABLE DATA</span><h2>Data export</h2></div></div>
        <p>Export raw sessions and structured review fields without summary truncation.</p>
        <div class="export-actions"><a href="/api/export/csv/">CSV</a><a href="/api/export/json/">JSON</a><a href="/api/export/markdown/">Markdown</a></div>
      </article>
      <article v-if="isAdmin" class="panel settings-card admin-console-card">
        <div class="card-title"><div><span class="eyebrow">ADMINISTRATION</span><h2>Django control panel</h2></div><span class="secure-badge">STAFF ONLY</span></div>
        <p>Manage accounts, inspect invitation visitors, and access recovery controls.</p>
        <div class="settings-actions"><a class="el-button el-button--primary" href="/admin/">Open Django Admin</a><a class="text-link" href="/admin/tracker/invitecode/dashboard/">Invitation dashboard</a><a class="text-link" href="/admin/tracker/invitecode/auth-recovery/">Reset login status</a></div>
      </article>
    </section>
    <section id="organization" class="panel organization-panel">
      <div class="section-heading"><div><span class="eyebrow">CONTENT ORGANIZATION</span><h2>Task presets and tags</h2></div><el-button type="primary" @click="openPresetEditor()">New task preset</el-button></div>
      <p class="section-note">Build up to four custom levels below a subject. Mark any task as a homepage shortcut; its tags are preselected when the Session starts.</p>
      <div class="tag-manager">
        <div class="tag-create"><el-input v-model="tagName" maxlength="64" placeholder="New tag name" @keyup.enter="createStudyTag" /><el-select v-model="tagColor" aria-label="Tag color"><el-option label="Green" value="green" /><el-option label="Blue" value="blue" /><el-option label="Pink" value="pink" /><el-option label="Yellow" value="yellow" /><el-option label="Purple" value="purple" /></el-select><el-button @click="createStudyTag">Add tag</el-button></div>
        <div v-if="studyTags.length" class="managed-tags"><span v-for="tag in studyTags" :key="tag.id" :class="`study-tag tag-${tag.color}`">#{{ tag.name }}<button type="button" :aria-label="`Delete ${tag.name}`" @click="deleteStudyTag(tag)">×</button></span></div>
      </div>
      <el-empty v-if="!presets.length" description="No task presets yet. Example: Mathematics → Calculus → Limits." />
      <el-tree v-else :data="presetTree" node-key="id" default-expand-all :expand-on-click-node="false" class="preset-tree">
        <template #default="{ data }">
          <div class="preset-tree-row" :class="{ inactive: !data.is_active }">
            <div><strong>{{ data.parent ? data.name : `${data.subject_label}: ${data.name}` }}</strong><small><span v-if="data.is_home_shortcut">HOME SHORTCUT · </span>LEVEL {{ data.depth }}<span v-if="data.tags.length"> · {{ tagLabels(data.tags) }}</span></small></div>
            <div><el-button v-if="data.depth < 4 && data.is_active" text @click.stop="openPresetEditor(undefined, data)">Add child</el-button><el-button text @click.stop="openPresetEditor(data)">Edit</el-button><el-button text type="danger" @click.stop="deletePreset(data)">{{ data.is_active ? 'Remove' : 'Delete' }}</el-button></div>
          </div>
        </template>
      </el-tree>
    </section>
    <section id="invitations" class="panel token-panel invite-panel">
      <div class="section-heading"><div><span class="eyebrow">{{ isAdmin ? 'ADMIN / REGISTRATION' : 'ACCOUNT / SHARING' }}</span><h2>Invite codes</h2></div><div class="invite-heading-actions"><a v-if="isAdmin" class="text-link" href="/admin/tracker/invitecode/dashboard/">Full visitor log</a><el-button type="primary" :disabled="!dailyInviteAvailable" @click="inviteOpen = true">{{ dailyInviteAvailable ? 'Generate invite' : 'Daily invite used' }}</el-button></div></div>
      <p class="section-note">{{ isAdmin ? 'Choose 1–100 uses per code. Raw codes are shown once and stored as hashes.' : 'You can generate one single-use invite per Shanghai calendar day. You can see the username after it is redeemed.' }}</p>
      <el-empty v-if="!invites.length" description="No invite codes" />
      <article v-for="invite in invites" :key="invite.id" class="token-row invite-row">
        <div><strong>{{ invite.name }}</strong><small>{{ invite.use_count }} used · {{ invite.remaining_uses }} remaining · created by {{ invite.created_by }}<span v-if="invite.last_used_at"> · last used {{ new Date(invite.last_used_at).toLocaleString('en-GB') }}</span><span v-if="invite.expires_at"> · expires {{ new Date(invite.expires_at).toLocaleString('en-GB') }}</span></small><small v-if="invite.visitors.length" class="invite-visitor-summary">REGISTERED · {{ invite.visitors.map((visitor) => visitor.username).join(', ') }}</small></div>
        <el-tag :type="invite.usable ? 'success' : 'info'">{{ invite.usable ? `${invite.remaining_uses} LEFT` : 'CLOSED' }}</el-tag>
        <div><el-button v-if="invite.is_active" text type="danger" @click="revokeInvite(invite)">Revoke</el-button></div>
      </article>
    </section>
    <section id="shortcuts" class="panel token-panel">
      <div class="section-heading"><div><span class="eyebrow">SHORTCUT CAPABILITIES</span><h2>Start and disturbance URIs</h2></div><el-button type="primary" @click="open = true">New capability</el-button></div>
      <p class="section-note">No sign-in is required when a valid secret URI is called. Start and disturbance use separate random secrets. Each can be copied only when created or regenerated.</p>
      <el-empty v-if="!tokens.length" description="No launch tokens" />
      <article v-for="token in tokens" :key="token.id" class="token-row capability-row">
        <div><strong>{{ token.name }}</strong><small>{{ token.subject }} · {{ token.usage_count }} starts<span v-if="token.max_uses"> / {{ token.max_uses }}</span> · {{ token.available_from.slice(0, 5) }}–{{ token.available_until.slice(0, 5) }} Asia/Shanghai</small><small v-if="!token.within_schedule && token.credential_valid && !token.is_paused" class="capability-state-note">OUTSIDE ACTIVE WINDOW · REQUESTS ARE SAFE NO-OPS</small></div>
        <el-tag :type="token.usable ? 'success' : 'info'">{{ token.is_paused ? 'PAUSED' : token.usable ? 'ACTIVE NOW' : token.credential_valid ? 'SCHEDULED OFF' : 'CLOSED' }}</el-tag>
        <div class="capability-actions"><el-button text @click="configure(token)">Configure</el-button><el-button v-if="token.is_active" text @click="action(token, token.is_paused ? 'resume' : 'pause')">{{ token.is_paused ? 'Resume' : 'Pause' }}</el-button><el-button text @click="action(token, 'regenerate')">New start URI</el-button><el-button :disabled="!token.is_active" text @click="action(token, 'regenerate-disturbance')">{{ token.has_disturbance_uri ? 'New disturbance URI' : 'Create disturbance URI' }}</el-button><el-button text type="danger" @click="action(token, 'delete')">Delete</el-button></div>
      </article>
      <details class="shortcut-inline-guide">
        <summary>iPhone Shortcuts setup / iPhone 快捷指令设置</summary>
        <div class="shortcut-guide-columns">
          <article><span>ENGLISH</span><h3>Start study</h3><ol><li>Create a capability and tap <b>Copy &amp; Open Shortcuts</b> beside the Shortcut Start URI.</li><li>In the new shortcut, add <b>Get Contents of URL</b>, paste the URI, set Method to <b>POST</b>, and leave the request body empty.</li><li>Name the shortcut and optionally add it to the Home Screen, Lock Screen, Action Button, widget, NFC, or another automation.</li></ol><h3>Detect a disturbance</h3><ol><li>Copy the separate Disturbance URI.</li><li>Open Shortcuts → Automation → + → <b>Charger</b> → <b>Is Disconnected</b> → <b>Run Immediately</b>.</li><li>Add <b>Get Contents of URL</b>, paste the Disturbance URI, choose <b>POST</b>, leave the body empty, then save.</li></ol><p>Pause disables both URIs without changing them. By default requests are effective only from 06:00 to 22:00 Asia/Shanghai. Outside the window, a valid request returns a safe no-op. A disturbance is counted only while a session is running. A stale running session over 12 hours is discarded.</p></article>
          <article lang="zh-CN"><span>中文</span><h3>开始学习</h3><ol><li>创建能力链接，点击 Shortcut Start URI 旁的 <b>复制并打开快捷指令</b>。</li><li>在新快捷指令中添加<b>获取 URL 内容</b>，粘贴 URI，把方法设为 <b>POST</b>，请求正文留空。</li><li>命名后可添加到主屏幕、锁屏、操作按钮、小组件、NFC 或其他自动化。</li></ol><h3>检测扰动</h3><ol><li>复制单独的 Disturbance URI。</li><li>打开快捷指令 → 自动化 → + → <b>充电器</b> → <b>已断开连接</b> → <b>立即运行</b>。</li><li>添加<b>获取 URL 内容</b>，粘贴扰动 URI，方法选 <b>POST</b>，正文留空并保存。</li></ol><p>暂停会临时关闭两个 URI，但不会改变 URI。默认仅在上海时区 06:00–22:00 生效；时段外会安全地空操作。只有存在运行中的学习任务时才累计扰动；超过 12 小时的遗留任务会被丢弃。</p></article>
        </div>
      </details>
    </section>
      </div>
    </div>
    <el-dialog v-model="open" title="Create Shortcut capability" width="min(620px, 94vw)">
      <el-form label-position="top">
        <el-form-item label="Name"><el-input v-model="form.name" /></el-form-item>
        <div class="form-pair"><el-form-item label="Subject"><el-select v-model="form.subject"><el-option v-for="(label, key) in subjects" :key="key" :label="label" :value="key" /></el-select></el-form-item><el-form-item label="Maximum uses"><el-input-number v-model="form.max_uses" :min="1" placeholder="Unlimited" /></el-form-item></div>
        <div class="form-pair"><el-form-item label="Available from"><el-input v-model="form.available_from" type="time" /></el-form-item><el-form-item label="Available until"><el-input v-model="form.available_until" type="time" /></el-form-item></div>
        <el-form-item label="Source label"><el-input v-model="form.source_label" /></el-form-item>
        <el-form-item label="Notes"><el-input v-model="form.notes" type="textarea" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="open = false">Cancel</el-button><el-button type="primary" @click="create">Create capability</el-button></template>
    </el-dialog>
    <el-dialog v-model="presetOpen" :title="editingPreset ? 'Edit task preset' : 'Create task preset'" width="min(640px, 94vw)">
      <el-form label-position="top">
        <div class="form-pair"><el-form-item label="Subject"><el-select v-model="presetForm.subject" :disabled="Boolean(editingPreset)"><el-option v-for="(label, key) in subjects" :key="key" :label="label" :value="key" /></el-select></el-form-item><el-form-item label="Task name"><el-input v-model="presetForm.name" maxlength="120" placeholder="For example: Limits" /></el-form-item></div>
        <el-form-item label="Parent task · Optional"><el-select v-model="presetForm.parent" clearable placeholder="Directly below the subject"><el-option v-for="preset in parentOptions" :key="preset.id" :label="`${preset.path} · level ${preset.depth}`" :value="preset.id" /></el-select></el-form-item>
        <el-form-item label="Default tags"><el-select v-model="presetForm.tag_ids" multiple clearable placeholder="Choose reusable tags"><el-option v-for="tag in studyTags" :key="tag.id" :label="`#${tag.name}`" :value="tag.id" /></el-select></el-form-item>
        <div class="preset-switches"><label><el-switch v-model="presetForm.is_home_shortcut" /> Show as a homepage button</label><label v-if="editingPreset"><el-switch v-model="presetForm.is_active" /> Active</label><el-form-item label="Order"><el-input-number v-model="presetForm.sort_order" :min="0" :max="65535" /></el-form-item></div>
        <el-alert title="A blank completion title defaults to this task's leaf name. Markdown details may remain empty." type="info" :closable="false" show-icon />
      </el-form>
      <template #footer><el-button @click="presetOpen = false">Cancel</el-button><el-button type="primary" @click="savePreset">Save task</el-button></template>
    </el-dialog>
    <el-dialog :model-value="Boolean(revealed)" title="Save these capability URIs now" width="min(760px, 96vw)" @close="revealed = null">
      <el-alert title="Raw secrets are stored only as hashes and cannot be shown again after this dialog closes." type="warning" :closable="false" show-icon />
      <div v-if="revealed?.shortcut_start_url" class="capability-reveal"><span>SHORTCUT START · POST</span><div class="reveal-url">{{ revealed.shortcut_start_url }}</div><div><el-button @click="copyCapability(revealed?.shortcut_start_url, 'Start URI')">Copy</el-button><el-button type="primary" @click="copyAndOpenShortcuts(revealed?.shortcut_start_url, 'Start URI')">Copy &amp; Open Shortcuts</el-button></div></div>
      <div v-if="revealed?.launch_url" class="capability-reveal"><span>BROWSER START · GET</span><div class="reveal-url">{{ revealed.launch_url }}</div><div><el-button @click="copyCapability(revealed?.launch_url, 'Browser start URI')">Copy</el-button></div></div>
      <div v-if="revealed?.disturbance_url" class="capability-reveal"><span>DISTURBANCE · POST</span><div class="reveal-url">{{ revealed.disturbance_url }}</div><div><el-button @click="copyCapability(revealed?.disturbance_url, 'Disturbance URI')">Copy</el-button><el-button type="primary" @click="copyAndOpenShortcuts(revealed?.disturbance_url, 'Disturbance URI')">Copy &amp; Open Shortcuts</el-button></div></div>
      <template #footer><el-button @click="revealed = null">I saved the URI</el-button></template>
    </el-dialog>
    <el-dialog v-model="tokenConfigureOpen" title="Configure capability" width="min(620px, 94vw)">
      <el-form label-position="top">
        <el-form-item label="Name"><el-input v-model="tokenConfigureForm.name" /></el-form-item>
        <div class="form-pair"><el-form-item label="Available from"><el-input v-model="tokenConfigureForm.available_from" type="time" /></el-form-item><el-form-item label="Available until"><el-input v-model="tokenConfigureForm.available_until" type="time" /></el-form-item></div>
        <div class="form-pair"><el-form-item label="Maximum starts"><el-input-number v-model="tokenConfigureForm.max_uses" :min="1" placeholder="Unlimited" /></el-form-item><el-form-item label="Expires at"><el-input v-model="tokenConfigureForm.expires_at" type="datetime-local" /></el-form-item></div>
        <el-form-item label="Source label"><el-input v-model="tokenConfigureForm.source_label" /></el-form-item>
        <el-form-item label="Notes"><el-input v-model="tokenConfigureForm.notes" type="textarea" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="tokenConfigureOpen = false">Cancel</el-button><el-button type="primary" @click="saveTokenConfiguration">Save</el-button></template>
    </el-dialog>
    <el-dialog v-model="inviteOpen" title="Generate invite code" width="min(560px, 94vw)">
      <el-form label-position="top">
        <el-form-item label="Label"><el-input v-model="inviteForm.name" maxlength="120" /></el-form-item>
        <div v-if="isAdmin" class="form-pair"><el-form-item label="Maximum uses"><el-input-number v-model="inviteForm.max_uses" :min="1" :max="100" /></el-form-item><el-form-item label="Expires at"><el-input v-model="inviteForm.expires_at" type="datetime-local" /></el-form-item></div>
        <el-alert v-else title="This invite can be used once. Your next invite becomes available on the next Shanghai calendar day." type="info" :closable="false" show-icon />
      </el-form>
      <template #footer><el-button @click="inviteOpen = false">Cancel</el-button><el-button type="primary" @click="createInvite">Generate</el-button></template>
    </el-dialog>
    <el-dialog :model-value="Boolean(revealedInvite)" title="Save this invite code now" width="min(620px, 94vw)" @close="revealedInvite = null">
      <el-alert title="The raw invite code cannot be viewed again after closing this dialog." type="warning" :closable="false" show-icon />
      <div class="reveal-url">{{ revealedInvite?.raw_code }}</div>
      <p class="invite-signup-url">Signup page: <a :href="revealedInvite?.signup_url">{{ revealedInvite?.signup_url }}</a></p>
      <template #footer><el-button type="primary" @click="copyInvite">Copy code</el-button><el-button @click="revealedInvite = null">Saved</el-button></template>
    </el-dialog>
  </div>
</template>
