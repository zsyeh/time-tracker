/**
 * Offline, synthetic-only URL budget audit. Requires the repository's installed
 * vue-router. Run with Node from a container mounting dependencies as
 * /work/frontend/node_modules; see README.md. Does not contact any server.
 */
import { createMemoryHistory, createRouter } from '../../../frontend/node_modules/vue-router/dist/vue-router.mjs'

const router = createRouter({ history: createMemoryHistory('/drill'), routes: [
  { path: '/preview', component: {} }, { path: '/practice', component: {} },
] })
const bytes = value => Buffer.byteLength(value, 'utf8')
// urllib.parse.urlencode / quote_plus used by drill.web_views.
const quotePlus = value => encodeURIComponent(value)
  .replace(/[!'()*]/g, c => '%' + c.charCodeAt(0).toString(16).toUpperCase())
  .replace(/%20/g, '+')
const queryString = values => Object.entries(values).map(([k, v]) => `${quotePlus(k)}=${quotePlus(v)}`).join('&')
// django.contrib.auth.views.redirect_to_login uses QueryDict.urlencode(safe='/').
const loginQuery = value => quotePlus(value).replaceAll('%2F', '/')
const q = '多元微分'.repeat(30) // Exactly the backend's 120 Unicode-character limit.
const filters = {
  q, document: '12345', topic: '12345', source_category: 'past_exam',
  type_group: 'short_answer', exam_type: 'short_answer', status: 'unattempted',
  favorite: '1', review_later: '1', marker: 'overconfident', include_structure: '1',
  sort: 'relevance', search_version: '2',
}
// Additional recognized scope keys are a conservative encoding-size case,
// not a claim that all collections expose these options together.
const scopeStress = { ...filters, collection: 'math2_selected', bucket: 'integration_methods',
  tier: 'core', kind: 'comprehensive', combined: '1', state: 'review',
  material: 'ready', course: 'circuit', scope: 'past_exam' }
const result = {
  generated_at: new Date().toISOString(),
  mode: 'offline actual Vue Router encoding and equivalent Python/Django quoting; no HTTP/authentication/data writes',
  query_unicode_characters: [...q].length,
  correction: 'The initial 180-character example was NOT a valid search. parse_query limits raw queries to 120 Unicode characters. It is superseded by these 120-character cases.',
  budget: { gunicorn_request_line_bytes: 8190, nginx_default_single_large_request_buffer_bytes: 8192 },
  source_files: ['frontend/drill/src/lib/listContext.ts', 'frontend/shared/search/queryState.ts',
    'frontend/drill/src/components/PracticeFilterPanel.vue', 'drill/search/query.py', 'drill/web_views.py'],
  cases: [],
}
for (const [name, query] of [['query_120', { q }], ['all_ui_filters_120', filters], ['recognized_scope_size_stress_120', scopeStress]]) {
  const returnTo = router.resolve({ path: '/practice', query: { ...query, page: '999', index_version: '1'.repeat(64) } }).fullPath
  const context = { version: 1, workspace: 'drill', source: 'practice', query, returnTo }
  const logical = router.resolve({ path: '/preview', query: { list: JSON.stringify(context) } }).fullPath
  const drillAuthStart = '/drill-auth/start?' + queryString({ next: logical, site: 'drill' })
  const drillLogin = '/accounts/login/?next=' + loginQuery(drillAuthStart)
  const ipAuthStart = '/ip-auth/start?' + queryString({ next: '/drill' + logical })
  const ipLogin = '/accounts/login/?next=' + quotePlus(ipAuthStart)
  const requestLine = path => bytes('GET ' + path + ' HTTP/1.1')
  const maxRequestLine = Math.max(requestLine(drillLogin), requestLine(ipLogin))
  result.cases.push({ name, return_to_bytes: bytes(returnTo), logical_preview_bytes: bytes(logical),
    ip_preview_bytes: bytes('/drill' + logical), drill_auth_start_bytes: bytes(drillAuthStart),
    accounts_login_bytes: bytes(drillLogin), ip_auth_start_bytes: bytes(ipAuthStart),
    ip_accounts_login_bytes: bytes(ipLogin), max_http11_request_line_bytes: maxRequestLine,
    remaining_8190_bytes: 8190 - maxRequestLine,
    absolute_first_location_bytes: bytes('https://timer.ehzsy.site' + drillAuthStart),
    location_alone_exceeds_4k_proxy_response_header_buffer: bytes('https://timer.ehzsy.site' + drillAuthStart) > 4096,
    fits_gunicorn_8190: maxRequestLine <= 8190,
  })
}
result.limitations = [
  'This is a deterministic encoding calculation, not end-to-end production login verification.',
  'Document/topic identifiers are synthetic numeric filter values; no nonempty search result is asserted.',
  'Request-line and upstream response-header budgets are separate. A long Location can exceed the default 4KB upstream header buffer.',
  'The longest accepted raw JSON/context string is not necessarily a supported HTTP URL. Do not claim the model 16384 field size is the network limit.',
  'Cookie and other response headers add to Location; allocate bounded response-header headroom.',
]
console.log(JSON.stringify(result, null, 2))
