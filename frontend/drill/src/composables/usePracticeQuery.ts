import { computed, onScopeDispose, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { normalizePracticeQuery, serializePracticeQuery, type PracticeQuery } from '../../../shared/search/queryState'

/** The URL owns the applied query. Input drafts never launch requests during IME. */
export function usePracticeQuery(invalidate: () => void) {
  const route = useRoute()
  const router = useRouter()
  const applied = computed(() => normalizePracticeQuery(route.query))
  const draft = ref(applied.value.q || '')
  const composing = ref(false)
  const refresh = ref(0)
  let timer: ReturnType<typeof setTimeout> | undefined
  let pending: PracticeQuery | null = null
  let pendingMode: 'push' | 'replace' = 'push'
  let queued = false
  let disposed = false
  const ownerPath = route.path
  function apply(patch: PracticeQuery, mode: 'push' | 'replace' = 'push', resetPage = true) {
    if (disposed || route.path !== ownerPath) return
    invalidate()
    pending = normalizePracticeQuery({ ...(pending || applied.value), ...patch, ...(resetPage ? { page: '', index_version: '' } : {}) })
    pendingMode = mode
    if (queued) return
    queued = true
    // Related filter changes in the same event become one URL and one request.
    queueMicrotask(() => {
      queued = false
      if (disposed || route.path !== ownerPath || !pending) { pending = null; return }
      const query = pending!
      pending = null
      if (serializePracticeQuery(query) !== serializePracticeQuery(applied.value)) void router[pendingMode]({ query })
      else refresh.value += 1
    })
  }
  function cancelTyping() { if (timer) clearTimeout(timer); timer = undefined }
  function cancelDraft() { cancelTyping(); composing.value = false; draft.value = applied.value.q || '' }
  function submitSearch() {
    cancelTyping()
    if (composing.value) return
    apply({ q: draft.value.trim() }, 'replace')
  }
  function input() {
    cancelTyping()
    invalidate() // Invalidate before debounce, including IME and empty drafts.
    if (!composing.value) timer = setTimeout(submitSearch, 250)
  }
  function compositionStart() { composing.value = true; cancelTyping(); invalidate() }
  function compositionEnd() { composing.value = false; input() }
  watch(() => applied.value.q, (query) => { if (!composing.value) draft.value = query || '' })
  watch(() => route.path, (path) => {
    if (path !== ownerPath) { cancelTyping(); pending = null }
  }, { flush: 'sync' })
  onScopeDispose(() => { disposed = true; cancelTyping(); pending = null })
  return { applied, draft, composing, refresh, apply, input, submitSearch, cancelDraft, compositionStart, compositionEnd }
}
