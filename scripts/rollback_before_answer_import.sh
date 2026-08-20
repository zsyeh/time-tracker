#!/usr/bin/env bash
set -Eeuo pipefail

usage() { echo "Usage: $0 --manifest FILE [--dry-run] [--yes]"; }
manifest=""
dry_run=false
confirmed=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest) manifest="$2"; shift 2;;
    --dry-run) dry_run=true; shift;;
    --yes) confirmed=true; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2;;
  esac
done
[[ -n "$manifest" && -f "$manifest" ]] || { echo "Manifest is required and must exist." >&2; exit 2; }
command -v python3 >/dev/null || { echo "python3 is required." >&2; exit 127; }
root="$(cd "$(dirname "$manifest")" && pwd)"
dump="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["database_dump"])' "$manifest")"
images="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["question_image_archive"])' "$manifest")"
[[ "$dump" != /* ]] && dump="$root/$dump"
[[ "$images" != /* ]] && images="$root/$images"
[[ -f "$dump" ]] || { echo "Database dump missing: $dump" >&2; exit 2; }
[[ -f "$images" ]] || { echo "Question image archive missing: $images" >&2; exit 2; }
case "$root" in /root/time-tracker/backups/*) ;; *) echo "Unexpected backup root: $root" >&2; exit 2;; esac
if [[ "$dry_run" == true ]]; then
  echo "ROLLBACK DRY-RUN OK"
  echo "database dump: $dump"
  echo "question image archive: $images"
  echo "No database or filesystem changes made."
  exit 0
fi
[[ "$confirmed" == true ]] || { echo "Destructive rollback requires --yes." >&2; exit 2; }
command -v pg_restore >/dev/null || { echo "pg_restore is required." >&2; exit 127; }
[[ -n "${DATABASE_URL:-}" ]] || { echo "DATABASE_URL is required." >&2; exit 2; }
pg_restore --exit-on-error --clean --if-exists --no-owner --no-acl --dbname="$DATABASE_URL" "$dump"
echo "Database restored from $dump."
if [[ -n "${QUESTION_IMAGE_ROOT:-}" ]]; then
  case "$QUESTION_IMAGE_ROOT" in /|/home|/root|/root/time-tracker) echo "Refusing unsafe QUESTION_IMAGE_ROOT: $QUESTION_IMAGE_ROOT" >&2; exit 2;; esac
  mkdir -p -- "$QUESTION_IMAGE_ROOT"
  tar -xzf "$images" -C "$QUESTION_IMAGE_ROOT"
fi
python manage.py check
printf 'ROLLBACK COMPLETED\n'
