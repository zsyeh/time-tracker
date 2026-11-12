# Independent implementation review evidence

Review date: 2026-11-12. Reviewer: independent `plan_review` agent. This reviewer changed only this evidence directory, with permission from the integration owner; implementation fixes were made by their respective owners.

All API records are invented. No production service was accessed, no answer was submitted and no learner record was changed. Chromium screenshots are not native Safari or iOS PWA acceptance.

## Reproduce

Start `frontend/e2e/fixture_server.py --port 8008` against the checkout’s current `frontend/dist` and `frontend/drill-dist`. Then run:

```sh
/home/eh/ei-page-tracking/browser-env/bin/python docs/uiux-rebuild-implementation/review/browser_review.py --repo . --output /tmp/ui-review
```

The script uses `/usr/bin/google-chrome`. The paper recovery test uses a simulated production origin solely to exercise the existing hostname-bound PWA branch; **every request is intercepted** and fulfilled from local build files / synthetic fixtures, with other hosts aborted. It cannot contact the real host.

## Evidence rounds

- `before-fixes/`: old Drill bundle reproduced Escape closing both popup and drawer; Tab lost focus to BODY; the diagnosis selector occupied 478px and submit began at y1022. Timer bundle already included paper validation, which passed. Build HTML SHA256 values identify the exact assets.
- `after-fixes/`: Escape and drawer rotation passed; Tab still lost focus to BODY. Compact diagnosis reduced to 210.6px with eight 44px rows, but submit y784–828 was partially clipped by pane bottom812. Reader rotation1180×820→390×844 passed; all seven visible controls remained at least44px, and Escape closed Reader. Deleted paper recovery passed.
- `final/`: both rebuilt applications passed the final script. Failed intermediate evidence is intentionally retained. The final JSON includes explicit checks and returns a failing exit code if any reviewed workflow fails.

Question screenshots render the full application shell and real QuestionView; only API responses are mocked. This differs from the isolated P06 component screenshots and specifically covers the narrow iPad answer pane.

## Final independent result

No unresolved P1 defect remains in the reviewed scope. [Final measurements](final/review.json) record these exact HTML build fingerprints:

| Application | SHA256 of built index.html |
| --- | --- |
| Timer / Learning OS | `5dad317400394a677e9ce49d1b41358b7c37e6f8cc976489735718b4369a5c8b` |
| Drill / EI | `dad3de4171e0e5c33f0d107f525574a956593c6c4c8e2deba105d3578afa7b3f` |

| Review case | Actual final evidence |
| --- | --- |
| Drill phone menu Escape | Closes only the popup; drawer stays open; focus returns to More tools. |
| Drill phone Tab / Shift+Tab | Popup closes; focus moves to the next / previous visible element inside the native dialog, never BODY. ArrowDown leaves exactly one menu tab stop. |
| Drawer → desktop rotation | Popup and drawer close; body scrolling is restored. |
| Timer phone menu | Escape and Tab both retain valid focus inside the drawer. |
| Appearance | System follows dark media; manual Light overrides media; Yellow changes accent while body remains white; reload and EI navigation retain the choice. |
| Real QuestionView at 1180×820, touch | Eight directly selectable diagnosis rows each remain 44px high; selector is 210.6px rather than 478px. Submit actions are fully visible at y748–792 inside a pane ending at y812. |
| Two selected diagnosis reasons | Both remain selected; primary-reason choices are present; submit actions stay fully visible. |
| Note editor and More actions | After scrolling the editor into view, Save is 44px high and unobstructed; submit actions remain visible; Undo and Reset menu entries are both visible and unobstructed. Neither destructive action was invoked. |
| Reader rotation to 390×844 | Reader stays open, has no horizontal overflow, all seven visible toolbar controls remain at least 44×44px; Escape closes it. |
| Deleted paper on PWA cold launch | Owner-scoped paper validation GET returns synthetic 404; old locally dirty location is not revived, root remains usable, and no JS error occurs. |

Visual inspection of [selected diagnosis](final/question-diagnosis-selected-1180x820.png), [Note and More](final/question-note-more-1180x820.png) and [Reader](final/question-reader-390x844.png) agrees with the measured bounds. The blue ring on the focused diagnosis row is a keyboard focus indicator, not a persistent colored selection border.

## Defects found and closed during independent review

| Finding / requirements | Implementation location | Closure evidence |
| --- | --- | --- |
| Escape bubbled into native drawer cancellation; menu Tab stranded focus at BODY; popup survived drawer replacement. R04/R15/R16 | `frontend/shared/ui/UiPopover.vue:21`, `frontend/shared/ui/UiMenu.vue:9` | Actual browser reproductions in earlier rounds; both apps pass final keyboard / rotation cases. |
| Diagnosis density hid primary actions in the actual narrow iPad answer pane. R11/R12/R14/R15 | `frontend/drill/src/components/DiagnosisSelector.vue:15`, `frontend/drill/src/views/QuestionView.vue:1433`, `:1465`, `:1515` | Compact two-column rows plus sticky submit section; final real-page screenshots and measurements. Original submit handlers remain in use. |
| Note Save was only 30px on touch; scoped inputs could override the shared 16px coarse-pointer font. R12/R15 | `QuestionView.vue:1569`, `frontend/drill/src/views/InsightView.vue`, `frontend/drill/src/components/PracticeFilterPanel.vue` | Save measured 44px in final build; scoped coarse-pointer font fixes reviewed. Physical Safari keyboard remains outside this evidence. |
| A locally dirty deleted paper could supersede the filtered server recovery state. R14/R15 | `frontend/shared/learningRecovery.ts:55`, `frontend/src/lib/learningRecovery.test.ts` | Explicit owner-scoped paper GET and failed-recovery branch; actual intercepted cold-launch browser test passes. |
| Search version absent from Practice pagination / question context. R09/R10/R14 | `frontend/drill/src/views/PracticeView.vue`, `frontend/drill/src/views/QuestionView.vue`, query-state normalizer | Source review confirms search/index version propagation and 409 page-one recovery; owner-added regression tests cover the branch. |
| Private search prefilter incorrectly lost matches split across body and tag or across two tags. R10/R14 | `tracker/api_views.py:80`, `drill/search/private.py`, `drill/test_search.py` | Independently supplied counterexample; final source intersects concepts, each combining text OR owner-scoped tag. Search owner reports complete 20k-session oracle and PG62 / SQLite56+6skip tests. These backend test runs were not rerun by this reviewer. |
| Primary hover contrast fell below 4.5:1 for two light accents. R01/R07/R16 | `frontend/shared/appearance/palette.ts`, `resolve.test.ts`, `frontend/shared/design/controls.css` | Separate generated hover/pressed tokens and all-palette contrast assertions reviewed. Integration owner owns the full test run. |
| Active legacy copy / save / erratum / selected controls retained excessive accent outlines; Light error text used a fixed pale color. R01/R02/R12 | `frontend/drill/src/styles.css` | Source reviewed: neutral secondary controls or semantic primary fill, and semantic error token. |
| Spelling expansion was not disclosed after the search field lost focus. R10 | `frontend/drill/src/views/PracticeView.vue:223`, `PracticeView.test.ts:73` | Final source shows restrained corrected-term feedback while preserving original query; regression test added by page owner. |

Additional source review covered external synchronous appearance bootstrap / CSP compatibility, preference validation and persistence, route-aware sidebars, grouped settings, user/workspace-scoped Heatmap and Insight state, preserved Question timing / Note / Attempt handlers, and request-local private matching. This review found no remaining high-severity defect in those inspected paths. It is not a claim that every route or every source line was exhaustively verified.

## Supplemental visual and interaction review

The final supplemental [measurements](supplement-final/supplement.json) and nine screenshots cover three additional acceptance areas. Run the same local fixture server and:

```sh
/home/eh/ei-page-tracking/browser-env/bin/python docs/uiux-rebuild-implementation/review/supplement_review.py --repo . --output /tmp/ui-review-supplement
```

The Timer build changed only after the scoped Trends refinement, with final HTML SHA256 `e02e4865a74d1d6716a983a4c4b96ea0d265d10693d4542c32f2915b68fec6fc`. The Drill HTML fingerprint is unchanged from the earlier final review. All supplementary cases passed; the reviewer coordinated Chrome execution with the search benchmark owner and closed Chrome before its performance window.

| Case | Final result and evidence |
| --- | --- |
| Trends: Light / Dark × 390 / 1180px | All four have no horizontal overflow, no intersecting label/value boxes, no intersecting breakdown headers, and all subject values fit their columns. Initial screenshot inspection found desktop summary labels directly adjoining values despite non-overlap; the owner changed `.insight > span, .insight > strong` to block layout. Final assertions require either a vertical separation of at least 4px or horizontal separation of at least 8px. All four now pass. Only the final Trends screenshots are archived here. |
| Safe public search excerpt | Synthetic public `search_match` contains an emoji before `Fourier`, a literal `<img ... onerror=...>` string and LaTeX. The rendered mark contains exactly `Fourier`, confirming codepoint offsets across the emoji; no `img` / `script` element is created, no payload executes, and text matches the source excerpt. The original `fourire` query remains while the UI shows `同时匹配：fourier`. |
| 20 Appearance / Accent combinations | Actual setting clicks cover Light and Dark × all ten accent options, followed by a reload for every combination. All retain appearance, accent, localStorage and cookie persistence. Body, page, sidebar, subtle and elevated neutral backgrounds remain unchanged within each scheme. Yellow and Monochrome have representative screenshots in both themes. |

Neutral surface values observed across every accent:

| Theme | Page | Sidebar | Subtle | Elevated |
| --- | --- | --- | --- | --- |
| Light | `#ffffff` | `#f7f7f7` | `#f5f5f5` | `#ffffff` |
| Dark | `#141414` | `#101010` | `#1b1b1b` | `#242424` |

Key screenshots: [Trends desktop Light](supplement-final/trends-light-1180.png), [Trends phone Dark](supplement-final/trends-dark-390.png), [safe search excerpt](supplement-final/practice-safe-search-light-1180.png), [Yellow Light settings](supplement-final/appearance-light-yellow-1180.png), [Monochrome Dark settings](supplement-final/appearance-dark-monochrome-1180.png). Screenshot inspection confirms the metrics. These are still synthetic Chromium checks, with the same device and production limits below.

### Final semantic-color / Note-control rebuild

After the integration owner separated format-marker colors from the user accent, increased the Note privacy control target and added the integrated-navigation PWA capability meta, the original `browser_review.py` was rerun against both final builds. [Final polish measurements](final-polish/review.json) pass every case again, with Note Save unobstructed at 44px, two diagnosis reasons selected, submit actions fully visible, both More menu actions accessible and Reader rotation intact. The Note expansion increases the scrollable content height as expected while the sticky submit section remains usable. [Final Note and More screenshot](final-polish/question-note-more-1180x820.png) was independently inspected.

- Timer HTML SHA256: `26d289bf4f9fddfa2b96e053a1fba5b2eff738431985ffac7a076db39d69f6ec`.
- Drill HTML SHA256: `94d4e4f89e31d4cae1818739d5a001d2c1dc24e9e073a4dd8f774b52a956456a`.
- This rerun does not claim another complete 20-accent screenshot matrix. The earlier 20 combinations remain recorded against their identified build.
- PWA capability detection was inspected in source; the integration owner runs `deploy/pwa/test_navigation.py` for integrated-shell and legacy fallback behavior. This browser script does not substitute for that test or native PWA device acceptance.

## Final public-search batch / trigger review

The reviewer independently inspected the final batch indexer, rebuild command, revision queue, source triggers, ready-state publication and rollback compatibility. The three newly identified correctness defects below were fixed by the search owner and re-read by this reviewer. No unresolved P1 defect remains in this inspected batch/trigger scope. This is a source-review conclusion supported by attributed test results; the reviewer did not run the PostgreSQL suite or a production benchmark.

| Area | Final implementation and verification |
| --- | --- |
| Captured revision safety | `drill/search/index.py:233` captures dirty `(question_id, revision)` before reading source, then deletes only those exact pairs after projection writes. A new dirty revision cannot match the cleanup predicate; an initially absent dirty row is not included. Batch rollback also rolls back its cleanup. |
| Reference-count idempotence | `index_batch` computes aggregate old/new per-question references and applies only the count delta, inside the same transaction as the projection upsert. Repeating a committed batch applies zero net count changes. The command advances `rebuild_last_pk` only after the batch returns from its atomic transaction, so a crash before checkpoint may replay a batch safely. |
| Atomic failure | `drill/test_search.py:test_batch_revision_survives_and_failure_rolls_back` now injects failure at projection `bulk_create`, after reference changes occurred, and asserts both the old projection hash and all lexeme frequencies are restored. This is stronger than the earlier failure-before-write test. |
| Concurrent source deletion | Review found that DELETE-if-small followed by decrement allowed two transactions to leave a zero-frequency row. `index.py:182` and the migration's `drill_search_projection_deleted` now perform atomic decrement first, acquiring the row lock, then delete exact zero in the same transaction. `test_two_connections_deleting_shared_lexemes_leave_no_zero_rows` uses two independent DB connections over four rounds and verifies no lexeme remains and workspace verification succeeds. |
| Ready publication race | Review found that a standalone verify could publish after a concurrent rebuild set `rebuilding=True` without changing generation. The final publication at `index.py:333` requires both the captured generation and `rebuilding=False` in the UPDATE predicate. `test_verify_does_not_publish_when_rebuild_starts` injects that transition immediately before promotion and asserts ready stays false. |
| Full-build gate | `rebuild_question_search.py:41` sets ready false before any batch. Failed batches stop with resumable state. Completion clears rebuilding, but only a successful complete verifier sets ready true; source-version mismatch rejects incompatible resume inputs. Verification checks current public source hashes, projection coverage, schema, reference counts, no pending dirty work and generation stability. |
| Old-image delete compatibility | Review found that old Django ORM collectors do not know the new projection/dirty foreign keys. The final Question BEFORE DELETE trigger in `0037_search_dirty_triggers.py` explicitly deletes both disposable rows; projection deletion still decrements references. `test_old_collector_raw_question_delete_cleans_derived_foreign_keys` directly deletes the source row without the new collector and asserts all derived rows are removed. No new field is required on an existing Question / Attempt / Note model for rollback reads or writes. |
| Source/worker semantics | The PostgreSQL triggers bump generation in the source transaction and queue public source changes, including bulk writes. Private Attempt/Note changes do not feed the public projection. Incremental queue retry and exact-revision cleanup remain unchanged by the batch optimization. The rebuild command and queue processor share the advisory worker lock; the new reference-count fix also covers source deletion outside that lock. |

The search owner reports the final targeted PostgreSQL lane as **30/30 passing in 24.761s**, including the four-round dual-connection deletion test, raw old-collector deletion, ready race and late transaction failure. The reviewer inspected those test bodies and the final implementation but did not independently rerun this lane. The integration owner separately runs the final whole-project suites.

`--resume` is a checkpoint recovery mechanism, not a repair for arbitrary pre-existing lexeme counter corruption. A failed verifier must keep hybrid disabled; any corruption repair must first select legacy mode and stop the worker, then rebuild only disposable search-derived data using `tests/search/README.md`, section “Corrupt disposable-index recovery”. That inspected runbook truncates only the three search-derived tables without CASCADE or identity reset, resets readiness and advances generation, then requires a complete rebuild and verification. It must never truncate source questions or learning records. This review did not perform that destructive recovery procedure.

The 9,281-row relevance reevaluation, 93k-volume verification/performance work, encrypted private-search latency and production restoration evidence remain owned by their respective runners. None is relabeled here as an independently executed benchmark.

### Last request-local private-search optimization

The final small performance patch adds `necessary_character_groups` / `private_candidate` in `drill/search/private.py`, invoked before the full matcher in `drill/search/query.py`. The reviewer read these functions, the owner-scoped/decryption path in `tracker/api_views.py` and the updated oracle without running Chrome, tests or benchmarks during the owner's quiet HTTP measurement window.

No new recall-loss or privacy defect was identified in this patch:

- Exclusion is limited to raw ASCII/basic-Han source values. Within that restricted alphabet, the existing normalizer cannot introduce an absent required letter/digit/Han character; the prefilter performs the same ASCII lowercasing. Sources containing `&` or characters outside that proven alphabet pass to the full normalizer, including entities, Unicode casefold/compatibility forms and formula symbols.
- Every alternative remains an OR, including all reviewed concept aliases and cooccurrence forms. Formula, identifier or otherwise unsupported keys disable exclusion for that group. Taking necessary characters across all fields and owner tags can admit extra candidates, but cannot remove a match accepted within an individual field. The original full Unicode/alias matcher remains the final decision.
- `_private_anchors` caches only query-derived character conditions on a per-request `QueryPlan`. It stores no row text. Decrypted values remain local to the current request; no persistent plaintext index, plaintext logging or cross-request result/content cache was introduced.
- `_private_matching_ids` reapplies `user=user`; tags and relation rows remain owner-scoped. Decryption still uses `user_id` and the existing model/field context, and copies only the model's protected field allowlist. The optimization does not expand the result or decryption permission boundary.
- The oracle now obtains its expected result using `private_matches(..., _prefilter=False)`. Actual results include both the SQL candidate stage and the new Python candidate stage before final matching, so a shared prefilter bug cannot be hidden by computing both sides with that prefilter enabled.

The owners report **14/14 targeted tests on PostgreSQL and 14/14 on SQLite** for this patch, including fullscan-oracle/owner isolation and encryption regressions. The integration owner's **547-test full run with 10 skips occurred before this optimization**; it must not be described as testing this later patch. These reported test runs and the ongoing HTTP performance results were not independently executed by this reviewer. The source-review conclusion is limited to the inspected prefilter, query lifecycle, scope and decryption boundary.

### Final public SQL execution-plan optimization

The reviewer independently inspected the diff from `f50a852` in `drill/search/postgres.py`, `drill/search/service.py` and `drill/test_search.py`, without running a database query, Chrome or benchmark during the owner's quiet window. No blocking semantic defect was found in these changes:

- The spelling-probe guard rejects only plans for which the existing `typo_candidates` cannot produce an English correction: its eligibility check uses the same single `en:` key, ASCII letters and minimum length. Membership, Chinese alias variants and formula handling remain intact.
- Score-mask extraction is restricted to the PostgreSQL score operation. It binds score/phrase parameters in the outer SELECT before the extracted-key parameters in the FROM subquery, matching textual SQL order. Generated aliases are fixed numeric identifiers; user terms remain parameters. For the integer bitmasks generated by the projection builder, cached-mask existence and bit checks preserve the old expression. Corrupted arbitrary JSON values are outside that invariant.
- Tier and identifier expressions retain their old paths. The field weights, phrase bonuses and complete stable result ordering (`identifier`, tier, score, document, question order, primary key) are unchanged.
- The aggregate CTE compiles the original filtered scope with the original `with_exam_type` annotation. Compiled scope parameters precede the bound current-user ID, matching SQL order. `COUNT(DISTINCT scope._stats_id)` preserves deduplication when a scope contains repeated relation joins.
- Latest attempts remain owner-scoped and use `DISTINCT ON (question_id)` with `created_at DESC, id DESC`, equivalent to the former per-question `-created_at, -pk` subquery. `done` / `correct` / `review` / `reset`, absent attempts and equal timestamps preserve their prior meanings. Missing metadata booleans remain uncounted through SQL FILTER's NULL behavior.
- The raw aggregate uses the existing Django connection inside `question_list_response`'s repeatable-read transaction; it does not open another connection or move aggregation outside the request snapshot. Empty compiled scopes return no rows, as the portable reference does.

New tests compare every optimized/reference score and resulting order for representative Chinese, English, alias, formula and identifier queries; compare aggregate rows for owner isolation, reset/done, same-time attempts, duplicate joins, missing content and empty scopes; and assert ineligible typo plans execute no probe. The search owner reports **27 targeted PostgreSQL tests passing**. This reviewer inspected their implementation but did not independently run them. Full-project test results recorded earlier predate this later SQL patch.

A non-blocking response-format observation was reported to the owner: the early return could bypass the function's final `corrected_terms` deduplication for repeated reviewed Chinese misspellings. The final early-return branch now deduplicates on a copied plan when necessary; source reinspection closes this observation. Candidate membership, ranking and statistics are unaffected.

Passing source review and equivalence tests does not establish the requested HTTP latency. The previously failing real-corpus broad-query and 93k cases must pass fresh complete HTTP measurements before the integration owner treats the performance release gate as satisfied.

### Final metadata-index and aggregate refinement

The reviewer subsequently read the final uncommitted `service.py`, `postgres.py`, rebuild command, equivalence tests and `0039_search_metadata_coverage_index.py`. This was a source-only review: no database queries, tests, Chrome session or benchmark were run during the search owner's quiet measurement window. No new P1 defect was identified in this final inspected diff.

- `service.py:245` uses `COUNT(*)` only when compiled active joins are proven many-to-one or one-to-one and there are no explicit extra tables. Multiplying or unknown relation joins retain `COUNT(DISTINCT scope._stats_id)`. The latest-attempt relation is unique by question ID, and the coverage relation joins the projection's OneToOne primary key, so these added joins do not multiply a proven-unique scope. The duplicate-attempt-join regression compares both aggregate paths to the unchanged ORM reference.
- `service.py:258` counts metadata-only coverage using the exact JSON boolean predicates `has_prompt = false` AND `has_latex = false`, matching the original Django JSONField lookups. Missing keys and JSON null do not become false. The partial relation joins IDs from the already filtered live scope; it neither widens workspace/collection membership nor applies user-independent attempt state. `broad_scope` chooses only an access path; both paths are compared for identical full and narrow scopes in the equivalence test.
- `0039_search_metadata_coverage_index.py` creates only a disposable projection index. Migration and operation are both non-atomic, permitting `CREATE INDEX CONCURRENTLY`; an invalid prior attempt is dropped concurrently before retry. Reverse migration uses `DROP INDEX CONCURRENTLY IF EXISTS`, and SQLite is a no-op. The query remains correct without this performance index. No source-table schema, learning data, extension or permission change is introduced.
- The extra score optimization at `postgres.py:123` concatenates an empty JSON object only for projection-generated object-valued term maps, behind the existing optimizer boundary. This preserves every key and integer bitmask. Bound phrase/score parameters still precede extracted-key parameters in textual SQL order. Tier, identifier, weights and final stable ordering are unchanged.
- `SET LOCAL jit = off` applies only inside hybrid request transactions and does not change connection-global configuration or the repeatable-read snapshot. The rebuild's `ANALYZE` targets only the three disposable derived tables, after batches complete and before optional verification. It cannot itself publish ready state; verifier failure still blocks hybrid readiness.
- The final aggregate regression covers both coverage settings and both broad/narrow paths over Drill, EI, duplicated joins, empty scopes, metadata-only content, same-time latest attempts, reset/done and a different user's attempts. The reviewer inspected these assertions. The owner is responsible for the fresh complete PostgreSQL/SQLite results and HTTP measurements after this last refinement; earlier 27-test results are not relabeled as verification of 0039 or the later changes.

This closure is limited to source semantics, parameter safety, transaction scope and migration reversibility. It does not independently establish production migration duration, index planner choice or the final latency gate.

## Verification boundaries and remaining release gates

- This directory is a focused independent review, not the entire R01–R16 acceptance matrix. The integration owner must combine it with module tests, the full screenshot matrix, search relevance/performance evidence and release checks.
- Chromium touch emulation cannot establish native iOS Safari or installed-PWA safe-area, soft-keyboard, browser-toolbar or background-resume correctness. Those remain explicit manual device checks.
- This script does not submit an Attempt, save a real Note, modify study state, reset a question or log out. Handler/payload preservation was reviewed in source; those workflows also require the existing automated integration tests.
- The deleted-paper test validates frontend recovery handling of a denied/missing paper. It does not independently prove production API ownership enforcement; that is a backend authorization test obligation.
- Search qrels, large-volume performance, migration duration, production backup restoration and deployment health were not independently executed by this reviewer. Search-owner reports are attributed as reports, not relabeled as independent passes.
- Appearance measurements confirm post-load state and reload persistence. They do not measure native first-paint flicker on physical PWA launches. External synchronous head bootstrap and non-inline CSP compatibility were checked in source.
- No production deployment or database change was performed by this reviewer. A clean review result does not replace backups, successful restore rehearsal, final integration tests, production smoke tests or rollback preparation.
