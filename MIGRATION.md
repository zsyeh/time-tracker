# Migration Guide

This guide describes how to move `jkxx` to another server while preserving
configuration and time-tracking data.

## Files To Move

Required source files:

- project repository files
- `.env` from the old server, if it exists
- `db.sqlite3`, if the service uses the default SQLite database

Generated files that do not need to be copied:

- `.venv/`
- `staticfiles/`
- `__pycache__/`
- `*.pyc`

## Export From Old Server

Stop the running service first so SQLite is not being written while copied.

```bash
cd /path/to/jkxx
cp .env /tmp/jkxx.env
cp db.sqlite3 /tmp/jkxx.db.sqlite3
git status -sb
```

Push the latest source code before moving servers:

```bash
git pull --ff-only
git push origin master
```

## Install On New Server

Clone the repository and restore runtime files:

```bash
git clone git@gitcode.com:gcw_Fuw4RG8L/jkxx.git
cd jkxx
cp /path/to/jkxx.env .env
cp /path/to/jkxx.db.sqlite3 db.sqlite3
```

Create the Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Run validation:

```bash
python manage.py check
python manage.py test
```

Start the development server for a quick smoke test:

```bash
python manage.py runserver 0.0.0.0:8000
```

## Environment Variables

The `.env.example` file lists the supported settings:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `TRACKER_API_TOKEN`
- `TRACKER_DAILY_TARGET_MINUTES`
- `TRACKER_WEEKLY_TARGET_MINUTES`
- `TRACKER_EXAM_DATE`

For production, keep `DJANGO_DEBUG=false` and include the server domain or IP in
`DJANGO_ALLOWED_HOSTS`.

## Data Checks After Migration

Open the dashboard and verify:

- today and weekly totals are visible;
- recent 30-day statistics are visible;
- all-time statistics include older records;
- the latest records list shows expected history;
- CSV export works with the configured `TRACKER_API_TOKEN`.

## Rollback

If the new server does not behave correctly:

```bash
git log --oneline -5
git checkout <previous_commit>
python manage.py migrate
python manage.py collectstatic --noinput
```

Restore the copied SQLite database if needed:

```bash
cp /path/to/jkxx.db.sqlite3 db.sqlite3
```
