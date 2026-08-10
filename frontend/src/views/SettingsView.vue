<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, post, put } from '../lib/api'
import type { InviteCode, LaunchToken, RuntimeSettingsResponse, RuntimeSettingsValues } from '../types'

const emit = defineEmits<{ changed: [] }>()

const tokens = ref<LaunchToken[]>([])
const open = ref(false)
const revealed = ref<LaunchToken | null>(null)
const theme = ref(localStorage.getItem('learning-os-theme') || 'coolapk')
const runtimeLoading = ref(true)
const runtimeSaving = ref(false)
const runtimeMeta = ref<RuntimeSettingsResponse | null>(null)
const isAdmin = ref(false)
const invites = ref<InviteCode[]>([])
const inviteOpen = ref(false)
const revealedInvite = ref<InviteCode | null>(null)
const runtimeForm = reactive<RuntimeSettingsValues>({
  homepage_content: '', study_room_code: '', tracking_start_date: '2026-05-23',
  exam_date: '2026-12-26', countdown_label: '2026 Postgraduate Exam',
})
const form = reactive({ name: 'Desktop shortcut', subject: 'math', source_label: 'Browser', max_uses: null as number | null, expires_at: null as string | null, notes: '' })
const inviteForm = reactive({ name: 'New member', max_uses: 1, expires_at: '' })
const subjects = { math: 'Mathematics', english: 'English', major: 'Major', training: 'Training' }
const themes = [
  { id: 'coolapk', label: 'Coolapk Green', color: '#10c469' },
  { id: 'youtube', label: 'YouTube Red', color: '#ff0033' },
  { id: 'bilibili', label: 'Bilibili Pink', color: '#fb7299' },
  { id: 'meituan', label: 'Meituan Yellow', color: '#ffd100' },
  { id: 'apple', label: 'Apple White', color: '#f5f5f7' },
]

function setTheme(value: string) {
  theme.value = value
  document.documentElement.dataset.theme = value
  localStorage.setItem('learning-os-theme', value)
}

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
async function loadAccess() {
  try {
    const auth = await api<{ user: { is_staff: boolean; is_superuser: boolean } }>('/api/auth/session/')
    isAdmin.value = auth.user.is_staff || auth.user.is_superuser
    if (isAdmin.value) await loadInvites()
  } catch (error) { ElMessage.error((error as Error).message) }
}
async function createInvite() {
  try {
    revealedInvite.value = await post<InviteCode>('/api/invite-codes/', {
      name: inviteForm.name,
      max_uses: inviteForm.max_uses,
      expires_at: inviteForm.expires_at || null,
    })
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
async function action(token: LaunchToken, name: string) {
  try {
    if (name === 'delete') await ElMessageBox.confirm('This launch URL will stop working immediately.', 'Delete launch token?', { type: 'warning', confirmButtonText: 'Delete', cancelButtonText: 'Cancel' })
    const value = await post<LaunchToken | undefined>(`/api/launch-tokens/${token.id}/${name}/`)
    if (value?.raw_token) revealed.value = value
    await load()
  } catch (error) { if (error !== 'cancel') ElMessage.error((error as Error).message) }
}
async function copy() {
  if (!revealed.value?.launch_url) return
  await navigator.clipboard.writeText(revealed.value.launch_url)
  ElMessage.success('Launch URL copied')
}
onMounted(() => { load(); loadRuntime(); loadAccess() })
</script>

<template>
  <div class="view-stack">
    <section class="page-intro"><span class="eyebrow">SYSTEM / ACCESS</span><h1>Settings</h1><p>Authentication, portable data, and scoped launch capabilities.</p></section>
    <section class="settings-grid">
      <article class="panel settings-card instance-settings" v-loading="runtimeLoading">
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
      <article class="panel settings-card theme-card">
        <div class="card-title"><div><span class="eyebrow">APPEARANCE</span><h2>Theme color</h2></div></div>
        <p>Choose one accent. Activity heatmap colors stay consistent for comparison.</p>
        <div class="theme-options">
          <button v-for="item in themes" :key="item.id" type="button" :class="{ active: theme === item.id }" @click="setTheme(item.id)"><i :style="{ background: item.color }" /><span>{{ item.label }}</span><b>{{ theme === item.id ? 'SELECTED' : '' }}</b></button>
        </div>
      </article>
      <article class="panel settings-card">
        <div class="card-title"><div><span class="eyebrow">PASSKEY</span><h2>Secure access</h2></div><span class="secure-badge">WebAuthn</span></div>
        <p>Use a platform authenticator or security key. Password access remains available for recovery.</p>
        <div class="settings-actions"><a class="el-button el-button--primary" href="/accounts/2fa/webauthn/add/">Add Passkey</a><a class="text-link" href="/accounts/2fa/">Manage</a></div>
      </article>
      <article class="panel settings-card">
        <div class="card-title"><div><span class="eyebrow">PORTABLE DATA</span><h2>Data export</h2></div></div>
        <p>Export raw sessions and structured review fields without summary truncation.</p>
        <div class="export-actions"><a href="/api/export/csv/">CSV</a><a href="/api/export/json/">JSON</a><a href="/api/export/markdown/">Markdown</a></div>
      </article>
      <article class="panel settings-card">
        <div class="card-title"><div><span class="eyebrow">DOCUMENTATION</span><h2>User guide</h2></div></div>
        <p>Open the standalone reference for registration, sessions, Markdown, reviews, and data isolation.</p>
        <div class="settings-actions"><a class="el-button" href="/guide/">Open user guide</a><a class="text-link" href="/contact/">Contact administrator</a></div>
      </article>
      <article v-if="isAdmin" class="panel settings-card admin-console-card">
        <div class="card-title"><div><span class="eyebrow">ADMINISTRATION</span><h2>Django control panel</h2></div><span class="secure-badge">STAFF ONLY</span></div>
        <p>Manage accounts, inspect invitation visitors, and access recovery controls.</p>
        <div class="settings-actions"><a class="el-button el-button--primary" href="/admin/">Open Django Admin</a><a class="text-link" href="/admin/tracker/invitecode/dashboard/">Invitation dashboard</a></div>
      </article>
    </section>
    <section v-if="isAdmin" class="panel token-panel invite-panel">
      <div class="section-heading"><div><span class="eyebrow">ADMIN / REGISTRATION</span><h2>Invite codes</h2></div><div class="invite-heading-actions"><a class="text-link" href="/admin/tracker/invitecode/dashboard/">Full visitor log</a><el-button type="primary" @click="inviteOpen = true">Generate invite</el-button></div></div>
      <p class="section-note">Choose 1–100 uses per code. Raw codes are shown once and stored as hashes.</p>
      <el-empty v-if="!invites.length" description="No invite codes" />
      <article v-for="invite in invites" :key="invite.id" class="token-row invite-row">
        <div><strong>{{ invite.name }}</strong><small>{{ invite.use_count }} used · {{ invite.remaining_uses }} remaining · created by {{ invite.created_by }}<span v-if="invite.last_used_at"> · last used {{ new Date(invite.last_used_at).toLocaleString('en-GB') }}</span><span v-if="invite.expires_at"> · expires {{ new Date(invite.expires_at).toLocaleString('en-GB') }}</span></small></div>
        <el-tag :type="invite.usable ? 'success' : 'info'">{{ invite.usable ? `${invite.remaining_uses} LEFT` : 'CLOSED' }}</el-tag>
        <div><el-button v-if="invite.is_active" text type="danger" @click="revokeInvite(invite)">Revoke</el-button></div>
      </article>
    </section>
    <section class="panel token-panel">
      <div class="section-heading"><div><span class="eyebrow">LAUNCH TOKENS</span><h2>Scoped start links</h2></div><el-button type="primary" @click="open = true">New token</el-button></div>
      <p class="section-note">A token can only start its assigned subject. The raw URL is displayed once.</p>
      <el-empty v-if="!tokens.length" description="No launch tokens" />
      <article v-for="token in tokens" :key="token.id" class="token-row">
        <div><strong>{{ token.name }}</strong><small>{{ token.subject }} · {{ token.usage_count }} uses<span v-if="token.max_uses"> / {{ token.max_uses }}</span></small></div>
        <el-tag :type="token.usable ? 'success' : 'info'">{{ token.usable ? 'ACTIVE' : 'INACTIVE' }}</el-tag>
        <div><el-button text @click="action(token, token.is_active ? 'revoke' : 'regenerate')">{{ token.is_active ? 'Revoke' : 'Regenerate' }}</el-button><el-button text type="danger" @click="action(token, 'delete')">Delete</el-button></div>
      </article>
    </section>
    <el-dialog v-model="open" title="Create launch token" width="min(560px, 94vw)">
      <el-form label-position="top">
        <el-form-item label="Name"><el-input v-model="form.name" /></el-form-item>
        <div class="form-pair"><el-form-item label="Subject"><el-select v-model="form.subject"><el-option v-for="(label, key) in subjects" :key="key" :label="label" :value="key" /></el-select></el-form-item><el-form-item label="Maximum uses"><el-input-number v-model="form.max_uses" :min="1" placeholder="Unlimited" /></el-form-item></div>
        <el-form-item label="Source label"><el-input v-model="form.source_label" /></el-form-item>
        <el-form-item label="Notes"><el-input v-model="form.notes" type="textarea" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="open = false">Cancel</el-button><el-button type="primary" @click="create">Create token</el-button></template>
    </el-dialog>
    <el-dialog :model-value="Boolean(revealed)" title="Save this URL now" width="min(620px, 94vw)" @close="revealed = null">
      <el-alert title="The raw token cannot be viewed again after closing this dialog." type="warning" :closable="false" show-icon />
      <div class="reveal-url">{{ revealed?.launch_url }}</div>
      <template #footer><el-button type="primary" @click="copy">Copy URL</el-button><el-button @click="revealed = null">Saved</el-button></template>
    </el-dialog>
    <el-dialog v-model="inviteOpen" title="Generate invite code" width="min(560px, 94vw)">
      <el-form label-position="top">
        <el-form-item label="Label"><el-input v-model="inviteForm.name" maxlength="120" /></el-form-item>
        <div class="form-pair"><el-form-item label="Maximum uses"><el-input-number v-model="inviteForm.max_uses" :min="1" :max="100" /></el-form-item><el-form-item label="Expires at"><el-input v-model="inviteForm.expires_at" type="datetime-local" /></el-form-item></div>
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
