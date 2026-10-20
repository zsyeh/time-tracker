# EI past-paper answer rollout, 2026-10-21

Scope: existing UCAS circuit, electronics and 859 books (documents 24–26),
82 original paper records, 1,342 indexed questions. This is not a claim that
all source indices or all answer boundaries have been verified.

## Global presentation

All indexed children expose the original-paper/full-answer entry. A matched
answer displays independently even when its question must still use the shared
full-page viewer. Unmatched answers are explicitly labelled as awaiting review;
full original answers remain lazily accessible. Missing original answers are
labelled as missing, not generated. The reviewed 2018 859 answers remain intact.
Known index/reference defects have visible warnings and deterministic exclusions
in `drill_sources/data/past_exam_answer_review.json`.

## Content coverage

The batch manifest adds 295 individual answers (425 full-width regions):
19 circuit, 78 electronics, 198 signals. Together with the 30 previously reviewed
2018 signal answers, this yields 325/1,342 independently cropped answers.
The new PNG payload is 70,184,748 bytes (database overhead excluded).
The remaining 1,017 are deliberately not presented as matched individual answers:

| Review reason | Count |
| --- | ---: |
| Missing answer anchor | 525 |
| Ambiguous/repeated answer anchor | 106 |
| Unverified interval | 103 |
| Unverified final interval | 29 |
| No safe full-width blank boundary | 196 |
| Original source has no answer | 45 |
| Invalid old question index | 11 |
| Reference subquestions differ | 1 |
| Boundary outside original answer region | 1 |

No source question, original image, old crop, revision, attempt, note or mastery
record is deleted/replaced. The renderer only inserts answer assets under stable
answer-specific source IDs, transactionally and idempotently. Conflicting crops
are refused. No database migration is needed. 2002 electronics must be reindexed
with review before matching: the existing index includes exam instructions and
mistakes judgement subitems for top-level questions. 2010 signals question 3 has
a reference with different subquestions; it is not imported as an exact solution.

## Reproduction and QA

603 unique answer pages: 374 existing recognition caches reused; 229 missing
scanned pages processed by local OCR. Narrow-margin OCR independently checks
printed anchor identities. Reliable text layers bypass OCR. This analysis does
not reconstruct equations or send whole books to a model.

```sh
python manage.py build_source_answer_regions /path/to/merged-index.json \
  --source-manifest /path/to/exams/manifest.json \
  --source-manifest /path/to/signals/manifest.json \
  --ocr-cache /path/to/cache --margin-cache /path/to/margins \
  --output /path/to/candidates.json
python manage.py render_source_question_regions \
  drill_sources/data/past_exam_answers_20261021.json \
  --source-dir /path/to/exams/sources --source-dir /path/to/signals/sources \
  --asset-type answer_crop --dry-run
```

The shipped batch excludes previously installed 2018 crops rather than replacing
their manually reviewed geometry. Candidate generation is not automatic approval:
24 stratified question/answer top/bottom samples were inspected, including circuit
diagrams, handwritten solutions, long cross-page derivations and waveforms. The
known bad index/reference cases were rejected after this sample. Geometry tests
preserve full width, check every crop against the PDF and prevent crossing the
next positively identified question. Unknown/missing identities remain in review.

Remaining work is substantive source/index and crop review, not a UI switch.
In particular 45 indexed entries belong to four source papers with no supplied
answer regions (2001 circuit and the three 2024 electronics sections).
