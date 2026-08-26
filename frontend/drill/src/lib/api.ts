function cookie(name: string): string {
  const item = document.cookie.split('; ').find((part) => part.startsWith(`${name}=`))
  return item ? decodeURIComponent(item.split('=').slice(1).join('=')) : ''
}

const inflightGets = new Map<string, Promise<unknown>>()

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
  if (options.body) headers.set('Content-Type', 'application/json')
  const csrf = cookie('csrftoken')
  if (csrf) headers.set('X-CSRFToken', csrf)
  const response = await fetch(url, { ...options, headers, credentials: 'same-origin' })
  if (response.status === 401 || response.status === 403) {
    const site = location.hostname.toLowerCase().startsWith('ei.') ? 'ei' : 'drill'
    const next = location.pathname + location.search
    location.assign(`https://timer.ehzsy.site/drill-auth/start?site=${site}&next=${encodeURIComponent(next)}`)
    throw new Error('Your session has expired.')
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = await response.json()
      message = body.detail || Object.values(body).flat().join('; ') || message
    } catch { /* non-JSON response */ }
    throw new Error(message)
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}

export const post = <T>(url: string, body: unknown) => api<T>(url, {
  method: 'POST',
  body: JSON.stringify(body),
})

export const remove = <T>(url: string) => api<T>(url, { method: 'DELETE' })
