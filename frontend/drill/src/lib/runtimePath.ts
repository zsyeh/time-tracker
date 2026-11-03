export function workspaceForPath(pathname: string): 'drill' | 'ei' | null {
  const match = pathname.match(/^\/(drill|ei)(?:\/|$)/)
  return match ? match[1] as 'drill' | 'ei' : null
}

const SERVER_PATH_PREFIXES = [
  '/api', '/static', '/accounts', '/admin', '/share', '/drill-auth', '/ip-auth',
]

export function workspaceFromSiteCookie(cookie: string): 'drill' | 'ei' | null {
  const value = cookie.split(';').map((part) => part.trim()).find(
    (part) => part.startsWith('time_tracker_ha_site='),
  )?.split('=', 2)[1]
  return value === 'drill' || value === 'ei' ? value : null
}

export function recoverIpWorkspacePath(options: {
  hostname: string
  pathname: string
  search?: string
  hash?: string
  cookie: string
}): string | null {
  const { hostname, pathname, search = '', hash = '', cookie } = options
  if (hostname !== '47.95.10.128' || pathname === '/' || workspaceForPath(pathname)) return null
  if (SERVER_PATH_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))) {
    return null
  }
  const workspace = workspaceFromSiteCookie(cookie)
  return workspace ? `/${workspace}${pathname}${search}${hash}` : null
}

const recoveredPath = recoverIpWorkspacePath({
  hostname: window.location.hostname.toLowerCase(),
  pathname: window.location.pathname,
  search: window.location.search,
  hash: window.location.hash,
  cookie: document.cookie,
})
if (recoveredPath) window.history.replaceState(window.history.state, '', recoveredPath)

const prefixedWorkspace = workspaceForPath(window.location.pathname)
export const runtimeWorkspace: 'drill' | 'ei' = prefixedWorkspace
  || (window.location.hostname.toLowerCase().startsWith('ei.') ? 'ei' : 'drill')
export const workspacePrefix = prefixedWorkspace ? `/${prefixedWorkspace}` : ''
export const routerBase = workspacePrefix ? `${workspacePrefix}/` : '/'

export function withWorkspacePrefix(url: string): string {
  if (!workspacePrefix || !url.startsWith('/') || url.startsWith('//')) return url
  if (url === workspacePrefix || url.startsWith(`${workspacePrefix}/`)) return url
  return url.startsWith('/api/') || url.startsWith('/share/') ? `${workspacePrefix}${url}` : url
}

export function withoutWorkspacePrefix(path: string): string {
  if (!workspacePrefix || !path.startsWith(workspacePrefix)) return path
  return path.slice(workspacePrefix.length) || '/'
}
