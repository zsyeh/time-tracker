# Learning OS Round 2 — regression repair and account preferences

## Scope and status

Source baseline0103df5; deployed baseline9df573e. Work is isolated on
`fix/learning-os-round2`; original worktrees and the R01–R16 matrix are preserved.
Core implementation, independent reviews, local tests and production builds are complete.
**Earlier successful production cutover:** core changes999b190,
server-first bootstrap fix15d3c42, followed by heatmap transfer fix2951e54. That earlier verified
image was `time-tracker-ha:20261112-round2-2951e54` (short image ID36aaa65b),
reported healthy by the release owner.31/31 core HTTPS checks and6/6 account-preference
checks pass; the98 edge serves the checked static assets with matching SHA256.

**Final additive release46e9d81 has also completed cutover:** existing
daily workload/deadline settings now join account preferences as `progress.drill` and
`progress.ei`, bringing the known allowlist from14 to16 fields. Final frontend61files/
309tests, backend591tests/12skips, two production builds and PGpreferences34/34 pass.
The release owner confirms deploy-exit0,healthy,OOM=false, successful search queue and
`No planned operations` migration plan. Final image:
`sha256:651d2fd38acc892006f47e9d535a17f032d08e3d7722543ca8344902a62ddc43`.
Its final **31/31 core and7/7 preference checks** passed, including progress-field
conflict/account isolation.98edge's three current assets match SHA256. Final20sample
API measurements are explicitly46e9d81below;2951e54's earlier31/6checks remain history.
Original R01–R16 decisions/matrices are retained; Round2 adds evidence in§32.

No existing learning data, question identity, statistics formula or total target set
was changed. The new progress fields synchronize existing user-editable parameters;
they do not redefine the statistical workload or prediction formula. Physical Safari/
PWA acceptance remains incomplete, so the entire native-device DoD is not claimed done.

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
| SYNC-01 | Additive tracker0022 UserPreferences; session+CSRF GET/PATCH`/api/user-preferences/`.14original account fields: Appearance,10accents,font,language,3sidebars,2saved-filter arrays,shared practice modes and per-workspace copy modes. Deployed46e9d81 adds2workspace progress fields without a database migration;7/7final production preferences checks include goals/conflict/isolation. |
| SYNC-02 | Server-first safe JSON before synchronous appearance bootstrap; private/no-store HTML/auth/API. Optimistic per-field PATCH with base revisions; unrelated fields merge, same-field409 requires explicit resolution. Account-affinity headers block stale-tab writes to another account. Stale GET/200/409 cannot regress accepted revision. |
| SYNC-03 | Account prefs exclude scroll,focus,open dialogs,window collapse,temporary query and runtime environment configuration. Presets are named/explicit,max10 per workspace; all real filter/scope keys preserved, page/index/from omitted. Applying a preset cancels stale input and old return contexts. |
| SYNC-04 | Debounced500ms writes,5/8s request bounds, account-scoped offline retry queue, focus/online/30s refresh. Auth change immediately clears private live UI and retains only the old account's scoped retry cache. Logout clears its cache. Sync never blocks study/timer submission. |

Legacy unowned practice keys require an explicit Settings import/discard choice;
they are never silently assigned to whichever account next logs in. Server settings,
keys and `.env` data remain excluded from preferences. Existing next-mode/auto-next
are shared betweenDrill/EI, while page-turn copy remains workspace-specific.

### Final progress-preference increment

`progress.drill` defaults to`{target:24,deadline:'2026-11-21'}` and`progress.ei` to
`{target:11,deadline:'2026-11-21'}`. These are the existing defaults, not new total
question targets. Each workspace is one atomic conflict field. Only the exact keys
target/deadline are accepted; target must be an integer1–500, deadline an ASCII
YYYY-MM-DD valid Gregorian date.1900/2000 leap-year boundaries, invalid days, booleans,
fractions, extra formula/total fields and trailing whitespace are tested.

Schema_version stays1; reading old rows only merges defaults in the response, without
rewriting them. Old clients' valid field PATCHes retain new stored values. The client
upgrades valid old14-field cache snapshots by adding only the two new defaults; it
does not accept arbitrary incomplete/corrupt snapshots. Device-only old progress
values require explicit import/discard alongside legacy practice settings. Daily
actual workload, deduplicated coverage, target collection and prediction calculations
are unchanged. The integrated UI saves valid edits through the shared account store;
preference sync is independent of question/timer submission.

### Persistence, security and recovery contract

GET returns`{schema_version,revision,values,field_revisions}` without creating a row.
PATCH accepts only`{schema_version:1,changes:{key:value},base_revisions:{key:n}}`, with
identical changed/base key sets. A global CAS makes the JSON merge atomic; per-field
revisions permit unrelated stale-device edits. Same-field conflict returns409 with
typed`current/conflicts`; no part of a failed multi-field request is saved. Resolution
is explicit, never replaying an old entire sidebar silently.

Only the authenticated session selects the owner; no arbitrary user_id is accepted.
PATCH requires CSRF. The bound page sends`X-Learning-User-ID`; if another tab changes
the login cookie, old-page GET/PATCH receives409 instead of reading/writing the newly
logged-in account. Preferences, auth session and private shell responses are no-store.
Django safe JSON is inserted before the external synchronous appearance bootstrap;
cached shell HTML never contains account values. Public/anonymous shells explicitly
inject null, ignoring a prior account's device preferences. Logout clears visual and
legacy cookies on local hosts, subdomains and the apex domain.

Payload/stored JSON is bounded to32KiB; presets are named, explicit and limited to10
perworkspace. Allowed filters include real course/material/tier/kind/combined/state/
scope/bucket fields; transient page/index_version/from/scroll/focus and runtime secrets
are rejected. Last user intent, staleGET/200/409, SSR offline-pending hydration and
cross-account late responses have dedicated regression tests. Account-scoped retry
queues and5/8s request bounds cannot block the independent study/timer API.

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

- Final release frontend: **61files /309tests passed**,12.65s. TypeScript and both
  latest Timer/Drill production builds exit0. No configured ESLint script exists.
  Vite retains existing large chunk warnings; no framework/dependency was added.
  The older`vitest-final.log` is60/297 historical evidence; the latest original
  log is[frontend-final.log](frontend-final.log), not a relabeled older run.
- Full backend: earlier deployed-stage **587tests/12skips** passed; release46e9d81
  **591tests/12skips** passed in159.770s. A skip is not a passing execution. The final
  [backend-final.log](backend-final.log) contains the actual completed591run.
  Final build logs:[Timer](build-timer-final.log),[Drill](build-drill-final.log).
- Dedicated16-field preferences: **PostgreSQL34/34**,5.721s; SQLite33pass/1PG-only
  skip,3.831s. Tests include actual middleware/session affinity, CSRF, two independent
  PGconnections, field conflicts, read-only old-row defaults, cross-device progress
  isolation and invalid calendar dates. TSschema11/11 and standalone strict tsc pass.
- Search/navigation PostgreSQL29/29. Heatmap negotiated compression4/4 onSQLite andPG,
  plus49relatedDrillAPI tests. Independent final increment review reran51frontend and
  4backend tests successfully; these are separate from the full-suite counts.
  `makemigrations --check --dry-run`: no missing migration.
- Chrome/WebKit scripted search/open/next/previous/return/research and Note/diagnosis/
  Reader pass. Latest final bundle evidence under`search-question/final/latest`.
- Real DjangoHTTP + PostgreSQL account sync: two devices/same account + another
  account, offline replay, server-first paint with main modules blocked, saved preset
  roundtrip and sidebarpin/order. Seven viewport/rotation states×fivefont sizes;
  latest WebKit check also asserts editable-font floor. `sync/`.
- Release46e9d81 adds **six real-HTTP WebKit integration groups passed**, including
  progress settings; see`sync/webkit-progress-final.json`. This is staged HTTP/PG,
  not itself proof of production deployment or physical iPadOS first paint.
- Heatmap backend: same9281-question public fixture,2warmups+10samples, five scopes,
  complete JSON byte/hash equal and same6/7SQL; no backend regression or N+1 found.
  Fixture has zero learning history; do not generalize that to heavy-history users.
- Local real-corpus HTTP search-context detail P50/P95 **1133/1146→72/78ms**,
  3warmups+30samples. Cold broad-search spikes remain recorded rather than discarded.
- Before deployment, authenticated production HTTPS GET-only benchmark, one client,
  2warmups+20samples (no frontend timing writes):

| Operation | Before9df573e P50/P95 ms | Final46e9d81 P50/P95 ms |
|---|---:|---|
| Drill search导数 |187.32/412.08|181.63/315.70|
| EI searchFourier |221.55/582.57|203.13/357.24|
| Bare question |86.71/122.21|86.28/156.56|
| Search-context question |4473.43/6670.78|93.82/112.65|
| Next question |91.97/142.21|109.94/288.54|
| Previous question |85.17/123.33|104.55/133.63|
| Selected heatmap |779.91/964.64|847.43/975.04|
| EI core heatmap |428.39/642.76|437.50/624.00|

Complete samples/statuses remain in[production-before.json](production-before.json)
and[performance-after.json](performance-after.json), whose revision is46e9d81.
Next/previousAPI, bare-questionP95 and selected-heatmap latency are worse in this final
sample; EIheatmapP50 is slightly worse while P95 is lower. Those broad performance
targets are **partially met, not all passed**. Earlier2951e54search139.96/148.24ms is
not substituted for final181.63/315.70ms. This GET-only measurement is separate from the
gzip browser transfer benchmark below and is not its encoded-body measurement.

API timings are different from browser usable/paint timings. Browser functional
fixtures use controlled API delays and no real scan assets; they are not production
image-paint benchmarks. WebKit lacks a supported longtask observer; report that as
unavailable, never as proof of zero long tasks.

### Actual production browser and scan images

Additional real-HTTPS browser sampling used one dedicated temporary synthetic account,
the same routes/assets, Chromium820×1180 and3samples perworkflow. First/search/heatmap
used fresh contexts; next/previous retained normal prefetch and cache. Before and after
9/9flows passed; real scan images had`complete && naturalWidth>0` and completed decode.
This evidence is not the synthetic160msAPI fixture and not a physical iPad.

| Workflow | UI usable median before→after ms | First real image decode before→after ms |
|---|---:|---:|
| First question |936→968|1316→997|
| Search list |1380→1484|—|
| Search result click |7139→206|7292→950|
| Next, normal prefetch |68→53|70→363|
| Previous, normal cache |50→55|51→57|
| Selected heatmap, first rollout |1304→1950|—|

Search-click blocking was removed and duplicate detailGETs fell2→1. **Next image
decode regressed70→363ms**, while the next UI improved. First-page UI and search-list
time also did not universally improve. All raw slow samples remain.3samples do not
establish a stable productionP95; nearest-rankP95 there is just the maximum.

CDP includes requests for neighboring/answer preloads, so bytes are not one image's
payload. Zero new requests after a next action can mean prefetch already started,
not a zero-byte image. Unfinished adjacent fetches remain null. Chrome long-task
observations are kept distinct from network wait. Full data/limitations:
[production browser results](search-question/final/production/README.md).

Opening production questions can create the synthetic account's own timing records;
this browser phase is **not** labeled GET-only. NoAttempt/Note was submitted. The
[cleanup record](synthetic-cleanup.json) confirms0newAttempts, deletion of the temporary
account and its3synthetic timing rows; real users' records were not cleaned up.

### Heatmap cold-load regression and gzip closure

The initial1304→1950ms cold heatmap regression is retained, not hidden by the local
rendering benchmark. A further5coldcontexts showed307KB uncompressed JSON and median
451ms body transfer, while response-complete→cell-insert was24ms and layout126ms.
No speculative SQL/index rewrite was made.2951e54 adds standard Django4.2 per-view
`gzip_page`, preserving decodedJSON, query/statistics/permission semantics and
non-negotiating clients. No Nginx reconfiguration or blanket private-page compression.

| Median metric | Diagnostic before gzip,5samples | After gzip,5samples |
|---|---:|---:|
| Selector usable |1403.3ms|803.6ms|
| First-cell RAF candidate |1209.2ms|765.4ms|
| Body transfer |450.6ms|16.8ms|
| Time to headers |117.5ms|167.4ms|
| API complete→cell insertion |24.1ms|22.8ms|
| Insertion→RAF/layout |125.9ms|125.4ms|
| Complete API resource |569.4ms|179.7ms|
| Encoded body |307254B|44184B|

Encoded body drops85.6%; every decoded body remains307254B. Finalselector samples
809/727/804/911/801ms improve the original before median1304ms. TTFB118→167ms did
not improve; the gain is transfer, not a claim of faster SQL. Verified HTTPS headers
include gzip and`Vary: Accept, Accept-Encoding, Cookie`. The first independent header
probe omitted its session and correctly403ed; the corrected request returned200,
and the failure remains documented. Before3/after3/diagnostic5/final5 are retained.

[Final compressed transfer evidence](search-question/final/production/heatmap-gzip-result.md)
and[framework/security review](heatmap/TRANSFER_COMPRESSION_REVIEW.md) describe the
negotiation, deferred DRF rendering, random padding and decoded-byte parity tests.
Five samples and a RAF candidate are not a stable P95 or physical screen-composition
guarantee. ExistingBrowsableAPIHTML is not falsely described as token-free.

## Migration and rollback

Only `tracker/migrations/0022_userpreferences.py`: one new user-owned table; no
alteration/backfill of Question,Attempt,Note,state,timer or aggregate tables. It is
compatible with the retained9df573e application. Normal rollback leaves the new table
and newer learning records intact.

Full production archive is retained privately on47 under
`/var/snap/docker/common/time-tracker-ha/backups/round2-20261112/`, alongside the
previous image ID, web drop-ins, PWA and previous search-queue units/state. Full
backup material remains private, not copied into the screenshot/report directory.
For46e9d81, `/var/snap/docker/common/time-tracker-ha/backups/round2-goals-20261112/`
retains2951e54 as the rollback application, reuses the full database archive via
symlink, and adds a fresh current UserPreferences dump checked by pg_restore/read.
It is not falsely described as a second newly captured full database archive.

A second snapshot excluding image blobs and their two linking tables was actually
restored to an isolated PostgreSQL database. Forward0022 and reverse0021 leave the
counts and complete-row digests of ten existing tables identical, including9281
questions,1347attempts,1379states,887timing sessions and6528timelogs. Evidence:
`migration-real-data-verification.json`. This is explicitly **not** a full image
restore. The full image-inclusive archive remains the disaster-recovery backup.

Application rollback:

```sh
# Run on root@47.95.10.128: restore the immediately previous healthy2951e54 app.
sh /var/snap/docker/common/time-tracker-ha/releases/round2-46e9d81/deploy/ha/round2-rollback.sh \
 /var/snap/docker/common/time-tracker-ha/backups/round2-goals-20261112
```

It restores web image/config, PWA and prior queue units/enabled/active state. It never
restores a stale database over newer study records. A full database disaster restore
requires stopping all writers, first backing up the current database, restoring to
an isolated database, verifying identities/counts, and changing the database selector
only after review. Do not run a production reverse migration just to roll back UI.

### Actual automatic rollback incident

The first15d3c42cutover reached Dockerhealthy, but the private deployment script also
probed`https://47.95.10.128/healthz`. That route does not exist and returned404. The
failure trap automatically restored9df573e, the retained image startingeaec8c27.
No reverse migration or old database restore occurred. The release owner changed the
extra probe to the actual`/accounts/login/`HTTP200 endpoint and successfully retried
the same image. Private backup directory`round2-20261112`contains
`automatic-rollback.log`and retry logs. No public sanitized log or recovery duration
is invented here. This exercises application rollback, not full database disaster
recovery.46e9d81now uses the separately retained2951e54application rollback target.

### Release record and production evidence

| Commit | Purpose | Confirmed release status |
|---|---|---|
|999b190|Core regression repairs and account preferences|Included in deployed successor|
|15d3c42|Apply account preferences before Timer/public render|Retry succeeded after the404probe correction|
|2951e54|Negotiate heatmap JSON compression|Healthy;31core+6prefs checks; edge3asset hashes; actual gzip5case follow-up|
|46e9d81|16-field progress preferences, cache upgrade, explicit legacy import|Healthy,OOM=false,deploy-exit0,no migration operations,queue success;31core/7prefs pass;98edge3assets match; final20sample API retained|

[Core production smoke](production-smoke.json) covers Timer/Drill/EI deep links,
Settings/Progress, both static bundles/bootstrap,PWAnavigation, catalog/search/
suggestions, trends/diagnostics,auth/recovery. [Preferences smoke](preferences-smoke.json)
covers two-session field merge, same-field409, sidebar/filter roundtrip, account
isolation/affinity, three private server-first shells, logout and progress-goal
conflict/isolation. [Release verification](release-verification.json) records the
final healthy/exit0/queue result. Temporary account
cleanup runs in finally. [Edge verification](edge-static-verification.json) checks
threeDrill assets served by98against SHA256. None is a claim that every share URL,
all native devices or every application page received a separate production test.

## Acceptance ledger

A checked item refers only to the stated evidence, not unperformed native-device QA.

- [x] Long text no longer collapses to a single-character column (8layouts).
- [x] Search results reliably open the correct question (both engines/workspaces).
- [x] Measured search-context blocking fixed (localreal HTTP andSQL).
- [ ] Original requirement: question loading recovers or beats the pre-rebuild baseline
  across the required paths. **Partially met:** search-context and first real image improve,
  but nextAPI/next-image samples and first UI are not universally faster. No complete
  performance pass is asserted; see the full comparison and source audit above.
- [x] Heatmap browser load/scroll improves; backend aggregation/query semantics remain
  unchanged. Later transfer-only gzip is separately measured and tested.
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
- [x] Final production release46e9d81: cutoverhealthy,31authenticated checks and7prefs
  checks passed;98edge3assets match. Functional deployment acceptance is separate
  from the explicitly partial performance outcomes above.

## Remaining coverage limits

No user screenshot/recording was accessible in the message. UI screenshot evidence
uses synthetic content. Actual production scan-image loading was measured separately
in sanitized Chrome JSON as described above. iPad hardware, Safari browser chrome,
native software keyboard, real safe-area insets, physical PWA lifecycle and on-device
cold-image painting remain unverified. No false completion is asserted for those items.

Screenshot delivery is authorized to `eh@20.222.88.115`, private directory
`/home/eh/learning-os-round2-screenshots/`. It contains only synthetic screenshots,
never production database backups or credentials.

## File/evidence map and final handoff

The full archived change inventory is[CHANGED_FILES.txt](CHANGED_FILES.txt); refresh it
after the final commit rather than claiming an older inventory includes later files.
The implementation centers on:

| Area | Real files / evidence |
|---|---|
| Account model/API | `tracker/models.py`,`tracker/user_preferences.py`,`tracker/migrations/0022_userpreferences.py`,`tracker/test_user_preferences.py` |
| Server-first identity | `tracker/preference_bootstrap.py`,`tracker/templatetags/learning_preferences.py`,`tracker/learning_context.py`,`tracker/api_views.py`,`tracker/web_views.py`,`drill/web_views.py`,auth/public/admin templates |
| Shared schema/store/theme | `frontend/shared/preferences/{schema,store,bootstrap}.ts`,`frontend/shared/appearance/`,sharedSidebar/settings widgets |
| Timer settings | `frontend/src/views/SettingsView.vue`and its test;[before/after evidence](settings/README.md) |
| Practice/Question | `frontend/drill/src/views/{PracticeView,QuestionView}.vue`,query/navigation/cache helpers;[module report](search-question/README.md) |
| Heatmap | `frontend/drill/src/views/HeatmapView.vue`,`drill/views.py`,`drill/test_heatmap_transfer.py`;[historical+performance report](heatmap/README.md) |
| Progress sync | `frontend/drill/src/components/PracticeTrendPanel.vue`,sharedschema/store,backenduser_preferences and their tests |
| Rollback | `deploy/ha/round2-rollback.sh`;private production backup material stays outsideGit |

Useful visual pairs: [old1180Settings](settings/before/shortcuts-light-1180.png)→
[final1180Settings](settings/after-final/shortcuts-light-1180.png),
[dark390syntheticURI](settings/after-final/synthetic-uri-dark-390.png),
[before9281matrix](heatmap/evidence/before-0103df5-9281-1180.png)→
[restored9281matrix](heatmap/evidence/restored-round2-9281-1180.png),
[selected diagnosis](search-question/final/latest/reader-webkit/question-diagnosis-selected-1180x820.png),
[Note/More](search-question/final/latest/reader-webkit/question-note-more-1180x820.png),
[390Reader](search-question/final/latest/reader-webkit/question-reader-390x844.png).
Each result applies to its recorded bundle/fixture; later changes need a risk-based
rerun, not renaming old screenshots. NativeSafari/PWA entries stay open.

At this document freeze,46e9d81is deployed healthy and final31core/7prefs/20sampleAPI
results are recorded. The actual latest logs are archived as
`backend-final.log`,`frontend-final.log`,`build-timer-final.log`,`build-drill-final.log`,
and final progress-field validation. RawAPIafter now correctly identifies46e9d81;
the2951e54gzip/browser evidence remains separately dated rather than relabeled.
The already completed
local final gate is591backend/12skips,61frontendfiles/309tests,PGpreferences34/34,
bothbuildsexit0 and6real-HTTPWebKit integration groups. Independent incremental review
passed51frontend/4backend. This reports implementation/release progress honestly
while keeping physical device acceptance and measured regressions visible.


## Release artifact integrity and latest regression

Full baseline-to-delivery file list: [CHANGED_FILES.txt](CHANGED_FILES.txt). It includes
source, regression tests, migration, rollback script and sanitized evidence, excluding
ignored build directories. Built artifacts are included in the deployed immutable image.
The release archive SHA256 is `0b16689aa82f28d0d23e59e5383d40b89b745b515d68b1996e8b1b63fd3db920`;
Drill index SHA256 is `53bb4b0bd76938cc2344e6c89546d43f78363374c96fecfa421d4cff399829bd`.

The original full database dump is2,931,709,569bytes, SHA256
`592459bd2d5aaf2dd7d478594a4fe708b5bc770efd29d22fcf2f48b530ed891d`;
its complete archive can be read by pg_restore (exit0). The separate actual-data
migration roundtrip is explicitly the subset restore described above. Deployment
backup directories are private on47; no backup/credential was uploaded to20.

Most recent exact-bundle WebKit search/Reader regression:
[46e9d81/README.md](search-question/final/latest/46e9d81/README.md).
It passes both workspaces' search/next/previous/return loops and diagnosis/Note/Reader
rotation with no JSerror, overlap or overflow; all67build files remain hash-identical
before/after the run. [Next-image source audit](search-question/final/latest/46e9d81/next-image-source-audit.md)
finds no changed image queue/prefetch policy, without dismissing the measured uncertainty.
Earlier295API samples remain in[performance-after-2951e54.json](performance-after-2951e54.json).

Screenshots on20also include final-sync/progress-account-goal.png and 375/1180 settings;
these use synthetic accounts/data. Production46code is pushed on `fix/learning-os-round2`;
subsequent documentation commits do not require replacing the already verified image.


Operational limit: the47root volume remains96%used, with1,792,348,160bytes free at
the final check. Images and rollback/backup archives have been retained; no unrelated
backup was pruned to make the release appear clean. Future builds and PostgreSQL WAL
need disk monitoring and a separate retention/export plan before additional growth.

Independent final review checked every Round2ID, final evidence numbers, original
Master prefix, local links and actual remote rollback files. It found no remaining
release-document blocker after the concrete rollback command and UTF-8 file list
were corrected. This review does not close the performance/hardware gaps above.
