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
