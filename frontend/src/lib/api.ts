function cookie(name: string): string {
  const item = document.cookie.split('; ').find((part) => part.startsWith(`${name}=`))
  return item ? decodeURIComponent(item.split('=').slice(1).join('=')) : ''
}

export async function api<T>(url: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const csrf = cookie('csrftoken')
  if (csrf) headers.set('X-CSRFToken', csrf)
  const response = await fetch(url, { ...options, headers, credentials: 'same-origin' })
  if (response.status === 401 || response.status === 403) {
    window.location.assign(`/accounts/login/?next=${encodeURIComponent(location.pathname + location.search)}`)
    throw new Error('登录状态已失效')
  }
  if (!response.ok) {
    let message = `请求失败 (${response.status})`
    try {
      const data = await response.json()
      message = data.detail || Object.values(data).flat().join('；') || message
    } catch { /* non-json response */ }
    const error = new Error(message) as Error & { status?: number }
    error.status = response.status
    throw error
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const post = <T>(url: string, body: unknown = {}) => api<T>(url, {
  method: 'POST',
  body: JSON.stringify(body),
})

export const patch = <T>(url: string, body: unknown) => api<T>(url, {
  method: 'PATCH',
  body: JSON.stringify(body),
})

export const remove = <T>(url: string) => api<T>(url, { method: 'DELETE' })
