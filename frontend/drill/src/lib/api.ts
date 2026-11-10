import { learningUserId } from '../../../shared/foregroundTimer'
function cookie(name: string): string {
  const item = document.cookie.split('; ').find((part) => part.startsWith(`${name}=`))
  return item ? decodeURIComponent(item.split('=').slice(1).join('=')) : ''
}

const inflightGets = new Map<string, Promise<unknown>>()

export class ApiError extends Error {
  constructor(public status: number, message: string, public body: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
  }
}

export async function api<T>(url: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method || 'GET').toUpperCase()
  if (method === 'GET' && !options.signal) {
    const existing = inflightGets.get(url)
    if (existing) return existing as Promise<T>
    const request = requestJson<T>(url, options).finally(() => inflightGets.delete(url))
    inflightGets.set(url, request)
    return request
  }
  return requestJson<T>(url, options)
}

async function requestJson<T>(url: string, options: RequestInit): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')
  if (learningUserId && !url.split('?')[0]!.endsWith('/api/auth/session/')) headers.set('X-Learning-User-ID', learningUserId)
  if (options.body) headers.set('Content-Type', 'application/json')
  const csrf = cookie('csrftoken')
  if (csrf) headers.set('X-CSRFToken', csrf)
  const response = await fetch(withWorkspacePrefix(url), { ...options, headers, credentials: 'same-origin' })
  let body: Record<string, unknown> = {}
  if (response.status !== 204) {
    try { body = await response.json() as Record<string, unknown> } catch { /* non-JSON response */ }
  }
  const detail = typeof body.detail === 'string' ? body.detail : ''
  const missingSession = response.status === 401
    || (response.status === 403 && /authentication credentials were not provided/i.test(detail))
  if (missingSession) {
    const next = withoutWorkspacePrefix(location.pathname) + location.search
    location.assign(`/drill-auth/start?site=${runtimeWorkspace}&next=${encodeURIComponent(next)}`)
    throw new ApiError(response.status, '登录已失效，正在重新认证。', body)
  }
  if (!response.ok) {
    const fallback: Record<number, string> = {
      403: '没有权限执行此操作。', 404: '请求的题目或资源不存在。',
      409: '数据已在其他页面更新，请确认后重试。', 429: '操作过于频繁，请稍后重试。',
    }
    const message = detail || Object.values(body).flat().join('; ')
      || fallback[response.status] || (response.status >= 500 ? '服务器暂时不可用，请稍后重试。' : `请求失败（${response.status}）`)
    throw new ApiError(response.status, message, body)
  }
  return response.status === 204 ? undefined as T : body as T
}

export const post = <T>(url: string, body: unknown) => api<T>(url, {
  method: 'POST',
  body: JSON.stringify(body),
})

export const remove = <T>(url: string) => api<T>(url, { method: 'DELETE' })
import { runtimeWorkspace, withWorkspacePrefix, withoutWorkspacePrefix } from './runtimePath'
