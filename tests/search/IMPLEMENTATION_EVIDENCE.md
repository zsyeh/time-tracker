# P05 implementation evidence — 2026-11-12

This report describes isolated development tests. It does not assert that a
production database has been migrated, indexed, evaluated or deployed.

## Final implementation status (supersedes the historical measurements below)

The final search code is frozen after the PostgreSQL performance review. This
section and the linked sanitized reports are authoritative; the older 62-test
and encrypted-search failure records below are retained as development history.

- **PostgreSQL: 74/74 regression tests pass**, 41.634s.
- **SQLite: 64 pass, 10 PostgreSQL-only tests skipped**, 29.211s.
- Integration owner also reports the final entire backend suite: **550 tests,
  11 PostgreSQL-only skips, pass**, 146.635s. PostgreSQL-specific search coverage
  is provided by the separate 74/74 run above.
- Final command is the same full module list shown in the historical section.
  It now includes score-by-score/order equivalence, correlated-vs-set aggregation
  equivalence (broad/narrow scopes, duplicate joins, owner isolation, `done`,
  `reset`, same-time attempt ties, missing/empty scopes and coverage), the private
  10k oracle, two-connection lexical deletion races, late transaction rollback,
  old-image/raw-SQL source deletion, and verification/rebuild race prevention.
- **0036–0039 forward and 0039→0035 reverse migration succeeded** in a separate
  disposable rollback database. 0039 adds only a concurrent partial index on
  public metadata-only projection IDs; it does not change source or learning data.
- Three isolated corpora—9,300 synthetic, 93,000 synthetic, and 9,281 actual
  public-metadata records—have matching normalizer v2/build inputs, ready state,
  and a valid 0039 index. See [readiness evidence](evidence/final-index-readiness.json).
  Original/private content, cookies and encryption keys are excluded from reports.

### Complete HTTP measurements

All reports below use PostgreSQL 15.18, Gunicorn 3 workers × 2 threads, 5 warmup
requests and 30 measured requests per query. Public concurrency is 5; private
concurrency is 1. No browser, build or concurrent test suite ran during these
measurements. This is isolated local HTTP, including auth/middleware/serialization;
it is not production Internet/TLS latency. Every recorded measured request was 200.

| Workload | Measured p95 | Status / evidence |
|---|---:|---|
| 10k plaintext private sessions, 2 queries | 57.3–112.7ms | Under 500ms; [final private report](evidence/private-http-v2-final-c1.json) |
| 10k encrypted private sessions, 2 queries | 422.9–466.1ms | Under 500ms; [final encrypted report](evidence/encrypted-http-v2-final-c1.json). Private code unchanged by subsequent public-query tuning |
| 9.3k synthetic public, 9 queries before final SQL tuning | 78.1–182.2ms | Baseline v2 context, **not substituted for actual-corpus validation**; [report](evidence/http-9300-v2-final-c5.json) |
| 93k full catalog, 69,754 matching questions | 172.2ms then 198.5ms | Previously 1,011.7ms; final code, stable count/version |
| 93k English typo, 2,759 matches | 433.2ms then 527.1ms | **10× scale p95=500ms gate remains borderline/unpassed in the repeat.** No claim of a complete scale-gate pass |
| Other warmed 93k queries | 130.6–376.4ms in repeat | All below scale 500ms; [complete warm repeat](evidence/http-93000-v2-release-warm-c5.json) |
| First 93k query after worker HUP | 660.4ms (max680.1ms) | Cold initialization tail retained; [first-run report](evidence/http-93000-v2-release-c5.json) |
| Actual Drill “导数”, 1,335 matches | **Final warm234.9ms**, median141.0ms; before tuning571.8ms | Under250ms; [final Drill report](evidence/http-real-drill-v2-release-warm-c5.json), [before](evidence/http-real-drill-v2-final-c5.json) |
| Actual Drill selected collection, 963 matches | **83.0ms** | Final code, actual nonempty collection; same final Drill report |
| Actual EI Fourier / exact LaTeX / Bode / RS | **140.7 / 60.0 / 81.7 / 59.8ms** | All under250ms; [final EI report](evidence/http-real-ei-v2-release-warm-c5.json) |
| Actual Drill first query after final-code HUP | 638.9ms | Explicit cold tail, not a warm pass; [report](evidence/http-real-drill-v2-release-first-c5.json) |

All six final actual-metadata queries passed the 250ms warmed p95 gate after the
entire backend suite finished: **180/180 HTTP200**, exactly one result count and
one index version per query. This checks the concrete six-query set, not every
possible search input or Internet/PWA latency.

The final source eliminates an inapplicable English-typo probe for Chinese-only
queries, extracts score masks once (and detoasts multi-key JSON once), computes
latest attempts once as a set, and keeps a thin materialized scope. Counts use
`COUNT(*)` only when active ORM joins provably preserve one row per Question;
unknown/multiplying joins retain `DISTINCT`. A small partial metadata index makes
full-catalog coverage counting independent of the width of public projections.
JIT is disabled only inside the search transaction. No candidate truncation,
learning-state cache, ranking-weight change or statistics-definition change was
introduced. The PostgreSQL rebuild command now explicitly analyzes only the three
disposable search tables, matching benchmark preparation.

Actual-corpus relevance is recorded separately in
`docs/uiux-rebuild-implementation/search-real-quality-fixed.json`. It is a sparse
developer judgment pool, not a blind or complete-recall benchmark. Full formulas,
reviewed Chinese typos, Latin typo-to-Chinese aliases and the known Fourier-series
hard negative have explicit regression evidence. Do not relabel unjudged results
as irrelevant or claim a full external relevance gate.

### Remaining limits

1. 93k typo tail varies across the 500ms scale target (433–527ms); retain this as
   a 10× load risk instead of hiding the slower repeat.
2. Worker reload/first-request initialization has a 0.64–0.68s tail; warmed
   measurements do not erase that latency.
3. Operator rollout approval and production migration/backfill/health checks
   belong to the integration owner. `DRILL_SEARCH_BACKEND=legacy` remains the
   committed default; no production action was taken by this search subagent.

## Historical regressions and rollback (earlier code)

Final command (both engines):

```
python manage.py test drill.test_search drill.test_navigation_queries \
  drill.test_final_exam_types drill.test_unattempted_navigation \
  tracker.tests.AnalyticsAndExportTests tracker.tests.UserDataAtRestEncryptionTests \
  --noinput --verbosity 1
```

- PostgreSQL 15.18: **62/62 pass**, 40.772s.
- SQLite: **56 pass, 6 PostgreSQL-only cases skipped**, 30.367s.
- `makemigrations --check --dry-run`: no changes detected.
- Python compileall and `git diff --check`: pass.
- Separate disposable rollback database migrated through 0038, seeded one synthetic
  Question, then reverted `drill` to 0035. 0038/0037/0036 reversed successfully;
  source Question count remained 1, exact prompt remained unchanged, derived search
  tables were gone. `pg_trgm` is intentionally not dropped by rollback.

Covered: literal/alias/short-Han/formula/identifier matching, stable pagination and
409 index version changes, live workspace/user state isolation, reset and legacy
`done` semantics, suggestions, page-only hydration, dirty revisions/retries,
lexeme frequency deltas, bulk-update triggers, workspace moves, deletion,
read-only repeatable-read snapshot, non-indexing of Note/answer, public snippets
with Unicode codepoint offsets, and legacy two-query navigation.

Private oracle: same-owner 10,000 synthetic sessions plus another owner's 10,000,
12 queries spanning English/Chinese aliases, entities, Markdown, Unicode, LaTeX,
short words and punctuation. Candidate+matcher IDs/count equal full-scan matcher;
no other-owner candidates. Additional cases combine a concept in body with one
in a tag and separate concepts in two tags. Encrypted model regression passes.
No private plaintext index, cross-request content cache or query log is created.

## Historical synthetic performance measurements (earlier code)

These are **not actual-corpus relevance results**. Corpus: 9,300 synthetic public
Questions (6,979 Drill / 2,321 EI), two users with 10,000 sessions each, second
user encrypted. PostgreSQL 15.18 Alpine; Gunicorn 3 workers × 2 threads. Public
HTTP: five warmups, 30 samples per query, concurrency 5. Private HTTP: five
warmups, 30 samples, concurrency 1. Other agents were running builds/screenshots
on the same machine, and worker reloads affected first-query tail latency.

After isolating public search candidates from poorly estimated catalog OR
filters (uncapped SQL relation with `OFFSET 0` planner boundary), nine public
queries had median 38.8–139.4ms; p95 ranged 93.2–618.4ms. The first query included
cold workers (618.4ms); typo case 258.0ms; remaining cases at most 199.2ms.
That early run was **not a full pass of the 250ms p95 release gate**. After the
final optional page-only snippets, a quiet-machine warm HTTP repeat of all nine
queries produced p95 **58.0–172.6ms**, all HTTP 200 (30 samples × concurrency 5).
This passes these synthetic 9.3k cases, not the actual restored corpus gate.

Plaintext private search after lossless SQL prefilter: median 53.6–87.6ms,
p95 57.2–476.1ms (the first query included cold workers). Encrypted private search
with ciphertext tuple streaming and bounded result hydration: median
627.1–670.7ms, p95 **641.1–1060.3ms**. The encrypted 10k 500ms target is **not met**.
There is no plaintext persistence or security downgrade to claim an artificial pass.

The final quiet warm repeat measured plaintext p95 **78.3–95.0ms** and encrypted
p95 **668.1–724.5ms**, all HTTP 200. Encryption remains above the 500ms target.

Evidence artifacts remain outside Git in `/tmp/precision-search-evidence/`:

- `http-9300-c5-optimized.json` (public complete HTTP)
- `http-9300-final-warm-c5.json` (final public code, quiet warm repeat)
- `private-http-10000-c1-final.json` (plaintext complete HTTP)
- `encrypted-http-10000-c1-stream.json` (encrypted complete HTTP)
- `private-http-final-warm-c1.json`, `encrypted-http-final-warm-c1.json`
- `service-9300-c5.json` (earlier service-only timing, not HTTP)
- `fourier-explain-*.json`, `explain-*.json`, `private-explain.json`

Cookies and encryption key in that private fixture directory must **never** be
committed, printed or copied into deployment documents. They belong only to the
synthetic local fixture. Final regression logs are `/tmp/search-final-pg.log` and
`/tmp/search-final-sqlite.log`.

## Historical release gates (superseded by the final status above)

1. Real privately judged relevance dataset: baseline and hybrid NDCG/recall/MRR,
   holdout separation and inspection of metadata-only unanswerable cases.
2. Quiet-machine complete HTTP p95 with final code and actual restored corpus.
3. 93,000-Question 10× workload, concurrency 5, index/backfill/freshness budget.
4. Encrypted private 10k 500ms target, explicitly unpassed as above.
5. Production migration, verified backfill, supervised worker and operator smoke
   checks. Those actions belong to the integration owner.

Until appropriate hybrid gates pass, leave `DRILL_SEARCH_BACKEND=legacy`.
A partial/unready hybrid index responds 503; it never silently switches algorithms.
An index version change responds 409; the client resets page and retries.

## Current operations contract

1. Legacy flag remains enabled during migrations and full rebuild.
2. Apply 0036–0039. PostgreSQL must allow `CREATE EXTENSION pg_trgm`; extension
   creation failure is explicit. Concurrent index migration is non-atomic and
   repairs invalid same-name indexes on retry.
3. `rebuild_question_search --workspace all --dry-run` validates public source
   size and reports maximum terms, source codepoints and manifest mismatches.
4. `rebuild_question_search --workspace all --batch-size 500 --verify` creates
   only disposable projections. Interrupted builds use `--resume`; changed
   normalizer/alias/manifest inputs require restarting without `--resume`.
   PostgreSQL planner statistics for the three disposable search tables are
   analyzed automatically before verification; source/learning tables are untouched.
5. Drain `process_question_search_queue --batch-size 100 --max-seconds 20`.
   Schedule a non-overlapping 25-second systemd timer with TimeoutStartSec=30;
   advisory lock prevents simultaneous rebuild/worker execution. Command exits
   nonzero for failures/quarantine/queue age over 300s. Inspect safe error codes.
6. `verify_question_search --workspace all --enqueue-mismatch`; drain and verify
   again if mismatches are queued. Verification reconciles hashes, scope, counts,
   schema and per-question lexical document frequencies before marking ready.
7. Switch to hybrid only after gates. Roll back first by flag to legacy, then stop
   worker. Additive derived tables may safely remain; schema rollback to 0035 is
   tested but unnecessary for an emergency flag rollback.

User Attempts, Notes, learning states, timers and question categories are never
rewritten by indexing. Search publication generation advances on source changes;
page queries, type aggregation and hydration use one read-only repeatable-read
snapshot. New index versions invalidate old page tokens instead of mixing pages.
