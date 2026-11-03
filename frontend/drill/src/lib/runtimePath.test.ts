// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { recoverIpWorkspacePath, workspaceForPath, workspaceFromSiteCookie } from './runtimePath'

describe('workspace path routing', () => {
  it('recognizes IP path-based Drill and EI workspaces', () => {
    expect(workspaceForPath('/ei/practice/question-id')).toBe('ei')
    expect(workspaceForPath('/drill/practice/question-id')).toBe('drill')
  })

  it('does not infer a workspace from unrelated paths', () => {
    expect(workspaceForPath('/practice/question-id')).toBeNull()
    expect(workspaceForPath('/eigenvalue')).toBeNull()
  })

  it('recovers a missing IP prefix only from the existing workspace cookie', () => {
    expect(recoverIpWorkspacePath({
      hostname: '47.95.10.128',
      pathname: '/practice/question-id',
      search: '?from=heatmap',
      hash: '#answer',
      cookie: 'time_tracker_ha_site=ei',
    })).toBe('/ei/practice/question-id?from=heatmap#answer')
    expect(recoverIpWorkspacePath({
      hostname: '47.95.10.128',
      pathname: '/made-up-page',
      cookie: 'time_tracker_ha_site=drill',
    })).toBe('/drill/made-up-page')
    expect(workspaceFromSiteCookie('a=1; time_tracker_ha_site=ei; b=2')).toBe('ei')
  })

  it('does not guess without context or rewrite server-owned paths', () => {
    expect(recoverIpWorkspacePath({
      hostname: '47.95.10.128', pathname: '/practice', cookie: '',
    })).toBeNull()
    expect(recoverIpWorkspacePath({
      hostname: 'example.test', pathname: '/practice', cookie: 'time_tracker_ha_site=ei',
    })).toBeNull()
    for (const pathname of ['/api/test', '/static/test.js', '/accounts/login/', '/share/token']) {
      expect(recoverIpWorkspacePath({
        hostname: '47.95.10.128', pathname, cookie: 'time_tracker_ha_site=ei',
      })).toBeNull()
    }
  })
})
