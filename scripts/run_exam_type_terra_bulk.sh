#!/usr/bin/env bash
# Local API classification only. Never imports results into the production DB.
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
audit_dir=${EXAM_TYPE_AUDIT_DIR:-/home/eh/learning-type-audit}
snapshot="$audit_dir/questions.jsonl"
output_dir="$audit_dir/production-terra"
python_bin="$audit_dir/.venv/bin/python"

[[ -s "$snapshot" && -x "$python_bin" ]] || { echo 'Missing snapshot or private Python environment' >&2; exit 1; }
mkdir -p "$output_dir"
chmod 700 "$output_dir"
exec 9>"$output_dir/bulk.lock"
flock -n 9 || { echo 'Terra bulk run is already active' >&2; exit 1; }
export EXAM_TYPE_MODEL=gpt-6.1-terra
export PYTHONPATH="$repo_dir${PYTHONPATH:+:$PYTHONPATH}"

phase() { printf '%s %s\n' "$(date --iso-8601=seconds)" "$1" | tee -a "$output_dir/bulk-status.log"; }
verify_base() {
  "$python_bin" - "$snapshot" "$output_dir/results-low.jsonl" <<'PY'
import sys
from pathlib import Path
from scripts.exam_type_classification import content_hash, read_jsonl
snapshot, results = map(Path, sys.argv[1:])
expected = {(r['source_system'], r['question_id']): content_hash(r) for r in read_jsonl(snapshot)}
found = {(r['source_system'], r['question_id']): r for r in read_jsonl(results)} if results.exists() else {}
missing = [key for key, digest in expected.items()
           if key not in found or found[key]['content_hash'] != digest
           or found[key].get('model_id') not in (None, 'gpt-6.1-terra')]
print(f'base_complete={len(expected)-len(missing)}/{len(expected)}', flush=True)
sys.exit(bool(missing))
PY
}

phase 'base classification started'
for attempt in 1 2 3; do
  "$python_bin" "$repo_dir/scripts/exam_type_classification.py" run \
    --input "$snapshot" --output-dir "$output_dir" --effort low \
    --batch-size 25 --concurrency 10 --full-approved
  if verify_base; then break; fi
  if [[ $attempt == 3 ]]; then phase 'base classification incomplete after 3 attempts'; exit 1; fi
  phase "retrying missing base results, attempt $((attempt+1))"
done

phase 'image followup started'
"$python_bin" "$repo_dir/scripts/exam_type_classification.py" followup \
  --input "$snapshot" --output-dir "$output_dir" --effort low --concurrency 10

phase 'report and candidate export started'
"$python_bin" "$repo_dir/scripts/exam_type_classification.py" report \
  --input "$snapshot" --output-dir "$output_dir"
"$python_bin" "$repo_dir/scripts/exam_type_classification.py" export \
  --input "$snapshot" --output-dir "$output_dir" --effort low
phase 'finished; production database remains unchanged'
