> **研究工作稿，非独立施工规范。** 本稿保留调研时的候选方案和审计证据。最终路径、尺寸、命名、存储key、Props、迁移顺序和算法以 [Master Plan](../MASTER_UI_UX_REBUILD_PLAN.md) 为唯一施工依据；不得直接从本稿选择不同方案。

# Existing Repository Audit — independent read-only report

Audit date: 2026-11-12. Repository: `/home/eh/precision-study-ui-20261111`; HEAD `6b83e29` (`refine study workspace from design research`). Initial `git status --short` empty. No business code, DB, commit, deployment or production service changed by this agent. This report complements the parent agent's primary Drill/search audit and `production_readonly.json`; all paths below are relative to repository unless absolute.

## 1. Runtime, builds and true application boundaries

- Two independently built Vue applications; NOT three frameworks: Timer uses `frontend/src/main.ts`, `frontend/src/router.ts`, `frontend/src/routes.ts`, `frontend/src/App.vue`, `frontend/src/styles.css`; Drill and EI share `frontend/drill/src/main.ts`, `App.vue`, `styles.css`, runtime workspace selection. `frontend/shared/foregroundTimer.ts` and `learningRecovery.ts` are already shared business infrastructure.
- Resolved lockfile versions: Vue 3.5.41; Vue Router 4.6.4; Element Plus 2.14.4; ECharts 6.1.0; TypeScript 5.9.3; Vite 5.4.21; Vitest 3.2.6; vue-tsc 2.2.12. `package.json` ranges differ, so record resolved versions in Phase 0.
- Timer globally registers selected Element Plus components through `frontend/src/elementComponents.ts`, styles through `elementStyles.ts`; Drill largely uses native controls. Shared neutral components should be native Vue/CSS and imported in both builds, not require migrating Drill to Element Plus or deleting Timer's working EP trees/dialogs/forms.
- `frontend/vite.config.ts`: base `/static/app/`, default output `frontend/dist`; `frontend/vite.drill.config.ts`: root `frontend/drill`, base `/static/drill/`, output `frontend/drill-dist`. Both support staging output environment variables. Shared component imports outside Drill root must be tested in both production builds.
- `frontend/tsconfig.json:17` includes only `src/**`; `tsconfig.drill.json:3` overrides include with `drill/src/**`. Existing imported shared TypeScript enters dependency graph, but NEW standalone shared tests/unimported files can escape typechecking. Plan must add `shared/**/*.ts`, `shared/**/*.vue` and intended test files to both include arrays while avoiding compiling application entrypoints twice.
- Django requirements: `Django>=4.2,<5.0`, DRF `>=3.15,<4`, psycopg `>=3.2,<4`, Python dotenv, django-allauth MFA, cryptography, PyMuPDF. Production observation (parent's read-only JSON) PostgreSQL 15.19; local fallback SQLite (`time_server/settings.py:130–143`). Do not make default SQLite installations unbootable when adding PostgreSQL search.
- API default is SessionAuthentication + IsAuthenticated, page-number pagination 25 (`time_server/settings.py:386–398`). Explicit public shares override permission; do not expose search just because it reads catalog data.

## 2. Existing behavior already solved — retain, do not rebuild

| Feature | Evidence | Preservation condition |
|---|---|---|
| Independent progress page | `frontend/drill/src/views/ProgressView.vue:2–18`; `PracticeView.vue:219`; `main.ts:38`; Django `/progress` fallback | Keep independent route and panel; Practice only lightweight progress link. Do not remigrate or recompute target formulas. |
| Heatmap next unattempted + return state | `HeatmapView.vue:106–232` return key, selection restore after DOM, locate feedback; `:325` button | Preserve filters + source order + highlight-only status filtering + source-index navigation. Review shared tokens without rewriting logic. |
| Exam type stats reduced borders | `components/ExamTypeControls.vue:36–42` already borderless stat rows, semantic text + check | Do not claim existing stats still use old colorful card outlines. Remaining selected background is accent-muted; lower noise further only with explicit contract. |
| EI overlap patch | prior commit `2aa6817`, `EiCockpitView.vue` and shared cockpit grid CSS | Screenshot with long recommendation + mastery text at 390/820/1180 remains regression check; do not reapply old patch blindly. |
| Secondary Drill tools popup | prior commit `2aa6817`, `frontend/drill/src/App.vue`, App test | Preserve discoverability and one-click normal high-frequency items. Shared popover refactor must meet keyboard/focus/boundary behavior. |
| Source selection race guard | five `*SelectedView.vue:25–36` use sequence token, nextTick, selected UUID scroll | Preserve request race suppression and existing URL filters. |
| Timer history URL/return | `HistoryView.vue:78–95` paginated server calls, sessionStorage return + query; restoration below | Do not replace server pagination with all-client lists or collapse multiple sessions. |
| Timer trend future-date correction | `TrendsView.vue:28–35`; `lib/heatmap.ts` historicalHeatmapWindow + tests | Retain historical window anchored to current date; future exam cells must not erase 7D/30D chart. |
| Timer/Question drafts and identity scope | `ActiveSession.vue:23–38`, `SessionDetailView.vue`, shared foregroundTimer; Drill apiIsolation tests | Do not remove user/session-keyed drafts, pagehide persistence, writer ownership or idempotent submissions. |
| Public/private route isolation | `frontend/src/App.vue:96–108`; publicApi uses credentials omit; public route meta | Anonymous share must not load private overview, auth requests, settings or recovery. |
| MathLab optional/lazy | `src/App.vue:12,53–78,112–117`; `MathLabView.vue:15–19` async modules; featureFlags | Keep feature flag, lazy renderer import, formula event dispatch, return focus, renderer fallback. No unrelated engine rewrite. |

## 3. Full Timer surface inventory and exact owner boundaries

| Real file / surface | Current content/behavior | Actual risk / required change | Suggested owner |
|---|---|---|---|
| `frontend/src/views/TodayView.vue` (88 lines) | PageHeader, countdown, private note, progress, subject summary, ActiveSession, HeatmapGrid | `styles.css:309–335` nested panel + dividers + 8px secondary text. Flatten overview while preserving daily hours/coefficients/countdown and exact session controls. | Timer pages owner; shared CSS edits proposed to Design System owner |
| `frontend/src/components/ActiveSession.vue` | Start subject/task, finish draft, tags, efficiency grades A–F, cancel/finish | `styles.css:336–359,791` bordered nested blocks. Button hierarchy with Finish primary, cancellation plain; grade choice is real business semantics, not Drill diagnosis. Draft and 25min/12h completion rules frozen. | Timer pages owner |
| `frontend/src/views/TrendsView.vue` (110 lines) | Range 7/30/60/180, duration/first-start chart, subject stats, recent week/month/tag/task rows | `:37–58` reads CSS variables but fallback purple, 10px chart labels; `:77` watches language/scheme but not NEW accent. Shared chart token reader + accent event/watch required. ResizeObserver/dispose and computation retained. | Statistics owner |
| `frontend/src/views/HistoryView.vue` (221 lines) | `/sessions`, real server pagination, date folders, subject/status filters, display properties, current-page sorting, Markdown drawer, edit | Current sort dropdown correctly says current page (`:189`), do not relabel as global sorting. `:200` clickable article lacks keyboard anchor/button. Search Enter only; read-only UI refactor can make row link with separate review button. Timer history is not Drill Insight and must appear in task map. | Timer history owner |
| `frontend/src/views/IssuesView.vue` (126 lines) | `/issues`, client query/filter/group/display controls, New/Edit/resolved issue form | Native menu UI reused, 10/11px labels via global CSS. Preserve issue types, repeat count, resolution flow; do not send UI query to question API. | Timer pages owner |
| `frontend/src/views/SessionDetailView.vue` | Session article + edit + metadata + ReviewTrend + public share creation/revocation | **Mounting may POST review** (`:64`), so real production visual audit cannot treat GET route viewing as non-mutating. Use synthetic API fixture/test DB. Keep returnTo validation, user draft scoping, share one-time URL behavior. | Timer pages owner |
| `frontend/src/views/SettingsView.vue` | General/runtime, appearance, encryption, Passkeys, export/admin, task presets/tags, invitations, launch capabilities | Preserve all controls and role restrictions; detailed mapping below. Whole page currently headings + nested setting-section cards. | Settings owner |
| `frontend/src/views/PublicShareView.vue:17–42` | anonymous sanitized Session Markdown from `/api/public/shares/:token/`, read-only | Standardize shell only, retain unavailable/expired UX and no account data. CSP blocks inline JS on this route; shared anti-flash bootstrap must be external same-origin or hash authorized (see security). | Shared/public shell owner |
| `frontend/src/views/MathLabView.vue` + `src/math-visualizer/styles/math-lab.css` | Optional full-screen formula visualization modal, 5 modules, adaptive quality | No standalone route. CSS `:17` blur, `:162` 6px glow, `:376/:644/:662` 8px labels; standardize chrome tokens, preserve plotting colors and scientific semantics/renderers. | Low-frequency/UI audit owner |
| `frontend/src/views/KnowledgeView.vue` | Source file exists but absent from `routes.ts` | Do not promise live Knowledge page or introduce a new route just to count it. Retain file unless dependency audit explicitly permits deletion. | Main architect |
| `frontend/src/components/HeatmapGrid.vue`, `ReviewTrend.vue`, `MarkdownPreview.vue` | Timer activity, review trend, sanitized business Markdown/fullscreen reader | Keep intentional horizontal scroll of dense calendar and full-screen reading; distinguish genuine content list markers from UI markers. Theme QA includes code blocks and KaTeX. | Timer/statistics/content owners |

## 4. Settings: real capabilities, no invented controls

`SettingsView.vue:304–430` contains the following groups that MUST survive reorganization:

| Target grouped settings section | Existing implementation | Rules |
|---|---|---|
| Account / Security | `:374–377` Passkey add/manage; `:206–212` auth access; logout currently AppSidebar | Links remain `/accounts/2fa/webauthn/add/`, `/accounts/2fa/`; ordinary user sees personal controls, admin sees admin links only with is_staff/is_superuser. No invented avatar/profile API. |
| Appearance | `:344–357`; `src/lib/uiPreferences.ts`; `SidebarPreferences.vue` | New System/Light/Dark and independent ten Accent choices; retain Language en/zh-CN/ja. Remove old six branded themes and sun/moon switch. |
| General (instance, superuser only) | `:326–342`, runtimeForm; `/api/settings/runtime/`; `tracker/runtime_settings.py:21–27,81–95,168–195` | Fields homepage_content, study_room_code, tracking_start_date, exam_date, countdown_label. This writes allowed dotenv values, NOT a user preference store. Appearance sync must not piggyback here. |
| Privacy | `:361–372`; PUT `/api/settings/data-encryption/` | Toggle intentionally rewrites existing private content with explicit confirmation (`:188–204`). Do not invoke during UI QA; preserve warning and post-change loading. New Accent rows do not share this persistence path. |
| Organization | `:393–408` task preset hierarchy <=4 levels, active/archive behavior, tags | Do not flatten hierarchy or remove archive compatibility to make rows visually simple. Keep dropdown/editor payloads. |
| Invitations | `:410–418`; `/api/invite-codes/` | Ordinary user daily self-service limit; admin multi-use; raw code once only; revocation confirmation. Show as grouped list/detail page without exposing secrets in screenshots. |
| Integrations | `:420+`; `/api/launch-tokens/` | Start URI vs disturbance URI are separate capability secrets; schedule window, max uses, expiry, pause/regenerate/delete preserved. Label values, do not render raw capability URL in list by default. |
| Data | `:380–390` exports and staff admin | Export CSV/JSON/Markdown retained, admin role guarded. Do not add restore/delete account controls absent backend. |

Recommendation: shared appearance/account rows plus Timer-specific settings sections. Drill/EI Settings can expose local appearance/language and actual practice preferences (only existing preferences verified from code), plus a clear link to Timer settings for server account/integrations; DO NOT copy entire SettingsView into Drill and fire Timer runtime/API calls eagerly. If product requires all shared account groups in all apps, extract groups with workspace-aware API wrapper and explicit auth contract rather than file-level reuse with Timer router assumptions.

## 5. Theme conflicts and marker root causes

1. `src/lib/uiPreferences.ts` and `drill/src/lib/uiPreferences.ts` duplicate two-mode `UiScheme = dark|light`, cookie `learning_os_color_scheme`, localStorage `learning-os-color-scheme`, plus language. Default is dark, not system. HTML bootstraps duplicate the same policy.
2. Timer independently has `learning-os-theme`, `data-theme`, six branded themes: `SettingsView.vue:17,47–54,88–91`; `frontend/index.html:18–22`. CSS `src/styles.css:100–104` changes --accent plus variants. Need one-time migration and removal of legacy active selectors; merely adding data-accent will leave selector ordering conflicts.
3. WorkspaceSwitcher has fake YouTube Premium variant (`src/components/navigation/WorkspaceSwitcher.vue:19–20`; CSS `:143–144`) coupled to theme. Remove these brand-specific branches when retiring old themes. Preserve neutral workspace identity.
4. Timer navigation dots are actual fallback DOM `<span class="sidebar-item-marker"/>` in `SidebarItem.vue:24,29`, painted by `src/styles.css:207–208 ::after`; not Markdown renderer and not list-style. Remove marker branch/use consistent real SVG icon OR label alignment. Do not globally disable ul/li markers: user Markdown legitimately uses bullets.
5. Timer sidebar current selection is already borderless row background (`src/styles.css:210`). Retain this property, improve density, icons, safe area. `AppSidebar.vue:32–36` and WorkspaceSwitcher duplicate workspace switch controls; architecture should consolidate once while retaining direct workspace access.
6. Timer fixed sidebar `src/styles.css:118–128` has no safe-area inset, mobile trigger `:823 top:9px`, global `frontend/index.html:5` lacks `viewport-fit=cover` unlike Drill. These are real PWA risks needing specific corrections.
7. Shared chart semantics: `ExamTypeControls.vue:46–49` and ExamTypeBadge currently use --accent for small question type; arbitrary accent switching would change classification semantics. Assign stable `--semantic-question-small/large/short-answer/unknown` tokens instead; keep their text labels. Success/warning and mastery must not derive from Accent.
8. `src/styles.css:115` global focus resets outline to none with focus shadow. Shared new controls need consistent ring, but contrast/inset clipping checked for old Element Plus wrappers and Markdown modal.

## 6. Shared primitive audit

| Existing primitive | Current behavior | Recommendation |
|---|---|---|
| `src/components/layout/PageHeader.vue`, `PageToolbar.vue` | Timer reusable sticky header + toolbar classes | Keep adapter exports/import compatibility, migrate styling to common primitives; Drill page headers currently native separate markup. Shared owner writes component APIs first. |
| `src/components/ui/MenuPopover.vue:5–45` | Inline absolute popup; outside pointer closes, Escape closes; aria-haspopup menu; arbitrary slot contains labels/selects/switches | Cannot treat filters as menu. Build real shared Popover (nonmodal on desktop, modal sheet mobile) with trigger focus restore, collision bounds, optional dialog semantics; Menu uses correct menuitem keyboard navigation separately. Existing `:41 role=menu` with form slot invalid semantics. |
| `src/components/ui/ToolbarChip.vue` | Timer toolbar button | Becomes filter selected condition token/chip only where real removal action exists; not every action chip-shaped. |
| `src/components/navigation/*` | Timer componentized; Drill App is inline | Extract shared layout primitives, keep workspace-specific navigation data and active matching adapters, no route-map blanket union. |
| `drill/components/FullscreenReader.vue`, `ReaderPracticeActions.vue` | mature protected reader, per-mode actions, directional colors, auto-next labels | Keep action event strings and props exact; only chrome/target minimum adjustments with screenshot + interaction tests. `ReaderPracticeActions.vue:30–41` still outline/color blocks; can neutralize surface while retaining icons + aria-pressed. |
| `drill/components/ExamTypeControls.vue`, `ExamTypeBadge.vue`, `ExamTypeEditor.vue` | format filtering, manual edit metadata, stats, type labels | Move selection into filter panel while retaining actual manual edit and small-practice entry. Do not rewrite classifier/metadata table. |
| `drill/components/HeatmapProgress.vue`, `ActivityCalendar.vue` | heatmap stats/progress + grid | Use shared numeric/semantic tokens; keep calendar scale/cell order. |
| `drill/components/MarkdownAnswer.vue`, `OriginalAnswer.vue`, `NoteVisibility.vue`, `SourcePaperViewer.vue`, `PaperQuestionContent.vue` | business rich text/images, answer availability, notes privacy, full source viewer | Preserve content semantics and Markdown; only chrome tokens. Avoid global list/border/overflow reset that affects math/images. |
| `drill/components/LearningSharePanel.vue`, `PdfPageStatusPanel.vue` | share creation/generation feedback; PDF page accounting | Keep permission/data semantics and loading; audit panel nested surfaces. |

## 7. Drill/EI low-frequency pages — complete mapping

All listed files are under `frontend/drill/src/views/`.

| Page | Current route and behavior | Required UI work / preservation |
|---|---|---|
| ActivityView, BookActivityView | `/activity`, `/book-activity`; same `/api/drill/heatmap/activity/`; ActivityCalendar | Neutral title/controls/calendar frames, typography. Preserve fixed activity date window and excluded reset events; no new backend stats. |
| CollectionView | `/favorites`, `/review-later` with different kind; server page; optional next | Compact rows/toolbars, status labels, actual favorite/review semantics. |
| FeelView | `/feel`, `/api/drill/feel/`, last-use recency | Remove decorative book card/chip framing; retain recency score definition. |
| ErrataView | `/errata`, workspace-visible queue | Compact rows, clear pending/handled status; preserve source linkage and handling actions. |
| DiagnosticQueueView | `/diagnostic-queue`, error/queue query, default hidden answer | Plain selection rows, larger labels; preserve diagnostic training default + question return context. |
| PapersView | `/papers`, saved papers list | Remove oversized generation card decoration; keep historical set/order IDs. |
| PaperNewView | `/papers/new`, blueprint selection + create | Blueprint rows, primary generate; preserve blueprint/mode payload. |
| PaperExamView | `/papers/:uuid` | **Mount starts paper via PATCH if needed (`:59–61`); QA fixture required.** Keep exam timing, autosave answers, complete action, question navigation. |
| PaperReviewView | `/papers/:uuid/review` | Neutral review toolbar, per-answer status not large outlines; keep review PATCH and image comparison. |
| PaperView | File remains, legacy `/paper` redirects to `/papers/new`; not imported live | No need to rebuild obsolete standalone local generator. Keep compatible redirect; do not claim live code removed unless imports validated. |
| PdfPageStatusView | `/selected-pdf-pages`; PdfPageStatusPanel | Keep page accounting operation; recovery whitelist currently incomplete (below). |
| EiCockpitView | `/cockpit`, progress/retention/recommendation, A/B/C/D mastery PATCH `/cockpit/topics/:id/` | Preserve solved overlap, compact neutral metric hierarchy + direct grade choice; keep grade/retention behavior, no formula changes. |
| SignalFormulaReviewView | `/signal-formulas?track=signal|four`; recall, core formula review, applications, errors; grade POST | Preserve ordered practice + reveal answer and A/B/C grading, contextual evidence. Reduce card nesting and colored outlines. |
| CircuitSelectedView | `/circuit-selected`, API `/api/drill/circuit-selected/` | Shared SelectedCollection UI adapter; preserve tier,bucket,kind,state,combined,type_group filters and per-page default tier. |
| SignalSelectedView | `/signal-selected`, API equivalent | Same shared adapter; do not change signal collection membership or order. |
| AnalogSelectedView | `/analog-selected`, API equivalent | Same, preserve analog subset and reasons. |
| DigitalSelectedView | `/digital-selected`, API equivalent | Preserve analysis/design/concept kinds and digital policy. |
| CommunicationSelectedView | `/communication-selected`, API equivalent | Preserve priority and cross-selection semantics. |
| NotFoundView | catchall excludes API/auth/static/share on server | Keep recovery/navigation route, no silent redirect to wrong workspace. |

The five selected views duplicate ~120 lines each. At lines 65–74 filters + ExamTypeControls repeat. At lines ~97–115 styles use notice border, group border, per-question 4px border-left and green/yellow entire border plus tinted background. Recommended shared **presentational** `SelectedCollectionLayout`/`CollectionFilters` with adapter data; retain each lib `*Selected.ts` and server API ordering. Preserve compact matrix toggle (40px columns) and labeled mode, don't force card-list conversion for all. Refactor one implementation + fixture compare first, then other four sequential adapters. This is an owner-isolated task once shared components freeze.

## 8. Routes, authentication and PWA compatibility blockers

### New Drill/EI Settings refresh bug to prevent

- `frontend/src/routes.ts:14` Timer `/settings`; no Drill route currently (`drill/src/main.ts:35–65`).
- Django `time_server/urls.py` explicit `path('settings', spa_view, name='spa_settings')` always returns Timer bundle.
- 47 nginx `deploy/ha/nginx-standby-promoted.conf:58–73` strips `/drill` or `/ei` and overwrites Host, so request `/drill/settings` reaches Django as `/settings` on Drill host. Simply adding Vue route is insufficient.
- Implement a host-aware SPA dispatcher for settings: `is_practice_host(request) ? drill_spa_view(request) : spa_view(request)`. `tracker/web_views.py:73–83 root_spa_view` already demonstrates host selection but ALSO returns operations_dashboard for dash host (`:79–80`); choose helper or explicitly test root_spa_view reuse and dash `/settings` expectation. Do not accidentally replace Timer settings with ops dashboard.
- Add `/settings` to `_safe_drill_target` whitelist (`drill/web_views.py:165–169`). `_safe_ip_target:181–185` permits prefixed UI already but must test callbacks preserve next and query.
- Add `(drill|ei)/settings` to `frontend/shared/learningRecovery.ts:12`, and `/settings` to `drill/recovery.py:253`; regression both host mode and IP prefix mode. `runtimePath.ts` routerBase and workspace prefixes stay authoritative.
- Existing `/selected-pdf-pages` has Vue route and login safe target but missing client and server recovery whitelist; include it in explicit route compatibility inventory and restoration tests if requirement says all route restore. Saved `/papers/new` and `/papers/:uuid` also aren't accepted by current recovery regex despite live router routes; do not silently broaden allowed routes without ownership/UUID validation. These gaps should be acknowledged and tested, not presented as newly introduced bugs.
- Unknown Drill paths serve recoverable SPA 404 via explicit catchall, but APIs/auth/static/share excluded (`time_server/urls.py` final regex). Don't broaden catchall to hide backend 404s.

### API / identity invariants

- Both frontend APIs add CSRF cookie token, `credentials:'same-origin'`, `X-Learning-User-ID` (`src/lib/api.ts:10–14`, `drill/lib/api.ts:36–40`). Drill wrapper uses `withWorkspacePrefix`, GET request coalescing and auth mismatch checks. New search cancellation must NOT share a request whose cancellation aborts unrelated consumer; examine wrapper coalescing with AbortSignal.
- Timer publicApi intentionally `credentials:'omit'` (`src/lib/api.ts:34–36`); don't reuse authenticated setting/search wrappers in shares.
- `tracker/web_views.py:49–69` public SPA CSP `script-src 'self'`, so existing inline HTML preference bootstrap is blocked here. New no-flash design should use static external same-origin early script or allowed content hash; do not relax to unsafe-inline. Drill static public share has stricter `default-src none`/no scripts (`drill/web_views.py:107–111`). Share styling via server template, not full private app shell.
- Public learning shares are separate pipeline `drill/learning_shares.py`, `templates/drill/*`, generated/static resource URLs and CSP hashes tested in `drill/test_learning_shares.py:88–89`. Color/typography edits may require deterministic CSS hash regeneration, preserve resource hash/path/access contract.

## 9. Search boundary requiring special care

- Timer `/api/search/` is **not** Drill question search: `tracker/api_views.py:619–717` aggregates completed sessions + issues, `q` bounded 120, limit bounded 24; currently `icontains`, timestamp sorting.
- Encrypted Timer accounts take decrypted Python iteration path (`:643–657,:671–679`) intentionally. Never copy decrypted session/note/issue data into global plaintext question-search index. If new search architecture covers private learning records, it needs explicit per-user privacy/security design, not accidental reuse of public metadata index.
- Timer `GlobalSearch.vue:33–57` already debounce 220ms + request version + LRU 20 entries; missing actual AbortController, cross-account/cache epoch contract and rich relevance. Keep keyboard ⌘K/Ctrl+K (`:107`) and route opening behavior.
- Timer History uses `/api/sessions/?articles=1&has_details=1&search=...&subject=...&status=...&page=...`; filtering/pagination separate from global search. Issues current list client filters; don't wire one generic API that loses established semantics.
- Main search work should explicitly label public question metadata search vs private learning content. Question Attempt/Note persistence and encryption unchanged.

## 10. Test environment truth and commands for future execution

Read-only diagnosis performed: `command -v node npm python3 docker` found Python3 and Docker, no node/npm in this shell. `python3 importlib.util.find_spec` found no django/playwright/psycopg/pytest. Node Docker image `node:22` is present; `docker run --rm --network none node:22 node --version` returned v22.23.4. No tests or builds run by this audit agent.

`frontend/node_modules` is a symlink to `/home/eh/src/time-tracker-ai-share/frontend/node_modules`. Mounting only current repo at `/work` leaves broken absolute symlink. For reproducible implementation, prefer isolated worktree dependencies with `npm ci`, or explicitly mount resolved dependency path and repo path at identical absolute locations. Do not mutate another task's dependency directory. Example READ-ONLY module test environment (Vitest may need writable temp/cache, mount only dedicated cache):

```sh
# After choosing a dedicated branch/worktree and copying a stable lockfile:
docker run --rm --network none \
  -v /home/eh/precision-study-ui-20261111:/work \
  -v /home/eh/src/time-tracker-ai-share/frontend/node_modules:/home/eh/src/time-tracker-ai-share/frontend/node_modules:ro \
  -w /work/frontend node:22 npm test
# Production check in separate build working directory, not mutable shared deps:
# npm run typecheck; npm run build; npm run build:drill
```

Package scripts: `test=vitest run`, `typecheck=vue-tsc --noEmit`, `build=vue-tsc --noEmit && vite build`, `build:drill=vue-tsc --noEmit -p tsconfig.drill.json && vite build --config vite.drill.config.ts`. No ESLint configured; do not fabricate lint result. Existing tests use `// @vitest-environment jsdom` where needed.

Recommended mandatory suites (actual files):

- Shared state/recovery: `frontend/src/lib/foregroundTimer.test.ts`, `learningRecovery.test.ts`; Drill `apiIsolation`, `workspaceScope`, `workspaceNavigation`, `workspaceMedia`, `workspaceReliability`, `runtimePath`, `questionNavigation`, `sourcePractice` tests.
- Reader/record: `FullscreenReader.test.ts`, `ReaderPracticeActions.test.ts`, `OriginalAnswer.test.ts`, `NoteVisibility.test.ts`, `views/QuestionRecord.test.ts`.
- Current UI: `App.test.ts`, `HeatmapView.test.ts`, `InsightView.test.ts`, `PracticeTrendPanel.test.ts`, `ExamTypeEditor.test.ts`, `chartTheme.test.ts`.
- Backend routes/auth/data: `tracker/tests.py`, `drill/tests.py`, `drill/test_recovery.py`, `test_recovery_migration.py`, `test_navigation_targets.py`, `test_navigation_queries.py`, `test_unattempted_navigation.py`, `test_diagnostics.py`, `test_practice_trends.py`, `test_shares.py`, `test_learning_shares.py`, `test_papers.py`, five `test_*_selected.py`, `test_exam_type_edit.py`, `test_asset_delivery.py`.
- PWA: `deploy/pwa/test_navigation.py` requires Python Playwright + Chromium; README explains fixture interception of IP requests, standalone simulation, no production writes. Don't claim it tests actual iPad Safari.
- Timer diagrams/content: `src/lib/markdown.test.ts`, `heatmap.test.ts`, `subjectStats.test.ts`, MathEngine/formulaRouter/numerics/fft tests; don't delete them for UI-only changes.
- Search needs new PostgreSQL integration test lane, not only SQLite ORM tests. Isolated PG database/container and explicit DATABASE_URL; never point manage.py test at live production connection.

## 11. Deployment audit and safe Phase 9 recommendations

- `deploy/ha/README.md:1–15`: 47 is sole writer; 98/RainYun edge proxy only; NUC offline/content clone. Historical HA failover/promotion files retained, must NOT be activated. Never set legacy-ha-explicitly-enabled marker.
- Authoritative runbook **not** generic `deploy/scripts/deploy-native.sh`: native script builds, migrates and restarts `time-tracker-web.service` (`:66–99`), while current production uses Docker systemd image drop-in. Do not run this on 47 blindly.
- Effective image configured `/etc/systemd/system/time-tracker-ha-web.service.d/20-local-ports.conf`; native Docker client `/usr/local/bin/time-tracker-docker` because Snap wrapper stalled, `25-native-client.conf` overrides preparation/stop (`deploy/ha/README.md:48–55`). Keep rollback copy of effective drop-ins/image. Base repo service tag is historical, not deploy truth.
- `deploy/ha/Dockerfile.standby`: Python 3.11, COPY code + prebuilt frontend bundles, collectstatic, Gunicorn loopback18000; healthcheck host Timer admin login. Generic `Dockerfile` builds Node18 + Python3.12 and entrypoint. Future deployment must inspect active image/Dockerfile path and pin artifact provenance; don't silently switch image families.
- PWA assets served separately: `/var/www/time-tracker-pwa/` via `deploy/ha/nginx-pwa.conf:2–10`. Updating image alone does not update navigation.js/manifest. Rollback includes both.
- 47 prefix routing and canonical domains must be checked using both `/drill/settings`, `/ei/settings` and host-specific `/settings`; static assets shared `/static/drill`. 98 share edge asset cache must preserve URL hashes and privacy; UI build deployment shouldn't purge or rewrite question assets.
- Parent summary says 6b83e29 has been deployed; this audit independently confirms local HEAD only, not current live image. Phase0/9 must inspect live current image with docker ps/systemd show and hash served assets; do not infer deployment solely from git.
- Before search migration: full `pg_dump -Fc` plus globals/role/exported migration ledger, encryption key/config protected backup (never print keys), checksum and restore rehearsal on isolated PG15; archive current image/drop-in/nginx/PWA assets. Search tables/indexes additive, app feature flag off until backfill/quality gate. `CREATE INDEX CONCURRENTLY` non-atomic migration, monitor lock duration and invalid indexes. Rollback app flag/image while leaving compatible additive schema; don't restore old full DB over subsequent study records.
- Deployment health must verify real API auth, both SPAs, direct refresh, anonymous share, PWA script and hashed assets. A login redirect proves route reachability, not logged-in UI correctness. Use test account on isolated/staging for stateful smoke; production read-only fixtures for visual.

## 12. Owner locking and integration hazards

Exclusive main/Design-System owner: both global CSS, both main.ts/HTML bootstrap, shared token/preferences/primitive files, both App shells/navigation adapters, routes.py/runtimePath/recovery whitelist, Django settings fallback, root build configs. Module agents may propose CSS aliases but never append global override blocks.

Independent owners after primitive contracts freeze: (a) Timer pages/settings, (b) selected-collection + low-frequency Drill adapters, (c) stats/history/heatmap selected surfaces per existing ownership, (d) search backend + migrations/tests, (e) reader/diagnosis one owner. Reader owner is sole editor of huge QuestionView; merge renderer/button/diagnosis changes atomically to avoid conflicting handler moves.

Search backend may run parallel after API/schema/normalization contract freeze. UI search owner consumes typed fixtures; no backend query mutation by UI agent. A review-only agent checks user identity/cache, encrypted content, recent study records, 403/404 behavior, and no owner files overwritten.

## 13. Evidence limits

This report is source/read-only runtime audit, not a claim that new UI/search tests passed. Actual screenshots available from parent's fixture audit in research directory are synthetic/current compiled app, not production data and not user-uploaded ChatGPT screenshots. Dedicated iPhone/iPad Safari keyboard + PWA resume tests remain required later. Current source route gaps, CSP bootstrap limitation, and two-mode theme differences are explicit evidence; proposed new files/components are proposals and should be marked `(new)` in the Master Plan.
