function cookie(name: string): string {
  const item = document.cookie.split('; ').find((part) => part.startsWith(`${name}=`))
  return item ? decodeURIComponent(item.split('=').slice(1).join('=')) : ''
}

export async function api<T>(url: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')
  if (options.body) headers.set('Content-Type', 'application/json')
  const csrf = cookie('csrftoken')
  if (csrf) headers.set('X-CSRFToken', csrf)
  const response = await fetch(url, { ...options, headers, credentials: 'same-origin' })
  if (response.status === 401 || response.status === 403) {
    location.assign(`/accounts/login/?next=${encodeURIComponent(location.pathname + location.search)}`)
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

