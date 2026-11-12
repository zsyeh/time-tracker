# P07 statistics and remaining pages

Scope: R01/R02/R03/R06/R12/R13/R14/R15/R16. Presentation changes preserve existing request handlers, collection definitions, statistics and learning records.

## Changes and protected behavior

| Page/component | Actual change | Protected behavior / evidence |
| --- | --- | --- |
| ProgressView / PracticeTrendPanel | Single goal heading, neutral aligned metric rows, neutral active range controls; axes 12px/tooltip 14px; visible data table disclosure; visual-preference event redraw | Existing dynamic goal, type breakdown, daily workload vs net coverage, forecasts/deadlines unchanged; existing tests plus appearance/data-table regression |
| DiagnosticDashboardView | Neutral data sections, semantic success for accuracy; accent/dashed second series, neutral submission comparison; readable axes/tooltip; accessible data tables | Existing dailyRate/percentages, range selection, queue routes and all API fields retained |
| EiCockpitView | Scoped neutral surfaces; 12px metadata/14px content/28px metrics; container-responsive topic rows; neutral A/B/C/D selected background; explicit due label | Existing grades and PATCH payload remain; recommendation text and all requirement/evidence fields visible; one-click save regression test |
| Circuit/Signal/Analog/Digital/CommunicationSelectedView | One SelectedCollectionLayout replaces five cloned CSS systems; compact filter disclosure and source notice; colored side borders replaced by state dot/text; label and matrix modes remain | All five selection libraries, tier/bucket/kind/state/combined/type group, question ordering/start logic unchanged; five parameterized route/mode regressions |
| Timer TrendsView | Shared chart visual tokens and appearance listener; removes purple fallback/tiny axes/area wash; data-table disclosure; rotation/viewport resize and cleanup | Same historicalHeatmapWindow and underlying statistics; regression verifies future dates excluded, original series preserved and theme redraw without refetch |
| Timer TodayView | Page-exclusive rules moved to scoped stylesheet; 12px metadata, larger readable numbers, neutral overview and natural data rows | Existing timers, goals, session actions and subject calculations unchanged |
| Timer HistoryView / IssuesView | Page-owned typography and row styles scoped; metadata at least 12px; touch actions stay reachable; resolved items remain readable | Existing server filters/pagination, issue resolution/delete and session review flows unchanged |
| Timer SessionDetailView / PublicShareView | Scoped typography, neutral article/context materials, wrapping properties, safe-area padding | Markdown remains rendered by original component; secret-link behavior, authorization and review POST unchanged |
| Drill Activity/BookActivity/ActivityCalendar/Feel | Scoped rules; quiet section boundaries and readable summaries; fixed neutral future cells | Existing calendar ranges, intensity levels, relative recency and routes unchanged |
| CollectionView / ErrataView / DiagnosticQueueView | Readable compact rows and metadata; removes decorative outer boxes and fixed yellow text | Original favorite/review-later distinction, attempt marks, queue membership and erratum history retained |
| PapersView / PaperNewView / PaperExamView / PaperReviewView | Scoped page styles; neutral blueprint selection; readable numbered position controls and safe-area footer; removes nested review shells | Original generation/start/completion/answer saves and item ordering untouched; selection adds aria state only |
| PaperQuestionContent | Scoped 16px question text and original white source image material | Asset URLs, sizing/loading and source text unchanged |
| PdfPageStatusView / PdfPageStatusPanel | Removes hardcoded light-only palette and color outlines; neutral form sections, semantic action hierarchy; reuses DiagnosisSelector | Existing page fingerprint/UUID matching, preview/apply, primary diagnosis selection, note append and save semantics unchanged |
| SignalFormulaReviewView | Neutral switches, no colored outlines or stacked section cards; 44px action controls | Existing recall/reveal/grade handlers and cycles retained |
| NotFoundView | Neutral simple page/actions | Retry/back/fallback routes retained |
| KnowledgeView / MathLabView / old PaperView | Non-live inventory only; no new route or rewritten business behavior | Existing feature gate and redirect kept |

Page-only rules migrated from global styles are enumerated in `p07-style-ownership.json`. Global/shared selectors remain owned by the main agent. The five collection pages have no individual stylesheet after migration.

## Local verification

- `vue-tsc --noEmit` and `vue-tsc --noEmit -p tsconfig.drill.json` passed during module integration.
- PracticeTrendPanel: 11 tests, including existing workload/forecast fixtures and appearance-only redraw.
- SelectedCollections: 5 tests, one per real collection.
- EiCockpitView: 1 test, existing PATCH contract and selection semantics.
- Timer TrendsView: 1 test, historical series + appearance/rotation/cleanup.
- PdfPageStatusPanel: 1 test, existing batch preview payload, multiselect and manual primary selection.
- Practice pagination: index version pinning and 409 reset retain the applied query and filters.
- Full repository regression, production builds, screenshot matrix and deployment gates are recorded by the main agent in the global progress ledger.

## Visual evidence and limits

Synthetic fixtures in `frontend/e2e/fixture_data.py` cover five subjects, long recommendations and topic titles, large counts, Timer data, and low-frequency forms. They contain invented content only. Browser evidence is Chromium emulation; it does not constitute real Safari/PWA hardware sign-off. Session review and paper entry can write in the real product, so screenshot checks must use this local fixture or an isolated test account.

P07 first-render evidence: `/home/eh/ui-rebuild-p07-first-render/manifest.json` (96 Chromium cases; identifies intermediate-bundle overflow, not a reliable before baseline). True baseline bundles were built from Git `6b83e29` under `/home/eh/ui-rebuild-p07-baseline` without altering the worktree. The global visual runner owns final paired screenshots. Inspect particularly the cockpit topic/aside boundary, compact collection grid, mobile paper footer, PDF status form, and long Timer context values.
