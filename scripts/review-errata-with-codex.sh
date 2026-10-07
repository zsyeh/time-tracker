#!/usr/bin/env bash
set -euo pipefail

cd /root/time-tracker
mkdir -p reports
count=$(/root/time-tracker/.venv/bin/python manage.py export_pending_errata --output reports/pending-errata.json)
if [ "$count" = "0" ]; then
  exit 0
fi

exec /usr/bin/flock -n /run/time-tracker-errata.lock \
  /root/.local/bin/codex exec --ephemeral --sandbox workspace-write --approve-for-me \
  --cd /root/time-tracker -o reports/errata-review-last.txt \
  "$(cat docs/errata_agent_prompt.md)"
