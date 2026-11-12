# Round 2 — Search entry and question loading (BUG-02/BUG-03)

## 最终46e9d81构建补充回归

新增进度目标账号同步后的最后构建已完成WebKit最小风险门禁：Drill/EI各1条完整交互与Reader1条，全部通过；16字段bootstrap、4次旋转、1GET去重及67文件哈希一致。详见[最终构建证据](final/latest/46e9d81/README.md)。此前完整设备矩阵与生产性能证据按阶段保留；next图片3样本变慢没有被标作普遍改善。


## Reproduced causes

1. `PracticeView.navigationQuery()` carries the **list pagination generation pin** into the question-detail URL. `DrillQuestionDetailView → navigation_queryset → membership → index_state` rejected a valid UUID with HTTP409 whenever the search generation changed between list response and click. This is not a UUID serialization or Drill/EI prefix bug.
2. `hybrid_membership` used an `IN (SELECT ... OFFSET 0)` relation. PostgreSQL15 chose a nested loop for document/source-constrained neighbor lookups and reexecuted its identical JSONB/GIN candidate scan **15–53 times per statement**. Three neighbor queries took approximately220/413/416ms in `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`; total search-context detail p50 was1135ms versus58ms for the same UUID without search context. Payload remained2326bytes. These measurements identify SQL execution, rather than payload size or a presumed frontend framework issue, as the main delay in this path.
3. Ordinary question entry supplied an AbortSignal directly to `fetchQuestion`, bypassing its shared in-flight prefetch. Practice and Question also construct equivalent query parameters in different insertion orders, causing distinct cache keys. Browser reproduction of old0103df5 showed **two GETs for the same clicked UUID**; the fixed path shares one GET.
4. Result pages were cached with the response's generation but read on remount with an empty component-local generation, so return-to-search could not immediately restore the cached list. Obsolete first-result prefetch timers were also not canceled when a new input invalidated the query.
5. Pending URL updates lacked an owning-route/disposal check. A draft search must never mutate a destination question route. Dedicated disposal and route-transition tests now cover this boundary.

## Changes and retained behavior

- `drill/search/service.py`: materialize public candidate IDs once per PostgreSQL statement; no result cap, scoring/normalization change or user result cache. Add `pin_version=True` and `materialize_candidates=True` defaults. Question navigation alone disables both via the root-owned `drill/views.py` hook: its already scoped one-to-one projection join avoids scanning global candidates for every neighbor lookup. Lists retain409 protection. Authentication, workspace scope, filters, readiness, user status semantics and UUID lookup are unchanged.
- `frontend/drill/src/lib/workspace.ts`: canonicalize detail cache/in-flight keys by sorting URL parameters. Account/workspace isolation and stale-response guards remain.
- `QuestionView.vue`: ordinary entry uses the same abortable shared navigation request already used by the full-screen reader. Cached content remains immediately visible, followed by server revalidation. No timer, Attempt, Note, diagnosis, submission, image URL/cache or next/previous semantic change.
- `PracticeView.vue`: stable scoped query+schema list-cache keys; query/page pins remain in page-specific keys; cancel obsolete speculative timers and capture their original context/sequence.
- `usePracticeQuery.ts`: discard pending timers/queued patches on route ownership loss or disposal. IME/debounce/cancellation/URL semantics retained.
- `drill/test_search_navigation_regression.py`: stale generation expires list pagination but not a valid detail UUID; next-unattempted ordering, EI boundary, anonymous rejection and index readiness still enforced.

No schema migration, source question mutation, search projection rebuild or statistics formula change is required by these search/question fixes.

## Measured HTTP comparison

Isolated actual public metadata corpus:9281 source questions; same PostgreSQL15 database; old0103df5 and round2 Gunicorn replicas both3workers×2threads; sequential real HTTP requests with the same authenticated fixture account. Each case has3warmups+30samples. p95 is nearest-rank29/30. This is local warm-network server latency, not physical iPad/Safari or production-network latency.

| Case | Before p50/p95 ms | After p50/p95 ms |
|---|---:|---:|
| Search `导数` |100/112|103/503 initial worker set; steady102/105|
| Search `偏导数` |61/63|61/63; steady62/66|
| Search `导数` + small type |94/107|97/100; steady97/101|
| Catalog browse |35/37|35/66|
| Same question without search context |61/68|61/65|
| Same question with `导数` context |1133/1146|**72/78 final** (intermediate materialized path142/154)|
| Selected-collection search entry |Not separately benchmarked|84/106 final|
| EI `Fourrier` search entry |Not separately benchmarked|139/149 final|

The first new-replica run included two503/543ms samples for broad search; they are retained in `http-bench.json`, not discarded. A subsequent90GET steady-state check is separately retained in `http-bench-steady.json`. This does not establish performance at arbitrary concurrency, cold processes or large remote network latency.

## Tests and browser status

- Focused frontend:5files,26tests passed (`frontend-tests.log`). Includes IME, stale request/debounce,409 paging, URL semantics, cache restoration, obsolete prefetch cancellation, route-disposal safeguards, account scope and query-order-independent request reuse.
- Focused PostgreSQL:29tests passed (`backend-tests.log`): original navigation equivalence, search API and new generation-entry/auth/workspace regressions. The selected cross-book and EI spelling-search test compares all nine navigation UUIDs between the one-to-one join and materialized paths and verifies the expected next target.
- Vite Drill production bundle built successfully into an isolated output directory; root performs final full TypeScript/test/build integration after shared preference changes.
- Synthetic browser fixture uses160ms detail delay and100ms list delay, with all timing/learning writes mocked. Old iPad-portrait bundle reproduced2clicked-detailGETs; round2 has1. **Final8/8 workflows pass** for Drill/EI ×390/820/1180/1440px: first entry→search→open→next→previous→return→type a pending draft and immediately open a result→return→search again.0JSerrors,0horizontal overflow,0observed long tasks. Direct first opens731–818ms include initial bundle/bootstrap plus synthetic API delay; search click→usable224–248ms; next52–62ms, previous45–76ms. These are controlled functional browser timings, not a production or iPad latency claim.
- Browser independently found the1180px fixed navigation button intercepted the return-to-bank button. Root moved the menu trigger into the existing Question toolbar through a named slot; final8-case real-click checks validate the return action without `force` or a z-index workaround.
- Physical iPadOS/Safari, actual image-transfer paint and production p50/p95 require root's deployment/GET-only evidence and real-device follow-up; they are not represented by the synthetic160ms browser numbers.

## Production baseline supplied by the root agent

`/home/eh/learning-os-round2-evidence/production-before.json`: deployed9df573e, authenticated GET-only HTTPS, one client,2warmups+20samples; no question frontend/timing writes. Search-context question p50/p95 **4473/6671ms**, bare87/122ms, next92/142ms, previous85/123ms. This confirms a much larger real deployment regression in the same context path. The root agent must append the matched post-deploy result; local72/78ms must not be presented as production timing.

## Remaining validation boundary

These module fixes are frozen. A fresh central production-bundle regression after shared Sidebar/Preferences integration passes **8/8** using a full server-schema SSR/auth preference fixture. `browser-central.json` records the complete flows; all67 bundle files have identical hashes before/after the run (`bundle-central-sha256.json`). Entry is `index-CiDf0Bfv.js`; index.html SHA-256 is `512e48da6e8f2cf13cff6b1927dd20ad83f6326c998037616583e190101e440b`. Earlier isolated-bundle8-case evidence remains separately retained. No deployment or production mutation was performed by this subagent.

## Independent preference concurrency and compatibility review

The same subagent added only frontend tests for the root-owned preference store. Factory/deferred/fake-timer tests exposed three P1 defects, all fixed by the root: an old successful PATCH response could roll back a newer GET snapshot; a delayed409 current snapshot had the same rollback risk; default preference HTTP requests lacked the existing account-affinity header and could follow another tab's changed login cookie into the wrong account. Final tests prove monotonic snapshots on both200/409, latest local intent preservation, explicit same-field conflict resolution, per-field two-device merge, SSR cached-pending restart, offline retry, identity epoch rejection, logout cleanup, write coalescing and an independent core question request finishing while preference save is stalled.16store+8schema tests pass.

Eight existing component test files were updated to bind an authenticated synthetic preference account rather than assigning unbound readonly/global localStorage state. Their diagnosis, reader, Note, share, chart, navigation and practice-action assertions remain; persistence assertions now check the account queue/cache. App navigation tests additionally verify a customized pinned order while More/Settings remain reachable. Final full frontend run: **60files/292tests passed** (`/home/eh/learning-os-round2-evidence/vitest-after-compat.log`). These local tests do not replace root's post-migration production sync and real-device verification.

## Final cross-engine evidence

[`final/chromium`](final/chromium) retains the central67-file bundle hashes,8complete Drill/EI workflows and an iPad screenshot. [`final/webkit`](final/webkit) passes the same8workflows on real Playwright WebKit engine27.2, additionally checking16orientation transitions and zero navigation/return rectangle overlaps. Each entry remains one detail GET and has no page JavaScript error or horizontal overflow. WebKit does **not** expose the Long Tasks PerformanceObserver type; the report explicitly marks it unsupported, rather than claiming zero long tasks. The replay script supports `--engine chromium|webkit --rotate` (default engine unchanged).

[`final/reader-chromium`](final/reader-chromium) and [`final/reader-webkit`](final/reader-webkit) reuse the existing independent `browser_review.question` interactions **and all original pass conditions**, configuring only the fixture URL for the central bundle. Both pass:8diagnosis options≥44px; selecting2diagnoses; sticky submit inside its pane; Note Save44px and unobstructed; More actions; full-screen Reader staying open after rotation to390px; all7reader controls≥44px; Escape close and no page errors. Screenshots are synthetic, contain no real notes/credentials and are retained alongside JSON. No answer was submitted.

These are Linux Chromium/WebKit engine checks, **not physical iPadOS Safari/PWA, browser chrome, native keyboard or device safe-area validation**. The root's subsequent preference auth-rejection/preset-draft fixes require its final build/test gate; these engine artifacts identify the central bundle they actually exercised and must not be relabeled as a later untested hash.

### Last risk gate and source freeze

[`final/latest`](final/latest) is the last gate after auth-affinity UI reset, preset pending-draft/old-return-context fixes and coarse-pointer16px input protection. **WebKit8/8** workflows plus16rotation transitions and **WebKit Reader1/1** pass, with identical full bundle hashes before/after. index.html SHA-256: `b100093faa52f2a341c3895c120086d4436dba4d80527cb15eff83630e342a41`. No untested later bundle is substituted for this evidence. The Reader test checks controls/diagnosis/Note/rotation; its text-only synthetic question has no real scanned assets, so it does not establish actual image-transfer/paint speed. Screenshots were also visually inspected.

Latest targeted tests: store20/20 (including401/unauthenticated403/account-change409 UI clearing while retaining the private account retry queue; ordinary CSRF403 does not discard it), Practice10/10 (including same-query saved-preset draft cancellation and removal of old `from` context). The root's final full suite has60files/297tests; the additional `from` assertion remains within the same existing test and passes its focused run. No further functionality or optional testing is planned by this subagent.
