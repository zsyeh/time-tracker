# Search verification

All committed texts and judgments are synthetic. `queries.v1.jsonl` contains 64
queries and a deterministic 20% holdout split. The qrels are for the **16-record core fixture only** (`seed_fixture.py
--questions 16 --private 0`). They are not valid judgments for the extended
9,300/93,000-row performance corpus or for the actual private corpus. The UUID
query uses the deterministic core fixture UUID; replace it in a real-corpus
release evaluation copy with an authorized real UUID. Do not write actual notes, tokens, or OCR bodies here.

Run Django regressions against an explicitly isolated `DATABASE_PATH` or
`DATABASE_URL`, never an inherited production `.env`:

```
python manage.py test drill.test_search drill.test_navigation_queries drill.test_final_exam_types
python manage.py rebuild_question_search --workspace all --dry-run
python manage.py rebuild_question_search --workspace all --batch-size 500 --verify
python manage.py process_question_search_queue --batch-size 100 --max-seconds 20
python manage.py verify_question_search --enqueue-mismatch
```

Use `benchmark_question_search --backend hybrid_v1 --user-id FIXTURE_USER_ID
--queries tests/search/queries.v1.jsonl --qrels tests/search/qrels.v1.jsonl
--repeats 30 --concurrency 5 --output PRIVATE_PATH` for **service** measurements.
Use `python tests/search/benchmark_http.py --base-url STAGING_URL --queries PATH
--cookie-file PRIVATE_0600_FILE --repeats 30 --concurrency 5 --output PRIVATE_PATH`
for authenticated complete **HTTP** measurements. The cookie file contains one
Cookie header string and is never logged. HTTP URL workspace must match each
fixture query file; split Drill and EI query files for dedicated hosts.

Release gates remain those in the Master plan: real privately judged corpus,
250ms complete HTTP p95, 10x fixture/concurrency, isolated users, and index freshness.
Passing synthetic functional tests does not waive those release gates. Default
`DRILL_SEARCH_BACKEND=legacy`; never enable a partially rebuilt hybrid index.

The private SQL prefilter is a provable superset only: static ASCII/basic-Han
alphabet check, necessary literal characters, owner tag union **per concept**,
and final Unicode matcher. Unicode/entity/formula uncertainty passes through.
Encrypted rows use request-local streaming ciphertext tuples and the existing
`decrypt_payload` context; only returned rows are hydrated. No private plaintext
search table, cross-request content cache, or search log is introduced.

## Corrupt disposable-index recovery

`--resume` resumes interrupted work; it does not repair arbitrary pre-existing
lexeme frequency corruption. Verification rejects inconsistent frequencies.
After switching to legacy and stopping the worker/rebuild, an operator may
clear **only** the three disposable projection/lexeme/dirty tables in a transaction
and reset search state. Never truncate `Question`, Attempts, Notes or user state.
PostgreSQL recovery SQL (no CASCADE, no identity reset):

```sql
BEGIN;
TRUNCATE TABLE drill_questionsearchdocument, drill_questionsearchlexeme,
  drill_questionsearchdirty;
UPDATE drill_questionsearchstate SET ready=false,rebuilding=false,
  rebuild_last_pk=0,build_source_version='',generation=generation+1;
COMMIT;
```

Then run a complete rebuild **without** `--resume`, drain and verify both
workspaces, evaluate quality, and only then consider enabling hybrid again.
This clears no original data and deliberately avoids deletion triggers that
cannot safely decrement an already-corrupt frequency counter.
