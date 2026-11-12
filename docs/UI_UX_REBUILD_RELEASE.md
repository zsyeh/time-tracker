# Precision Study UI/UX — implementation and release record

Implementation branch: `ui-rebuild/integration`. Baseline: `6b83e2924b9042e75e87bc091ea7f24e0948f8ee`.

The user explicitly authorized implementation, commits and production deployment with rollback on 2026-11-12. The earlier research-only restriction was superseded. The full specification remains [MASTER_UI_UX_REBUILD_PLAN.md](MASTER_UI_UX_REBUILD_PLAN.md); this record maps the delivered work and its actual evidence. The execution ledger is [UI_UX_REBUILD_PROGRESS.md](UI_UX_REBUILD_PROGRESS.md).

## Work allocation and integration

| Owner | Delivered scope |
|---|---|
| Main | Shared neutral tokens/controls, theme bootstrap, appearance migration and persistence, both application shells, navigation, routes/recovery, Django/admin/public theme integration, global CSS integration, production build/release/rollback |
| implement_practice | Controlled diagnosis rows, action toolbar, reader presentation and existing practice preferences; Heatmap/Insight state recovery, filters and responsive layout |
| implement_pages | Both Settings, Practice search/filter/URL state, Timer GlobalSearch; charts, progress, diagnostics, Cockpit, five subject collections and other page styles; real-corpus judgments and independent quality comparison |
| plan_search | Public derived search schema/index/query/normalization/ranking/aliases/suggestions/excerpts, bounded rebuild/queue/verification, private owner-scoped search, migrations and isolated PostgreSQL functional/performance checks |
| plan_review | Independent read-only source and real-bundle browser review; menu focus, recovery, diagnosis density, theme, responsive regressions and search concurrency/rollback review |

Shared files had one integration owner. No worktree reset or replacement of another agent's uncommitted work was used. The previous worktree and its untracked research documents were retained.

## Requirement traceability — delivered implementation

All paths below are relative to the repository. T/UAC identifiers continue to refer to the Master plan. Evidence is retained rather than replacing failed intermediate runs with passing screenshots.

| Requirement | Decision and actual implementation | Tasks / test and acceptance evidence |
|---|---|---|
| R01 | Semantic primary/secondary/plain/icon/menu/selection controls in `frontend/shared/ui` and `shared/design/controls.css`; neutral diagnosis and selection rows; ordinary colored borders removed from actual Question actions and page components | P01/P03/P06/P07; appearance/contrast and action/diagnosis tests; review `final-polish`, core/P07 manifests; UAC03/14/15 |
| R02 | Light white/neutral-gray materials; remove duplicate page containers and card boundaries, retain structural separators and accessible field boundaries | P01/P07; both global styles and page-scoped styles; Light screenshot matrices and actual 20-combination surface measurements; UAC04 |
| R03 | Replace old sidebar marker DOM and rules with shared `navigation/NavigationItem.vue`, SVG icons and whole-row state; remove decorative app credit blocks; business Markdown renderer retained | P02/P07; both App/sidebar sources, auth templates; navigation tests and browser review; UAC02/16 |
| R04 | Shared sidebar 240px desktop / 224px compact desktop, native modal drawer below 900px, workspace switcher, prioritized primary links, small More popover, account footer | P02; `frontend/drill/src/App.vue`, Timer navigation adapter and shared navigation; menu Escape/Tab/roving/rotation tests recorded in review JSON; UAC01/18 |
| R05 | System/Light/Dark via shared appearance resolver, legacy preference migration, synchronous external head bootstrap and durable cookie/localStorage state | P01/P03; `shared/appearance`, `build/appearancePlugin.ts`, both indexes/main, Django templates; unit tests plus actual System/manual/reload checks; UAC07 |
| R06 | Pure neutral backgrounds, sidebar and elevated surfaces; accent variables cannot set neutral surfaces | P01; shared tokens and palette tests; 20 actual Light/Dark×accent combinations measure unchanged neutral page/sidebar/subtle/elevated surfaces; UAC05/06/09 |
| R07 | Ten independent accents including readable Yellow/Lime and scheme-aware Monochrome; primary on-solid and hover/pressed contrast, fixed semantic/status/format tokens | P01/P03; `appearance/palette.ts`, AccentColorPicker, generated static adapter; all palette contrast tests and 20 persisted browser selections; UAC08/09 |
| R08 | Natural SettingsGroup/SettingsRow hierarchy; separate Appearance/Accent and existing practice/admin/security/runtime preferences; no fabricated features | P03; both Settings views, shared row/group/appearance components; settings/preferences/backend permissions tests, Light/Dark screenshots; UAC10 |
| R09 | Compact search/filter/sort toolbar, one advanced Filter panel with mobile sheet, active count/summary, clear and empty states; retain all source/topic/status/collection semantics | P04; PracticeFilterPanel, usePracticeQuery, shared queryState; IME/abort/stale response/URL/pagination/409 tests; UAC11 |
| R10 | PostgreSQL public disposable projection, Han 1/2-grams, normalized text/formulas, identifier/concept/alias and bounded spelling recall, stable ranking/pagination/versioning, suggestions and safe codepoint excerpts; private plaintext never persisted in a new search index | P05; `drill/search`, migrations0036–39, four commands, `tracker/api_views.py`; PostgreSQL tests, real source-verified 41-query fixed comparison, synthetic HTTP/10× reports; UAC12/13. Limitations below are explicit |
| R11 | All eight diagnoses remain one-click controlled checkbox rows, multi/manual primary logic retained; narrow practice pane uses compact two-column layout and sticky in-pane submit bar | P06; DiagnosisSelector/Question/PdfPageStatusPanel; handlers/payload tests and actual full Question two-choice/Note/More browser evidence; UAC14/19/20 |
| R12 | Main mastery action filled, review secondary, utilities plain/menu, dangerous reset labeled; existing Reader actions remain directly accessible | P01/P06; PracticeActionToolbar/ReaderPracticeActions/Question; direct event/zoom/focus and existing record contract tests; UAC15/19 |
| R13 | Quiet metric rows/sections, fewer nested surfaces, page-owned styles extracted from shared global overrides | P07; PracticeTrendPanel, DiagnosticDashboard, Cockpit, SelectedCollectionLayout and page audit manifest; actual screenshots and original chart/grade/selection tests; UAC04/17 |
| R14 | Timer/Attempt/Note/diagnostic payloads, source-indexed navigation, learning states and statistical calculations preserved; semantic colors independent of user accent | P06/P07; original backend regressions and focused frontend workflow tests; review source diff and full Question/Reader checks; UAC19/20 |
| R15 | Responsive drawer/popovers/sheets, min-width0 grids, real 375/390/430/820/1180/1440 screenshot matrix, touch44px and editable16px, visualViewport positioning, safe-area styles; PWA capability marker prevents duplicate floating Timer navigation | P02/P04/P08; core72/P07-96 screenshots, rotation/menu/reader evidence, `deploy/pwa/test_navigation.py` browser/standalone/navigator.standalone tests; UAC18/21. Native hardware caveat below |
| R16 | Shared tokens, typography, button/field/menu/settings/data/loading/empty/focus rules across Timer/Drill/EI and related Django shells; business-specific page geometry retained | P01–P08; both production builds, frontend251 and full backend regression logs, page audit and independent visual review; UAC17/21 |

## Design system decisions

- Neutral surfaces are separate from accent and status roles. Light uses white/#f7f7f7/#f5f5f5; Dark uses #141414/#101010/#1b1b1b/#242424. These are intentionally lower-chroma than the original suggested blue-gray palette.
- Shared typography uses platform Chinese/Latin fallbacks, 24px page titles, 17px section titles, 14px body, 12px captions and tabular statistics/time. Source questions remain readable at 16px where appropriate.
- Primary actions are limited; most secondary actions are neutral or borderless. Native checkbox/select semantics are retained. Focus rings remain visibly accented.
- Appearance is a device/browser preference and uses `learning.ui.visual.v1` plus a non-secret versioned cookie for sibling application hosts. No new server-side user preference schema was necessary. Existing practice setting keys remain compatible.
- No new frontend framework, search service, UI framework or statistics algorithm was introduced.

## Evidence and test interpretation

- [Independent review](uiux-rebuild-implementation/review/README.md) retains the failing intermediate runs, final and final-polish runs, additional Trends/search/20-accent checks and reproducible scripts.
- [Real search judgments](uiux-rebuild-implementation/search-real-qrels.json) contain 41 queries, 142 explicitly source-checked judgments and 39 real public question UUIDs. The same immutable judgments were used before and after fixes.
- [Initial comparison](uiux-rebuild-implementation/search-real-quality.json) and [fixed comparison](uiux-rebuild-implementation/search-real-quality-fixed.json) preserve actual result UUIDs. Legacy MRR0.369 → v2 0.700; known-target Recall@20 0.419 →0.743. These are sparse development judgments, **not exhaustive recall, an independent user holdout, or HTTP latency measurements**.
- Formula regressions found by real data were repaired: both exact real formulas return their expected UUID first. Audited Chinese typos and English aliases work even when the source only has Chinese text. Direct topics rank ahead of ancestor-only matches.
- [Fixed findings](uiux-rebuild-implementation/search-real-findings-fixed.json) distinguish real defects from sparse target samples missing the first page while other correct, unjudged results rank above them.
- Core screenshot matrix:72; P07 page matrix:96; focused practice/history/reader/menus and supplemental cases are separate. Synthetic APIs prevent accidental timer/Note/Attempt writes during browser QA.
- Final actual-metadata HTTP: six queries,180/180 HTTP200, p9559.8–234.9ms under250ms warm target; counts/index versions stable. This is local isolated HTTP, not Internet TLS latency.
- Final SQL-only real-corpus recheck: [82-call results](uiux-rebuild-implementation/search-real-quality-final-sql.json) have identical counts/top24/metrics to the fixed comparison. Final full backend:550 tests OK(11 skips); dedicated PostgreSQL74/74; frontend56 files/251 tests and both production builds pass.
- [Search functional/performance evidence](../tests/search/IMPLEMENTATION_EVIDENCE.md) retains the before/cold/warm reports. Encrypted10k p95423–466ms passes500ms; 93k typo433–527ms remains a disclosed10× load tail risk, while directory172–199ms passes. Cold workers638–680ms are reported separately.
- ESLint is not configured in the repository. Bundle-size and classic PWA-script Vite notices are retained; they are not presented as test failures or silently hidden.

## Data and rollback protection

47 remains the only production writer. 98 remains the HTTPS/share edge. No migration or application service was introduced on the edge or NUC for production traffic.

Verified production backup directory:

`/var/snap/docker/common/time-tracker-ha/backups/ui-rebuild-20261112`

It contains the complete PostgreSQL custom dump, roles, existing image ID, service drop-ins, PWA directory, sensitive settings/key copy, migration baseline and restore evidence. Sensitive contents are not committed or printed. The entire dump was restored into an isolated, resource-limited PostgreSQL instance; counts9281 Question/1324 Attempt/6528 TimeLog/89 migrations and sample image SHA-256 were verified. The isolated instance was removed afterward. A mistaken initial validation table name was corrected transparently; both the intermediate error and final validation are retained.

Application rollback is `deploy/ha/ui-rebuild-rollback.sh BACKUP_DIRECTORY`. It stops the derived-index timer, restores the old image configuration and PWA directory and checks health. It **does not restore the old database over new study records**. Additive search tables can remain while the old application runs; legacy source-delete compatibility was explicitly tested. Derived-only schema reversal was rehearsed separately on an isolated database.

## Remaining limits to communicate

1. Native iOS Safari / physical installed-PWA keyboard, safe-area, background-resume and first-paint behavior cannot be certified by Chromium emulation. Existing native dialog/safe-area infrastructure was retained, and emulated rotation and 44px targets passed.
2. Encrypted private records require request-local decryption to preserve confidentiality. The final 10k encrypted fixture passed the 500ms warm HTTP target (p95 423–466ms) using a conservative request-local prefilter; no persisted private plaintext index or cross-user cache was introduced. Synthetic fixture latency is not a guarantee for every user record distribution.
3. Scanned images without OCR remain searchable through real metadata, not invented full question text. Sparse judgments cannot establish full corpus recall. Short ambiguous Chinese terms such as “波特” can still include literal matches inside other names; explicit “Bode”/“波特图” is more precise.
4. The complete backup is verified on47. Interrupted local transfers have `.incomplete` suffixes and are not restore inputs or claimed offsite backups.

## Release status

Application source: `9df573e4a70cc5cf9f70a9c232c84470c4f2afb7`. The final image was built on47 from the verified retained base (identical requirements.txt), with both prebuilt frontends; no registry dependency or migration was executed by the Docker build. Archive SHA256 `501f9ac1c8e7d5ce32cd93c0a9620172bc5277af44b589a22843ccd031912432`.

Production preflight passed (only existing HSTS include/preload recommendations). Additive migrations0036–0039 applied successfully while the old application remained healthy. Verified backfill and application cutover/smoke are recorded below after execution.
