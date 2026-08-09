<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, post } from '../lib/api'
import type { LaunchToken } from '../types'

const tokens = ref<LaunchToken[]>([])
const open = ref(false)
const revealed = ref<LaunchToken | null>(null)
const form = reactive({ name: 'Desktop shortcut', subject: 'math', source_label: 'Browser', max_uses: null as number | null, expires_at: null as string | null, notes: '' })
const subjects = { math: 'Mathematics', english: 'English', major: 'Major', training: 'Training' }

async function load() {
  try { tokens.value = await api<LaunchToken[]>('/api/launch-tokens/') }
  catch (error) { ElMessage.error((error as Error).message) }
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
onMounted(load)
</script>

<template>
  <div class="view-stack">
    <section class="page-intro"><span class="eyebrow">SYSTEM / ACCESS</span><h1>Settings</h1><p>Authentication, portable data, and scoped launch capabilities.</p></section>
    <section class="settings-grid">
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
  </div>
</template>
