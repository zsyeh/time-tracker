import { post } from './api'
import { uiLanguage } from './uiPreferences'

export interface ShareLinkResponse {
  share_url: string
  markdown_url: string
}

async function copyText(value: string) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value)
      return
    } catch {
      // Safari may reject the async Clipboard API after the network request;
      // fall through to the selection-based copy path while the click continues.
    }
  }
  const input = document.createElement('textarea')
  input.value = value
  input.readOnly = true
  input.style.position = 'fixed'
  input.style.opacity = '0'
  document.body.appendChild(input)
  input.select()
  const copied = document.execCommand('copy')
  input.remove()
  if (!copied) throw new Error('Copy failed. Please copy the URL from the opened page.')
}

export async function createAndCopyShare(endpoint: string) {
  const response = await post<ShareLinkResponse>(endpoint, {})
  try {
    await copyText(response.share_url)
  } catch {
    window.prompt(uiLanguage.value === 'zh-CN' ? '复制分享链接' : 'Copy the share link', response.share_url)
  }
  return response
}

export async function createAndCopyShareOnGesture(endpoint: string | Promise<string>) {
  const request = Promise.resolve(endpoint).then((path) => post<ShareLinkResponse>(path, {}))
  let eagerCopy: Promise<boolean> | null = null
  if (navigator.clipboard?.write && window.ClipboardItem) {
    try {
      // Start the ClipboardItem write during the page-turn button gesture.
      // Safari can then wait for the authenticated share request to finish.
      const urlBlob = request.then((response) => new Blob([response.share_url], { type: 'text/plain' }))
      void urlBlob.catch(() => { /* Share creation may fail after the clipboard request starts. */ })
      eagerCopy = navigator.clipboard.write([
        new window.ClipboardItem({ 'text/plain': urlBlob }),
      ]).then(() => true, () => false)
    } catch { /* Fall back to text copying after the request. */ }
  }
  const response = await request
  if (eagerCopy && await eagerCopy) return { response, copied: true }
  try {
    await copyText(response.share_url)
    return { response, copied: true }
  } catch {
    return { response, copied: false }
  }
}
