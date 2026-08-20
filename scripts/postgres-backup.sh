#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'USAGE'
Usage: postgres-backup.sh [--output-dir DIR] [--label LABEL] [--database-url URL]

Creates a PostgreSQL custom-format dump, SHA-256 checksum, and metadata manifest.
DATABASE_URL is used when --database-url is omitted.
USAGE
}

output_dir="${BACKUP_DIR:-../backups/time-tracker/postgresql}"
label="manual"
database_url="${DATABASE_URL:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir) output_dir="$2"; shift 2 ;;
    --label) label="$2"; shift 2 ;;
    --database-url) database_url="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$database_url" ]] || { echo "必须设置 DATABASE_URL 或传入 --database-url。" >&2; exit 2; }
command -v pg_dump >/dev/null || { echo "未找到 pg_dump，请安装 PostgreSQL 客户端。" >&2; exit 127; }
command -v psql >/dev/null || { echo "未找到 psql，请安装 PostgreSQL 客户端。" >&2; exit 127; }

umask 077
mkdir -p -- "$output_dir"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
safe_label="$(printf '%s' "$label" | tr -cs 'A-Za-z0-9._-' '-')"
base="${output_dir%/}/time-tracker-${safe_label}-${timestamp}"
dump_file="${base}.dump"
manifest_file="${base}.manifest"

cleanup() { rm -f -- "$dump_file" "$manifest_file" "${dump_file}.sha256"; }
trap 'status=$?; if (( status != 0 )); then cleanup; fi; exit "$status"' EXIT

pg_dump --format=custom --no-owner --no-acl --file="$dump_file" "$database_url"
checksum="$(sha256sum "$dump_file" | awk '{print $1}')"
created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
server_version="$(psql "$database_url" -X -Atqc 'SHOW server_version')"
database_name="$(psql "$database_url" -X -Atqc 'SELECT current_database()')"

printf '%s  %s\n' "$checksum" "$(basename "$dump_file")" > "${dump_file}.sha256"
cat > "$manifest_file" <<MANIFEST
{
  "format": "postgresql-custom",
  "created_at_utc": "$created_at",
  "database": "$database_name",
  "server_version": "$server_version",
  "dump": "$(basename "$dump_file")",
  "sha256": "$checksum",
  "safety": "Secrets are read from DATABASE_URL and never written to this manifest."
}
MANIFEST

trap - EXIT
printf '备份完成:\n  dump: %s\n  sha256: %s\n  manifest: %s\n' "$dump_file" "${dump_file}.sha256" "$manifest_file"
