# Backup and restore

Keep database backups outside the repository and never archive `.env` with a
shareable source bundle. A practical retention policy is 7 daily, 4 weekly, and
12 monthly copies, plus a JSON export. Encrypt off-host copies.

If any user enables database-at-rest encryption, also back up the server key at
`DATA_ENCRYPTION_KEY_PATH` separately from the database. The default is
`.data-encryption.key` beside `TRACKER_LOCAL_ENV_PATH` (inside the persistent data
volume for Docker). Preserve mode `600`. A database dump without this key cannot
recover encrypted content; do not put the key in the same archive as the dump.

## SQLite

Stop writers or use SQLite's backup command:

```bash
sqlite3 db.sqlite3 ".backup '/safe/backups/learning-os.sqlite3'"
gzip -9 /safe/backups/learning-os.sqlite3
python manage.py dumpdata --natural-foreign --natural-primary | gzip > /safe/backups/learning-os.json.gz
```

Restore while Web and MCP are stopped:

```bash
gunzip -c /safe/backups/learning-os.sqlite3.gz > /tmp/learning-os-restore.sqlite3
sqlite3 /tmp/learning-os-restore.sqlite3 'PRAGMA integrity_check;'
cp /tmp/learning-os-restore.sqlite3 /path/to/time-tracker/db.sqlite3
python manage.py migrate --noinput
```

## PostgreSQL

```bash
pg_dump --format=custom --no-owner "$DATABASE_URL" > /safe/backups/learning-os.dump
sudo -u postgres createdb --owner=learning_os learning_os_restore_test

# Extensions must be installed by a database administrator. Exclude their TOC
# entries from the application-role restore after creating them once.
sudo -u postgres psql -d learning_os_restore_test \
  -c 'CREATE EXTENSION IF NOT EXISTS pg_stat_statements;'
pg_restore --list /safe/backups/learning-os.dump \
  | grep -vE 'EXTENSION( -)? pg_stat_statements' \
  > /safe/backups/learning-os.restore.list
pg_restore --exit-on-error --no-owner \
  --use-list=/safe/backups/learning-os.restore.list \
  --dbname=learning_os_restore_test \
  /safe/backups/learning-os.dump
```

Verify a restore in an isolated database: integrity check, migration state,
session count, aggregate duration, user ownership, and export readability. A
backup is not considered valid until this restore verification succeeds.

CSV/JSON/Markdown exports are useful additional human-readable copies, but do not
replace a relational database backup because they omit authentication state and
some operational metadata.

## 安全优先：PostgreSQL 一键备份与回滚

仓库提供两个可执行脚本：

- `scripts/postgres-backup.sh`：生成 PostgreSQL custom-format dump、SHA-256 校验文件和不含凭据的 manifest。
- `scripts/postgres-rollback.sh`：回滚前自动创建当前数据库的保护性备份，再恢复指定 dump。

脚本只从 `DATABASE_URL` 或命令行参数读取连接串，不读取或归档 `.env`；建议把备份目录放在仓库之外，并设置目录权限为 `700`。

创建备份：

```bash
export DATABASE_URL='postgresql://USER:PASSWORD@HOST:5432/DBNAME'
./scripts/postgres-backup.sh --output-dir /safe/backups/time-tracker/postgresql --label pre-deploy
```

一键回滚（默认模式，不删库重建）：

```bash
./scripts/postgres-rollback.sh \
  --dump /safe/backups/time-tracker/postgresql/time-tracker-pre-deploy-YYYYMMDDTHHMMSSZ.dump \
  --backup-dir /safe/backups/time-tracker/postgresql \
  --yes
```

`--yes` 是有意设计的二次确认；没有它，脚本不会修改数据库。回滚前的保护性 dump 即使恢复失败也会保留。恢复默认使用 `pg_restore --clean --if-exists`，不会删除并重建数据库；恢复完成后应停止 Web/MCP 写入或置于维护页，并运行：

```bash
python manage.py migrate --check
python manage.py check --deploy
```

仅在必须精确重建数据库、并且已准备好管理员连接时，才使用高风险模式：

```bash
export PGADMIN_DATABASE_URL='postgresql://ADMIN:PASSWORD@HOST:5432/postgres'
./scripts/postgres-rollback.sh --dump /safe/path/backup.dump --yes --replace-database
```

该模式要求 `PGADMIN_DATABASE_URL`，会终止目标数据库连接、删除并重建数据库。生产环境操作前必须确认维护窗口、应用已停止、备份校验通过，并保留自动生成的 `pre-rollback-*` 备份。
