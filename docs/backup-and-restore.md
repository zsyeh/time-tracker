# Backup and restore

Keep database backups outside the repository and never archive `.env` with a
shareable source bundle. A practical retention policy is 7 daily, 4 weekly, and
12 monthly copies, plus a JSON export. Encrypt off-host copies.

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
