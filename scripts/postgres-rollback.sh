#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'USAGE'
Usage: postgres-rollback.sh --dump FILE --yes [--database-url URL] [--replace-database]

Restores a PostgreSQL custom-format dump. A pre-rollback backup is created first.
--replace-database is opt-in and requires a database owner/admin able to recreate DB.
USAGE
}

dump_file=""
database_url="${DATABASE_URL:-}"
backup_dir="${BACKUP_DIR:-../backups/time-tracker/postgresql}"
replace_database=false
confirmed=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dump) dump_file="$2"; shift 2 ;;
    --database-url) database_url="$2"; shift 2 ;;
    --backup-dir) backup_dir="$2"; shift 2 ;;
    --replace-database) replace_database=true; shift ;;
    --yes) confirmed=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$dump_file" && -f "$dump_file" ]] || { echo "必须传入存在的 --dump 文件。" >&2; exit 2; }
[[ -n "$database_url" ]] || { echo "必须设置 DATABASE_URL 或传入 --database-url。" >&2; exit 2; }
[[ "$confirmed" == true ]] || { echo "回滚会覆盖数据库。请复核 dump 后追加 --yes。" >&2; exit 2; }
command -v pg_restore >/dev/null || { echo "未找到 pg_restore，请安装 PostgreSQL 客户端。" >&2; exit 127; }
command -v pg_dump >/dev/null || { echo "未找到 pg_dump，请安装 PostgreSQL 客户端。" >&2; exit 127; }
command -v psql >/dev/null || { echo "未找到 psql，请安装 PostgreSQL 客户端。" >&2; exit 127; }

umask 077
mkdir -p -- "$backup_dir"
if [[ -f "${dump_file}.sha256" ]]; then sha256sum --check "${dump_file}.sha256"; fi

pre_label="pre-rollback-$(date -u +%Y%m%dT%H%M%SZ)"
"$(dirname "$0")/postgres-backup.sh" --output-dir "$backup_dir" --label "$pre_label" --database-url "$database_url"

if [[ "$replace_database" == true ]]; then
  database_name="$(psql "$database_url" -X -Atqc 'SELECT current_database()')"
  admin_url="${PGADMIN_DATABASE_URL:-}"
  [[ -n "$admin_url" ]] || { echo "--replace-database 需要设置 PGADMIN_DATABASE_URL。" >&2; exit 2; }
  admin_db="$(psql "$admin_url" -X -Atqc 'SELECT current_database()')"
  psql "$admin_url" -X -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$database_name' AND pid <> pg_backend_pid();"
  psql "$admin_url" -X -v ON_ERROR_STOP=1 -c "DROP DATABASE \"$database_name\";"
  psql "$admin_url" -X -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"$database_name\";"
  pg_restore --exit-on-error --no-owner --no-acl --dbname="$database_url" "$dump_file"
  printf '已重建并恢复数据库 %s（管理连接: %s）。\n' "$database_name" "$admin_db"
else
  pg_restore --exit-on-error --clean --if-exists --no-owner --no-acl --dbname="$database_url" "$dump_file"
  printf '已在原数据库中清理并恢复 dump；未执行删库重建。\n'
fi

psql "$database_url" -X -v ON_ERROR_STOP=1 -Atqc 'SELECT current_database(), current_user, now()'
printf '回滚完成。建议立即运行 Django migrate/check 和业务冒烟测试。\n'
