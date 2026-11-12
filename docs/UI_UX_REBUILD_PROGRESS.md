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
