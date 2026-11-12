# Round 2 — independent preferences review

Reviewer: `round2_heatmap`, after freezing heatmap ownership. This is a code review, not a claim of physical Safari validation. Root owns store/integration changes; backend owner owns model/API/migration.

## Reviewed boundaries

- `tracker/user_preferences.py`: authenticated session+CSRF; private/no-store; explicit field allowlist; runtime/environment fields excluded; schema and safe revision bounds; account inferred from authenticated user; atomic global-CAS JSON merge plus per-field conflicts.
- `tracker/models.py` / `migrations/0022_userpreferences.py`: separate additive OneToOne table, no changes to study records.
- `tracker/test_user_preferences.py`: independent-field merge, stale complete-document rejection, real PostgreSQL connections, CSRF/account isolation, migration/reversal history preservation.
- `frontend/shared/preferences/schema.ts`, `bootstrap.ts`, `store.ts`.

Backend initial read found no P1. This statement does not replace the backend owner's executed tests or root's production migration validation.

## Frontend P1 findings sent to root

These reflect the first landed store implementation. **All three are now closed after reviewing the final store and independently re-running the regression tests.** They remain recorded to preserve the audit trail.

| ID | Reproduction | Required invariant |
|---|---|---|
| SYNC-REVIEW-01 | Server appearance=System. Send Dark PATCH; before completion click System. `set()` deletes pending because value equals old server snapshot. Dark response arrives, pending is absent, UI/server remain Dark. | Last user intent survives in-flight writes; preserve reverse intent, rebase after acknowledgement and send the final value. |
| SYNC-REVIEW-02 | Start GET refresh; change preference and complete PATCH revision1; delayed GET revision0 then calls accept and replaces UI/cache with stale state. | Same-account stale responses cannot decrease accepted server revision or overwrite newer acknowledgements. Use serialization or request/revision guards and a deferred-response test. |
| SYNC-REVIEW-03 | Offline edits exist in the account cache. Reload/PWA restart receives authenticated server bootstrap. Constructor seeds user/server then `render()` calls `cache()` with empty pending, overwriting offline edits; same-user `bind()` skips cache hydration. | Load validated account pending before any seed cache write. Server bootstrap remains authority for confirmed values; pending edits survive reload with original base revisions and explicit conflicts. |

Additional integration gates: `readPreferenceBootstrap()` expects string `user_id`; server JSON must serialize the identity consistently. Sidebar Settings/Home must remain pinned independently of configurable hidden/group arrays. Auth expiry/account switching must reset identity and ignore old pending responses, not merely show an error while continuing to expose another account's preset labels.

## Completed delegated boundary hardening

Root authorized this reviewer to implement only `schema.ts` and new `schema.test.ts`:

- `validPreference(key,value)` validates every known enum/boolean, workspace Sidebar IDs/list uniqueness, exact structural fields, at most ten saved filter presets, per-workspace collections, search/query allowed keys and lengths, safe document/topic IDs, and excludes transient query fields.
- Unicode lengths use code points to match Python rather than incorrectly rejecting astral characters accepted by the backend.
- `validSnapshot()` rejects missing/corrupt known fields and unsafe field/global revisions, while allowing safe unknown future fields. Array/record confusion, prototype keys and cyclic snapshots are rejected before clone/render.
- Existing defaults and key IDs are unchanged. Root will call `validPreference` when loading queued cache entries.

Verification: 8 schema tests passed; full frontend `npm run typecheck` passed after these edits. Heatmap remains frozen with 11 passing component tests and prior production build. Root owns final integrated tests. The final dispositions are recorded below.


## Final disposition — three P1 findings closed

Reviewed final `store.ts`, `store.test.ts`, strict `schema.ts`, and the actual `LearningAccountContextMiddleware`:

| Finding | Verified implementation | Regression evidence | Status |
|---|---|---|---|
| SYNC-REVIEW-01 | `inFlight` tracks sent keys; setting the old server value retains pending reverse intent while that field is in flight. Successful acknowledgement rebases the newer serial and schedules its final write. | `keeps the final System intent when Dark is already in flight` | Closed |
| SYNC-REVIEW-02 | GET snapshots below accepted revision are ignored; late successful PATCH acknowledgements and409 snapshots cannot roll a newer accepted snapshot back. Remaining local intent is compared against the current field revision and conflicts stay explicit. | staleGET/newPATCH; stale200/newGET; newer local intent behind same-field remote edit; stale409/newGET tests | Closed |
| SYNC-REVIEW-03 | Constructor applies seed using `render(false)` without overwriting cache. First `bind()` hydrates validated same-account pending even when identity was seeded, then applies server authority while preserving pending bases. | `preserves an offline queued change across SSR bootstrap and same-account restart` | Closed |

Additional safeguards reviewed: `epoch` rejects previous-account responses even if transport ignores AbortSignal; real HTTP reads and writes send the bound `X-Learning-User-ID`; existing middleware returns409 for a cookie-account mismatch rather than allowing a stale tab to write another account's settings. The final store's `accountChanged()` clears live private labels and pending UI on an auth/affinity rejection while retaining the prior account's separately scoped offline queue. Explicit logout clears the active account cache and visual adapter. Strict `validPreference` now guards queued cache values before rendering.

Independent rerun: `npm test -- shared/preferences/store.test.ts shared/preferences/schema.test.ts` completed with **16 store +8 schema =24 tests passed**,14:36UTC on2026-11-12. Log: `/home/eh/round2-independent-preferences-tests.log`. The cases include debounce/coalescing, offline recovery, both conflict resolutions, account switching/logout, core-question independence, identity headers and reordered200/409 replies. This reviewer found no remaining P1 in the reviewed store/API boundaries. Root's staged real-HTTP cross-device flow, browser QA and final production smoke remain separate required gates; unit tests do not claim physical Safari coverage.

## Final increment — account-owned progress goals

Reviewed only, without editing business source: `tracker/user_preferences.py` and its tests; `frontend/shared/preferences/schema.ts` and tests; `store.ts` cache upgrade; `legacy.ts` / explicit import UI; `PracticeTrendPanel.vue` and tests; generated appearance bootstrap compatibility.

**No P1 found in this increment.** Findings by required gate:

- **Statistics/forecast formulas unchanged.** `drill/practice_trend_views.py` has no change. The panel's existing coverage, mastery, required-rate, prediction and workload computations remain unchanged. Only the existing workload target/deadline inputs move from unowned browser storage to `progress.drill` / `progress.ei`. Drill24, EI11 and2026-11-21 defaults match the former panel; the EI307 plan and dynamic Drill goal denominator are not modified or made writable preference fields.
- **Additive old-cache upgrade preserves pending edits.** Before strict snapshot validation, `readCache()` fills only the two missing progress fields from current defaults. It does not repair missing/corrupt earlier fields. Existing account-scoped pending edits retain their original values/base revisions/serials and pass the existing per-field validation. The regression test removes both progress fields from an old snapshot and proves its offline font edit is sent successfully. Separate corrupt-existing-field tests reject rather than silently salvage unsafe data. No database schema migration is required for these two additive JSON keys; GET defaults do not rewrite existing rows.
- **API isolation/conflicts remain explicit.** Strict goals allow exactly `{target,deadline}`, target must be an actual integer1–500, and the date must be a real Gregorian calendar date. Account identity continues to come from authentication/affinity, with the existing CSRF/session/no-store protections. Each workspace goal is a separate CAS field; stale same-workspace changes conflict atomically, independent EI/Drill edits merge, and another account receives its own defaults/settings. Formula/total override keys are rejected.
- **One local action → one trend load.** Local target/deadline refs update before `store.set()`. The primitive-valued preference watcher therefore sees equality and skips a duplicate request. A remote target/deadline change updates the panel and loads once; equal-value snapshot clones and unrelated accent changes do not fetch. Multi-panel tests prove one call per mounted panel. The existing API helper can additionally coalesce identical in-flight HTTP GETs. Date-range selection remains temporary panel state, outside synchronized goals.
- **Invalid date handling is consistent.** Clearing the date input restores the account date without persisting or fetching. Frontend calendar validation handles leap years without timezone conversion; backend uses `date.fromisoformat` after exact ASCII formatting. Invalid dates, year0000, extra fields and wrong target types are rejected; valid leap years and1/500 boundaries are accepted.
- **Legacy settings require explicit ownership.** The panel neither reads nor deletes `practice.trend.settings.v1/v2.*` automatically. Settings offers explicit import to the currently bound account. The historic v1 deadline2026-11-22→2026-11-21 conversion is preserved, while an existing v2 date is retained. Invalid current v2 data is not replaced silently by older v1 data. Original keys are cleared only by explicit import/dismiss actions; imported values enter the existing optimistic, cached retry/CAS pipeline.

Independent verification completed at15:35UTC on2026-11-12:

- Four frontend files: schema11 + store23 + legacy2 + PracticeTrendPanel15 = **51/51 tests passed**. Log `/home/eh/round2-independent-progress-frontend.log`.
- Four new backend API cases: additive defaults/legacy row preservation, independent-workspace + two-device conflict + account isolation, invalid goal atomic rejection, target/calendar boundaries = **4/4 passed** on an isolated ephemeral SQLite test database. Log `/home/eh/round2-independent-progress-backend.log`.

These are targeted independent checks. Root owns the final full-suite/build results and post-deployment real-account cross-device smoke; this review does not claim those later gates have already run or that physical Safari was available.

## Image-copy multiplier increment — independent read-only review

Reviewed the new shared account field `practice.image_copy_scale` (default1, finite numeric1–8), strict frontend/backend validation and additive cache upgrade, `ImageCopyScaleSetting.vue`, the practice-preference adapter, clipboard PNG builder and QuestionView manual/page-turn/fallback call sites.

- One PNG at1× retains its original Blob bytes without decoding or allocating a canvas. Other exports use the chosen scale; requested upscales have a16×1024×1024 output-pixel budget, plus existing width/height bounds. The budget limits destination canvas allocation, not all source-image decoding memory. Limited-size feedback is exposed rather than claiming an oversized export is the full requested multiplier.
- The existing Safari-sensitive sequence remains: construct ClipboardItem with a pending Blob Promise and invoke clipboard.write synchronously within the originating action, before URLs/media finish loading. Page-turn and manual copies both pass the current account multiplier; share/download fallback uses the same setting. No question-image asset, timer, Note, attempt/submission or statistics behavior is modified by the reviewed diff.
- Presets1/2/3/4× and explicitly saved custom finite values use the existing optimistic account pipeline, shared between Drill/EI. Old valid account caches add only the missing multiplier default and retain pending edits; backend GET defaults do not rewrite old rows. No database migration is required for this additional JSON field.

Two concrete findings were reported and subsequently checked closed:

1. The initial backend called `math.isfinite()` before checking bounds, which raises OverflowError for a valid JSON integer such as10**1000. Root now checks numeric type and range before finiteness, and the API regression case includes that large integer expecting400. Root reports the amended PostgreSQL case passed.
2. The initial async share/download fallback could finish after a question/multiplier change and repopulate the current Blob cache with the previous export. Root now captures UUID, multiplier, URLs and filename; checks current identity after awaiting the build and in error handling; and avoids downloading another question's assets on a stale failure. This matches the manual-copy guard.

Independent focused run: imageClipboard10 + ImageCopyScaleSetting1 + practicePreferences4 + schema12 + store24 = **51/51 tests passed**,2026-11-13 00:02Asia/Shanghai. Log `/home/eh/image-copy-scale-independent.log`. This run preceded the two small guard/order amendments above, which were then read and verified; root owns the final amended full-suite/build and true-PNG browser dimensions. No remaining blocking finding in the reviewed increment. Mock canvas tests do not claim actual PNG byte dimensions or physical Safari clipboard permission success.
