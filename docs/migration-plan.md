# Personal Learning OS migration plan

## Baseline (2026-08-09)

- Runtime: Django 4.2, Gunicorn, Nginx, systemd, SQLite.
- Historical tables: `tracker_timelog` and `tracker_dailystudystat`.
- Historical inventory: 125 completed sessions, 52 daily-stat rows, 9,581 total minutes.
- Existing fields that must remain intact: category, start time, end time, note, daily first start, daily count, and daily total minutes.
- Existing owners: two usable Django superuser accounts. Historical tracker data will be assigned to the configurable migration owner, defaulting to the lowest-id superuser (`eh`, id 1 on production).
- Authentication baseline: a fixed `Authorization` header enforced by custom middleware. This will be removed from browser flows after session authentication is operational.
- Production: `timer.ehzsy.site` terminates TLS at Nginx and proxies to Gunicorn on `127.0.0.1:8000`.

## Verified backups

- Full working-tree archive: `/root/backups/time-tracker-pre-personal-learn-20260809.tar.gz`
- SQLite copy: `/root/backups/time-tracker-pre-v3-20260809.sqlite3`
- Django JSON export: `/root/backups/time-tracker-pre-v3-20260809.json.gz`

Both database backups were read after creation. They contain 125 `TimeLog` rows,
52 `DailyStudyStat` rows, and 9,581 total completed minutes.

## Incremental migration

1. Extend `TimeLog` in place instead of renaming or recreating its table.
2. Add nullable ownership and review fields, backfill every historical row to the migration owner, verify counts and duration, then make ownership required.
3. Add ownership to daily statistics and replace the global date uniqueness rule with `(user, date)` uniqueness.
4. Add independent issue, knowledge-point, launch-token models. Passkeys are stored by django-allauth's maintained WebAuthn implementation.
5. Keep timestamps and raw notes byte-for-byte; derive session status from existing end times.
6. Replace browser header authentication only after password/session login and ownership-filtered APIs pass tests.
7. Keep the legacy MCP process isolated. It does not embed an AI model or call an AI API.
8. Introduce the Vue application behind the same origin. Keep server-rendered login and emergency admin access available.
9. Deploy with a second pre-migration database backup, migrate while the web service is stopped, validate invariants, then restart.

## Rollback

Stop the web and MCP services before replacing the database:

```bash
systemctl stop time-tracker-web.service time-tracker-mcp.service
cp /root/backups/time-tracker-pre-v3-20260809.sqlite3 /root/time-tracker/db.sqlite3
git switch agent/add-chatgpt-mcp
systemctl start time-tracker-web.service time-tracker-mcp.service
```

For an application-level restore into an empty migrated database:

```bash
python manage.py flush --noinput
python manage.py loaddata /root/backups/time-tracker-pre-v3-20260809.json.gz
```

Database replacement is the preferred rollback because it restores schema and
data atomically. Keep all three backups until post-deployment totals are verified.
