# BUG-04 / BUG-08 — heatmap regression repair

## Historical source and preserved behavior

The last actual production source before the large UI rebuild was `6b83e2924b9042e75e87bc091ea7f24e0948f8ee`; the released rebuild is `0103df5437084b25a3e70afc6cb9cb68e436f681`. Inspection used `git show`/`git diff`, not an imagined reconstruction.

`frontend/drill/src/views/HeatmapView.vue` at 6b83e29 had:

- One bordered neutral surface per book, 16px padding (12px on phones), 8px inter-book spacing.
- Topic matrix: 26px cells / 5px gaps. Question matrix: 28px cells / 4px gaps, including touch devices.
- Blank cells with `status-*` semantics; hidden year/index spans. Type-color preview is the existing optional CSS bottom stripe. Selection is an outside outline.
- Existing topic preview; question preview, with source-indexed questions opening directly; document/order hierarchy and filtering.

The rebuild replaced these with 32px numbered cells (44px on coarse pointers), status glyph children, `cell-*` treatment and flat book sections. Round 2 restores the actual old matrix, book layout and status treatment. It retains the rebuild's account/workspace-scoped restoration, request cancellation and race protection, accessible names, query-preserved filters, next-unattempted locator, and all source-indexed routes. Backend search improvements are not reverted.

There are no screenshots/recordings attached in this tool-visible turn. Historical code and reproducible browser screenshots establish the comparison; physical iPad Safari remains a required honest coverage limitation.

## Rejected hypothesis

`DrillHeatmapView` uses `.only()` and accesses `final_question_type`. Initial suspicion was a deferred-field N+1. Root verified `workspace_questions` / `filter_exam_type` annotate this field with `Coalesce`; it is not a model property and `.only()` does not remove annotations. **No N+1 conclusion is claimed.** Root owns actual SQL/count/API measurements and any backend change in `drill/views.py`.

## Targeted frontend fixes

- `shallowRef` treats whole API payloads as immutable snapshots, avoiding deep proxies for thousands of records. Each successful fetch replaces the snapshot.
- Per-cell `v-memo` includes item identity, selection, quick-highlight and language; a selection no longer rebuilds unchanged cells. Response replacements and label/locale changes invalidate the relevant cells.
- A warm cached return restores its selection and scroll immediately, while revalidation continues; a slow request no longer delays already available context.
- Omit the old always-hidden year/index/type-dot spans: the exact old visual is retained with one button node per question, while `aria-label`, `title`, `data-question-order` and the preview preserve identity and status.
- No virtualization, extra dependencies, new backend source or independent PWA state system.

## Reproducible measurements

`browser_heatmap.py` creates a public synthetic fixture of 963 questions and a worst-case single-book 9,281-question matrix. Five fresh Chromium contexts per case; iPad 1180×820 touch, iPhone 390×844 touch, desktop 1440×900. API is intercepted with exactly the same JSON (270,925 / 2,625,803 bytes), so this **isolates frontend work and does not measure database latency**.

`load_ms` measures navigation through all cells present plus two animation frames, including shell/bundle/driver time. `select_ms` and `filter_ms` include Playwright's actionable-click wait and two animation frames; treat them as comparable end-to-end browser operation measurements, not pure JavaScript CPU time. The script records DOM count, cell geometry, long tasks, scroll frame gaps and JavaScript errors. There is no CPU or network throttling and concurrent host workload is not controlled; medians indicate direction, not a physical iPad guarantee. Screenshot fixtures never write learning data.

Commands (fixture servers must be launched against the matching prebuilt root):

```sh
UI_REBUILD_FIXTURE_ROOT=/home/eh/ui-rebuild-20261112 python frontend/e2e/fixture_server.py --port 8014
UI_REBUILD_FIXTURE_ROOT=/home/eh/precision-study-ui-20261111 python frontend/e2e/fixture_server.py --port 8015
UI_REBUILD_FIXTURE_ROOT=/home/eh/learning-os-round2 python frontend/e2e/fixture_server.py --port 8016
python docs/round2/heatmap/browser_heatmap.py --url http://127.0.0.1:8014 --label before-0103df5 --output docs/round2/heatmap/evidence
python docs/round2/heatmap/browser_heatmap.py --url http://127.0.0.1:8015 --label historical-6b83e29 --output docs/round2/heatmap/evidence
python docs/round2/heatmap/browser_heatmap.py --url http://127.0.0.1:8016 --label restored-round2 --output docs/round2/heatmap/evidence
```

Use the recorded absolute Python environment `/home/eh/ei-page-tracking/browser-env/bin/python` when Playwright is unavailable in the active interpreter. Browser is `/usr/bin/google-chrome`.

## Verification

Existing 7 heatmap component tests pass. Added cases prove cached return restores before a pending refresh, verify historical status rendering retains accessible question metadata, and prove a fresh server snapshot invalidates memoized cached state/selection. All 11 pass. Production Drill build/typecheck passed. Root is responsible for final integrated build/test, SQL/API evidence, multi-device integration and deployment.

## Final browser comparison

All values are medians of five fresh contexts. Scroll is median of each run’s45-frame p95gap. Milliseconds; synthetic interceptedAPI only.

| Build | Questions | Width | Load | Select | Filter | Matrix DOM nodes | Scroll p95 framegap | JS errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| historical-6b83e29 | 963 | 1180 | 653.39 | 163.1 | 82.2 | 2889 | 16.9 | 0 |
| historical-6b83e29 | 963 | 390 | 615.44 | 162.8 | 82.1 | 2889 | 17.7 | 0 |
| historical-6b83e29 | 963 | 1440 | 613.09 | 164.6 | 82.3 | 2889 | 17.5 | 0 |
| historical-6b83e29 | 9281 | 1180 | 959.27 | 253.7 | 280.5 | 27843 | 29.8 | 0 |
| historical-6b83e29 | 9281 | 390 | 947.26 | 260.4 | 265.1 | 27843 | 34.9 | 0 |
| historical-6b83e29 | 9281 | 1440 | 960.73 | 280.2 | 280.5 | 27843 | 59.2 | 0 |
| before-0103df5 | 963 | 1180 | 633.79 | 98.3 | 98.6 | 2433 | 17.9 | 0 |
| before-0103df5 | 963 | 390 | 575.6 | 152.7 | 98.8 | 2433 | 17.7 | 0 |
| before-0103df5 | 963 | 1440 | 639.56 | 99.6 | 99.4 | 2433 | 17 | 0 |
| before-0103df5 | 9281 | 1180 | 1210.4 | 327.7 | 414.3 | 23446 | 79.8 | 0 |
| before-0103df5 | 9281 | 390 | 1088.21 | 369.4 | 414.1 | 23446 | 61.6 | 0 |
| before-0103df5 | 9281 | 1440 | 1452.95 | 370.7 | 463.6 | 23446 | 93.3 | 0 |
| restored-round2 | 963 | 1180 | 596.09 | 85.2 | 82.5 | 963 | 16.9 | 0 |
| restored-round2 | 963 | 390 | 514.08 | 139.0 | 82.0 | 963 | 17.7 | 0 |
| restored-round2 | 963 | 1440 | 597.58 | 86.6 | 82.3 | 963 | 17.3 | 0 |
| restored-round2 | 9281 | 1180 | 816.52 | 122.1 | 198.8 | 9281 | 26.5 | 0 |
| restored-round2 | 9281 | 390 | 727.24 | 168.7 | 198.7 | 9281 | 31.2 | 0 |
| restored-round2 | 9281 | 1440 | 830.72 | 124.1 | 215.6 | 9281 | 43.3 | 0 |

The final iPad 9,281-cell case improves versus the released rebuild: load1,210→817ms (−33%), selection328→122ms (−63%), filter414→199ms (−52%). It also improves versus the actual pre-rebuild6b baseline (959/254/281ms). DOM falls23,446→9,281 (−60%). No synthetic API payload reduction is claimed: both builds received exactly the sameJSON. Backend/API measurements belong to root’s separate evidence.

`restored-stage1*` deliberately preserves intermediate evidence before removal of invisible spans, not the final candidate. The checked screenshots match historical28px geometry rather than the rebuilt44px coarse layout. First snapshots are taken after exercising selection/filter and returning to page top, not unmodified first-paint shots.


## Final historical overview alignment

After the measured component optimization, root requested restoration of the remaining historical overview arrangement: large total-question number, then attempted/mastered values; the next-unattempted locator sits on the same action row as the state filters, as in6b83e29. This final change only rearranges the small overview/toolbar DOM and preserves all fetching/memoization/cache logic. Added a structural regression test. The `restored-round2` timing evidence above predates this final toolbar-only arrangement and is not relabeled as a post-arrangement timing run. Final integrated screenshots/build are owned by root. Matrix geometry, node counts and optimization logic are unchanged.

Root's build-time fontScalePlugin multiplies font-size declarations by `--ui-font-scale`; heatmap fonts therefore follow the account preset without local calc overrides. The historical28/26px cell widths/heights and spacing are separate geometry and are not scaled.

## Actual PostgreSQL API/SQL comparison — no backend regression

Machine-readable measurements: [`backend-comparison.json`](backend-comparison.json). Full captured parameterized SQL and `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` are retained in the two `api-*-full.json.gz` archives. `bench_backend.py` refuses databases other than the isolated `precision_search_real` fixture and sets the session read-only. No production database or user session was used.

Environment: PostgreSQL15.18; the real public-metadata fixture contains9,281 Question rows, **zero Attempt and zero QuestionUserState rows**. Therefore these measurements cover real catalog/manifest/materialization costs and empty-history query overhead; they do not establish worst-case performance for a user with a large attempt history. Actual qualifying counts are5,847 Drill questions,2,830 EI questions,963 Drill-selected,421 EI-core (`material=all`); the remaining rows are not practiceable in these scopes.

Two warmups and ten measured runs per scope per version. This benchmark invokes the actual DRF APIView with an existing synthetic authenticated user and includes JSON rendering, while excluding browser/network/auth/middleware time. P95 uses nearest rank and is the maximum of ten samples; the smaller sample size is stated rather than pretending to be the productionHTTP benchmark.

| Scope | SQL count before→after | JSON bytes | API+JSON P50 before→after | API+JSON P95 before→after | SQL execute wall P50 before→after |
|---|---:|---:|---:|---:|---:|
| Drill all / questions | 6→6 | 1,812,014 | 411→416ms | 464→444ms | 124→127ms |
| Drill selected963 | 6→6 | 307,609 | 76→74ms | 107→103ms | 27→27ms |
| EI all / questions | 6→6 | 893,874 | 202→201ms | 231→226ms | 55→55ms |
| EI core421 | 6→6 | 170,309 | 52→51ms | 80→78ms | 22→22ms |
| Drill topics | 7→7 | 158,808 | 373→376ms | 381→391ms | 144→145ms |

**The complete rendered JSON SHA256 matches exactly between versions for every scope**, as do byte counts and query counts. At measurement time before the later transfer-only gzip decorator, the normalized AST SHA256 of `DrillHeatmapView` at6b83e29,0103df5 and HEAD was identical (`dd8300bd1b866430cbe3c38a7f9477d149e34e292208700094f0693f2db5a18f`). No backend heatmap regression or per-question N+1 was reproduced. The measured repair is on the frontend rendering/restoration path.

EXPLAIN observations, without guessing about absent indexes:

- The all-Drill question SELECT returns5,847 rows in about15.6ms server execution (planning0.7ms).
- Three attempt/timing queries each expand the loaded5,847 IDs into roughly24KiB SQL /5,850 parameters. With no history the actual plan executes in0.05–0.12ms, but planning takes5–6ms and execute-wrapper wall time is about22ms per query. Parameter adaptation, submission and planning are measurable costs even when the result is empty.
- API view time around385ms versus SQL execute wall127ms also includes fetching results, model construction and Python grouping; JSON serialization adds about30ms for1.8MB. It is incorrect to label that difference as an indexed SQL scan or N+1 without profiling.

Release decision: **do not modify heatmap backend SQL or add indexes in this repair**. The class and payload remain unchanged; this avoids disturbing statistics and state semantics after frontend fixes already beat the historical browser baseline. A later isolated benchmark may evaluate bounded PG-array membership or a values projection if catalog growth warrants it. A naïve live subquery would re-evaluate membership after the question snapshot and needs an explicit concurrency/semantics review. These are deferred experiments, not claimed implemented optimizations.

## Production follow-up: negotiated JSON transfer compression

Real HTTPS cold-context sampling initially found selected heatmap1304→1950ms;
that result is preserved in`../search-question/final/production/`. A second five-case
breakdown found response completion→DOM insertion23–31ms and insertion→RAF121–138ms,
while307254bytes of JSON were sent uncompressed and body transfer varied46–673ms.
The current Nginx has`gzip on` but no JSON`gzip_types`. Both CDP andResourceTiming
confirmed encodedBodySize equals decodedBodySize; this was a measured transfer
bottleneck rather than a guessed SQL/index defect. Subsequent5-case cold median1403ms
does not erase the initial regression.

Main added standard Django4.2`gzip_page` only toDrillHeatmapView.dispatch. Django's
middleware decorator registers a post-render callback forDRFResponse, negotiates
Accept-Encoding, setsVary/Content-Length, skips existing encodings and uses100bytes
of random-padding protection. Data aggregation, auth, filters and JSON body after
decoding are unchanged; requests without gzip retain their exact original body.
No new infrastructure, backend query/index rewrite or Nginx configuration change.
The endpoint retains its existing renderers; do not call BrowsableAPIHTML token-free.

Four focused transfer tests pass inSQLite andPostgreSQL, plus49existing/new DrillAPI
checks. They assert byte-for-byte decompression equality in both workspaces, exact
counts, no prompt leakage, negotiated/no-negotiation behavior, account states,
workspace rejection, affinity rejection and anonymous authentication. Independent
review verified installed Django's deferred-render and compression implementation.
Production compressed bytes and cold-screen evidence are recorded after rollout.


### Subsequent production transfer-only correction

The API/SQL table above was measured before root added a per-view gzip decorator in response to later production cold-load/network measurements. That later change does not rewrite GET aggregation or question/statistics semantics; the historical full-class AST hash is retained as dated measurement evidence, not falsely asserted for the newly decorated class. Independent compression review and4 passing tests are recorded in [`TRANSFER_COMPRESSION_REVIEW.md`](TRANSFER_COMPRESSION_REVIEW.md). Root owns the final compressed transfer and cold-first-screen production comparison; BUG-04 must not be closed solely from local API equivalence.
