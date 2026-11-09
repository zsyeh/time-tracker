# EI / Drill original exam-form classification

This pipeline runs on the local NUC. It does not call an API from Django and
does not overwrite `Question.question_type`, which remains in use by paper
generation. `QuestionExamType` is an independent audited result table.

The final classification is authoritative for practice, heatmaps, selected
collections, learning shares and type statistics. All candidates are imported,
including `unknown` and `review_required=true`. Audit flags and `review_reasons`
never gate imports, reads or type filters. Unknown remains unknown; the legacy
field is used only when no final classification record exists.

Small questions mean choice, fill and judgment. Short answers have their own
filter; large means a worked solution. Practice navigation retains these filters.

## Read-only snapshot

The query in `scripts/exam_type_snapshot.sql` exports only question metadata,
asset hashes and a boolean indicating whether anyone submitted the question.
It never exports image bytes, answers, notes or credentials. Run it from the
local NUC against the authoritative 47 database with a read-only transaction:

```bash
mkdir -p ~/learning-type-audit
chmod 700 ~/learning-type-audit
ssh root@47.95.10.128 'set -a; . /var/snap/docker/common/time-tracker-ha/secrets/database.env; set +a; PGOPTIONS="-c default_transaction_read_only=on" psql "$DATABASE_URL" -qAt' \
  < scripts/exam_type_snapshot.sql > ~/learning-type-audit/questions.jsonl
```

Do not place the snapshot or `~/.api_key_secret` in Git. The key file must
contain one raw API key and have mode 0600. Install the official Python SDK in
a private local virtual environment: `python3 -m venv ~/learning-type-audit/.venv`
and `~/learning-type-audit/.venv/bin/pip install 'openai>=2,<3'`.

## Validation and small trial

```bash
python3 scripts/exam_type_classification.py prepare \
  --input ~/learning-type-audit/questions.jsonl \
  --output-dir ~/learning-type-audit/trial-v2 --size 300

PY=~/learning-type-audit/.venv/bin/python
$PY scripts/exam_type_classification.py run \
  --input ~/learning-type-audit/trial-v2/validation_sample.jsonl \
  --output-dir ~/learning-type-audit/trial-v2 --effort none --limit 70 \
  --concurrency 10 --force-ai
$PY scripts/exam_type_classification.py run \
  --input ~/learning-type-audit/trial-v2/validation_sample.jsonl \
  --output-dir ~/learning-type-audit/trial-v2 --effort low --limit 70 \
  --concurrency 10 --force-ai
$PY scripts/exam_type_classification.py followup \
  --input ~/learning-type-audit/trial-v2/validation_sample.jsonl \
  --output-dir ~/learning-type-audit/trial-v2 --effort low --limit 4
$PY scripts/exam_type_classification.py report \
  --input ~/learning-type-audit/questions.jsonl \
  --output-dir ~/learning-type-audit/trial-v2
```

Watch progress with `tail -f ~/learning-type-audit/trial-v2/run-low.log` or
`tail -f ~/learning-type-audit/trial-v2/run-low-image.log`. `validation_queue.csv`
contains the 300-question human annotation queue. Fill `human_label`,
`annotator` and `evidence` only after inspecting the original question, using
`question_url` for image-only records. Existing verified labels remain marked
`existing_verified`. An AI prediction is never a human gold label.
Regenerating the queue preserves manual labels and rejects labels whose source
content hash changed. Reports from this trial directory count only the current
validation sample, even if older result caches remain in the directory.

The script rejects missing, duplicate or unexpected IDs, invalid workspace
types, malformed subquestion counts and unknown labels without review. It
stores no model confidence number. Hashes include metadata and question-image
SHA-256 values. If a record changes, the old cache entry is ignored. Image
follow-up reads one asset at a time from 47 with a read-only DB transaction,
checks its SHA-256 locally, limits each image to 4 MB, and keeps at most
`--concurrency` images in flight. The production importer reads question and
asset metadata in chunks without loading `image_data`. Image-only decisions
remain review-required even when the model returns a type.

To compare GPT-6.1 Terra on the same validation sample, copy the sample and
queue into a separate private output directory, then prefix the `run` and
`report` commands with `EXAM_TYPE_MODEL=gpt-6.1-terra`. Keep `--effort low`
for a direct comparison. Model IDs are checked before reusing cached AI
results; the report estimates cost using each result's recorded model ID.

## Full run and incremental run — after approval and 300 human labels

Use a new output directory for the production run so validation predictions
do not pollute it. An initial full API run is deliberately gated by
`--full-approved` and must not be started during the audit phase.

```bash
PY=~/learning-type-audit/.venv/bin/python
mkdir -p ~/learning-type-audit/production
$PY scripts/exam_type_classification.py run \
  --input ~/learning-type-audit/questions.jsonl \
  --output-dir ~/learning-type-audit/production --effort low \
  --concurrency 10 --batch-size 25 --full-approved
$PY scripts/exam_type_classification.py followup \
  --input ~/learning-type-audit/questions.jsonl \
  --output-dir ~/learning-type-audit/production --effort low
$PY scripts/exam_type_classification.py export \
  --input ~/learning-type-audit/questions.jsonl \
  --output-dir ~/learning-type-audit/production --effort low
```

For incremental work, re-export the metadata and run the same commands using
the same production output directory. The content hash cache skips unchanged
questions. The report gives per-workspace type counts and proportions,
completed-training counts, review queue size, confusion matrices and API
token/cost estimates. OpenAI response usage is the source of token numbers;
failed requests without retained usage are listed separately and cannot be
claimed as exact billed cost.

## Database import — after a verified backup and migration approval

Before applying migrations `0032_questionexamtype` and `0033_questionexamtype_review_reasons`, create and verify a
PostgreSQL backup and record the rollback procedure. Deploy the tested image,
then run the migration only after explicit approval. The importer defaults to
dry-run and verifies each question's current content hash and workspace. It
refuses stale records before any write. Applying requires an unused 0600
rollback backup path and a batch ID. Each batch is one database transaction.

```bash
python manage.py import_exam_types --input /path/import-candidates.jsonl \
  --expected-workspace-count drill=5837 --expected-workspace-count ei=2798
python manage.py import_exam_types --input /path/import-candidates.jsonl \
  --apply --batch-id exam_form_20261109_01 \
  --expected-workspace-count drill=5837 --expected-workspace-count ei=2798 \
  --backup /secure/path/exam_form_20261109_01.rollback.json
python manage.py import_exam_types \
  --rollback /secure/path/exam_form_20261109_01.rollback.json
```

Rollback refuses to run if any row has been changed by a later batch. No
existing chapter, knowledge-point, difficulty, answer or legacy paper-type
field is modified.

Apply locks the affected question rows, checks all hashes and workspace totals,
upserts every row in batches of 200 and verifies all stored classification and
audit values before committing. A failure rolls back the entire import. The
rollback JSON is private, written and fsynced before any classification write.
`scripts/rehearse_exam_type_import.py` exercises dry-run, repeated full imports
and both rollbacks against an empty, isolated PostgreSQL database populated
from the production metadata snapshot (no image bytes or personal notes).
