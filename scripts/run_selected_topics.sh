#!/usr/bin/env bash
# Local API classification only; database import remains a separate audited step.
set -euo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
audit_dir=${SELECTED_TOPIC_AUDIT_DIR:-/home/eh/selected-topic-audit}
python_bin=${SELECTED_TOPIC_PYTHON:-/home/eh/learning-type-audit/.venv/bin/python}
exec "$python_bin" "$repo_dir/scripts/classify_selected_topics.py" \
  --input "$audit_dir/export.json" --output-dir "$audit_dir" \
  --concurrency "${SELECTED_TOPIC_CONCURRENCY:-20}" "$@"
