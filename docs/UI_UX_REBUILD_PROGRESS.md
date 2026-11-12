# UI/UX Rebuild — execution ledger

- Baseline: `6b83e2924b9042e75e87bc091ea7f24e0948f8ee`.
- Integration branch/worktree: `ui-rebuild/integration`, `/home/eh/ui-rebuild-20261112`.
- Authorization: user message “开始按照要求工作和部署提交 注意留回滚” authorizes implementation, commits and deployment with rollback. It supersedes the preceding research-only restriction; Phase 8 gates still apply.
- Production rechecked: `time-tracker-ha:20261112-design-6b83e29`, healthy; service active; no production changes yet.
- Current phase: P00 baseline checks running; P01 foundation and independent modules started against frozen Master contracts.
- Dependencies: isolated frontend packages in `/home/eh/ui-rebuild-node-modules`; do not modify the previous worktree's dependency symlink.

## Ownership

| Owner | Files | Tasks | State |
|---|---|---|---|
| Main | shared/design/appearance/ui, both App/main/styles/index/config, navigation/routes/recovery/templates | P01/P02, integration/release | in_progress |
| plan_search | search backend/models/search view sections/migrations/tests/settings search flags | P05 | in_progress |
| implement_pages | Timer Settings/GlobalSearch, Drill Settings/Practice/filter/composable/tests | P03/P04 | in_progress |
| implement_practice | Question/DiagnosisSelector/PracticeActionToolbar/Reader/LearningSharePanel/tests | P06 | in_progress |
| Unassigned | Heatmap/Insight/statistics/low-frequency pages | P07 | pending |
| Independent review | read only candidate, tests/evidence | P08 | pending |
| Main | backups, migrations, image/PWA publish, health/rollback | P09 | pending |

## Baseline evidence

Master research evidence uses the identical baseline SHA: 8 current-build fixture screenshots, read-only schema/search diagnostics and 6 research reports. These are not implementation results. Full Vitest baseline and selected backend regression are running; results will be recorded before declaring P00 passed.

## Continuation

Read Master §11–18 and §22–30, this ledger, git status/diff and active agent messages. Keep file ownership. Do not deploy before integration tests and review. Preserve old image/PWA/config and fresh restorable DB backup. No database restore over newer study records during normal rollback.

## Verified baseline and foundation (in progress)

- Baseline frontend: 40 files / 177 tests passed.
- Baseline backend: 133 tests passed after `collectstatic` in an isolated archived baseline. Initial missing-manifest failures were environment setup, not ignored.
- Current integration frontend at first checkpoint: 52 files / 235 tests passed; both production builds passed. Later P07 edits require final rerun.
- Shared appearance: neutral semantic tokens, ten accents, System/Light/Dark, migration/persistence, no-inline synchronous bootstrap; 23 appearance/contrast tests plus neutral-source invariant.
- Navigation: shared sidebar, native mobile drawer, source marker DOM/CSS removed, route-aware active state, More popup, settings host fallback + recovery.
- First browser pass: 72 fixture screenshots over six viewports × Light/Dark × six core pages; no page overflow or uncaught JS error. This is Chromium, not physical Safari. Visual review identified and is fixing old mobile header inset and iPad sidebar media syntax.
- P06 local verification: reader five direct actions, zoom and coarse targets, 12 browser cases; saved evidence under `docs/uiux-rebuild-implementation/p06`.
- Design refinement ADR-01: History two-column threshold uses its actual content container 900px, preserving 1180px iPad landscape after the 224px sidebar. This replaces the plan's generic 960px example based on actual available width; phone/820 portrait use tabs.
- Production unchanged. Fresh backup/restore preparation follows before any migration or restart.

## QA-driven decision updates (2026-11-12)
- Actual full QuestionView at iPad landscape 1180×820 showed the general <600px diagnosis single-column rule pushed submit below the visible pane. P06 uses the compact two-column selector inside the existing answer pane: all eight options remain direct checkbox choices, 44px targets and 14px labels. Generic wide selectors retain grouped rows. This explicitly supersedes the Master single-column rule for the narrow practice control pane only; handlers and persistence are unchanged.
- Timer header/toolbar negative margins used a different inset from their content container and caused 2–6px overflow. Both now derive from the actual content inset.
- Full fresh PostgreSQL custom-format backup retained on 47; isolated resource-limited restore rehearsal is running, without modifying production tables. Incomplete local transfer files are not usable backups.

## Final integrated UI candidate
- Full frontend suite: 56 files / 251 tests passed. Timer and Drill TypeScript + production builds passed; existing bundle-size notices retained. ESLint is not configured.
- Full backend suite: 538 tests, OK, 7 PostgreSQL-only / environment skips in SQLite lane. Targeted PostgreSQL search/navigation/encryption lane 62/62 passed before the final real-data alias additions; final aliases have a further targeted PostgreSQL run.
- Historical recovery migration test now restores current graph leaves in finally; previously it left the database at 0035 and made later migration tests mix forward/backward plans after additive 0036–38. No production migration semantics changed for this test correction.
- Independent Chromium full-Question and shared-menu review: final pass, including 44px diagnoses/Note save, actual two-choice diagnosis, note scroll/More reachability, Reader rotation, both App menus and deleted paper recovery. Evidence: docs/uiux-rebuild-implementation/review/final.
- Core matrix 72 screenshots and P07 96 screenshots: no JavaScript exceptions or page horizontal overflow. These use synthetic APIs, and are explicitly not native Safari/iOS PWA sign-off. Final extra Trends/search screenshots are being refreshed after the last visual refinements.
- Public search actual metadata export is 9,281 questions (23 documents, 1,458 topics, 8,635 exam-type rows); private learner records and binary images were excluded. An independently source-verified 41-query development relevance set is being compared with both actual engines; it is not a user-blind holdout.
- Private encrypted 10k benchmark remains above the plan's 500ms target (~668–725ms on the isolated fixture); plaintext 10k ~78–95ms; no persisted private plaintext index or cross-user cache was added to hide that limitation.
