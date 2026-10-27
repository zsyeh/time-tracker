import { post } from './api'

export interface ShareLinkResponse {
  share_url: string
  markdown_url: string
}

async function copyText(value: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value)
    return
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
  await copyText(response.share_url)
  return response
}
