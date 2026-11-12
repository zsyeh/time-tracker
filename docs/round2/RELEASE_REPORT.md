# Learning OS Round 2 — regression repair and account preferences

## Scope and status

Source baseline0103df5; deployed baseline9df573e. Work is isolated on
`fix/learning-os-round2`; original worktrees and the R01–R16 matrix are preserved.
Implementation, independent reviews, local tests and production builds are complete.
Production cutover is **pending** backup validation and deployment health checks.
No existing learning data, question identity, statistics formula or target was changed.

## Changes

| Requirement | Implementation / evidence |
|---|---|
| BUG-01 | Timer capability row uses a real minmax content column and separate action row; long URI/code wrap without squeezing the title. Final structural screenshots8/8,390/820/1180/1440, Light/Dark. Title at1180:45.7→585.6px. `settings/README.md`. |
| BUG-02 | Valid UUID detail ignores pagination generation pins while list pagination keeps protection. Search-context neighbor lookup uses a scoped1:1 projection join; list candidates materialize once. Route-owned input timers cannot rewrite a question destination. `search-question/README.md`. |
| BUG-03 | Canonical detail request keys share prefetch with ordinary entry, reducing clicked-detail GETs2→1. List cache restores page/filter/scroll immediately then revalidates. No image/timer/Note/Attempt semantics removed. |
| BUG-04 | Immutable shallow heatmap snapshots, per-cell memo and redundant DOM removal. Synthetic9281 matrix first render1210→817ms, cell DOM23446→9281, selection328→122ms, filter414→199ms. Full details and historical comparison in`heatmap/README.md`. |
| BUG-05 | Settings categories render independent panels; no unreliable smooth scrolling to the wrong container. Query and old hash links remain compatible; form nodes/drafts remain mounted. |
| BUG-06 | Drill question navigation button now occupies the existing toolbar slot. Timer navigation occupies PageHeader flow instead of a competing fixed overlay. Final WebKit8cases/16rotations and Reader check have no button overlap. |
| BUG-07 | Shared configurable navigation: pin/More, touch44px up/down order, group collapse, reset; workspace/home/account/settings remain accessible. Window collapse stays in account-scoped sessionStorage. |
| BUG-08 | Restore actual pre-rebuild6b83e29 geometry/book grouping/status/overview, retaining quick filters, next locator, source-indexed navigation, cache/restoration and performance repairs. No invented historical design. |
| BUG-09 | Account font90/95/100/105/110%, recommended default95. Build-time PostCSS applies a font token to legacy typography, leaving image/canvas/hit-target geometry intact. Coarse editable text stays≥16px to avoid Safari focus zoom. |
| SYNC-01 | Additive tracker0022 UserPreferences; session+CSRF GET/PATCH`/api/user-preferences/`,14validated account keys. Appearance,10accents,font,language,3sidebars,2saved-filter arrays,shared practice modes and per-workspace copy modes. |
| SYNC-02 | Server-first safe JSON before synchronous appearance bootstrap; private/no-store HTML/auth/API. Optimistic per-field PATCH with base revisions; unrelated fields merge, same-field409 requires explicit resolution. Account-affinity headers block stale-tab writes to another account. Stale GET/200/409 cannot regress accepted revision. |
| SYNC-03 | Account prefs exclude scroll,focus,open dialogs,window collapse,temporary query and runtime environment configuration. Presets are named/explicit,max10 per workspace; all real filter/scope keys preserved, page/index/from omitted. Applying a preset cancels stale input and old return contexts. |
| SYNC-04 | Debounced500ms writes,5/8s request bounds, account-scoped offline retry queue, focus/online/30s refresh. Auth change immediately clears private live UI and retains only the old account's scoped retry cache. Logout clears its cache. Sync never blocks study/timer submission. |

Legacy unowned practice keys require an explicit Settings import/discard choice;
they are never silently assigned to whichever account next logs in. Server settings,
keys and `.env` data remain excluded from preferences. Existing next-mode/auto-next
are shared betweenDrill/EI, while page-turn copy remains workspace-specific.

## Independent work and integration

- Search/Question agent: root-cause SQL/browser investigations, navigation/cache fixes,
  preference deferred-response tests, original-test compatibility, Chrome/WebKit flows
  and Reader regression.
- Heatmap agent: historical source visual restoration, component/performance tests,
  read-only old/current backend SQL comparison, independent preference review.
- Backend/Settings agent: UserPreferences model/API/migration, PostgreSQL/SQLite
  concurrency/security/migration tests, Settings panel/URI repair and screenshots.
- Main: shared ownership, account bootstrap/store, navigation/customization/font,
  named filter presets, API/SPA integration, full gates, backups and release.

## Tests and performance evidence

- Full frontend: **60files /297tests passed**. TypeScript and Timer/Drill production
  builds passed. No configured ESLint script exists. Vite retains existing large
  chunk warnings; no framework/dependency added to production.
- Full backend final: **583tests run,12environment skips, no failures**.
- Dedicated preferences: PostgreSQL30/30; SQLite29pass/1PG-only skip. Search/navigation
  PostgreSQL29/29. `makemigrations --check --dry-run`: no missing migration.
- Chrome/WebKit scripted search/open/next/previous/return/research and Note/diagnosis/
  Reader pass. Latest final bundle evidence under`search-question/final/latest`.
- Real DjangoHTTP + PostgreSQL account sync: two devices/same account + another
  account, offline replay, server-first paint with main modules blocked, saved preset
  roundtrip and sidebarpin/order. Seven viewport/rotation states×fivefont sizes;
  latest WebKit check also asserts editable-font floor. `sync/`.
- Heatmap backend: same9281-question public fixture,2warmups+10samples, five scopes,
  complete JSON byte/hash equal and same6/7SQL; no backend regression or N+1 found.
  Fixture has zero learning history; do not generalize that to heavy-history users.
- Local real-corpus HTTP search-context detail P50/P95 **1133/1146→72/78ms**,
  3warmups+30samples. Cold broad-search spikes remain recorded rather than discarded.
- Before deployment, authenticated production HTTPS GET-only benchmark, one client,
  2warmups+20samples (no frontend timing writes):

| Operation | Before P50/P95 ms | After |
|---|---:|---|
| Drill search导数 |187/412|pending|
| EI searchFourier |222/583|pending|
| Bare question |87/122|pending|
| Search-context question |4473/6671|pending|
| Next question |92/142|pending|
| Previous question |85/123|pending|
| Selected heatmap |780/965|pending|
| EI core heatmap |428/643|pending|

API timings are different from browser usable/paint timings. Browser functional
fixtures use controlled API delays and no real scan assets; they are not production
image-paint benchmarks. WebKit lacks a supported longtask observer; report that as
unavailable, never as proof of zero long tasks.

## Migration and rollback

Only `tracker/migrations/0022_userpreferences.py`: one new user-owned table; no
alteration/backfill of Question,Attempt,Note,state,timer or aggregate tables. It is
compatible with the retained9df573e application. Normal rollback leaves the new table
and newer learning records intact.

Fresh full production archive is retained privately on47 under
`/var/snap/docker/common/time-tracker-ha/backups/round2-20261112/`, alongside the
previous image ID, web drop-ins, PWA and previous search-queue units/state. Full
archive verification and final release identifiers are recorded after validation.

A second snapshot excluding image blobs and their two linking tables was actually
restored to an isolated PostgreSQL database. Forward0022 and reverse0021 leave the
counts and complete-row digests of ten existing tables identical, including9281
questions,1347attempts,1379states,887timing sessions and6528timelogs. Evidence:
`migration-real-data-verification.json`. This is explicitly **not** a full image
restore. The full image-inclusive archive remains the disaster-recovery backup.

Application rollback:

```sh
sh /path/to/release/deploy/ha/round2-rollback.sh \
 /var/snap/docker/common/time-tracker-ha/backups/round2-20261112
```

It restores web image/config, PWA and prior queue units/enabled/active state. It never
restores a stale database over newer study records. A full database disaster restore
requires stopping all writers, first backing up the current database, restoring to
an isolated database, verifying identities/counts, and changing the database selector
only after review. Do not run a production reverse migration just to roll back UI.

## Acceptance ledger

A checked item refers only to the stated evidence, not unperformed native-device QA.

- [x] Long text no longer collapses to a single-character column (8layouts).
- [x] Search results reliably open the correct question (both engines/workspaces).
- [x] Measured search-context blocking fixed (localreal HTTP andSQL).
- [x] Local question API improves versus baseline; navigation path keeps one GET.
- [x] Heatmap browser load/scroll improves; backend unchanged.
- [x] Historical visual source restored and compared to6b83e29.
- [x] Settings categories show the intended independent panel.
- [x] Collapsed sidebar/menu/return controls do not overlap in tested layouts.
- [x] Sidebar pin,More,order,groups and reset implemented.
- [x] Five font sizes preview instantly; touch/image geometry retained.
- [x] Account appearance/accent stored by server and observed on another client.
- [x] Account font observed on another client.
- [x] Account sidebar observed on another client.
- [x] Explicitly saved filter presets survive server roundtrip and reapplication.
- [x] Account/CSRF/affinity tests prevent cross-account writes and stale responses.
- [ ] Physical PWA quit/relaunch and Safari native first-paint verification; browser
  fresh-context/server bootstrap and unit cache restart pass, but not equivalent.
- [x] Offline/retry/timeout behavior keeps loaded core UI usable in automated tests.
- [ ] Physical iPadOS landscape/portrait and desktop comparison on user hardware;
  Linux Chrome/WebKit viewport/rotation checks passed.
- [x] Additive migration preserves restored actual learning rows and digests.
- [ ] Production cutover and authenticated access checks (pending).

## Remaining coverage limits

No user screenshot/recording was accessible in the message. All screenshot evidence
uses synthetic content. Actual iPad hardware, Safari browser chrome, native software
keyboard, real safe-area insets, physical PWA lifecycle and cold scan-image painting
remain to be confirmed on device. No false completion is asserted for those items.

Screenshot delivery is authorized to `eh@20.222.88.115`, private directory
`/home/eh/learning-os-round2-screenshots/`. It contains only synthetic screenshots,
never production database backups or credentials.
