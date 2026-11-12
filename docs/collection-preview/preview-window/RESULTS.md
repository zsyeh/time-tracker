# Preview window implementation and QA

## Implemented source (exclusive module ownership)

- `frontend/drill/src/views/PreviewView.vue`: shared ListContext/session integration, initial/deep-link locating, current ordinal/manual jump, errors/retry, saved entry/offset recovery, question-state refresh, account-change cancellation, localized notices, paper snapshot explanation, read-only fullscreen reader.
- `frontend/drill/src/components/preview/VirtualPreviewList.vue`: independent bounded scroller, TanStack dynamic measurements, directional2/3-screen overscan with20-row normal target, visible-row exception, measured anchor restore/cancellation, stable geometry keys and numerical height ledger, actual `entry_id` question-component keys, end marker.
- `PreviewQuestionRow.vue`: question-only source/content, distinct Attempt identity/date, Note excerpt, semantic state and explicit practice action. Paper preview clearly opens current original as separate practice. OCR/Markdown is rendered only when no question image exists, matching Question presentation.
- `PreviewAssetImage.vue`: aspect-ratio placeholder, near/visible observers, image lease lifecycle, one-tap opening, drag/pinch cancellation, separate zoom, keyboard access, retry. The final44px minimum figure height prevents a very shallow scan from clipping its44px zoom touch target.
- `lib/preview/imagePipeline.ts`: preview-only image transfer4/decode2, current-account header, abort/revoke lifecycle, visible priority,12-image/32MP soft admission, no answer warming.
- `lib/preview/layout.ts`: dimension estimates, bounded directional range, bounded helper caches.

No shared/backend file was edited by this subagent. Router/cache/context/backend integration is owned by the primary agent. No commits or deployment were performed here.

## Local module validation

25 tests passed across `layout.test.ts` (4), `imagePipeline.test.ts` (5), `PreviewAssetImage.test.ts` (3), `PreviewView.test.ts` (13). Tests include real-entry navigation, original browsing anchor, deep-link A→browse B→open B→browser Back, account removal, context switch, stale/out-of-order manual jump, both user-facing notices, pinch/drag/cancel, network/decode admission, cancellation and soft-budget exception. Drill TypeScript check passed during integration; final central build/test logs are owned by the primary agent.

## Final actual corpus run

Evidence: [real-favorite-2000.json](real-favorite-2000.json), [mobile screenshot](real-favorite-2000-mobile.png), [landscape screenshot](real-favorite-2000-landscape.png).

Environment: localhost8035 production-prefix proxy → isolated local Django/PostgreSQL; built production frontend; synthetic2000-favorite account, real imported public question metadata and2326 SHA-verified original PNGs (~127.8MB). These measurements are not production-network latency and do not establish physical iPad Safari performance.

| Observation | Measured result |
|---|---:|
| First displayed preview-image load from navigation time origin |704.70ms|
| Continuous downward traversal |first-visible index1040|
| Reverse traversal |150 scroller steps; recorded sample index785 before later steps|
| Absolute ordinal1250 |first-visible index1249, top offset−0.28125px|
| Maximum mounted virtual rows |20|
| Maximum cached metadata |500|
| Maximum entire-document DOM count |431|
| Maximum mounted ready PNG elements |12|
| Maximum pixels represented by mounted ready PNGs |7,864,562|
| Maximum sampled Chromium JS heap |21.32MiB|
| Long tasks |1, start123.6ms/duration288ms during startup; none recorded during later traversal|
| Horizontal overflow at sampled widths390/1024/1366 |0 samples|
| Browser JavaScript errors |0|

The active image pixels and JS heap do not measure total browser-native decoded-image/cache memory. Visible source-image exceptions and explicit full-screen original scans remain soft-budget exceptions, not a hard native-memory guarantee.

The injected offset600 request interruption recovered through the UI retry, retaining the prior reading anchor. There were49 successful preview API responses over25 unique offsets (24 repeated offsets across explicit refresh/eviction/reverse traversal). This stress run deliberately intercepts requests to simulate failure, which disables normal browser HTTP cache in Playwright; its226 image resource transfers and zero recorded HTTP cache hits therefore must not be used as a normal HTTP-cache verdict.

The App wrote only its existing device learning-recovery endpoint (2 PUTs); this preview run never entered Question, started a timer, or submitted an Attempt/Note/mastery update. The source image SHA validation/import is documented by the backend audit separately.

## Independent normal HTTP-cache run

Evidence: [real-http-cache.json](real-http-cache.json); script [real-http-cache.py](real-http-cache.py).

This uses a separate50-favorite fixture account, actual original PNGs, a fresh browser context and **no Playwright route interception**. Four ordinal50↔1 jumps produced43 recorded image resource requests,26 cache hits (`transferSize=0` with nonzero body size). Original image responses were `private, max-age=31536000, immutable`, with `Vary: Accept, Cookie`. Only one metadata request was made for the50-item collection; later jumps reused the session. Ready images8–9, mounted rows7–9, browser JS errors0. This proves normal HTTP cache reuse independently from the failure-injection test.

## Baselines and limits

- `synthetic-window.json` is a synthetic10k-row dynamic-ratio stress fixture; it does not represent corpus content/performance.
- `real-practice-5847.json` tested actual Practice5847 entries before full PNG import; most bodies were deliberately empty then. It is metadata/layout evidence only.
- `real-favorite-2000-before-geometry.*` records the failing ordinal1250→index1275 baseline, retained to show the measured regression. It is not acceptance evidence.
- `real-favorite-2000-geometry-only.*` records an intermediate run with no decoded images and a CSP error. It is not image/performance acceptance. The final fresh-document run captured the strict CSP unchanged, actual decoded PNGs, and zero JS errors.
- Native physical Safari/PWA, slow remote network, browser-native decode-memory limits and every historical source's data semantics require their separately assigned acceptance coverage. No claim of coverage is inferred from Chromium viewport resizing.
- The final one-line44px shallow-image touch-target correction is included in the final central build; the primary agent performs its final bundle smoke. It does not invalidate the measured mixed-height geometry/cache conclusions.
