> **研究工作稿，非独立施工规范。** 本稿保留调研时的候选方案和审计证据。最终路径、尺寸、命名、存储key、Props、迁移顺序和算法以 [Master Plan](../MASTER_UI_UX_REBUILD_PLAN.md) 为唯一施工依据；不得直接从本稿选择不同方案。

# Search Research and Executable Architecture — 2026-11-12

Scope: read-only research for R09/R10/R14/R15/R16. No business code, database, deployment or commit changes. Baseline is 6b83e29. Relative paths refer to /home/eh/precision-study-ui-20261111. Proposed files/models explicitly marked NEW are future work. This document is evidence and detailed specification to integrate into the Master Plan.

## 1. Established code and production facts

### 1.1 Technology and corpus

- requirements.txt:1 constrains Django >=4.2,<5.0; DRF >=3.15,<4; psycopg >=3.2,<4. time_server/settings.py:130–143 uses DATABASE_URL or SQLite fallback. Preserve SQLite development/tests.
- Parent-supplied read-only production_readonly.json: PostgreSQL 15.19 primary; pg_trgm 1.6 and unaccent 1.1 available, neither installed. Drill migration0035, Tracker0021. Re-read migration heads before assigning future migration numbers.
- EI:2,889 Question rows,2,830 practiceable,296 prompt nonempty,0 latex nonempty;2,593 image/296 markdown. Drill:6,392 rows,5,847 practiceable,5,861 prompt nonempty,0 latex;2,880 image/1,817 mixed/1,695 text. Nonempty text is NOT evidence of OCR accuracy or complete body coverage.
- Question relation with indexes15,736,832 bytes; Topic901,120; Document147,456. Existing indexes on these tables all B-tree, no search index.
- No relevance judgments/qrels exist in this research. No claimed accuracy improvement. Baseline timings, if collected by parent, are low-sample SQL measurements and must not be represented as robust HTTP p95.
- drill/models.py:12–92 defines workspace/title/display_title/filename and topic hierarchy; :95–232 defines stable UUID, labels, prompt/latex/content_mode, document/topic/similarity_topic, question_order, classifications.
- drill/management/commands/import_ei_paired_pdfs.py:551–563 intentionally writes empty prompt/latex and image mode. Search must work from metadata without promising hidden image-body recall.
- drill_sources/models.py:6–23 has SourceQuestionAnchor O2O to a real Question with label/key/source image pointer. Index child label/key, not all parent-page text into every child.
- Existing reviewed metadata: drill/data/{circuit,signal,analog,digital,communication}_selected_v1.json, loaders e.g. drill/signal_selected.py:12–22. Reuse included records' label, bucket title, tags only after UUID+fingerprint validation. Do not index excluded/pending reasons or answers as question body. Do not reclassify questions.

### 1.2 Actual chains and defects

| Chain | Real implementation | Required change/protection |
|---|---|---|
| Practice input | frontend/drill/src/views/PracticeView.vue:66–80,95–150:400ms debounce, AbortController, sequence guard; q sent only length>=2;1-character input retains stale results | Keep existing cancel infrastructure; allow Han1/2 and single technical symbol; IME guard |
| Local suggestions | PracticeView.vue:51–63,152–162: cached book/topic includes; choosing sets filters and clears q | Distinguish query suggestion from book/topic filter action |
| URL/recovery | PracticeView.vue:117–121,170–199: localStorage fallback, reads selected URL fields, no filter URL sync; marker missing persisted payload | Canonical applied URL, scoped fallback, preserve all filters/scroll/selection |
| Cache/auth | runtimePath.ts:42–56, api.ts:16–40, workspace.ts:77–96,129–140 | Use existing prefix/API/user isolation/cache invalidation |
| List API | drill/urls.py:73; views.py:646–694: OR icontains labels/prompt/similarity_topic; book/latex absent; source order;24/page | Rich membership/relevance, all old payload keys, unchanged pre-type-filter type_statistics |
| Navigation | drill/views.py:214–251 duplicates old q predicate; :402–515 intentionally uses source order/fallbacks | One membership helper; retain next/previous order and mature fallback semantics |
| Insight | views.py:1796–1972; InsightView.vue:42–50,84–125: separate Attempt/Note pagination; metadata+private Note matching | No Attempt dedup; keep recent/oldest default; owner-scoped Note search |
| Timer global | frontend/src/components/GlobalSearch.vue:33–57 has220ms/version but no abort; tracker/api_views.py:619–717; time_server/urls.py:114 | Only completed personal sessions/issues, not question bank; retain response kinds/time order |
| Timer history | tracker/api_views.py:76–146; HistoryView.vue:82,124–144 | Parameter search rather than q; preserve server pagination |
| Privacy | tracker/models.py:119,239–243,560–595; api_views.py:101–111,643–679; data_encryption.py:198–240 | At-rest encrypted personal text must never produce shared plaintext search index/log/cache |

## 2. Official research and chosen architecture

Sources actually opened:

- PostgreSQL15 pg_trgm: https://www.postgresql.org/docs/15/pgtrgm.html
- FTS control/dictionaries/indexes: https://www.postgresql.org/docs/15/textsearch-controls.html ; https://www.postgresql.org/docs/15/textsearch-dictionaries.html ; https://www.postgresql.org/docs/15/textsearch-indexes.html
- Django4.2 search: https://docs.djangoproject.com/en/4.2/ref/contrib/postgres/search/
- GIN operator classes/JSON operators: https://www.postgresql.org/docs/15/gin-builtin-opclasses.html ; https://www.postgresql.org/docs/15/functions-json.html
- Concurrent index/migrations: https://www.postgresql.org/docs/15/sql-createindex.html ; https://docs.djangoproject.com/en/4.2/ref/contrib/postgres/operations/
- Unicode: https://docs.python.org/3/library/unicodedata.html ; https://www.postgresql.org/docs/15/functions-string.html
- Isolation/transactions: https://www.postgresql.org/docs/15/transaction-iso.html ; https://docs.djangoproject.com/en/4.2/topics/db/transactions/
- Input: https://developer.mozilla.org/en-US/docs/Web/API/AbortController ; https://developer.mozilla.org/en-US/docs/Web/API/Element/compositionend_event

Engineering conclusions, not claims about other products' private backend:
- pg_trgm is useful for Latin vocabulary typo candidates. Its punctuation-insensitive character trigrams do not encode Chinese short-word or formula meaning.
- Built-in FTS has vectors/weights/GIN, but a plain English/simple configuration is not an educational Chinese segmenter. English stemming/stop words can mishandle technical tokens such as Z.
- GIN jsonb_ops supports key existence and any/all-key operators. JSONField enables portable model state; PG supplies the production inverted index. jsonb_path_ops must NOT replace jsonb_ops for this design.
- Concurrent indexes need non-atomic migrations and explicit invalid-index checks.
- Normalize searchable copies only; tokenizing math before NFKC prevents loss of superscript meaning.
- Search response count/page should share a PG snapshot; app-wide isolation changes are unnecessary.
- Abort and IME handling complement debounce; none replaces monotonic response guards.

| Alternative | Decision |
|---|---|
| OR icontains | Preserve behind rollback flag only; not accepted final quality |
| Whole-body trigram | Reject: long noisy text dilutes short queries; weak Chinese/formula semantics |
| FTS alone | Reject as sole architecture; explicit segmentation still required |
| Chinese PG extensions | Additional server/dictionary maintenance unjustified at9,281 records |
| JSON lexeme GIN + field recheck + bounded vocabulary typo expansion | RECOMMENDED |
| Elasticsearch/Meilisearch/new OCR | No new infrastructure; revisit only after measured10× corpus failure and separate architecture decision |

## 3. Prescribed new modules and schema

NEW drill/search/{__init__,normalize,query,index,postgres,sqlite,service,suggestions}.py; NEW drill/data/search_aliases_v1.json. Model definitions go in existing drill/models.py.

### QuestionSearchDocument (disposable derived data)

- question: OneToOneField Question, primary_key=True,CASCADE,related_name search_document.
- workspace: CharField16/indexed, rechecked against live document.
- schema_version: PositiveSmallIntegerField1.
- source_hash: CharField64 SHA256 of indexed source fields+manifest/alias versions.
- labels_norm,book_norm,topics_norm,body_norm,formula_norm: TextField. Field boundaries U+001F; phrase check cannot join different fields.
- identifiers: JSONField list of exact UUID, normalized source/anchor label/key and qualified source numbers. question_order is NOT automatically the printed number.
- terms: JSONField object key→bitmask. Bits label1/book2/topic or approved metadata4/body8/formula16/identifier32. Example terms: zh1:导, zh2:导数, en:fourier, concept:fourier_transform, math:partial. Multiple source occurrences OR masks.
- coverage: JSONField booleans has_prompt/has_latex/has_anchor/has_reviewed_metadata and evidence labels. No assertion that nonempty prompt is correct OCR.
- indexed_at: DateTimeField.

Never store user Note, Attempt, marker, mastery, timing or account data here. Never silently truncate indexed source/terms. Backfill records maxima; if a pathological source exceeds100,000 code points, preflight fails with count/UUID and implement derived chunk rows before rollout. No record may be silently skipped.

### QuestionSearchLexeme

id,workspace,term CharField120,kind latin|concept|book|topic,display,document_frequency,target JSON,target_key CharField,schema_version. Unique(workspace,kind,term,target_key). Latin vocabulary:3–48 letters/alphanumeric terms from metadata and prompt occurring>=2 documents; one-occurrence technical terms allowed only if reviewed aliases identify them. Exclude noisy single-use OCR tokens from typo expansion.

### QuestionSearchDirty and QuestionSearchState

Dirty: question O2O PK,revision bigint1,enqueued_at. State: workspace unique,schema_version,generation bigint,aliases_hash,manifest_hash,last_completed_at,rebuilding bool. All are derived; existing records untouched.

### Required PG indexes

    CREATE INDEX CONCURRENTLY drill_search_terms_gin
      ON drill_questionsearchdocument USING gin (terms jsonb_ops);
    CREATE INDEX CONCURRENTLY drill_search_ws_schema
      ON drill_questionsearchdocument (workspace, schema_version, question_id);
    CREATE INDEX CONCURRENTLY drill_lexeme_term_trgm
      ON drill_questionsearchlexeme USING gin (term gin_trgm_ops)
      WHERE kind = 'latin';
    CREATE INDEX CONCURRENTLY drill_lexeme_prefix
      ON drill_questionsearchlexeme (workspace, kind, term varchar_pattern_ops);

TrigramExtension only after role/availability verification; unaccent not required. PG-only indexes/triggers use vendor-guarded database operations with SeparateDatabaseAndState. Plain JSONField model/ordinary indexes remain SQLite-compatible. State must match models; makemigrations --check must pass. Concurrent operations migration atomic=False, no surrounding transaction. Verify pg_index.indisvalid/indisready. A failed index with same name is not repaired by IF NOT EXISTS.

## 4. Exact normalization/query semantics

NORMALIZER_VERSION=1. normalize_document/query share pure functions; raw source and input unchanged.

1. Extract formula runs and LaTeX macros before prose NFKC. No TeX execution/eval; no user regex.
2. Prose: decode HTML entities once; remove Markdown formatting while keeping content/code words; NFKC+casefold; NBSP→space; collapse whitespace; remove invisible format controls. Preserve operators/sign differences. Chinese compact copy ignores whitespace between Han characters for PDF line-break tolerance; English words keep boundaries.
3. Han indexing: ALL unigrams and overlapping bigrams, no field crossing. One-char query uses zh1 exact; two uses zh2 exact. Unknown>=3-char contiguous phrase uses all bigrams AND, then literal compact phrase verification in one field. This avoids shuffled-gram false matches. No trigram/fuzzy for1/2 Han.
4. Known phrases: longest-match reviewed educational lexicon + complete topic names, then required concept groups AND. Alternatives inside a group OR. Thus 隐函数 偏导数 and 偏导数 隐函数 have same membership. Do not broad-OR every bigram as unrelated keywords.
5. Latin: casefold whole words/technical identifiers; no English stop words. Single Z/R/C exact symbol/token only, no prefix. For every ordinary Latin token, index full en:<token>, prefixes from length2 as enpre:<prefix>, and overlapping character trigrams en3:<gram>. Prefix query>=2 therefore uses direct GIN key, not a truncated vocabulary expansion; contained-token query>=3 uses all en3 grams then verifies substring inside an actual token. No candidate or prefix vocabulary truncation. Exact whole tokens rank above prefix then contains. For tokens>48 characters, preserve full exact token and trigrams; prefix keys first48 characters, with a query>48 using gram recall and exact prefix verification. Max32 vocabulary candidates applies ONLY to typo suggestions below.
6. Seed canonical equivalences: 傅里叶变换/Fourier transform/傅立叶变换; 拉普拉斯变换/Laplace transform; 卡诺图/Karnaugh map/K-map; RS触发器/RS 触发器/RS flip-flop; 负反馈/negative feedback; 波特图/Bode plot; Z变换/Z 变换/Z-transform. Do not equate Fourier series with Fourier transform, or every derivative with partial derivative. Alias JSON has canonical/equivalents/common_typos/workspace/notes/test_ids.
7. English typo fallback only when original exact/prefix result count<5. pg_trgm searches Latin vocabulary with transaction-local similarity threshold0.25, at most32 candidate WORDS. Bounded Damerau-Levenshtein verifies distance<=1 for3–6 letters;<=2 and normalized distance<=.25 for>=7; no fuzzy1/2-letter. Accept max3 alternatives/group sorted distance,frequency,lexical. Original exact hits rank above; UI reports corrected matches; input/URL remain original. All question rows matching accepted alternative terms are uncapped. Chinese>=3 typo correction is suggestion-only from reviewed typo list or dictionary edit-distance1; no silent rewriting.
8. Formula token equivalence: frac/dfrac/tfrac→math:frac; partial/∂→math:partial; int/∫; sum/∑; infty/∞; Greek macro/symbol names. Ignore only layout macros left/right/spacing; unwrap math font/operatorname wrappers retaining words. Preserve operation order, identifiers, superscript/subscript, relational signs. x^2≠x2, x_1≠x1. Unicode superscript runs (e.g.²) become ^{…} and subscript runs (e.g.₂) become _{…} BEFORE NFKC. Normalize U+2212 minus and fullwidth minus to ASCII minus inside formula search copies, without discarding sign. Canonicalize x^2 and x^{2} to the same exponent-group form; x₂ equals x_2, not x2. Do not promise algebraic equivalence or a/b=frac{a}{b}. Unknown macro exact macro:name. Formula field layout whitespace ignored, semantic characters retained. Existing latex fields empty does not remove required future compatibility; prompt Markdown can contain formula text today.
9. Guards: max120 Unicode codepoints,max12 semantic groups; invalid complexity returns400, not silent truncation. Empty q retains browse. Nonempty punctuation-only q returns200 count0 reason=no_terms; never wildcard all. Recognized mathematical symbols can yield exact token search. Parameterize SQL everywhere.

## 5. Retrieval, rank, contracts and state

### 5.1 One candidate membership helper

search_questions(base_queryset,QueryPlan) returns original Question QuerySet with score annotations. Apply authoritative workspace/collection/practiceable/document/topic/source/user-state/marker scope. JSON key predicates provide indexed candidate recall; phrase checks verify compact strings. Never materialize first500 and call it full search/count.

    SELECT q.id
    FROM drill_question q
    JOIN drill_questiondocument d ON d.id=q.document_id
    JOIN drill_questionsearchdocument s ON s.question_id=q.id
    WHERE d.workspace=%s AND s.workspace=%s AND s.schema_version=%s
      AND (s.terms ?& %s::text[])
      AND (s.terms ?| %s::text[])
      AND (position(%s in s.topics_norm)>0 OR position(%s in s.body_norm)>0);

Above is a parameterized pattern; actual query groups compile AND/OR shape from an allowlisted AST. JSONField has_key/has_keys/has_any_keys or narrow reviewed expression class; no user SQL identifiers. High-frequency single char retrieves/ranks ALL matches then SQL LIMIT24/OFFSET. A sequential scan for common terms may be correct planner behavior; do not force indexes.

### 5.2 Rank v1

For each required group choose best matched source priority: identifier8,label6,topic5,book4,formula3,body2. Multiply by100, exact literal100%,canonical alias90%,prefix75%,contains65%,typo60%; integer arithmetic. Sum group scores. Additional boosts: exact full identifier10000,exact readable label4000,whole-query topic1200,book800,label600,body200. Repeated OCR occurrences get no extra boost.

sort=relevance order: exact_identifier desc,score desc,document_id,question_order,pk.
sort=source order: document_id,question_order,pk.
Empty q default source; nonempty default relevance. No mastery/history/personalization rank effects. Score internal, not displayed as fake confidence%.

### 5.3 Existing API retained, additive v2

Keep /api/drill/questions/; runtime prefixes /drill/api/drill/questions/ and /ei/api/drill/questions/. Preserve q,document,topic,source_category,past_exam,unattempted,marker,include_structure,type_group,exam_type and selected collection keys collection/bucket/tier/kind/combined/state/material/course/from. Do not reinterpret selected state as generic status. New optional sort=relevance|source,search_version=2,index_version=opaque. If Filter UI exposes favorite/review_later, use owner-scoped Exists via common filter helper; never index learning state.

Keep page24,count,next,previous,results and all QuestionSummary fields. type_statistics remains AFTER search/non-type filters but BEFORE type filter (drill/test_final_exam_types.py:72–87). Add:
search={version:2,query,normalized_query,index_version,mode:exact|expanded|empty|legacy,reason:null|no_terms,corrected_terms:[],suggestions:[],stale:false,coverage:{metadata_only_count}}.
Optional result search_match={fields,kind:exact|alias|prefix|contains|typo,excerpt,highlights:[[start,end]],coverage:text|metadata}. Excerpt<=160 codepoints; escaped text/mark, never v-html. Metadata hit says metadata, no fabricated question-body snippet.

Feature flags DRILL_SEARCH_BACKEND=legacy|hybrid_v1 and DRILL_SEARCH_SUGGESTIONS=0|1. New client sends2; backend readiness gates enable. Legacy clients retain shape/filters. No user-selectable backend.

NEW /api/drill/search/suggestions/?q=…&limit=8, same auth/prefix; returns query,index_version,results[{kind:query|document|topic,label,query?,filters?,reason}],ambiguous. Clamp1..8; empty q=[]; no saved private search history. Immediate cached-catalog suggestions retained; remote suggestions only focused/local<3. Full search already carries correction suggestions, avoid two expensive queries per key.

Errors:400 input;409 {code:SEARCH_INDEX_CHANGED,index_version,detail} for obsolete continuation;503 only no complete active index when explicitly asking v2; ordinary auth unchanged. Never silently change requested page.

### 5.4 Stable pagination/cache

index_version=schema:alias_hash_prefix:catalog_generation. Increment generation in same transaction as index update. PG one search service read transaction is repeatable-read set BEFORE its first query; count/results/generation share snapshot. Do not change global isolation. Page2+ includes version; if obsolete409, frontend keeps query/filter, resets1 and explains refreshed data. No snapshot kept across requests.

Unchanged index AND user state gives deterministic pages. Attempt/favorite changes intentionally affect filters; existing state event invalidates caches/resets relevant pages. No freezing user state in search index.

Cache key includes sorted applied params,user/workspace,search/index version; max existing5min plus invalidation. No new Redis/server result cache/private query log. Public vocabulary memoization by workspace+generation may use bounded128-entry60s cache.

### 5.5 Practice navigation

Replace BOTH list q predicate and navigation_queryset q block with shared membership helper. Preserve mature source-order next/previous and cross-book fallbacks; relevance listing is not a new practice sequence. Add return-search URL retaining page/filter. Existing selected manifest stays authority; query never widens selection. Test old search/unattempted navigation and new alias/typo membership.

### 5.6 Insight/Timer privacy

Insight metadata uses shared question membership; Attempts retain IDs and chronology, Note list independently searches owner Note via private normalized literal/token-AND matcher. No shared indexing of notes.

Timer input gains IME/AbortController guards, existing /api/search kinds and chronological semantics remain. Unicode/token-AND/synonym matcher runs INSIDE owner-scoped search; unencrypted may SQL-prefilter+verify, encrypted streams only own records via established decryption. No plaintext index/long-lived cache. No early newest-N cap;10k-own/10k-other-user fixture validates latency/isolation. If this cannot meet gate, architecture must be revised with privacy-aware design before claiming R10 done, not silently skip encrypted search.

## 6. Frontend Search/Filter state

NEW frontend/shared/search/queryState.ts (pure), NEW frontend/drill/src/composables/usePracticeQuery.ts. Canonical applied URL, draft input separate<=250ms. Allowlist params, retain selected context. Enter immediate except composing; Escape closes suggestions not input; clear resets page1 once. compositionstart cancels debounce/request; compositionend schedules once. Increment request version WHEN INPUT CHANGES to prevent response painting in debounce interval; AbortError silent, non-abort only current token may set error; unmount abort.

router.replace for typing and immediate filter edits, push for explicit suggestion/navigation; avoid one history entry per filter checkbox. Stable query key serialization; page1 omitted. Filter controls retain existing immediate-apply semantics. Each deliberate control change commits URL/filter state and starts one superseding request; dependent changes (e.g. book resets invalid topic) are batched as one commit. Done/Escape/backdrop only close the panel and never revert applied filters. Clear commits one reset immediately. No extra Apply step or draft-state UI; this preserves current operation cost. Filter count=nondefault semantic groups, q/sort excluded. One compact removable-summary row; internal horizontal scroll if needed, never viewport overflow. All book/topic/type/source controls in Filter panel; no colored-card taxonomy. If retaining quick state control<=4 options, justify direct frequent use.

Persist scroll/selected UUID per user/workspace/canonical query. Migrate old key only into current workspace after ID validation, never override explicit URL. Restore after data+nextTick then animation-frame measurement; no repeated jump once user scrolls. Existing learningRecovery remains PWA authority.

Input combobox/listbox keyboard semantics, up/down/Enter/Escape, polite results announcement, touch input>=16px. Desktop40px/coarse pointer44px controls. Popover>=768px, modal sheet<768px; viewport-constrained max height, sticky Done, safe-area/visualViewport keyboard handling, correct focus return. User-facing search coverage distinguishes metadata/body.

## 7. Sync and migration rollout

### 7.1 Bulk update protection

Imports use bulk_update/.update (import_question_bank.py:136; import_ei_honey_pdfs.py:251–260) and Question has no general updated_at. Signals alone are insufficient.

PG triggers enqueue to NEW Dirty table only:
- Question INSERT/relevant UPDATE; source-hash-affecting fields only, OLD/NEW IS DISTINCT FROM.
- Document title/display/workspace updates enqueue document questions.
- Topic title/display/normalized/parent updates enqueue document questions to cover ancestor paths.
- SourceAnchor insert/update/delete enqueue child IDs.
- Question delete cascades derived rows.
Manifest/alias file changes detected by hashes, enqueue relevant workspace before activation.

NEW rebuild_question_search command: --workspace drill|ei|all --batch-size100 --resume --verify --dry-run. Dry-run no writes; ordinary run writes derived tables only.
NEW process_question_search_queue: --batch-size100 --max-seconds45, advisory lock single worker. Capture dirty revision, build current source, transactional upsert then delete dirty only captured revision, increment generation; concurrent source change remains queued.
NEW deploy/ha systemd timer every30s executes existing web-image command; no Celery/Redis. Normal freshness<=60s.

Worker failure keeps complete active index readable; search.stale=true while dirty and quiet “资料更新中，搜索可能暂未包含最新内容”. This is explicit bounded staleness, not hidden candidate truncation. Hybrid cannot enable with incomplete initial index. Full tokenizer/alias rebuild temporarily switches the search backend to legacy, runs the resumable full derived rebuild, verifies all rows/queue/hash/readiness, increments generation and switches hybrid back on. UI reports temporarily simplified search. Initial release does not implement an unspecified shadow-table swap. Normal incremental indexing remains<=60s. Daily source_hash reconciliation batches all rows, enqueues missing/mismatch/orphans; not just timestamp assumption.

SQLite skips PG triggers; test fixtures invoke builder/hook shim. Production trigger/race semantics tested on PostgreSQL15 separately.

### 7.2 Safe sequence

1. Re-read HEAD/migration/PG/role/disk; backup+restore rehearsal. Record source/UUID/classification/Attempt/Note/timing counts and deterministic invariants privately.
2. Add plain models/dirty triggers with legacy flag; backward-compatible deployed backend. No source mutation.
3. Extension+concurrent index migration, non-atomic. Inspect validity; failed new index dropped/retried, never fake state.
4. Rebuild batch100/resume; drain queue; vocabulary; verify all intended records including structures if include_structure; hashes/manifest resolution/sample normalized terms.
5. ANALYZE new tables; qrels/performance tests on staging; limited read-only production EXPLAIN; clean indexes/queue.
6. Activate hybrid then new frontend; Drill/EI/prefix/filter/navigation smoke; timer on; legacy/image retained>=7days.
7. Rollback flag+image first; leave additive derived tables. Stop worker if necessary. No immediate destructive down migration. Later approved cleanup removes new triggers/indexes/tables; don't drop shared extension.
8. Never restore old database over ongoing learning writes merely because search rollout failed. Actual data corruption follows separate incident restore plan.

## 8. Relevance and performance evaluation

### 8.1 Dataset and judgments

NEW tests/search/queries.v1.jsonl and qrels.v1.jsonl contain synthetic/public metadata only; real private qrels live in release artifacts. Query fields id/workspace/q/filters/intent/category/expected_behavior; judgments query_id/question_uuid/grade0..3/reason/judge/source_coverage.

At least60 queries, each evaluable nonempty query has>=20 judged pooled candidates: union legacy/new top20 + independent book/topic/keyword positives. Grade3 exact concept/identifier,2 direct relevance,1 tangential,0 unrelated. Blind retrieval system; dual review20% and disagreements. Unanswerable corpus queries explicitly labeled, not fabricated positives. Image-only subset separate. Pooled Recall is not all-corpus recall.

### 8.2 Mandatory seed query groups

| IDs | Cases |
|---|---|
| S-Q01–05 | 多元微分,偏导数,导数,隐函数,导 single Han |
| S-Q06–09 | 傅里叶变换,傅立叶变换,Fourier,fourier transform; don't silently equate Fourier series |
| S-Q10–13 | Z 变换,Z变换,z-transform,Z exact symbol |
| S-Q14–18 | 拉普拉斯,Laplace,卡诺图,Karnaugh map,K-map |
| S-Q19–23 | RS 触发器,RS触发器,负反馈,Bode,波特图 |
| S-Q24–28 | actual book display/raw title,source label/anchor key,printed number+book,UUID |
| S-Q29–32 | 隐函数 偏导数 vs reverse,Fourier 变换,RS 触发器 逻辑 |
| S-Q33–37 | Fourer,Foureir,Lapalce,Karnaughh,傅里页变换 |
| S-Q38–43 | \partial,∂,\frac{a}{b},\dfrac{a}{b},x^2,x² |
| S-Q44–48 | x ( t ) vs x(t),\left(x\right),unknown macro,x_1,x1 |
| S-Q49–53 | empty,whitespace,special wildcard punctuation,emoji-only,SQL/HTML-looking |
| S-Q54–60 | multi-filters,marker userA/B,selected scope,page cycle,generation409,metadata-only image,fullwidth/NBSP |

Synthetic negative fixtures: same term only in answer,another user's Note,other workspace,source-anchor sibling or excluded outline. These must not leak into wrong query scope.

### 8.3 Quantitative release gates — targets, not measured facts

- Exact-ID top1=100%; alias target top3=100% synthetic; cross-user/workspace leakage0; count/page inconsistency0.
- Judged actual corpus nDCG@10>=.85; when baseline<.85 gain>=.15, otherwise no regression. Pooled Recall@20>=.90, P@10>=.80 technical multi-term, MRR@10>=.90 navigational. Report denominators/pool limits. Broad single-Han tested exact full match-set equality in synthetic data, not an impossible universal precision guarantee.
- English typo target top5>=90%, wrong automatic correction<=5%;1/2Han auto rewrite0. Metadata-known image subset Recall@20>=.90; hidden image-body text outside searchable evidence.
- Same resource-class current-corpus authenticated HTTP:5warmups+30requests/query,concurrency1/5; warm p95<=250ms,p99<=750ms; suggestions p95<=150ms; first-after-app-restart p95<=1s. Last committed keystroke→results<=650ms at controlled100ms RTT including250ms debounce. Thresholds not silently lowered.
-10× synthetic corpus~93k records with similar text distribution,concurrency5:p95<=500ms,p99<=1.5s,max2s. No all-corpus Python ranking in production question engine, no forcing planner enable_seqscan=off.
- Normal sync<=60s; interruption/resume/racing update no lost queue row; fixed-version pages duplicate0. Cache/network/render metrics separate.
- Personal Timer10k-owner fixture p95<=500ms, no search only newestN. Failure requires explicit remaining architecture work.

### 8.4 Benchmark procedure

NEW benchmark_question_search command --backend legacy|hybrid_v1 --queries PATH --qrels PATH --repeats30 --concurrency1 --output PRIVATE_PATH. No writes; IDs/scores/timings not body/notes; same service+authorization scope. Staging synthetic test user; production read-only context uses existing authorized user without creating login/timing state.

JSON output: SHA,DB version,corpus count/hash,schema/alias/index version,server CPU/RAM/storage,timestamp,concurrency,query IDs,count,top20UUID,DB/serialization/HTTP timings,median/p95/p99,error count,quality metrics. Before/after use SAME snapshot.

EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) for common1Han,rare2Han,long multi-concept,English typo,mixed filters,deep page. Production statement_timeout1s,staging2s. Record new relation sizes/backfill time; invariant comparison confirms source/business data unchanged. Parent's3sample baseline can establish real current behavior but is not this release gate.

## 9. Task/test/file handoff

| Task | Files/dependency | Completion evidence |
|---|---|---|
| SEARCH-00 | Phase0 read-only baseline | S-BASE01 aggregate,S-BASE02 qrels+legacy metrics |
| SEARCH-01 | NEW normalize/query/alias/fixtures | S-N01–16 Unicode/Han/English/formula/negative pairs |
| SEARCH-02 | models+migrations+worker/triggers;depends01 | S-DB01 PG+SQLite migrations,S-DB02 index validity,S-DB03 bulk/race/resume,S-DB04 rollback invariants |
| SEARCH-03 | NEW PG/sqlite/service;views list+navigation;depends02 | S-API01 filters,S-API02 count/page24,S-API03 scope,S-NAV01 synonyms,S-TYPE01 statistics,S-PAGE01 version |
| SEARCH-04 | NEW suggestions+urls;depends03 | S-SUG01 typo,S-SUG02 prefix/contains full recall,S-SUG03 auth/prefix |
| SEARCH-05 | PracticeView,NEW composable/queryState,workspace,types;depends shared UI+03 | S-UI01 IME/debounce/abort,S-UI02 URL/cache/back,S-UI03 immediate filters/Done closes,S-UI04 loading/empty/error |
| SEARCH-06 | Insight+views helper;Timer GlobalSearch/api_views private helper | S-PRIV01 Attempt/Note,S-PRIV02 encryption,S-PRIV03 account isolation |
| SEARCH-07 | NEW benchmark/qrels;independent review | S-QUAL01 all metrics,S-PERF01 current/10× |
| SEARCH-08 | NEW search-index timer+deploy docs;after07 main only | S-DEPLOY01 migration,S-SMOKE01 paths/auth,S-ROLL01 rollback |

Preserve existing drill/test_navigation_queries.py, drill/tests.py:533, drill/test_final_exam_types.py, tracker/tests.py:1410–1438 and1894–1914, API-isolation/workspace tests.
NEW drill/test_search_normalization.py,test_search_api.py,test_search_postgres.py,test_search_index_sync.py; frontend/drill/src/views/PracticeView.search.test.ts;frontend/shared/search/queryState.test.ts;Timer global-search tests. PG15 tests mandatory, not replaced by SQLite.

## 10. Risks/evidence gaps

- No full OCR/body-quality audit; cannot promise search hidden image content. Metadata coverage labels honest.
- Ranking constants v1 may need evaluation-driven change using held-out split; do not tune held-out and claim unbiased result.
- JSON GIN performance requires actual current/10× proof; recommended architecture is reasoned design, not measured victory over FTS.
- Trigger install lock_timeout2s and fail cleanly; do not alter learning tables. At-rest private search remains distinct security boundary.
- Production role pg_trgm permissions, personal corpus volume and authenticated HTTP harness require Phase0 verification.
- Django4.2 official docs now warn unsupported release. Record separate maintenance risk, don't silently upgrade stack during UI/search work.
- Source number not always question_order; use source labels/anchor metadata and book qualification.
- Strict complete recall can't be measured without judging every corpus row; report pooled metrics and exhaustive synthetic tests honestly.

### Read-only normalization probe executed in this research

A standalone Python unicodedata probe (no repo/DB writes) confirmed: fullwidth Ｆｏｕｒｉｅｒ→fourier; Z+NBSP+变换→z 变换; naïve NFKC maps BOTH x² and x₂ to x2, while x^2 and x_2 remain distinct; U+2212 minus remains different from ASCII minus. This directly supports math-token extraction and explicit superscript/subscript/sign handling before prose normalization. It is not an implemented search test or search-quality benchmark.


## 11. Measured baseline and mandatory query pipeline optimization

Parent executed production read-only SQL baseline stored in search-baseline.json. Each sample is current queryset count plus evaluation of the first24 annotated Question objects. No HTTP, serializer, or type_statistics timing is included;3 samples/query are insufficient to estimate a trustworthy tail percentile.

| Workspace/query | Count | Median ms | Max ms |
|---|---:|---:|---:|
| Drill 导数 |455|1445.51|1471.19|
| Drill 隐函数 |95|432.69|524.26|
| Drill 多元微分 |134|498.21|619.80|
| EI 傅里叶变换 |58|942.43|1089.56|
| EI Fourier |0|675.20|784.16|
| EI RS 触发器 |0|729.31|775.46|

Zero matches still execute the count and slice SQL with repeated multi-field OR substring predicates and joins. With no search index, an empty result does not imply cheap work. It CANNOT be explained as24-object hydration or serializer work: there are no objects and no serializer in those samples. Without EXPLAIN/CPU/I/O evidence, do not attribute a measured percentage of latency to a specific component.

Code-proven expensive query shapes:
- with_exam_type (drill/exam_types.py:15–21) is an O2O LEFT JOIN + Coalesce/Case, not itself a correlated subquery.
- question_progress (drill/views.py:54–75) adds an Attempt join, two Count aggregates, two Exists and three scalar state/latest subqueries. Applied before LIMIT, this produces an aggregate query selecting all Question columns, including large text. PostgreSQL may collapse GROUP BY to primary keys using functional dependency; do not claim all columns literally appear in GROUP BY without compiling SQL.
- Full API additionally executes queryset_type_statistics (exam_types.py:56–64), selecting every candidate's latest result and counting in Python. This was excluded from the measured baseline and can add work.
- Existing QuestionSummarySerializer (serializers.py:12–73) does not need prompt/latex/answers; pdf_pages_for does need fingerprint (drill/ei_selected_pdf_pages.py:16–20). Page hydration must include that field to prevent N+1 fetches.

### 11.1 Prescribed execution stages

Stage A, thin membership:
Build canonical non-type scope from original Question/document and necessary owner-scoped state predicates; retrieve only question_id,document_id,question_order,final_question_type,integer rank. Hybrid search terms join only derives membership/rank. Marker/favorite filters use Exists to avoid row multiplication. No question_progress, all-body selection, select_related object hydration or Count joins. Preserve collection helpers and their scope exactly.

Stage B, SQL scope statistics and exact page count:
Compute final_type + latest result for this PRE-TYPE candidate set, using a lateral latest row or a filtered DISTINCT ON subquery on PostgreSQL; SQLite uses the equivalent scalar Subquery. Aggregate by final_question_type into <=6 rows:
total = count(*)
attempted = count(*) FILTER (WHERE latest_result IN ('done','correct','review'))
mastered = count(*) FILTER (WHERE latest_result IN ('done','correct'))
review = count(*) FILTER (WHERE latest_result='review').
No Attempt or reset is unattempted. Fold final types into existing small/large/short_answer/unknown response groups. Derive post-type exact total by summing only rows allowed by the intersection of type_group and exam_type. This preserves pre-type type_statistics while avoiding a second expensive count and avoids downloading N candidate state rows.

Illustrative structure (identifiers/filters fixed, values parameterized):
    WITH candidate AS MATERIALIZED (
      SELECT q.id, q.document_id, q.question_order,
             COALESCE(e.question_type, CASE q.question_type
               WHEN 'single_choice' THEN 'choice'
               WHEN 'fill_blank' THEN 'fill'
               WHEN 'solution' THEN 'large'
               ELSE 'unknown' END) AS final_type
      FROM ... authoritative non-type scope and indexed query membership ...
    ), scoped AS (
      SELECT c.*, a.result AS latest_result
      FROM candidate c
      LEFT JOIN LATERAL (
        SELECT result FROM drill_questionattempt
        WHERE user_id=%s AND question_id=c.id
        ORDER BY created_at DESC,id DESC LIMIT 1
      ) a ON TRUE
    )
    SELECT final_type,count(*) AS total,
      count(*) FILTER(WHERE latest_result IN ('done','correct','review')) AS attempted,
      count(*) FILTER(WHERE latest_result IN ('done','correct')) AS mastered,
      count(*) FILTER(WHERE latest_result='review') AS review
    FROM scoped GROUP BY final_type;

The above query is structural, not a complete runnable replacement: the authoritative scope compiler supplies FROM/WHERE. If an unattempted filter is applied, reuse this SAME latest result before aggregation, not a second identical scalar lookup. A known empty candidate scope returns zero stats/count immediately and skips page/hydration; it must not rerun a full empty search query.

Stage C, page IDs only:
Apply type filter to thin membership, deterministic rank/source order, LIMIT24 OFFSET. Only IDs/order/rank leave database, not source text or current notes. Full candidate membership and count remain uncapped. If statistics post-type total0, skip this stage. Paginator adapter must use precomputed count; never PageNumberPagination over the hydrated aggregate QuerySet (which reintroduces count of an aggregate).

Stage D, hydrate only page24:
Question.objects.filter(pk__in=page_ids), select_related document/similarity_topic, then existing question_progress (restricted to24) and only serializer fields:
id,uuid,document_id,similarity_topic_id,question_order,source_label,display_label,is_past_exam,source_category,record_kind,exam_year,exam_variant,question_type,fingerprint;
document id/title/display_title; similarity_topic id/title/display_title.
Annotation values remain selected. Build ID→row map and serialize in exact page_ids order. No prompt,latex,answer text,QuestionAsset.data or PDF binary. Assert SQL count does not grow with page size and no serializer deferred-field N+1.
Existing private saved_note field stays for compatibility; do not use it for shared rank/cache scope.

All stages occur within the specified narrow repeatable-read snapshot. q-free browse also benefits from the thin→stats→IDs→hydrate pipeline; it must not force search index use.

### 11.2 Supporting latest-state index

Existing models.py:513–516 has (user,question) and(user,created_at), but no ordered composite latest index. Inspect production QuestionAttempt index catalog before adding; if absent create concurrently:
    CREATE INDEX CONCURRENTLY drill_attempt_latest_search_idx
    ON drill_questionattempt(user_id,question_id,created_at DESC,id DESC)
    INCLUDE(result);
This is an additive read optimization, no learning row mutation. Migration state and SQLite vendor handling follow the other indexes. Do not delete old indexes in this rebuild. Measure write-overhead and storage; latest tie-breaking -created_at,-pk is unchanged.

### 11.3 Performance evidence required

Separate timers for scope/normalization, StageB stats/count, StageC IDs, StageD hydrate/serialize, and whole HTTP. Initial planning budgets under warm current corpus: scope+rank50ms,stats60ms,pageIDs40ms,hydrate+serialize60ms,remaining20ms; these are diagnostics budgets, not additive excuses or measured results. Total p95<=250ms remains the release gate. If it fails, EXPLAIN (ANALYZE,BUFFERS) on isolated staging first; identify plan/data/CPU cause before changing budgets. Do not call a20ms bare GIN query a successful250ms complete API.

Test S-PERF02: query instrumentation verifies no source-body select before page IDs, no hydration when count0, no aggregate count by paginator, <=24 Question objects hydrated, constant query count, type_statistics identical to legacy fixture for every type and state. Source/Attempt/user-state hashes unchanged. No more production diagnostics were executed for this follow-up.
